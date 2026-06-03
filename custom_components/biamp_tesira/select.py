"""Select platform for Biamp Tesira."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_SOURCE_SELECTOR, BlockEntityConfig
from .const import DOMAIN, ENTITY_TYPE_SELECT
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity, BiampTesiraControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []
    for point in coordinator.control_points:
        if point.entity_type == ENTITY_TYPE_SELECT and point.options:
            entities.append(BiampTesiraControlSelect(coordinator, point))
    for block in coordinator.block_entities:
        if block.block_type == BLOCK_SOURCE_SELECTOR:
            entities.append(BiampTesiraSourceSelect(coordinator, block))
    async_add_entities(entities)


class BiampTesiraControlSelect(BiampTesiraControlEntity, SelectEntity):
    """Select from control point options list."""

    def __init__(self, coordinator, point) -> None:
        super().__init__(coordinator, point)
        self._attr_options = list(point.options or [])

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(self.point.unique_id)
        if raw is None:
            return None
        val = str(raw)
        return val if val in self._attr_options else val

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_control_value(self.point, option)


class BiampTesiraSourceSelect(BiampTesiraBlockEntity, SelectEntity):
    """Source selector block — options discovered from current source value."""

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)
        self._attr_options: list[str] = []

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(self.block.unique_id)
        if raw is None:
            return None
        val = str(int(raw)) if isinstance(raw, (int, float)) else str(raw)
        if val not in self._attr_options:
            self._attr_options = sorted(set(self._attr_options + [val]))
        return val

    async def async_select_option(self, option: str) -> None:
        try:
            value: str | int = int(option)
        except ValueError:
            value = option
        await self.coordinator.async_set_block_value(self.block, value)
