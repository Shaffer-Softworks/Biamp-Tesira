"""Tests for control point command building."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from biamp_tesira.control_point import ControlPoint  # noqa: E402


def test_quoted_instance_tag():
    point = ControlPoint(
        unique_id="x",
        name="Zone",
        instance_tag="my level",
        command="get",
        attribute="level",
        index1=1,
    )
    assert point.get_command() == '"my level" get level 1'


def test_preset_command():
    point = ControlPoint(
        unique_id="p",
        name="Preset",
        instance_tag="DEVICE",
        command="get",
        attribute="recallPreset",
        preset=1001,
        entity_type="button",
    )
    assert point.recall_preset_command() == "DEVICE recallPreset 1001"
