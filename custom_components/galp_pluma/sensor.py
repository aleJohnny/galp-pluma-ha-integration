"""Sensores da garrafa Pluma."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PlumaConfigEntry
from .coordinator import PlumaCoordinator
from .entity import PlumaEntity
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
    entities: list[SensorEntity] = [
        PlumaSensor(coordinator, entry, description) for description in SENSORS
    ]
    entities.append(PlumaLastReadSensor(coordinator, entry))
    async_add_entities(entities)


class PlumaSensor(PlumaEntity, SensorEntity):
    """Sensor de uma garrafa Pluma."""

    entity_description: PlumaSensorDescription

    def __init__(
        self,
        coordinator: PlumaCoordinator,
        entry: PlumaConfigEntry,
        description: PlumaSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "level" or self.coordinator.data is None:
            return None
        attributes: dict[str, Any] = {"raw_frame": self.coordinator.data.raw}
        if self.coordinator.last_error:
            attributes["last_error"] = self.coordinator.last_error
        return attributes


class PlumaLastReadSensor(PlumaEntity, SensorEntity):
    """Quando foi a última leitura bem-sucedida (útil com intervalos longos)."""

    _attr_translation_key = "last_read"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PlumaCoordinator, entry: PlumaConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_read")

    @property
    def available(self) -> bool:
        # Fica disponível enquanto houver uma leitura anterior, mesmo que a
        # última tentativa tenha falhado: é justamente aí que é útil.
        return self.coordinator.last_read is not None

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_read
