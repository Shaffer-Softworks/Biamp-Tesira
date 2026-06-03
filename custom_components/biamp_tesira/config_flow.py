"""Config flow for Biamp Tesira."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .block_registry import (
    BLOCK_DEFINITIONS,
    BlockEntityConfig,
    block_from_flow_input,
    block_type_labels,
)
from .const import (
    ATTR_MATRIX_INPUT,
    ATTR_MATRIX_OUTPUT,
    CONF_BLOCK_ENTITIES,
    CONF_CONTROL_POINTS,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PROTOCOL,
    CONF_SUBSCRIPTION_INTERVAL,
    CONF_USERNAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SSH_PORT,
    DEFAULT_SUBSCRIPTION_INTERVAL,
    DEFAULT_TELNET_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    PROBE_DEVICE_INFO,
    PROTO_SSH,
    PROTO_TELNET,
)
from .control_point import ControlPoint
from .discovery import async_discover_devices
from .importer import parse_control_points
from .tesira_client import TesiraClient
from .util import parse_device_info

_LOGGER = logging.getLogger(__name__)

STEP_CONNECT_METHOD_SCHEMA = vol.Schema(
    {
        vol.Required("method"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value="manual",
                        label="Enter IP address manually",
                    ),
                    selector.SelectOptionDict(
                        value="discovery",
                        label="Discover on network (UDP)",
                    ),
                ],
                mode=selector.SelectSelectorMode.LIST,
            ),
        ),
    }
)


def _connection_schema(
    *,
    host: str | None = None,
    protocol: str = PROTO_SSH,
) -> vol.Schema:
    default_port = DEFAULT_SSH_PORT if protocol == PROTO_SSH else DEFAULT_TELNET_PORT
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host or ""): str,
            vol.Required(CONF_PROTOCOL, default=protocol): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[PROTO_SSH, PROTO_TELNET],
                    translation_key="protocol",
                )
            ),
            vol.Required(CONF_PORT, default=default_port): int,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
            vol.Optional(
                CONF_SUBSCRIPTION_INTERVAL,
                default=DEFAULT_SUBSCRIPTION_INTERVAL,
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=60000)),
        }
    )


def _add_block_schema(
    *,
    block_options: list[selector.SelectOptionDict],
    instance_tag_default: str = "",
    instance_tag_choices: list[str] | None = None,
) -> vol.Schema:
    """Schema for adding a typed block entity."""
    if instance_tag_choices:
        instance_tag_field = vol.In(instance_tag_choices)
    else:
        instance_tag_field = str

    return vol.Schema(
        {
            vol.Required("block_type"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=block_options)
            ),
            vol.Required("instance_tag", default=instance_tag_default): (
                instance_tag_field
            ),
            vol.Required("name", default=""): str,
            vol.Optional("channel", default=1): int,
            vol.Optional(ATTR_MATRIX_INPUT): int,
            vol.Optional(ATTR_MATRIX_OUTPUT): int,
            vol.Optional("subscribe", default=False): bool,
            vol.Optional("preset_id"): int,
        }
    )


class BiampTesiraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Biamp Tesira."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_SSH_PORT
        self._protocol: str = PROTO_SSH
        self._username: str = DEFAULT_USERNAME
        self._password: str = ""
        self._poll_interval: int = DEFAULT_POLL_INTERVAL
        self._subscription_interval: int = DEFAULT_SUBSCRIPTION_INTERVAL
        self._control_points: list[ControlPoint] = []
        self._block_entities: list[BlockEntityConfig] = []
        self._discovered_hosts: list[str] = []
        self._device_info: dict[str, str] = {}
        self._aliases: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BiampTesiraOptionsFlowHandler:
        return BiampTesiraOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            if user_input.get("method") == "discovery":
                return await self.async_step_discovery()
            return await self.async_step_manual()
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CONNECT_METHOD_SCHEMA,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._apply_connection_input(user_input)
            try:
                await self._validate_connection()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_import()
        return self.async_show_form(
            step_id="manual",
            data_schema=_connection_schema(),
            errors=errors,
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._apply_connection_input(user_input)
            try:
                await self._validate_connection()
            except CannotConnect:
                return self.async_show_form(
                    step_id="discovery",
                    data_schema=self._discovery_schema(),
                    errors={"base": "cannot_connect"},
                )
            return await self.async_step_import()

        devices = await async_discover_devices()
        self._discovered_hosts = [d.ip_address for d in devices]

        if not self._discovered_hosts:
            return self.async_show_form(
                step_id="discovery",
                data_schema=_connection_schema(),
                errors={"base": "discovery_failed"},
            )

        if len(self._discovered_hosts) == 1:
            self._host = self._discovered_hosts[0]
            try:
                await self._validate_connection()
            except CannotConnect:
                pass
            else:
                return await self.async_step_import()

        return self.async_show_form(
            step_id="discovery",
            data_schema=self._discovery_schema(),
        )

    def _discovery_schema(self) -> vol.Schema:
        if self._discovered_hosts:
            default_port = (
                DEFAULT_SSH_PORT
                if self._protocol == PROTO_SSH
                else DEFAULT_TELNET_PORT
            )
            return vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self._discovered_hosts[0],
                    ): vol.In(self._discovered_hosts),
                    vol.Required(CONF_PROTOCOL, default=self._protocol): str,
                    vol.Required(CONF_PORT, default=default_port): int,
                    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                    ): int,
                    vol.Optional(
                        CONF_SUBSCRIPTION_INTERVAL,
                        default=DEFAULT_SUBSCRIPTION_INTERVAL,
                    ): int,
                }
            )
        return _connection_schema()

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            text = (user_input.get("import_text") or "").strip()
            if text:
                try:
                    is_json = text.lstrip().startswith(("{", "["))
                    self._control_points = parse_control_points(
                        text, is_json=is_json
                    )
                except (ValueError, TypeError) as err:
                    return self.async_show_form(
                        step_id="import",
                        data_schema=vol.Schema(
                            {vol.Optional("import_text", default=""): str}
                        ),
                        errors={"base": "invalid_import"},
                        description_placeholders={"detail": str(err)},
                    )
            return await self.async_step_block_entity()

        return self.async_show_form(
            step_id="import",
            data_schema=vol.Schema({vol.Optional("import_text", default=""): str}),
        )

    async def async_step_block_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            if user_input.get("add_block"):
                return await self.async_step_add_block()
            return self._create_entry()

        return self.async_show_form(
            step_id="block_entity",
            data_schema=vol.Schema(
                {
                    vol.Optional("add_block", default=False): bool,
                }
            ),
            description_placeholders={
                "aliases": ", ".join(self._aliases[:8]) or "none",
            },
        )

    async def async_step_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            try:
                block = block_from_flow_input(user_input)
            except ValueError as err:
                return self.async_show_form(
                    step_id="add_block",
                    data_schema=self._add_block_form_schema(),
                    errors={"base": "invalid_import"},
                    description_placeholders={"detail": str(err)},
                )
            self._block_entities.append(block)
            return await self.async_step_block_entity()

        return self.async_show_form(
            step_id="add_block",
            data_schema=self._add_block_form_schema(),
        )

    def _add_block_form_schema(self) -> vol.Schema:
        block_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in block_type_labels()
        ]
        alias_options = self._aliases or ["Level1"]
        return _add_block_schema(
            block_options=block_options,
            instance_tag_default=alias_options[0] if alias_options else "",
            instance_tag_choices=alias_options if alias_options else None,
        )

    def _apply_connection_input(self, user_input: dict[str, Any]) -> None:
        self._host = user_input[CONF_HOST]
        self._protocol = user_input[CONF_PROTOCOL]
        self._port = user_input[CONF_PORT]
        self._username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
        self._password = user_input.get(CONF_PASSWORD, "")
        self._poll_interval = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        self._subscription_interval = user_input.get(
            CONF_SUBSCRIPTION_INTERVAL, DEFAULT_SUBSCRIPTION_INTERVAL
        )

    def _create_entry(self) -> FlowResult:
        assert self._host is not None
        self.async_set_unique_id(self._host.lower())
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Biamp Tesira ({self._host})",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_PROTOCOL: self._protocol,
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                "device_info": self._device_info,
            },
            options={
                CONF_POLL_INTERVAL: self._poll_interval,
                CONF_SUBSCRIPTION_INTERVAL: self._subscription_interval,
                CONF_CONTROL_POINTS: [cp.to_dict() for cp in self._control_points],
                CONF_BLOCK_ENTITIES: [be.to_dict() for be in self._block_entities],
            },
        )

    async def _validate_connection(self) -> None:
        assert self._host is not None
        client = TesiraClient(
            self._host,
            self._port,
            protocol=self._protocol,
            username=self._username,
            password=self._password,
        )
        response = None
        try:
            await client.connect()
            response = await client.send_command(PROBE_DEVICE_INFO)
            if response.raw:
                self._device_info = parse_device_info(response.raw)
            self._aliases = await client.get_aliases()
        finally:
            await client.disconnect()
        if response is None or not response.raw:
            raise CannotConnect


class BiampTesiraOptionsFlowHandler(config_entries.OptionsFlow):
    """Options for polling, imports, and block entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            if user_input.get("manage_blocks"):
                return await self.async_step_add_block()
            poll = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            sub = user_input.get(
                CONF_SUBSCRIPTION_INTERVAL, DEFAULT_SUBSCRIPTION_INTERVAL
            )
            import_text = (user_input.get("import_text") or "").strip()
            control_points = list(
                self.config_entry.options.get(CONF_CONTROL_POINTS, [])
            )
            block_entities = list(
                self.config_entry.options.get(CONF_BLOCK_ENTITIES, [])
            )

            if import_text:
                try:
                    is_json = import_text.lstrip().startswith(("{", "["))
                    parsed = parse_control_points(import_text, is_json=is_json)
                    control_points = [cp.to_dict() for cp in parsed]
                except (ValueError, TypeError) as err:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._options_schema(),
                        errors={"base": "invalid_import"},
                        description_placeholders={"detail": str(err)},
                    )

            return self.async_create_entry(
                data={
                    CONF_POLL_INTERVAL: poll,
                    CONF_SUBSCRIPTION_INTERVAL: sub,
                    CONF_CONTROL_POINTS: control_points,
                    CONF_BLOCK_ENTITIES: block_entities,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(),
        )

    async def async_step_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            try:
                block = block_from_flow_input(user_input)
            except ValueError as err:
                return self.async_show_form(
                    step_id="add_block",
                    data_schema=self._add_block_form_schema(),
                    errors={"base": "invalid_import"},
                    description_placeholders={"detail": str(err)},
                )
            blocks = list(self.config_entry.options.get(CONF_BLOCK_ENTITIES, []))
            blocks.append(block.to_dict())
            return self.async_create_entry(
                data={
                    **dict(self.config_entry.options),
                    CONF_BLOCK_ENTITIES: blocks,
                }
            )

        return self.async_show_form(
            step_id="add_block",
            data_schema=self._add_block_form_schema(),
        )

    def _add_block_form_schema(self) -> vol.Schema:
        block_options = [
            selector.SelectOptionDict(value=k, label=v.label)
            for k, v in BLOCK_DEFINITIONS.items()
        ]
        return _add_block_schema(block_options=block_options)

    def _options_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                vol.Optional(
                    CONF_SUBSCRIPTION_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SUBSCRIPTION_INTERVAL, DEFAULT_SUBSCRIPTION_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=50, max=60000)),
                vol.Optional("import_text", default=""): str,
                vol.Optional("manage_blocks", default=False): bool,
            }
        )


class CannotConnect(HomeAssistantError):
    """Unable to connect to Tesira."""
