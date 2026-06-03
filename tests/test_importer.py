"""Tests for control point import."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from biamp_tesira.importer import parse_control_points  # noqa: E402


CSV_SAMPLE = """name,instance_tag,command,attribute,index1,entity_type
Main Level,Level1,get,level,1,number
"""

JSON_SAMPLE = """[
  {"name": "Mute", "instance_tag": "Mute1", "attribute": "mute", "index1": 1, "entity_type": "switch"}
]"""


def test_parse_csv():
    points = parse_control_points(CSV_SAMPLE, is_json=False)
    assert len(points) == 1
    assert points[0].instance_tag == "Level1"
    assert points[0].get_command() == "Level1 get level 1"


def test_parse_json():
    points = parse_control_points(JSON_SAMPLE, is_json=True)
    assert len(points) == 1
    assert points[0].entity_type == "switch"
