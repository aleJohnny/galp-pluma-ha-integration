"""Sensores da garrafa Pluma."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlumaConfigEntry
from .const import DOMAIN
from .coordinator import PlumaCoordinator
from .protocol import PlumaReading


@dataclass(frozen=True, kw_only=True)
class PlumaSensorDescription(SensorEntityDescription):
    """Descrição de um sensor com a função que extrai o valor."""

    value_fn: Callable[[PlumaReading], int]


SENSORS: tuple[PlumaSensorDescription, ...] = (
    PlumaSensorDescription(
        key="level",
        translation_key="level",
        icon="mdi:gas-cylinder",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.level,
    ),
    PlumaSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.temperature,
    ),
    # Valor cujo significado ainda se desconhece: desativado por defeito,
    # útil para quem quiser ajudar a descobrir o que é.
    PlumaSensorDescription(
        key="raw_byte_7",
        translation_key="raw_byte_7",
        icon="mdi:numeric",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.byte7,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Cria os sensores de uma garrafa."""
    coordinator = entry.runtime_data
    async_add_entities(
        PlumaSensor(coordinator, entry, description) for description in SENSORS
    )


class PlumaSensor(CoordinatorEntity[PlumaCoordinator], SensorEntity):
    """Sensor de uma garrafa Pluma."""

    entity_description: PlumaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlumaCoordinator,
        entry: PlumaConfigEntry,
        description: PlumaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        address = coordinator.address
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            name=entry.title,
            manufacturer="Galp",
            model="Pluma (Bluetooth)",
        )

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "level" or self.coordinator.data is None:
            return None
        return {"raw_frame": self.coordinator.data.raw}
