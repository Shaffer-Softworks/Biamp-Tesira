"""Number platform for Biamp Tesira control points and block entities."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_MATRIX_CROSSPOINT_LEVEL, BlockEntityConfig
from .const import DOMAIN, ENTITY_TYPE_NUMBER
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity, BiampTesiraControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from control points and block entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        BiampTesiraNumber(coordinator, point)
        for point in coordinator.control_points
        if point.entity_type == ENTITY_TYPE_NUMBER
    ]
    for block in coordinator.block_entities:
        if block.block_type == BLOCK_MATRIX_CROSSPOINT_LEVEL:
            entities.append(BiampTesiraBlockNumber(coordinator, block))
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


class BiampTesiraBlockNumber(BiampTesiraBlockEntity, NumberEntity):
    """Matrix crosspoint level block."""

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)
        self._attr_mode = NumberMode.AUTO
        self._attr_native_min_value = -100.0
        self._attr_native_max_value = 0.0
        self._attr_native_unit_of_measurement = "dB"

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get(self.block.unique_id)
        if raw is None:
            return None
        return float(raw)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_block_value(self.block, value)
