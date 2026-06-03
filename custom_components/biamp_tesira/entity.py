"""Base entities for Biamp Tesira."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DOMAIN
from .coordinator import BiampTesiraCoordinator
from .control_point import ControlPoint


def device_info(coordinator: BiampTesiraCoordinator) -> DeviceInfo:
    """Shared device info for a config entry."""
    info = coordinator.entry.data.get("device_info") or {}
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        name=info.get("name") or f"Biamp Tesira ({coordinator.entry.data[CONF_HOST]})",
        manufacturer="Biamp",
        model=info.get("model") or "Tesira",
        sw_version=info.get("sw_version"),
        hw_version=info.get("hw_version"),
        serial_number=info.get("serial_number"),
    )


class BiampTesiraControlEntity(CoordinatorEntity[BiampTesiraCoordinator]):
    """Control point entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BiampTesiraCoordinator,
        point: ControlPoint,
    ) -> None:
        super().__init__(coordinator)
        self.point = point
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{point.unique_id}"
        self._attr_name = point.name
        self._attr_device_info = device_info(coordinator)


class BiampTesiraBlockEntity(CoordinatorEntity[BiampTesiraCoordinator]):
    """Block-based entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BiampTesiraCoordinator,
        block,
    ) -> None:
        super().__init__(coordinator)
        self.block = block
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{block.unique_id}"
        self._attr_name = block.name
        self._attr_device_info = device_info(coordinator)
