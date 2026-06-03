"""Block entity definitions for typed Tesira TTP mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.const import Platform

from .const import (
    ATTR_BLOCK_TYPE,
    ATTR_CHANNEL,
    ATTR_INSTANCE_TAG,
    ATTR_MATRIX_INPUT,
    ATTR_MATRIX_OUTPUT,
    ATTR_SUBSCRIBE,
    BLOCK_AUDIO_METER,
    BLOCK_LEVEL,
    BLOCK_LOGIC_STATE,
    BLOCK_MUTE,
    BLOCK_PRESET,
    BLOCK_SIGNAL_PRESENT,
    BLOCK_SOURCE_SELECTOR,
)


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    """Metadata for a supported Tesira block type."""

    block_type: str
    label: str
    platform: str
    default_attribute: str
    supports_channel: bool = True
    supports_subscribe: bool = True


BLOCK_DEFINITIONS: dict[str, BlockDefinition] = {
    BLOCK_LEVEL: BlockDefinition(
        BLOCK_LEVEL,
        "Level",
        Platform.MEDIA_PLAYER,
        "level",
    ),
    BLOCK_MUTE: BlockDefinition(
        BLOCK_MUTE,
        "Mute",
        Platform.SWITCH,
        "mute",
    ),
    BLOCK_LOGIC_STATE: BlockDefinition(
        BLOCK_LOGIC_STATE,
        "Logic State",
        Platform.SWITCH,
        "state",
    ),
    BLOCK_SOURCE_SELECTOR: BlockDefinition(
        BLOCK_SOURCE_SELECTOR,
        "Source Selector",
        Platform.SELECT,
        "source",
        supports_channel=False,
    ),
    BLOCK_PRESET: BlockDefinition(
        BLOCK_PRESET,
        "Preset Recall",
        Platform.BUTTON,
        "recallPreset",
        supports_channel=False,
        supports_subscribe=False,
    ),
    BLOCK_SIGNAL_PRESENT: BlockDefinition(
        BLOCK_SIGNAL_PRESENT,
        "Signal Present Meter",
        Platform.BINARY_SENSOR,
        "present",
    ),
    BLOCK_AUDIO_METER: BlockDefinition(
        BLOCK_AUDIO_METER,
        "Audio Meter",
        Platform.SENSOR,
        "level",
    ),
}


@dataclass(frozen=True, slots=True)
class BlockEntityConfig:
    """Configured block entity stored in config entry options."""

    unique_id: str
    name: str
    block_type: str
    instance_tag: str
    channel: int = 1
    subscribe: bool = False
    matrix_input: int | None = None
    matrix_output: int | None = None
    preset_id: int | None = None

    @property
    def definition(self) -> BlockDefinition:
        """Return block definition metadata."""
        return BLOCK_DEFINITIONS[self.block_type]

    def format_instance_tag(self) -> str:
        tag = self.instance_tag.strip()
        if " " in tag and not (tag.startswith('"') and tag.endswith('"')):
            return f'"{tag}"'
        return tag

    def get_command(self) -> str:
        """Build TTP get for this block."""
        return self._build("get")

    def set_command(self, value: str | float | int | bool) -> str:
        """Build TTP set for this block."""
        if isinstance(value, bool):
            val = "true" if value else "false"
        else:
            val = str(value)
        return self._build("set", val)

    def toggle_command(self) -> str:
        """Build TTP toggle."""
        return self._build("toggle")

    def preset_command(self) -> str:
        """DEVICE recallPreset."""
        preset = self.preset_id if self.preset_id is not None else 1
        return f"DEVICE recallPreset {preset}"

    def subscription_token(self) -> str:
        """Stable token for TTP subscribe."""
        return f"ha_{self.unique_id}"[:32]

    def _build(self, verb: str, value: str | None = None) -> str:
        attr = self.definition.default_attribute
        parts = [self.format_instance_tag(), verb, attr]
        if self.definition.supports_channel:
            parts.append(str(self.channel))
        if self.block_type == BLOCK_SIGNAL_PRESENT:
            parts[2] = "present"
        if value is not None:
            parts.append(value)
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unique_id": self.unique_id,
            "name": self.name,
            ATTR_BLOCK_TYPE: self.block_type,
            ATTR_INSTANCE_TAG: self.instance_tag,
            ATTR_CHANNEL: self.channel,
            ATTR_SUBSCRIBE: self.subscribe,
        }
        if self.matrix_input is not None:
            data[ATTR_MATRIX_INPUT] = self.matrix_input
        if self.matrix_output is not None:
            data[ATTR_MATRIX_OUTPUT] = self.matrix_output
        if self.preset_id is not None:
            data["preset_id"] = self.preset_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockEntityConfig:
        return cls(
            unique_id=data["unique_id"],
            name=data["name"],
            block_type=str(data[ATTR_BLOCK_TYPE]),
            instance_tag=str(data[ATTR_INSTANCE_TAG]),
            channel=int(data.get(ATTR_CHANNEL, 1)),
            subscribe=bool(data.get(ATTR_SUBSCRIBE, False)),
            matrix_input=_optional_int(data.get(ATTR_MATRIX_INPUT)),
            matrix_output=_optional_int(data.get(ATTR_MATRIX_OUTPUT)),
            preset_id=_optional_int(data.get("preset_id")),
        )


def block_type_labels() -> list[tuple[str, str]]:
    """Return (block_type, label) for selectors."""
    return [(k, v.label) for k, v in BLOCK_DEFINITIONS.items()]


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
