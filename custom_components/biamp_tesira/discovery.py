"""UDP discovery for Biamp devices (port 12000)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from .const import DISCOVERY_TIMEOUT, DISCOVERY_UDP_PORT

_LOGGER = logging.getLogger(__name__)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """A device found via UDP discovery."""

    ip_address: str
    raw: bytes


async def async_discover_devices(
    broadcast_address: str = "255.255.255.255",
) -> list[DiscoveredDevice]:
    """Broadcast on Biamp discovery port and collect unique IPs."""
    found: dict[str, DiscoveredDevice] = {}

    def _probe() -> None:
        import socket
        import time

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(DISCOVERY_TIMEOUT)
        try:
            sock.sendto(b"\x00", (broadcast_address, DISCOVERY_UDP_PORT))
            deadline = time.time() + DISCOVERY_TIMEOUT
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except TimeoutError:
                    break
                ip = addr[0]
                if ip not in found:
                    found[ip] = DiscoveredDevice(ip_address=ip, raw=data)
                for match in _IP_RE.findall(
                    data.decode("latin-1", errors="ignore")
                ):
                    if match not in found:
                        found[match] = DiscoveredDevice(
                            ip_address=match, raw=data
                        )
        except OSError as err:
            _LOGGER.debug("UDP discovery failed: %s", err)
        finally:
            sock.close()

    await asyncio.get_running_loop().run_in_executor(None, _probe)
    return list[DiscoveredDevice](found.values())
