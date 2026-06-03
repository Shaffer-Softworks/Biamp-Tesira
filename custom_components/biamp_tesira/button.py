"""Button platform for Biamp Tesira presets."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_PRESET, BlockEntityConfig
from .const import DOMAIN, ENTITY_TYPE_BUTTON
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity, BiampTesiraControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        BiampTesiraPresetButton(coordinator, point)
        for point in coordinator.control_points
        if point.entity_type == ENTITY_TYPE_BUTTON
    ]
    for block in coordinator.block_entities:
        if block.block_type == BLOCK_PRESET:
            entities.append(BiampTesiraBlockPresetButton(coordinator, block))
    async_add_entities(entities)


class BiampTesiraPresetButton(BiampTesiraControlEntity, ButtonEntity):
    """Recall preset via control point."""

    async def async_press(self) -> None:
        await self.coordinator.async_recall_preset(self.point)


class BiampTesiraBlockPresetButton(BiampTesiraBlockEntity, ButtonEntity):
    """Recall preset via block config."""

    async def async_press(self) -> None:
        await self.coordinator.async_press_block(self.block)
