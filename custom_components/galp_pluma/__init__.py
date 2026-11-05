"""Integração Galp Pluma: nível de gás por Bluetooth Low Energy."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import PlumaCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR
    ]

type PlumaConfigEntry = ConfigEntry[PlumaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PlumaConfigEntry) -> bool:
    """Configura uma garrafa."""
    coordinator = PlumaCoordinator(hass, entry, entry.data[CONF_ADDRESS])
    # Se a garrafa estiver a dormir o setup falha com ConfigEntryNotReady e o
    # Home Assistant repete automaticamente com pausas crescentes.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: PlumaConfigEntry) -> None:
    """Aplica o novo intervalo de leitura sem recarregar (e sem acordar a garrafa)."""
    entry.runtime_data.async_apply_options()
    entry.runtime_data.async_update_listeners()


async def async_unload_entry(hass: HomeAssistant, entry: PlumaConfigEntry) -> bool:
    """Descarrega a garrafa."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
