"""Ligação BLE à garrafa Pluma: liga, pede o estado, desliga."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .protocol import (
    CHAR_UUID,
    CMD_HELLO,
    CMD_STATUS,
    DEFAULT_KEY,
    PlumaConnectionError,
    PlumaProtocolError,
    PlumaReading,
    build_command,
    parse_status,
)

_LOGGER = logging.getLogger(__name__)

RESPONSE_TIMEOUT = 10.0  # segundos à espera da notificação
HELLO_TO_STATUS_DELAY = 0.3  # a app deixa passar ~0,3 s entre os dois comandos


async def async_read_status(
    ble_device: BLEDevice,
    *,
    key: bytes = DEFAULT_KEY,
    ble_device_callback: Callable[[], BLEDevice] | None = None,
) -> PlumaReading:
    """Liga à garrafa, envia os comandos e devolve a leitura.

    A garrafa entra em "deep sleep" e só aceita ligações durante janelas curtas,
    por isso o establish_connection tenta várias vezes com pausas.
    """
    loop = asyncio.get_running_loop()
    future: asyncio.Future[PlumaReading] = loop.create_future()
    last_error: PlumaProtocolError | None = None

    def _on_notify(_char: object, data: bytearray) -> None:
        nonlocal last_error
        try:
            reading = parse_status(bytes(data))
        except PlumaProtocolError as err:
            # Pode ser uma notificação que não é a resposta ao estado: ignorar
            # e continuar à espera, mas guardar o motivo para o log.
            last_error = err
            _LOGGER.debug("Notificação ignorada (%s): %s", err, bytes(data).hex())
            return
        if not future.done():
            future.set_result(reading)

    name = ble_device.name or ble_device.address
    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name,
            max_attempts=3,
            ble_device_callback=ble_device_callback,
        )
    except (BleakError, TimeoutError, OSError) as err:
        raise PlumaConnectionError(f"não foi possível ligar a {name}: {err}") from err

    try:
        await client.start_notify(CHAR_UUID, _on_notify)
        await client.write_gatt_char(CHAR_UUID, build_command(CMD_HELLO, key), response=True)
        await asyncio.sleep(HELLO_TO_STATUS_DELAY)
        await client.write_gatt_char(CHAR_UUID, build_command(CMD_STATUS, key), response=True)
        return await asyncio.wait_for(future, timeout=RESPONSE_TIMEOUT)
    except TimeoutError as err:
        detail = f" (última frame inválida: {last_error})" if last_error else ""
        raise PlumaConnectionError(f"sem resposta de {name}{detail}") from err
    except (BleakError, OSError) as err:
        raise PlumaConnectionError(f"erro de comunicação com {name}: {err}") from err
    finally:
        try:
            await client.disconnect()
        except (BleakError, TimeoutError, OSError):
            _LOGGER.debug("Erro ao desligar de %s", name, exc_info=True)
