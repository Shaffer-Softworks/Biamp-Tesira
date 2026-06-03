"""Tests for TTP response parsing."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from biamp_tesira.tesira_client import parse_response  # noqa: E402


def test_parse_level_value():
    lines = ['Level1 get level 1 +OK "value":-12.500000']
    result = parse_response(lines, "Level1 get level 1")
    assert result.ok
    assert result.value == -12.5


def test_parse_bool_value():
    lines = ['Mute1 get mute 1 +OK "value":true']
    result = parse_response(lines, "Mute1 get mute 1")
    assert result.ok
    assert result.value is True


def test_parse_aliases_list():
    lines = ['SESSION get aliases +OK "list":["Level1" "Mute1" "DEVICE"]']
    result = parse_response(lines, "SESSION get aliases")
    assert result.ok
    assert result.value == ["Level1", "Mute1", "DEVICE"]


def test_parse_error():
    lines = ["-ERR: address not found"]
    result = parse_response(lines, "Bad get")
    assert not result.ok


def test_parse_ok_only():
    lines = ["+OK"]
    result = parse_response(lines, "DEVICE recallPreset 1")
    assert result.ok
