"""Base comum às entidades de uma garrafa Pluma."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlumaCoordinator

if TYPE_CHECKING:
    from . import PlumaConfigEntry


class PlumaEntity(CoordinatorEntity[PlumaCoordinator]):
    """Entidade ligada ao dispositivo (garrafa) e ao seu coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PlumaCoordinator, entry: PlumaConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        address = coordinator.address
        self._attr_unique_id = f"{address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            name=entry.title,
            manufacturer="Galp",
            model="Pluma (Bluetooth)",
        )
