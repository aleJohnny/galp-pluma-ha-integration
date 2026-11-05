"""Intervalo de leitura da garrafa como entidade, para poder ser automatizado."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlumaConfigEntry
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import PlumaCoordinator
from .entity import PlumaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria o controlo do intervalo de uma garrafa."""
    async_add_entities([PlumaIntervalNumber(entry.runtime_data, entry)])


class PlumaIntervalNumber(PlumaEntity, NumberEntity):
    """Minutos entre leituras desta garrafa (0 = só manual).

    Escreve nas opções da entrada de configuração, que é a mesma coisa que
    "Configurar" na página da integração; por isso os dois ficam sempre iguais.
    """

    _attr_translation_key = "scan_interval"
    _attr_icon = "mdi:timer-cog-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_SCAN_INTERVAL
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: PlumaCoordinator, entry: PlumaConfigEntry) -> None:
        super().__init__(coordinator, entry, "scan_interval")
        self._entry = entry

    @property
    def available(self) -> bool:
        # Pode ser alterado mesmo que a garrafa não esteja acessível.
        return True

    @property
    def native_value(self) -> int:
        return int(self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    async def async_set_native_value(self, value: float) -> None:
        minutes = int(value)
        if 0 < minutes < MIN_SCAN_INTERVAL:
            raise ServiceValidationError(
                f"O intervalo mínimo é {MIN_SCAN_INTERVAL} minutos "
                "(ou 0 para leitura só manual)."
            )
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_SCAN_INTERVAL: minutes},
        )
