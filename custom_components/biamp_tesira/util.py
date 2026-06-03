"""Utilities for Biamp Tesira."""

from __future__ import annotations

import re
from typing import Any

_BOOL_TRUE = {True, "true", "1", 1, 1.0, "on", "yes"}
_BOOL_FALSE = {False, "false", "0", 0, 0.0, "off", "no"}


def coerce_bool(value: Any) -> bool | None:
    """Normalize TTP boolean-like values."""
    if value is None:
        return None
    if value in _BOOL_TRUE or str(value).lower() in ("true", "1", "on", "yes"):
        return True
    if value in _BOOL_FALSE or str(value).lower() in ("false", "0", "off", "no"):
        return False
    try:
        return float(value) != 0.0
    except (TypeError, ValueError):
        return bool(value)


def db_to_level(db: float) -> float:
    """Convert dB Tesira level to HA 0..1 scale (-100..20 dB)."""
    clamped = max(-100.0, min(20.0, float(db)))
    return (clamped + 100.0) / 120.0


def level_to_db(level: float) -> float:
    """Convert HA 0..1 volume to dB."""
    fraction = max(0.0, min(1.0, float(level)))
    return round(fraction * 120.0 - 100.0, 2)


def parse_device_info(raw: str) -> dict[str, str]:
    """Extract device metadata from DEVICE get deviceInfo response."""
    info: dict[str, str] = {}
    patterns = {
        "serial_number": r'"serialNumber"\s*:\s*"([^"]+)"',
        "model": r'"deviceType"\s*:\s*"([^"]+)"',
        "sw_version": r'"firmwareVersion"\s*:\s*"([^"]+)"',
        "name": r'"deviceName"\s*:\s*"([^"]+)"',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            info[key] = match.group(1)
    return info
