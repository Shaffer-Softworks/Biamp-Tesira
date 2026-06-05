"""The Biamp Tesira integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import BiampTesiraCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_COMMAND = "send_command"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Biamp Tesira from a config entry."""
    coordinator = BiampTesiraCoordinator(hass, entry)

    try:
        await coordinator.client.connect()
        await coordinator.client.get_aliases()
        await coordinator.async_setup_subscriptions()
        await coordinator.async_config_entry_first_refresh()
    except (ConnectionError, TimeoutError, OSError) as err:
        await coordinator.client.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to Tesira at {entry.data[CONF_HOST]}:"
            f"{entry.data[CONF_PORT]}: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: BiampTesiraCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register send_command service once."""

    async def send_command(call) -> None:
        command = call.data.get("command", "").strip()
        if not command:
            return
        host = call.data.get(CONF_HOST)
        coordinators: dict[str, BiampTesiraCoordinator] = hass.data.get(DOMAIN, {})
        if not coordinators:
            _LOGGER.error("No Biamp Tesira instances configured")
            return
        if host:
            coordinator = next(
                (
                    c
                    for c in coordinators.values()
                    if c.entry.data[CONF_HOST] == host
                ),
                None,
            )
            if coordinator is None:
                _LOGGER.error("No Tesira config entry for host %s", host)
                return
        elif len(coordinators) == 1:
            coordinator = next(iter(coordinators.values()))
        else:
            _LOGGER.error(
                "Multiple Tesira instances; specify host in service call"
            )
            return
        response = await coordinator.client.send_command(command)
        if not response.ok:
            _LOGGER.error("Tesira command failed: %s", response.error or response.raw)

    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        send_command,
        schema=vol.Schema(
            {
                vol.Required("command"): cv.string,
                vol.Optional(CONF_HOST): cv.string,
            }
        ),
    )
