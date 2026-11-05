"""Coordinator que lê o estado da garrafa, espaçado e tolerante a falhas."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import async_read_status
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    GIVE_UP_RETRY_MINUTES,
    MAX_CONSECUTIVE_FAILURES,
    RETRY_INTERVAL_MINUTES,
    STALE_MIN_MINUTES,
)
from .protocol import PlumaError, PlumaReading

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def interval_from_minutes(minutes: int | float | None) -> timedelta | None:
    """Converte minutos num intervalo; 0 significa "só leitura manual"."""
    if not minutes or int(minutes) <= 0:
        return None
    return timedelta(minutes=int(minutes))


class PlumaCoordinator(DataUpdateCoordinator[PlumaReading]):
    """Lê a garrafa de tempos a tempos (ou só quando pedido).

    - O intervalo é por garrafa; 0 desativa a leitura automática.
    - Se uma leitura falhar (deep sleep, fora de alcance), mantém a última
      leitura boa e tenta de novo em breve. Só fica "indisponível" quando a
      última leitura boa é demasiado antiga.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        self.address = address
        self.last_read: datetime | None = None  # UTC, da última leitura bem-sucedida
        self.last_error: str | None = None  # motivo da última leitura falhada
        self._failures = 0
        self._lock = asyncio.Lock()  # nunca duas ligações em simultâneo
        self._normal_interval = interval_from_minutes(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=self._normal_interval,
        )

    @callback
    def async_apply_options(self) -> None:
        """Aplica o intervalo guardado nas opções, sem recarregar a integração."""
        self._normal_interval = interval_from_minutes(
            self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self._failures = 0
        self.update_interval = self._normal_interval
        self._reschedule()
        self.async_update_listeners()

    def _reschedule(self) -> None:
        """Faz o novo intervalo valer já, em vez de esperar pelo temporizador antigo."""
        # São métodos internos do DataUpdateCoordinator, mas são a forma de
        # aplicar o intervalo de imediato. O que cancela o temporizador tem
        # nomes diferentes consoante a versão do Home Assistant, e é preciso
        # cancelá-lo explicitamente para passar a "só manual" (intervalo None),
        # porque o agendamento não cancela nada nesse caso. Se nenhum existir,
        # o novo intervalo passa a valer a seguir à próxima leitura.
        for name in ("_unschedule_refresh", "_async_unsub_refresh", "_schedule_refresh"):
            method = getattr(self, name, None)
            if callable(method):
                method()

    def _ble_device(self):
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    def _is_stale(self) -> bool:
        """A última leitura boa é antiga demais para continuar a mostrá-la?"""
        if self.last_read is None:
            return True
        if self._normal_interval is None:
            return False  # só manual: o último valor mantém-se sempre
        limit = max(2 * self._normal_interval, timedelta(minutes=STALE_MIN_MINUTES))
        return dt_util.utcnow() - self.last_read > limit

    def _set_retry_interval(self) -> None:
        """Depois de uma falha, tenta de novo mais cedo (só em modo automático)."""
        if self._normal_interval is None:
            return  # modo manual: não agenda nada
        if self._failures < MAX_CONSECUTIVE_FAILURES:
            self.update_interval = min(
                timedelta(minutes=RETRY_INTERVAL_MINUTES), self._normal_interval
            )
        else:
            self.update_interval = self._give_up_interval()

    def _give_up_interval(self) -> timedelta | None:
        """Intervalo a usar depois das tentativas rápidas falharem."""
        if self._normal_interval is None:
            return None
        return min(timedelta(minutes=GIVE_UP_RETRY_MINUTES), self._normal_interval)

    async def _async_update_data(self) -> PlumaReading:
        async with self._lock:
            return await self._async_read()

    async def _async_read(self) -> PlumaReading:
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
            self.last_error = str(err)
            if self.data is not None and not self._is_stale():
                _LOGGER.debug(
                    "Falha %d a ler %s (mantém a última leitura): %s",
                    self._failures,
                    self.address,
                    err,
                )
                self._set_retry_interval()
                return self.data
            self.update_interval = self._give_up_interval()
            raise UpdateFailed(str(err)) from err

        self._failures = 0
        self.last_error = None
        self.last_read = dt_util.utcnow()
        self.update_interval = self._normal_interval
        return reading
