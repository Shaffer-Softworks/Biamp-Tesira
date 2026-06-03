#!/usr/bin/env python3
"""Minimal Telnet TTP mock for Biamp Tesira integration testing."""

from __future__ import annotations

import asyncio
import json
import re

HOST = "0.0.0.0"
PORT = 23

IAC_WILL_ECHO = bytes([0xFF, 0xFE, 0x01])
IAC_DONT_ECHO = bytes([0xFF, 0xFC, 0x01])

ALIASES = [
    "DEVICE",
    "Level1",
    "Mute1",
    "Logic1",
    "SourceSel1",
    "Meter1",
]

_STATE: dict[str, object] = {
    "level:Level1:1": -12.0,
    "mute:Level1:1": False,
    "state:Logic1:1": False,
    "source:SourceSel1": 1,
    "present:Meter1:1": True,
    "level:Meter1:1": -24.5,
}


def _strip_iac(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF and i + 2 < len(data):
            i += 3
            continue
        out.append(data[i])
        i += 1
    return bytes(out)


def _quote_tag(tag: str) -> str:
    tag = tag.strip().strip('"')
    if " " in tag:
        return f'"{tag}"'
    return tag


def _handle_command(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    upper = line.upper()

    if upper.startswith("SESSION SET VERBOSE"):
        return '+OK\n'
    if upper.startswith("SESSION SET DETAILEDRESPONSE"):
        return '+OK\n'
    if upper.startswith("SESSION GET ALIASES"):
        lst = " ".join(f'"{a}"' for a in ALIASES)
        return f'+OK "list":[{lst}]\n'

    if upper.startswith("DEVICE GET DEVICEINFO"):
        payload = {
            "deviceName": "Tesira-Mock",
            "serialNumber": "MOCK0001",
            "deviceType": "Server",
            "firmwareVersion": "1.0-mock",
        }
        return f'+OK {json.dumps(payload, separators=(",", ":"))}\n'

    if upper.startswith("UNSUBSCRIBE"):
        return "+OK\n"

    if " SUBSCRIBE " in upper:
        return "+OK\n"

    if upper.startswith("DEVICE RECALLPRESET"):
        return "+OK\n"

    match = re.match(
        r'^(".*?"|\S+)\s+(get|set|toggle)\s+(\S+)(?:\s+(\d+))?(?:\s+(\d+))?(?:\s+(.+))?$',
        line,
        re.IGNORECASE,
    )
    if not match:
        return "-ERR: parse error\n"

    tag = _quote_tag(match.group(1))
    verb = match.group(2).lower()
    attr = match.group(3).lower()
    ch = match.group(4) or "1"
    value_arg = match.group(6)

    key = f"{attr}:{tag.strip('\"')}:{ch}" if ch else f"{attr}:{tag.strip('\"')}"
    if attr == "source":
        key = f"source:{tag.strip('\"')}"

    if verb == "get":
        if key in _STATE:
            val = _STATE[key]
            if isinstance(val, bool):
                return f'+OK "value":{"true" if val else "false"}\n'
            if isinstance(val, (int, float)):
                return f'+OK "value":{val}\n'
            return f'+OK "value":{json.dumps(str(val))}\n'
        return '-ERR: address not found\n'

    if verb in ("set", "toggle"):
        if value_arg is not None:
            if value_arg.lower() in ("true", "false"):
                _STATE[key] = value_arg.lower() == "true"
            else:
                try:
                    _STATE[key] = float(value_arg) if "." in value_arg else int(value_arg)
                except ValueError:
                    _STATE[key] = value_arg
        elif verb == "toggle" and isinstance(_STATE.get(key), bool):
            _STATE[key] = not _STATE[key]
        return "+OK\n"

    return "+OK\n"


async def _handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    buffer = b""
    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            if IAC_WILL_ECHO in chunk:
                writer.write(IAC_DONT_ECHO)
                await writer.drain()
            buffer += _strip_iac(chunk)
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                line = line_bytes.decode("ascii", errors="replace").strip("\r")
                if not line:
                    continue
                response = _handle_command(line)
                if response:
                    writer.write(response.encode("ascii"))
                    await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    server = await asyncio.start_server(_handle_client, HOST, PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    print(f"Tesira TTP mock listening on {addrs}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
