"""Testes da lógica do cliente BLE e do coordinator.

Usam um cliente BLE falso (e, sem Home Assistant instalado, os stubs do
conftest.py). Não substituem um teste com a garrafa nem com o Home Assistant.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import REAL_BLEAK, REAL_HA
from galp_pluma import client, protocol

pytestmark = pytest.mark.skipif(
    REAL_BLEAK, reason="os testes usam um cliente BLE falso, não o bleak real"
)

GOOD_FRAME = bytes.fromhex("03010000000000821461a5")  # 97 %
BAD_FRAME = bytes.fromhex("0301000000000070175a00")  # checksum errado


class FakeClient:
    """Imita o BleakClient: responde ao comando de estado com frames dadas."""

    def __init__(self, responses=(GOOD_FRAME,), fail_write=None):
        self.responses = list(responses)
        self.fail_write = fail_write
        self.writes: list[bytes] = []
        self.callback = None
        self.disconnected = False

    async def start_notify(self, uuid, callback):
        assert uuid == protocol.CHAR_UUID
        self.callback = callback

    async def write_gatt_char(self, uuid, data, response=False):
        assert uuid == protocol.CHAR_UUID
        assert response is True
        if self.fail_write:
            raise self.fail_write
        self.writes.append(bytes(data))
        if bytes(data) == protocol.build_command(protocol.CMD_STATUS):
            loop = asyncio.get_running_loop()
            for frame in self.responses:
                loop.call_soon(self.callback, None, bytearray(frame))

    async def disconnect(self):
        self.disconnected = True


def _device():
    return client.BLEDevice("AA:BB:CC:DD:EE:FF", "Pluma--test")


def _patch_connection(monkeypatch, fake):
    async def fake_establish(*args, **kwargs):
        return fake

    monkeypatch.setattr(client, "establish_connection", fake_establish)


def test_read_status_happy_path(monkeypatch):
    fake = FakeClient()
    _patch_connection(monkeypatch, fake)

    reading = asyncio.run(client.async_read_status(_device()))

    assert reading.level == 97
    assert fake.writes == [
        protocol.build_command(protocol.CMD_HELLO),
        protocol.build_command(protocol.CMD_STATUS),
    ]
    assert fake.disconnected


def test_invalid_notification_is_ignored_until_a_valid_one(monkeypatch):
    fake = FakeClient(responses=(BAD_FRAME, GOOD_FRAME))
    _patch_connection(monkeypatch, fake)

    reading = asyncio.run(client.async_read_status(_device()))

    assert reading.level == 97
    assert fake.disconnected


def test_no_response_times_out(monkeypatch):
    fake = FakeClient(responses=())
    _patch_connection(monkeypatch, fake)
    monkeypatch.setattr(client, "RESPONSE_TIMEOUT", 0.05)

    with pytest.raises(protocol.PlumaConnectionError, match="sem resposta"):
        asyncio.run(client.async_read_status(_device()))
    assert fake.disconnected


def test_only_invalid_notifications_reports_last_error(monkeypatch):
    fake = FakeClient(responses=(BAD_FRAME,))
    _patch_connection(monkeypatch, fake)
    monkeypatch.setattr(client, "RESPONSE_TIMEOUT", 0.05)

    with pytest.raises(protocol.PlumaConnectionError, match="checksum"):
        asyncio.run(client.async_read_status(_device()))


def test_connection_failure_is_wrapped(monkeypatch):
    async def failing(*args, **kwargs):
        raise client.BleakError("deep sleep")

    monkeypatch.setattr(client, "establish_connection", failing)

    with pytest.raises(protocol.PlumaConnectionError, match="não foi possível ligar"):
        asyncio.run(client.async_read_status(_device()))


def test_write_failure_is_wrapped_and_disconnects(monkeypatch):
    fake = FakeClient(fail_write=client.BleakError("desligada"))
    _patch_connection(monkeypatch, fake)

    with pytest.raises(protocol.PlumaConnectionError, match="erro de comunicação"):
        asyncio.run(client.async_read_status(_device()))
    assert fake.disconnected


# --- coordinator (só com os stubs: com o HA real precisaria de um `hass` real)

coordinator_tests = pytest.mark.skipif(
    REAL_HA, reason="precisa de um hass real; correr com os testes do Home Assistant"
)


@pytest.fixture
def coordinator_module():
    from galp_pluma import coordinator

    return coordinator


def _coordinator(module, device="present", options=None):
    hass = SimpleNamespace(device=_device() if device == "present" else None)
    entry = SimpleNamespace(options=options or {})
    return module.PlumaCoordinator(hass, entry, "AA:BB:CC:DD:EE:FF")


class Clock:
    """Relógio controlável para substituir dt_util.utcnow nos testes."""

    def __init__(self):
        self.now = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock(coordinator_module, monkeypatch):
    fake = Clock()
    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", fake)
    return fake


def _patch_read(monkeypatch, module, outcome):
    """`outcome["value"]` é a leitura a devolver ou a exceção a lançar."""

    async def fake_read(device, **kwargs):
        if isinstance(outcome["value"], Exception):
            raise outcome["value"]
        return outcome["value"]

    monkeypatch.setattr(module, "async_read_status", fake_read)


@coordinator_tests
def test_interval_from_minutes(coordinator_module):
    f = coordinator_module.interval_from_minutes
    assert f(None) is None
    assert f(0) is None  # 0 = só leitura manual
    assert f(-5) is None
    assert f(60) == timedelta(hours=1)
    assert f(43200) == timedelta(days=30)


@coordinator_tests
def test_coordinator_default_interval(coordinator_module):
    from galp_pluma import const

    coord = _coordinator(coordinator_module)
    assert coord.update_interval == timedelta(minutes=const.DEFAULT_SCAN_INTERVAL)


@coordinator_tests
def test_each_bottle_has_its_own_interval(coordinator_module):
    in_use = _coordinator(coordinator_module, options={"scan_interval": 1440})
    reserve = _coordinator(coordinator_module, options={"scan_interval": 10080})
    default = _coordinator(coordinator_module)
    assert in_use.update_interval == timedelta(days=1)
    assert reserve.update_interval == timedelta(days=7)
    assert default.update_interval not in (in_use.update_interval, reserve.update_interval)


@coordinator_tests
def test_manual_only_has_no_polling(coordinator_module):
    coord = _coordinator(coordinator_module, options={"scan_interval": 0})
    assert coord.update_interval is None


@coordinator_tests
def test_apply_options_changes_interval_and_reschedules(coordinator_module, monkeypatch):
    coord = _coordinator(coordinator_module, options={"scan_interval": 30})
    calls = []
    # O coordinator de substituição não tem estes métodos; no Home Assistant real
    # existem (com nomes que variam por versão), por isso regista-se só o que se chama.
    monkeypatch.setattr(coord, "_async_unsub_refresh", lambda: calls.append("unsub"), raising=False)
    monkeypatch.setattr(coord, "_schedule_refresh", lambda: calls.append("schedule"), raising=False)

    coord.config_entry.options = {"scan_interval": 1440}
    coord.async_apply_options()
    assert coord.update_interval == timedelta(days=1)
    assert calls == ["unsub", "schedule"]  # cancela o temporizador antigo, depois agenda
    assert coord.listeners_called == 1  # a entidade number atualiza-se

    calls.clear()
    coord.config_entry.options = {"scan_interval": 0}
    coord.async_apply_options()
    assert coord.update_interval is None
    assert calls == ["unsub", "schedule"]
    assert coord.listeners_called == 2


@coordinator_tests
def test_failures_keep_last_value_and_back_off_to_hourly(coordinator_module, monkeypatch, clock):
    # Garrafa lida uma vez por dia: uma leitura falhada não pode adiar a seguinte
    # por um dia inteiro.
    coord = _coordinator(coordinator_module, options={"scan_interval": 1440})
    good = protocol.parse_status(GOOD_FRAME)
    outcome = {"value": good}
    _patch_read(monkeypatch, coordinator_module, outcome)

    # 1) leitura boa
    coord.data = asyncio.run(coord._async_update_data())
    assert coord.data.level == 97
    assert coord.last_read == clock.now
    assert coord.update_interval == timedelta(days=1)

    # 2) falhas: mantém o último valor e tenta de 3 em 3 minutos
    outcome["value"] = protocol.PlumaConnectionError("a dormir")
    clock.advance(days=1)
    for _ in range(4):
        assert asyncio.run(coord._async_update_data()) is good
        assert coord.update_interval == timedelta(minutes=3)
        clock.advance(minutes=3)

    # 3) esgotadas as tentativas rápidas, continua de hora a hora (e não de dia a dia)
    for _ in range(2):
        assert asyncio.run(coord._async_update_data()) is good
        assert coord.update_interval == timedelta(minutes=60)
    assert coord.last_error == "a dormir"

    # 4) recuperação: volta ao intervalo da garrafa
    outcome["value"] = good
    assert asyncio.run(coord._async_update_data()).level == 97
    assert coord._failures == 0
    assert coord.last_error is None
    assert coord.update_interval == timedelta(days=1)


@coordinator_tests
def test_becomes_unavailable_only_when_last_good_reading_is_too_old(
    coordinator_module, monkeypatch, clock
):
    # Intervalo de 15 min: limite = max(2 x 15 min, 60 min) = 60 min.
    coord = _coordinator(coordinator_module, options={"scan_interval": 15})
    good = protocol.parse_status(GOOD_FRAME)
    outcome = {"value": good}
    _patch_read(monkeypatch, coordinator_module, outcome)
    coord.data = asyncio.run(coord._async_update_data())

    outcome["value"] = protocol.PlumaConnectionError("a dormir")
    clock.advance(minutes=59)
    assert asyncio.run(coord._async_update_data()) is good  # ainda aceitável

    clock.advance(minutes=2)  # passou de 60 min sem nenhuma leitura boa
    with pytest.raises(coordinator_module.UpdateFailed):
        asyncio.run(coord._async_update_data())
    assert coord.update_interval == timedelta(minutes=15)  # continua a tentar


@coordinator_tests
def test_manual_only_keeps_value_and_never_schedules_retries(coordinator_module, monkeypatch, clock):
    coord = _coordinator(coordinator_module, options={"scan_interval": 0})
    good = protocol.parse_status(GOOD_FRAME)
    outcome = {"value": good}
    _patch_read(monkeypatch, coordinator_module, outcome)
    coord.data = asyncio.run(coord._async_update_data())

    outcome["value"] = protocol.PlumaConnectionError("fora de alcance")
    clock.advance(days=90)
    assert asyncio.run(coord._async_update_data()) is good  # nunca fica "velha"
    assert coord.update_interval is None  # nem agenda tentativas automáticas


@coordinator_tests
def test_coordinator_first_failure_without_data_raises(coordinator_module, monkeypatch):
    coord = _coordinator(coordinator_module)

    async def fake_read(device, **kwargs):
        raise protocol.PlumaConnectionError("a dormir")

    monkeypatch.setattr(coordinator_module, "async_read_status", fake_read)

    with pytest.raises(coordinator_module.UpdateFailed):
        asyncio.run(coord._async_update_data())


@coordinator_tests
def test_coordinator_device_out_of_range(coordinator_module):
    coord = _coordinator(coordinator_module, device="absent")

    with pytest.raises(coordinator_module.UpdateFailed, match="fora de alcance"):
        asyncio.run(coord._async_update_data())
