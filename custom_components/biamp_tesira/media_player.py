"""Media player platform for Tesira level blocks."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .block_registry import BLOCK_LEVEL, BlockEntityConfig
from .const import DOMAIN
from .coordinator import BiampTesiraCoordinator
from .entity import BiampTesiraBlockEntity
from .util import coerce_bool, db_to_level, level_to_db


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media_player entities for level blocks."""
    coordinator: BiampTesiraCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        BiampTesiraLevelMediaPlayer(coordinator, block)
        for block in coordinator.block_entities
        if block.block_type == BLOCK_LEVEL
    ]
    async_add_entities(entities)


class BiampTesiraLevelMediaPlayer(BiampTesiraBlockEntity, MediaPlayerEntity):
    """Tesira level block as volume control."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(
        self, coordinator: BiampTesiraCoordinator, block: BlockEntityConfig
    ) -> None:
        super().__init__(coordinator, block)
        self._muted = False

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        raw = self.coordinator.data.get(self.block.unique_id)
        if raw is None:
            return None
        try:
            return db_to_level(float(raw))
        except (TypeError, ValueError):
            return None

    @property
    def is_volume_muted(self) -> bool | None:
        return self._muted

    async def async_set_volume_level(self, volume: float) -> None:
        db = level_to_db(volume)
        tag = self.block.format_instance_tag()
        cmd = f"{tag} set level {self.block.channel} {db}"
        response = await self.coordinator.client.send_command(cmd)
        if not response.ok:
            raise RuntimeError(response.error or response.raw)
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, self.block.unique_id: db}
        )

    async def async_volume_up(self) -> None:
        if self.volume_level is None:
            return
        await self.async_set_volume_level(min(1.0, self.volume_level + 0.05))

    async def async_volume_down(self) -> None:
        if self.volume_level is None:
            return
        await self.async_set_volume_level(max(0.0, self.volume_level - 0.05))

    async def async_mute_volume(self, mute: bool) -> None:
        tag = self.block.format_instance_tag()
        val = "true" if mute else "false"
        cmd = f"{tag} set mute {self.block.channel} {val}"
        response = await self.coordinator.client.send_command(cmd)
        if not response.ok:
            raise RuntimeError(response.error or response.raw)
        self._muted = mute
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh level and mute."""
        tag = self.block.format_instance_tag()
        level_resp = await self.coordinator.client.send_command(
            f"{tag} get level {self.block.channel}"
        )
        if level_resp.ok and level_resp.value is not None:
            self.coordinator.async_set_updated_data(
                {
                    **self.coordinator.data,
                    self.block.unique_id: level_resp.value,
                }
            )
        mute_resp = await self.coordinator.client.send_command(
            f"{tag} get mute {self.block.channel}"
        )
        if mute_resp.ok:
            muted = coerce_bool(mute_resp.value)
            if muted is not None:
                self._muted = muted
