"""Tests for block entity command building."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from biamp_tesira.block_registry import (  # noqa: E402
    BlockEntityConfig,
    block_from_flow_input,
)
from biamp_tesira.const import (  # noqa: E402
    BLOCK_MATRIX_CROSSPOINT,
    BLOCK_MATRIX_CROSSPOINT_LEVEL,
)


def test_matrix_crosspoint_commands():
    block = BlockEntityConfig(
        unique_id="matrix_crosspoint_Mixer1_2_3",
        name="Mic to LR",
        block_type=BLOCK_MATRIX_CROSSPOINT,
        instance_tag="Mixer1",
        matrix_input=2,
        matrix_output=3,
    )
    assert block.get_command() == "Mixer1 get crosspointLevelState 2 3"
    assert block.set_command(True) == "Mixer1 set crosspointLevelState 2 3 true"
    assert block.toggle_command() == "Mixer1 toggle crosspointLevelState 2 3"


def test_matrix_crosspoint_level_commands():
    block = BlockEntityConfig(
        unique_id="matrix_crosspoint_level_Mixer1_2_3",
        name="Mic to LR gain",
        block_type=BLOCK_MATRIX_CROSSPOINT_LEVEL,
        instance_tag="Mixer1",
        matrix_input=2,
        matrix_output=3,
    )
    assert block.get_command() == "Mixer1 get crosspointLevel 2 3"
    assert block.set_command(-6.0) == "Mixer1 set crosspointLevel 2 3 -6.0"


def test_matrix_block_serialization_round_trip():
    block = BlockEntityConfig(
        unique_id="matrix_crosspoint_Mixer1_2_3",
        name="Mic to LR",
        block_type=BLOCK_MATRIX_CROSSPOINT,
        instance_tag="Mixer1",
        matrix_input=2,
        matrix_output=3,
        subscribe=True,
    )
    restored = BlockEntityConfig.from_dict(block.to_dict())
    assert restored.matrix_input == 2
    assert restored.matrix_output == 3
    assert restored.get_command() == block.get_command()


def test_block_from_flow_input_matrix():
    block = block_from_flow_input(
        {
            "block_type": BLOCK_MATRIX_CROSSPOINT,
            "instance_tag": "Mixer1",
            "name": "Mic to LR",
            "matrix_input": 2,
            "matrix_output": 3,
            "subscribe": True,
        }
    )
    assert block.unique_id == "matrix_crosspoint_Mixer1_2_3"
    assert block.matrix_input == 2
    assert block.matrix_output == 3


def test_block_from_flow_input_matrix_requires_indices():
    with pytest.raises(ValueError, match="matrix_input and matrix_output"):
        block_from_flow_input(
            {
                "block_type": BLOCK_MATRIX_CROSSPOINT,
                "instance_tag": "Mixer1",
                "name": "Mic to LR",
            }
        )
