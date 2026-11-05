"""Seletor do tipo de gás (butano/propano)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlumaConfigEntry
from .const import (
    CONF_GAS_TYPE,
    GAS_ICONS,
    GAS_TYPES,
    gas_type_from_entry,
)
from .coordinator import PlumaCoordinator
from .entity import PlumaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria o seletor de tipo de gás de uma garrafa."""
    async_add_entities([PlumaGasTypeSelect(entry.runtime_data, entry)])


class PlumaGasTypeSelect(PlumaEntity, SelectEntity):
    """Tipo de gás da garrafa (guardado nas options, visível para automações)."""

    _attr_translation_key = CONF_GAS_TYPE
    _attr_options = GAS_TYPES

    def __init__(
        self, coordinator: PlumaCoordinator, entry: PlumaConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, CONF_GAS_TYPE)

    @property
    def current_option(self) -> str:
        return gas_type_from_entry(self.entry)

    @property
    def icon(self) -> str:
        return GAS_ICONS.get(self.current_option, "mdi:gas-cylinder")

    async def async_select_option(self, option: str) -> None:
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_GAS_TYPE: option},
        )
        self.async_write_ha_state()