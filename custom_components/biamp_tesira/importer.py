"""Import control points from CSV or JSON."""

from __future__ import annotations

import csv
import json
from io import StringIO
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
from .control_point import ControlPoint

_REQUIRED = {ATTR_INSTANCE_TAG, ATTR_ATTRIBUTE}

_CSV_ALIASES = {
    "friendly_name": "name",
    "friendly name": "name",
    "label": "name",
    "tag": ATTR_INSTANCE_TAG,
    "instance": ATTR_INSTANCE_TAG,
    "instance_tag": ATTR_INSTANCE_TAG,
    "instancetag": ATTR_INSTANCE_TAG,
    "verb": ATTR_COMMAND,
    "cmd": ATTR_COMMAND,
    "command": ATTR_COMMAND,
    "attr": ATTR_ATTRIBUTE,
    "attribute": ATTR_ATTRIBUTE,
    "index_1": ATTR_INDEX1,
    "index1": ATTR_INDEX1,
    "index_2": ATTR_INDEX2,
    "index2": ATTR_INDEX2,
    "type": ATTR_ENTITY_TYPE,
    "entity_type": ATTR_ENTITY_TYPE,
    "min": ATTR_MIN,
    "max": ATTR_MAX,
    "preset": ATTR_PRESET,
    "unit": ATTR_UNIT,
    "options": ATTR_OPTIONS,
}


def parse_control_points(content: str, *, is_json: bool) -> list[ControlPoint]:
    """Parse control points from CSV or JSON text."""
    if is_json:
        return _parse_json(content)
    return _parse_csv(content)


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        norm_key = _CSV_ALIASES.get(key.strip().lower(), key.strip().lower())
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        normalized[norm_key] = value.strip() if isinstance(value, str) else value
    return normalized


def _parse_json(content: str) -> list[ControlPoint]:
    data = json.loads(content)
    if isinstance(data, dict) and "control_points" in data:
        rows = data["control_points"]
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError("JSON must be a list or object with 'control_points' key")
    return [_row_to_control_point(_normalize_row(dict(r))) for r in rows]


def _parse_csv(content: str) -> list[ControlPoint]:
    reader = csv.DictReader(StringIO(content.strip()))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    points: list[ControlPoint] = []
    for row in reader:
        if not any(v and str(v).strip() for v in row.values()):
            continue
        points.append(_row_to_control_point(_normalize_row(row)))
    return points


def _row_to_control_point(row: dict[str, Any]) -> ControlPoint:
    missing = _REQUIRED - set(row.keys())
    if missing:
        raise ValueError(f"Row missing required fields: {', '.join(sorted(missing))}")

    name = row.get("name") or row.get("unique_id")
    instance_tag = str(row[ATTR_INSTANCE_TAG])
    attribute = str(row[ATTR_ATTRIBUTE]).lower()
    command = str(row.get(ATTR_COMMAND, "get")).lower()
    entity_type = str(row.get(ATTR_ENTITY_TYPE, ENTITY_TYPE_NUMBER)).lower()

    index1 = _optional_int(row.get(ATTR_INDEX1))
    index2 = _optional_int(row.get(ATTR_INDEX2))
    unique_id = row.get("unique_id") or _default_unique_id(
        instance_tag, attribute, index1, index2, entity_type
    )

    if entity_type not in (
        ENTITY_TYPE_NUMBER,
        ENTITY_TYPE_SWITCH,
        ENTITY_TYPE_BUTTON,
        ENTITY_TYPE_SELECT,
    ):
        raise ValueError(f"Unknown entity_type: {entity_type}")

    options_raw = row.get(ATTR_OPTIONS)
    options: list[str] | None = None
    if options_raw:
        if isinstance(options_raw, list):
            options = [str(o) for o in options_raw]
        else:
            options = [p.strip() for p in str(options_raw).split("|") if p.strip()]

    return ControlPoint(
        unique_id=str(unique_id),
        name=str(name or unique_id),
        instance_tag=instance_tag,
        command=command,
        attribute=attribute,
        index1=index1,
        index2=index2,
        entity_type=entity_type,
        min_value=_optional_float(row.get(ATTR_MIN)),
        max_value=_optional_float(row.get(ATTR_MAX)),
        preset=_optional_int(row.get(ATTR_PRESET)),
        unit=row.get(ATTR_UNIT),
        options=options,
    )


def _default_unique_id(
    instance_tag: str,
    attribute: str,
    index1: int | None,
    index2: int | None,
    entity_type: str,
) -> str:
    parts = [instance_tag.replace(" ", "_"), attribute]
    if index1 is not None:
        parts.append(str(index1))
    if index2 is not None:
        parts.append(str(index2))
    parts.append(entity_type)
    return "_".join(parts)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
