"""Binary sensor platform for Biamp Tesira."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_SIGNAL_PRESENT, BlockEntityConfig
from .const import DOMAIN
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity, device_info
from .util import coerce_bool


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        TesiraConnectionBinarySensor(coordinator),
    ]
    entities.extend(
        BiampTesiraSignalPresent(coordinator, block)
        for block in coordinator.block_entities
        if block.block_type == BLOCK_SIGNAL_PRESENT
    )
    async_add_entities(entities)


class TesiraConnectionBinarySensor(BinarySensorEntity):
    """Report whether the Tesira TTP session is connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "TTP connected"

    def __init__(self, coordinator: BiampTesiraCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_connected"
        self._attr_device_info = device_info(coordinator)

    @property
    def is_on(self) -> bool:
        return self.coordinator.client.connected

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class BiampTesiraSignalPresent(BiampTesiraBlockEntity, BinarySensorEntity):
    """Signal present meter."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)

    @property
    def is_on(self) -> bool | None:
        return coerce_bool(self.coordinator.data.get(self.block.unique_id))
