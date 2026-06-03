"""Sensor platform for Biamp Tesira meters."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_AUDIO_METER, BlockEntityConfig
from .const import DOMAIN
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        BiampTesiraAudioMeter(coordinator, block)
        for block in coordinator.block_entities
        if block.block_type == BLOCK_AUDIO_METER
    ]
    async_add_entities(entities)


class BiampTesiraAudioMeter(BiampTesiraBlockEntity, SensorEntity):
    """Audio meter level in dB."""

    _attr_native_unit_of_measurement = "dB"

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get(self.block.unique_id)
        if raw is None:
            return None
        return float(raw)
