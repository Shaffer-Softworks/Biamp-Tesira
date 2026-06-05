"""Async TTP client for Biamp Tesira (SSH and Telnet)."""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .const import (
    SESSION_DETAILED_OFF,
    SESSION_GET_ALIASES,
    SESSION_VERBOSE_ON,
    TELNET_IAC_DONT_ECHO,
    TELNET_IAC_WILL_ECHO,
)

_LOGGER = logging.getLogger(__name__)

_asyncssh: Any | None = None
_asyncssh_lock = asyncio.Lock()

_LINE_END = b"\n"
_IAC = 0xFF

_ERR_RE = re.compile(r"-ERR", re.IGNORECASE)
_VALUE_RE = re.compile(
    r'"value"\s*:\s*("(?:\\.|[^"\\])*"|true|false|-?[\d.]+)',
    re.IGNORECASE,
)
_LIST_RE = re.compile(r'"list"\s*:\s*\[(.*?)\]', re.IGNORECASE | re.DOTALL)

SubscriptionCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class TesiraResponse:
    """Parsed TTP command response."""

    raw: str
    ok: bool
    value: Any = None
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class TesiraClient:
    """Async client for a single Tesira TTP session over SSH or Telnet."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        protocol: str,
        username: str = "default",
        password: str = "",
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._protocol = protocol
        self._username = username
        self._password = password
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._buffer = bytearray()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._ssh_conn: Any = None
        self._ssh_process: Any = None
        self._subscription_callbacks: dict[str, SubscriptionCallback] = {}
        self._aliases: list[str] = []

    @property
    def connected(self) -> bool:
        """Return True if transport is open."""
        if self._protocol == "ssh":
            return self._ssh_process is not None
        return self._writer is not None and not self._writer.is_closing()

    @property
    def aliases(self) -> list[str]:
        """Cached instance tags from SESSION get aliases."""
        return list(self._aliases)

    def register_subscription_callback(
        self, token: str, callback: SubscriptionCallback
    ) -> None:
        """Register handler for publish-token updates."""
        self._subscription_callbacks[token] = callback

    def unregister_subscription_callback(self, token: str) -> None:
        """Remove subscription handler."""
        self._subscription_callbacks.pop(token, None)

    async def connect(self) -> None:
        """Open session and configure TTP."""
        async with self._lock:
            await self._connect_unlocked()
            await self._configure_session_unlocked()

    async def disconnect(self) -> None:
        """Close transport."""
        async with self._lock:
            await self._disconnect_unlocked()

    async def send_command(self, command: str) -> TesiraResponse:
        """Send a TTP command and wait for the response."""
        async with self._lock:
            if not self.connected:
                await self._connect_unlocked()
                await self._configure_session_unlocked()
            return await self._send_unlocked(command)

    async def get_aliases(self) -> list[str]:
        """Return instance tags from the Tesira system."""
        response = await self.send_command(SESSION_GET_ALIASES)
        if response.ok and isinstance(response.value, list):
            self._aliases = response.value
            return self._aliases
        return []

    async def subscribe(
        self,
        instance_tag: str,
        attribute: str,
        index1: int,
        token: str,
        interval_ms: int,
        *,
        index2: int | None = None,
        callback: SubscriptionCallback | None = None,
    ) -> TesiraResponse:
        """Subscribe to attribute updates."""
        if callback:
            self.register_subscription_callback(token, callback)
        tag = _quote_tag(instance_tag)
        parts = [tag, "subscribe", attribute.lower(), str(index1)]
        if index2 is not None:
            parts.append(str(index2))
        parts.extend([token, str(interval_ms)])
        cmd = " ".join(parts)
        return await self.send_command(cmd)

    async def unsubscribe(self, token: str) -> TesiraResponse:
        """Unsubscribe a publish token."""
        self.unregister_subscription_callback(token)
        return await self.send_command(f"unsubscribe {token}")

    async def _connect_unlocked(self) -> None:
        await self._disconnect_unlocked()
        if self._protocol == "ssh":
            await self._connect_ssh_unlocked()
        else:
            await self._connect_telnet_unlocked()
        self._buffer.clear()

    async def _connect_telnet_unlocked(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
        except OSError as err:
            raise ConnectionError(
                f"Cannot connect to {self._host}:{self._port}: {err}"
            ) from err
        await self._negotiate_echo()
        await self._drain_pending(timeout=0.5)

    async def _connect_ssh_unlocked(self) -> None:
        asyncssh = await _get_asyncssh()

        try:
            self._ssh_conn = await asyncio.wait_for(
                asyncssh.connect(
                    self._host,
                    port=self._port,
                    username=self._username,
                    password=self._password or None,
                    known_hosts=None,
                ),
                timeout=self._timeout,
            )
            self._ssh_process = await self._ssh_conn.create_process(
                term_type="VT100", encoding=None
            )
        except (OSError, asyncssh.Error) as err:
            raise ConnectionError(
                f"Cannot SSH to {self._host}:{self._port}: {err}"
            ) from err

        self._reader = self._ssh_process.stdout
        self._writer = self._ssh_process.stdin
        await self._drain_pending(timeout=0.5)

    async def _configure_session_unlocked(self) -> None:
        await self._send_unlocked(SESSION_VERBOSE_ON)
        await self._send_unlocked(SESSION_DETAILED_OFF)

    async def _disconnect_unlocked(self) -> None:
        if self._protocol == "ssh":
            if self._ssh_process:
                try:
                    self._ssh_process.close()
                    await self._ssh_process.wait_closed()
                except OSError:
                    pass
            if self._ssh_conn:
                self._ssh_conn.close()
                await self._ssh_conn.wait_closed()
            self._ssh_process = None
            self._ssh_conn = None
        elif self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass

        self._reader = None
        self._writer = None
        self._buffer.clear()

    async def _dispatch_subscription(self, line: str) -> None:
        parsed = parse_response([line], "")
        token_match = re.search(r'"publishToken"\s*:\s*"([^"]+)"', line)
        token = token_match.group(1) if token_match else ""
        callback = self._subscription_callbacks.get(token)
        if callback and parsed.ok:
            try:
                await callback(line, parsed.data)
            except Exception:
                _LOGGER.exception("Subscription callback failed for %s", token)

    async def _send_unlocked(self, command: str) -> TesiraResponse:
        line = command.strip() + "\n"
        try:
            await self._write_bytes(line.encode("ascii"))
            raw_lines = await self._read_response_lines()
        except OSError as err:
            await self._disconnect_unlocked()
            raise ConnectionError(f"Communication error: {err}") from err
        return parse_response(raw_lines, command)

    async def _write_bytes(self, data: bytes) -> None:
        if self._protocol == "ssh" and self._ssh_process:
            self._ssh_process.stdin.write(data)
            await self._ssh_process.stdin.drain()
        elif self._writer:
            self._writer.write(data)
            await self._writer.drain()
        else:
            raise ConnectionError("Not connected")

    async def _negotiate_echo(self) -> None:
        if not self._writer:
            return
        self._writer.write(TELNET_IAC_WILL_ECHO)
        await self._writer.drain()
        try:
            await asyncio.wait_for(self._read_some(max_bytes=64), timeout=2.0)
        except TimeoutError:
            pass

    async def _read_response_lines(self) -> list[str]:
        lines: list[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout

        while loop.time() < deadline:
            remaining = max(0.1, deadline - loop.time())
            line = await self._read_line(timeout=remaining)
            if line is None:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            lines.append(stripped)
            if _is_complete_response(stripped, lines):
                break
        else:
            raise TimeoutError("Timed out waiting for Tesira response")

        await self._drain_subscription_lines()
        return lines

    async def _drain_subscription_lines(self) -> None:
        """Process publish lines that arrived after the command response."""
        while True:
            line = await self._read_line(timeout=0.05)
            if line is None:
                break
            stripped = line.strip()
            if stripped and (
                "publishToken" in stripped or '"value"' in stripped
            ):
                await self._dispatch_subscription(stripped)

    async def _read_line(self, *, timeout: float) -> str | None:
        while True:
            if b"\n" in self._buffer:
                idx = self._buffer.index(b"\n")
                raw = bytes(self._buffer[:idx])
                del self._buffer[: idx + 1]
                return _decode_line(raw)

            if not self._reader:
                raise ConnectionError("Not connected")

            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=timeout,
                )
            except TimeoutError:
                return None

            if not chunk:
                raise ConnectionError("Connection closed by Tesira")
            self._buffer.extend(_strip_iac(chunk))

    async def _read_some(self, *, max_bytes: int) -> bytes:
        if not self._reader:
            return b""
        try:
            chunk = await asyncio.wait_for(
                self._reader.read(max_bytes),
                timeout=2.0,
            )
        except TimeoutError:
            return b""
        if chunk:
            self._buffer.extend(_strip_iac(chunk))
        return chunk

    async def _drain_pending(self, *, timeout: float) -> None:
        if not self._reader:
            return
        try:
            while True:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=timeout,
                )
                if not chunk:
                    break
                self._buffer.extend(_strip_iac(chunk))
        except TimeoutError:
            pass


def parse_response(lines: list[str], command: str) -> TesiraResponse:
    """Parse TTP response lines."""
    raw = "\n".join(lines)
    if not lines:
        return TesiraResponse(raw=raw, ok=False, error="Empty response")

    for line in reversed(lines):
        if _ERR_RE.search(line):
            return TesiraResponse(raw=raw, ok=False, error=line)

        list_match = _LIST_RE.search(line)
        if list_match and "aliases" in command.lower():
            items = _parse_ttp_list(list_match.group(1))
            return TesiraResponse(
                raw=raw,
                ok=True,
                value=items,
                data={"list": items},
            )

        value_match = _VALUE_RE.search(line)
        if value_match:
            value = _parse_ttp_value_token(value_match.group(1))
            return TesiraResponse(
                raw=raw,
                ok=True,
                value=value,
                data={"value": value},
            )

        if line.strip().upper().startswith("+OK"):
            return TesiraResponse(raw=raw, ok=True, value=None)

    return TesiraResponse(raw=raw, ok=True, value=None)


def _parse_ttp_list(blob: str) -> list[str]:
    items: list[str] = []
    for quoted in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', blob):
        items.append(quoted.replace('\\"', '"'))
    if not items:
        for bare in re.findall(r'\S+', blob.replace('"', "")):
            if bare not in items:
                items.append(bare)
    return items


def _parse_ttp_value_token(token: str) -> Any:
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].replace('\\"', '"')
    lower = token.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


def _is_complete_response(line: str, all_lines: list[str]) -> bool:
    upper = line.upper()
    if "+OK" in upper or "-ERR" in upper:
        return True
    if '"value"' in line or '"list"' in line:
        return True
    if "publishToken" in line:
        return True
    return len(all_lines) >= 2


def _strip_iac(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == _IAC and i + 2 < len(data):
            i += 3
            continue
        out.append(data[i])
        i += 1
    return bytes(out)


def _decode_line(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").strip("\r")


async def _get_asyncssh() -> Any:
    """Load asyncssh in a worker thread (import does blocking filesystem I/O)."""
    global _asyncssh
    if _asyncssh is not None:
        return _asyncssh
    async with _asyncssh_lock:
        if _asyncssh is not None:
            return _asyncssh
        try:
            _asyncssh = await asyncio.to_thread(
                importlib.import_module, "asyncssh"
            )
        except ImportError as err:
            raise ConnectionError("asyncssh is required for SSH") from err
    return _asyncssh


def _quote_tag(instance_tag: str) -> str:
    tag = instance_tag.strip()
    if " " in tag and not (tag.startswith('"') and tag.endswith('"')):
        return f'"{tag}"'
    return tag
