"""Botão para ler a garrafa já, sem esperar pelo intervalo."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlumaConfigEntry
from .coordinator import PlumaCoordinator
from .entity import PlumaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria o botão de uma garrafa."""
    async_add_entities([PlumaRefreshButton(entry.runtime_data, entry)])


class PlumaRefreshButton(PlumaEntity, ButtonEntity):
    """Lê a garrafa agora. Útil com intervalos longos ou em modo só manual."""

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: PlumaCoordinator, entry: PlumaConfigEntry) -> None:
        super().__init__(coordinator, entry, "refresh")

    @property
    def available(self) -> bool:
        # Sempre disponível: é precisamente o que se usa quando a leitura falhou.
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
        if self.coordinator.last_error:
            raise HomeAssistantError(
                f"Não foi possível ler a garrafa: {self.coordinator.last_error}"
            )
