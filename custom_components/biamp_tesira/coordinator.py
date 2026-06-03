"""Data update coordinator for Biamp Tesira."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .block_registry import BlockEntityConfig
from .const import (
    BLOCK_PRESET,
    CONF_BLOCK_ENTITIES,
    CONF_CONTROL_POINTS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SUBSCRIPTION_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SUBSCRIPTION_INTERVAL,
    DOMAIN,
    ENTITY_TYPE_BUTTON,
    MAX_SUBSCRIPTIONS,
)
from .control_point import ControlPoint
from .tesira_client import TesiraClient

_LOGGER = logging.getLogger(__name__)


class BiampTesiraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Tesira control points and block entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.client = TesiraClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            protocol=entry.data[CONF_PROTOCOL],
            username=entry.data.get(CONF_USERNAME, "default"),
            password=entry.data.get(CONF_PASSWORD, ""),
        )
        self.control_points: list[ControlPoint] = [
            ControlPoint.from_dict(cp)
            for cp in entry.options.get(CONF_CONTROL_POINTS, [])
        ]
        self.block_entities: list[BlockEntityConfig] = [
            BlockEntityConfig.from_dict(be)
            for be in entry.options.get(CONF_BLOCK_ENTITIES, [])
        ]
        self._subscribed: set[str] = set()
        poll = entry.options.get(CONF_POLL_INTERVAL, 30)
        self.subscription_interval = entry.options.get(
            CONF_SUBSCRIPTION_INTERVAL, DEFAULT_SUBSCRIPTION_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll),
        )

    async def async_setup_subscriptions(self) -> None:
        """Subscribe block entities that requested live updates."""
        count = 0
        for block in self.block_entities:
            if not block.subscribe or not block.definition.supports_subscribe:
                continue
            if count >= MAX_SUBSCRIPTIONS:
                _LOGGER.warning("Max subscriptions reached; skipping %s", block.name)
                break
            token = block.subscription_token()

            async def _callback(
                _line: str, data: dict[str, Any], *, uid: str = block.unique_id
            ) -> None:
                value = data.get("value")
                if value is not None:
                    self.async_set_updated_data({**self.data, uid: value})

            if token in self._subscribed:
                continue
            try:
                await self.client.subscribe(
                    block.instance_tag,
                    block.definition.default_attribute,
                    block.channel,
                    token,
                    self.subscription_interval,
                    callback=_callback,
                )
                self._subscribed.add(token)
                count += 1
            except (ConnectionError, TimeoutError, OSError) as err:
                _LOGGER.warning(
                    "Subscribe failed for %s: %s", block.name, err
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current values."""
        data: dict[str, Any] = dict(self.data)
        errors: list[str] = []

        for point in self.control_points:
            if point.entity_type == ENTITY_TYPE_BUTTON:
                continue
            try:
                response = await self.client.send_command(point.get_command())
            except (ConnectionError, TimeoutError, OSError) as err:
                raise UpdateFailed(f"Tesira communication failed: {err}") from err

            if not response.ok:
                errors.append(f"{point.unique_id}: {response.error or response.raw}")
                data[point.unique_id] = None
            else:
                data[point.unique_id] = response.value

        for block in self.block_entities:
            if block.block_type == BLOCK_PRESET:
                continue
            if block.subscribe and block.unique_id in data:
                continue
            try:
                response = await self.client.send_command(block.get_command())
            except (ConnectionError, TimeoutError, OSError) as err:
                raise UpdateFailed(f"Tesira communication failed: {err}") from err

            if not response.ok:
                errors.append(f"{block.unique_id}: {response.error or response.raw}")
                data[block.unique_id] = None
            else:
                data[block.unique_id] = response.value

        if errors and not any(v is not None for v in data.values()):
            raise UpdateFailed("; ".join(errors[:3]))

        for err in errors:
            _LOGGER.warning("Poll issue: %s", err)

        return data

    async def async_set_control_value(
        self, point: ControlPoint, value: str | float | int | bool
    ) -> None:
        """Send SET for a control point."""
        response = await self.client.send_command(point.set_command(value))
        if not response.ok:
            raise RuntimeError(response.error or response.raw)
        self.async_set_updated_data(
            {**self.data, point.unique_id: response.value if response.value is not None else value}
        )

    async def async_set_block_value(
        self, block: BlockEntityConfig, value: str | float | int | bool
    ) -> None:
        """Send SET for a block entity."""
        response = await self.client.send_command(block.set_command(value))
        if not response.ok:
            raise RuntimeError(response.error or response.raw)
        self.async_set_updated_data(
            {**self.data, block.unique_id: response.value if response.value is not None else value}
        )

    async def async_recall_preset(self, point: ControlPoint) -> None:
        """Recall preset via control point or DEVICE."""
        cmd = point.recall_preset_command()
        response = await self.client.send_command(cmd)
        if not response.ok:
            raise RuntimeError(response.error or response.raw)

    async def async_press_block(self, block: BlockEntityConfig) -> None:
        """Press a block button (preset)."""
        response = await self.client.send_command(block.preset_command())
        if not response.ok:
            raise RuntimeError(response.error or response.raw)
