"""Testes da lógica do cliente BLE e do coordinator.

Usam um cliente BLE falso (e, sem Home Assistant instalado, os stubs do
conftest.py). Não substituem um teste com a garrafa nem com o Home Assistant.
"""

import asyncio
from datetime import timedelta
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


@coordinator_tests
def test_coordinator_default_interval(coordinator_module):
    coord = _coordinator(coordinator_module)
    assert coord.update_interval == timedelta(minutes=15)


@coordinator_tests
def test_coordinator_custom_interval(coordinator_module):
    coord = _coordinator(coordinator_module, options={"scan_interval": 30})
    assert coord.update_interval == timedelta(minutes=30)


@coordinator_tests
def test_coordinator_tolerates_failures_then_gives_up(coordinator_module, monkeypatch):
    coord = _coordinator(coordinator_module)
    good = protocol.parse_status(GOOD_FRAME)
    outcome = {"value": good}

    async def fake_read(device, **kwargs):
        if isinstance(outcome["value"], Exception):
            raise outcome["value"]
        return outcome["value"]

    monkeypatch.setattr(coordinator_module, "async_read_status", fake_read)

    # 1) leitura boa
    coord.data = asyncio.run(coord._async_update_data())
    assert coord.data.level == 97
    assert coord.update_interval == timedelta(minutes=15)

    # 2) falhas: mantém o último valor e passa a tentar de 3 em 3 minutos
    outcome["value"] = protocol.PlumaConnectionError("a dormir")
    for _ in range(4):
        data = asyncio.run(coord._async_update_data())
        assert data is good
        assert coord.update_interval == timedelta(minutes=3)

    # 3) à 5.ª falha seguida desiste e volta ao intervalo normal
    with pytest.raises(coordinator_module.UpdateFailed):
        asyncio.run(coord._async_update_data())
    assert coord.update_interval == timedelta(minutes=15)

    # 4) recuperação
    outcome["value"] = good
    assert asyncio.run(coord._async_update_data()).level == 97
    assert coord._failures == 0


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
