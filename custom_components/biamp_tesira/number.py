"""Number platform for Biamp Tesira control points."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_TYPE_NUMBER
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from control points."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        BiampTesiraNumber(coordinator, point)
        for point in coordinator.control_points
        if point.entity_type == ENTITY_TYPE_NUMBER
    ]
    async_add_entities(entities)


class BiampTesiraNumber(BiampTesiraControlEntity, NumberEntity):
    """TTP numeric control point."""

    def __init__(self, coordinator: BiampTesiraCoordinator, point) -> None:
        super().__init__(coordinator, point)
        self._attr_mode = NumberMode.AUTO
        if point.min_value is not None:
            self._attr_native_min_value = point.min_value
        if point.max_value is not None:
            self._attr_native_max_value = point.max_value
        if point.unit:
            self._attr_native_unit_of_measurement = point.unit

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get(self.point.unique_id)
        if raw is None:
            return None
        return float(raw)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_control_value(self.point, value)
