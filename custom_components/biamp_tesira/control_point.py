"""Control point model for Tesira TTP entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    ATTR_ATTRIBUTE,
    ATTR_COMMAND,
    ATTR_ENTITY_TYPE,
    ATTR_INDEX1,
    ATTR_INDEX2,
    ATTR_INSTANCE_TAG,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_OPTIONS,
    ATTR_PRESET,
    ATTR_UNIT,
    ENTITY_TYPE_BUTTON,
    ENTITY_TYPE_NUMBER,
    ENTITY_TYPE_SELECT,
    ENTITY_TYPE_SWITCH,
)


@dataclass(frozen=True, slots=True)
class ControlPoint:
    """A single TTP addressable control point."""

    unique_id: str
    name: str
    instance_tag: str
    command: str
    attribute: str
    index1: int | None = None
    index2: int | None = None
    entity_type: str = ENTITY_TYPE_NUMBER
    min_value: float | None = None
    max_value: float | None = None
    preset: int | None = None
    unit: str | None = None
    options: list[str] | None = None

    def format_instance_tag(self) -> str:
        """Quote instance tag when it contains spaces."""
        tag = self.instance_tag.strip()
        if " " in tag and not (tag.startswith('"') and tag.endswith('"')):
            return f'"{tag}"'
        return tag

    def get_command(self) -> str:
        """Build a TTP get command."""
        return self._build_command("get")

    def set_command(self, value: str | float | int | bool) -> str:
        """Build a TTP set command."""
        return self._build_command("set", value=_format_ttp_value(value))

    def toggle_command(self) -> str:
        """Build a TTP toggle command."""
        return self._build_command("toggle")

    def recall_preset_command(self) -> str:
        """Build DEVICE recallPreset for button entities."""
        preset = self.preset if self.preset is not None else 1
        return f"DEVICE recallPreset {preset}"

    def _build_command(
        self,
        verb: str,
        *,
        value: str | None = None,
    ) -> str:
        cmd = verb.lower()
        parts = [self.format_instance_tag(), cmd, self.attribute.lower()]
        if self.index1 is not None:
            parts.append(str(self.index1))
        if self.index2 is not None:
            parts.append(str(self.index2))
        if value is not None:
            parts.append(value)
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for config entry storage."""
        data: dict[str, Any] = {
            "unique_id": self.unique_id,
            "name": self.name,
            ATTR_INSTANCE_TAG: self.instance_tag,
            ATTR_COMMAND: self.command,
            ATTR_ATTRIBUTE: self.attribute,
            ATTR_ENTITY_TYPE: self.entity_type,
        }
        if self.index1 is not None:
            data[ATTR_INDEX1] = self.index1
        if self.index2 is not None:
            data[ATTR_INDEX2] = self.index2
        if self.min_value is not None:
            data[ATTR_MIN] = self.min_value
        if self.max_value is not None:
            data[ATTR_MAX] = self.max_value
        if self.preset is not None:
            data[ATTR_PRESET] = self.preset
        if self.unit is not None:
            data[ATTR_UNIT] = self.unit
        if self.options is not None:
            data[ATTR_OPTIONS] = self.options
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlPoint:
        """Deserialize from config entry storage."""
        index1 = data.get(ATTR_INDEX1)
        index2 = data.get(ATTR_INDEX2)
        options = data.get(ATTR_OPTIONS)
        return cls(
            unique_id=data["unique_id"],
            name=data["name"],
            instance_tag=str(data[ATTR_INSTANCE_TAG]),
            command=str(data.get(ATTR_COMMAND, "get")).lower(),
            attribute=str(data[ATTR_ATTRIBUTE]).lower(),
            index1=int(index1) if index1 is not None and index1 != "" else None,
            index2=int(index2) if index2 is not None and index2 != "" else None,
            entity_type=str(
                data.get(ATTR_ENTITY_TYPE, ENTITY_TYPE_NUMBER)
            ).lower(),
            min_value=_optional_float(data.get(ATTR_MIN)),
            max_value=_optional_float(data.get(ATTR_MAX)),
            preset=int(data[ATTR_PRESET]) if data.get(ATTR_PRESET) is not None else None,
            unit=data.get(ATTR_UNIT),
            options=list(options) if options else None,
        )


def _format_ttp_value(value: str | float | int | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(value)
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
