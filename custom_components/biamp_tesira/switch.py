"""Switch platform for Biamp Tesira."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import (
    BLOCK_LOGIC_STATE,
    BLOCK_MATRIX_CROSSPOINT,
    BLOCK_MUTE,
    BlockEntityConfig,
)
from .const import DOMAIN, ENTITY_TYPE_SWITCH
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity, BiampTesiraControlEntity
from .util import coerce_bool


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        BiampTesiraControlSwitch(coordinator, point)
        for point in coordinator.control_points
        if point.entity_type == ENTITY_TYPE_SWITCH
    ]
    for block in coordinator.block_entities:
        if block.block_type in (BLOCK_MUTE, BLOCK_LOGIC_STATE, BLOCK_MATRIX_CROSSPOINT):
            entities.append(BiampTesiraBlockSwitch(coordinator, block))
    async_add_entities(entities)


class BiampTesiraControlSwitch(BiampTesiraControlEntity, SwitchEntity):
    """Generic TTP switch control point."""

    @property
    def is_on(self) -> bool | None:
        return coerce_bool(self.coordinator.data.get(self.point.unique_id))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_control_value(self.point, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_control_value(self.point, False)


class BiampTesiraBlockSwitch(BiampTesiraBlockEntity, SwitchEntity):
    """Mute or logic_state block switch."""

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)

    @property
    def is_on(self) -> bool | None:
        return coerce_bool(self.coordinator.data.get(self.block.unique_id))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_block_value(self.block, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_block_value(self.block, False)
