"""Coordinator que lê periodicamente o estado da garrafa."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import async_read_status
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CONSECUTIVE_FAILURES,
    RETRY_INTERVAL_MINUTES,
)
from .protocol import PlumaError, PlumaReading

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PlumaCoordinator(DataUpdateCoordinator[PlumaReading]):
    """Lê o nível da garrafa; tolera falhas curtas causadas pelo deep sleep."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        self.address = address
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._normal_interval = timedelta(minutes=minutes)
        self._failures = 0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=self._normal_interval,
        )

    def _ble_device(self):
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    async def _async_update_data(self) -> PlumaReading:
        ble_device = self._ble_device()
        try:
            if ble_device is None:
                raise PlumaError(
                    "garrafa fora de alcance (nenhum adaptador ou proxy a vê-la)"
                )
            reading = await async_read_status(
                ble_device, ble_device_callback=self._ble_device
            )
        except PlumaError as err:
            self._failures += 1
            if self.data is not None and self._failures < MAX_CONSECUTIVE_FAILURES:
                # Mantém a última leitura disponível e volta a tentar em breve.
                _LOGGER.debug(
                    "Falha %d/%d a ler %s: %s",
                    self._failures,
                    MAX_CONSECUTIVE_FAILURES,
                    self.address,
                    err,
                )
                self.update_interval = timedelta(minutes=RETRY_INTERVAL_MINUTES)
                return self.data
            self.update_interval = self._normal_interval
            raise UpdateFailed(str(err)) from err

        self._failures = 0
        self.update_interval = self._normal_interval
        return reading
