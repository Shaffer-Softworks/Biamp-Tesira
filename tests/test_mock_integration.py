"""Integration test against the Telnet mock (optional, no HA)."""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from biamp_tesira.tesira_client import TesiraClient  # noqa: E402

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 2323


async def _exercise_mock() -> None:
    client = TesiraClient(
        MOCK_HOST,
        MOCK_PORT,
        protocol="telnet",
    )
    try:
        await asyncio.wait_for(client.connect(), timeout=3.0)
    except (ConnectionError, TimeoutError, OSError) as err:
        pytest.skip(f"Mock not running on {MOCK_HOST}:{MOCK_PORT}: {err}")

    try:
        aliases = await client.get_aliases()
        assert "Level1" in aliases

        resp = await client.send_command("Level1 get level 1")
        assert resp.ok
        assert resp.value is not None

        set_resp = await client.send_command("Level1 set level 1 -6.0")
        assert set_resp.ok
    finally:
        await client.disconnect()


def test_mock_session_and_level():
    """Requires mock: docker compose --profile mock up -d."""
    asyncio.run(_exercise_mock())
