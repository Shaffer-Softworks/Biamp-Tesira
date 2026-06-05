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
    block_requires_matrix,
    block_type_labels,
)
from .const import (
    ATTR_MATRIX_INPUT,
    ATTR_MATRIX_OUTPUT,
    BLOCK_PRESET,
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
                        value="discovery",
                        label="Search the network",
                    ),
                    selector.SelectOptionDict(
                        value="manual",
                        label="Enter IP address",
                    ),
                ],
                mode=selector.SelectSelectorMode.LIST,
            ),
        ),
    }
)

_PROTOCOL_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[PROTO_SSH, PROTO_TELNET],
        translation_key="protocol",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

_IMPORT_TEXT_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        multiline=True,
    )
)

_ENTITIES_MENU_OPTIONS = {
    "finish": "Finish setup",
    "add_block": "Add a block entity",
    "import": "Import control points (CSV/JSON)",
}

_OPTIONS_MENU_OPTIONS = {
    "timing": "Polling and live updates",
    "import_control_points": "Import control points",
    "add_block": "Add a block entity",
}


def _connection_schema(
    *,
    host: str | None = None,
    protocol: str = PROTO_SSH,
) -> vol.Schema:
    default_port = DEFAULT_SSH_PORT if protocol == PROTO_SSH else DEFAULT_TELNET_PORT
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host or ""): str,
            vol.Required(CONF_PROTOCOL, default=protocol): _PROTOCOL_SELECTOR,
            vol.Required(CONF_PORT, default=default_port): int,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
        }
    )


def _index_number_selector(*, min_val: int = 1, max_val: int = 256) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_val,
            max=max_val,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _add_block_basics_schema(
    *,
    block_options: list[selector.SelectOptionDict],
    instance_tag_default: str = "",
    instance_tag_choices: list[str] | None = None,
) -> vol.Schema:
    """First step: block type, instance tag, and display name."""
    if instance_tag_choices:
        instance_tag_field: Any = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=instance_tag_choices,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    else:
        instance_tag_field = str

    return vol.Schema(
        {
            vol.Required("block_type"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=block_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("instance_tag", default=instance_tag_default): (
                instance_tag_field
            ),
            vol.Required("name", default=""): str,
        }
    )


def _add_block_details_schema(block_type: str) -> vol.Schema:
    """Second step: only the fields required for the selected block type."""
    fields: dict[Any, Any] = {}
    definition = BLOCK_DEFINITIONS[block_type]

    if block_requires_matrix(block_type):
        fields[vol.Required(ATTR_MATRIX_INPUT, default=1)] = _index_number_selector()
        fields[vol.Required(ATTR_MATRIX_OUTPUT, default=1)] = _index_number_selector()
    elif block_type == BLOCK_PRESET:
        fields[vol.Required("preset_id", default=1)] = _index_number_selector(
            min_val=1, max_val=9999
        )
    elif definition.supports_channel:
        fields[vol.Required("channel", default=1)] = _index_number_selector()

    if definition.supports_subscribe:
        fields[vol.Optional("subscribe", default=True)] = bool

    return vol.Schema(fields)


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
        self._pending_block: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BiampTesiraOptionsFlowHandler:
        return BiampTesiraOptionsFlowHandler()

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
                return await self.async_step_entities_menu()
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
            return await self.async_step_entities_menu()

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
                return await self.async_step_entities_menu()

        return self.async_show_form(
            step_id="discovery",
            data_schema=self._discovery_schema(),
        )

    async def async_step_entities_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose how to add Home Assistant entities, or finish setup."""
        if user_input is not None:
            if user_input["next"] == "finish":
                return self._create_entry()
            if user_input["next"] == "add_block":
                return await self.async_step_add_block()
            if user_input["next"] == "import":
                return await self.async_step_import()

        return self.async_show_menu(
            step_id="entities_menu",
            menu_options=_ENTITIES_MENU_OPTIONS,
            description_placeholders=self._entities_menu_placeholders(),
        )

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
                            {
                                vol.Optional(
                                    "import_text", default=text
                                ): _IMPORT_TEXT_SELECTOR
                            }
                        ),
                        errors={"base": "invalid_import"},
                        description_placeholders={"detail": str(err)},
                    )
            return await self.async_step_entities_menu()

        return self.async_show_form(
            step_id="import",
            data_schema=vol.Schema(
                {vol.Optional("import_text", default=""): _IMPORT_TEXT_SELECTOR}
            ),
        )

    async def async_step_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._pending_block = user_input
            return await self.async_step_add_block_details()

        return self.async_show_form(
            step_id="add_block",
            data_schema=self._add_block_basics_schema(),
            description_placeholders=self._entities_menu_placeholders(),
        )

    async def async_step_add_block_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        block_type = str(self._pending_block["block_type"])
        if user_input is not None:
            try:
                block = block_from_flow_input({**self._pending_block, **user_input})
            except ValueError as err:
                return self.async_show_form(
                    step_id="add_block_details",
                    data_schema=_add_block_details_schema(block_type),
                    errors={"base": "invalid_import"},
                    description_placeholders={
                        "detail": str(err),
                        "block_type": BLOCK_DEFINITIONS[block_type].label,
                    },
                )
            self._block_entities.append(block)
            self._pending_block = {}
            return await self.async_step_entities_menu()

        return self.async_show_form(
            step_id="add_block_details",
            data_schema=_add_block_details_schema(block_type),
            description_placeholders={
                "block_type": BLOCK_DEFINITIONS[block_type].label,
            },
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
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self._discovered_hosts,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_PROTOCOL, default=self._protocol): (
                        _PROTOCOL_SELECTOR
                    ),
                    vol.Required(CONF_PORT, default=default_port): int,
                    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            )
        return _connection_schema()

    def _add_block_basics_schema(self) -> vol.Schema:
        block_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in block_type_labels()
        ]
        alias_options = self._aliases or ["Level1"]
        return _add_block_basics_schema(
            block_options=block_options,
            instance_tag_default=alias_options[0] if alias_options else "",
            instance_tag_choices=alias_options if self._aliases else None,
        )

    def _entities_menu_placeholders(self) -> dict[str, str]:
        device_name = (
            self._device_info.get("deviceName")
            or self._device_info.get("model")
            or ""
        )
        return {
            "device_name": device_name or "Tesira",
            "aliases": ", ".join(self._aliases[:12]) or "none found",
            "block_count": str(len(self._block_entities)),
            "control_point_count": str(len(self._control_points)),
        }

    def _apply_connection_input(self, user_input: dict[str, Any]) -> None:
        self._host = user_input[CONF_HOST]
        self._protocol = user_input[CONF_PROTOCOL]
        self._port = user_input[CONF_PORT]
        self._username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
        self._password = user_input.get(CONF_PASSWORD, "")

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
        except (ConnectionError, TimeoutError, OSError):
            raise CannotConnect from None
        finally:
            await client.disconnect()
        if response is None or not response.raw:
            raise CannotConnect


class BiampTesiraOptionsFlowHandler(config_entries.OptionsFlow):
    """Options for polling, imports, and block entities."""

    def __init__(self) -> None:
        self._pending_block: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            if user_input["next"] == "timing":
                return await self.async_step_timing()
            if user_input["next"] == "import_control_points":
                return await self.async_step_import_control_points()
            if user_input["next"] == "add_block":
                return await self.async_step_add_block()

        return self.async_show_menu(
            step_id="init",
            menu_options=_OPTIONS_MENU_OPTIONS,
            description_placeholders=self._options_summary(),
        )

    async def async_step_timing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    **dict(self.config_entry.options),
                    CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                    CONF_SUBSCRIPTION_INTERVAL: user_input[
                        CONF_SUBSCRIPTION_INTERVAL
                    ],
                }
            )

        return self.async_show_form(
            step_id="timing",
            data_schema=self._timing_schema(),
        )

    async def async_step_import_control_points(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            import_text = (user_input.get("import_text") or "").strip()
            control_points = list(
                self.config_entry.options.get(CONF_CONTROL_POINTS, [])
            )
            if import_text:
                try:
                    is_json = import_text.lstrip().startswith(("{", "["))
                    parsed = parse_control_points(import_text, is_json=is_json)
                    control_points = [cp.to_dict() for cp in parsed]
                except (ValueError, TypeError) as err:
                    return self.async_show_form(
                        step_id="import_control_points",
                        data_schema=vol.Schema(
                            {
                                vol.Optional(
                                    "import_text",
                                    default=import_text,
                                ): _IMPORT_TEXT_SELECTOR
                            }
                        ),
                        errors={"base": "invalid_import"},
                        description_placeholders={"detail": str(err)},
                    )

            return self.async_create_entry(
                data={
                    **dict(self.config_entry.options),
                    CONF_CONTROL_POINTS: control_points,
                }
            )

        existing = self.config_entry.options.get(CONF_CONTROL_POINTS, [])
        return self.async_show_form(
            step_id="import_control_points",
            data_schema=vol.Schema(
                {vol.Optional("import_text", default=""): _IMPORT_TEXT_SELECTOR}
            ),
            description_placeholders={
                "control_point_count": str(len(existing)),
            },
        )

    async def async_step_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._pending_block = user_input
            return await self.async_step_add_block_details()

        return self.async_show_form(
            step_id="add_block",
            data_schema=self._add_block_basics_schema(),
        )

    async def async_step_add_block_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        block_type = str(self._pending_block["block_type"])
        if user_input is not None:
            try:
                block = block_from_flow_input({**self._pending_block, **user_input})
            except ValueError as err:
                return self.async_show_form(
                    step_id="add_block_details",
                    data_schema=_add_block_details_schema(block_type),
                    errors={"base": "invalid_import"},
                    description_placeholders={
                        "detail": str(err),
                        "block_type": BLOCK_DEFINITIONS[block_type].label,
                    },
                )
            blocks = list(self.config_entry.options.get(CONF_BLOCK_ENTITIES, []))
            blocks.append(block.to_dict())
            self._pending_block = {}
            return self.async_create_entry(
                data={
                    **dict(self.config_entry.options),
                    CONF_BLOCK_ENTITIES: blocks,
                }
            )

        return self.async_show_form(
            step_id="add_block_details",
            data_schema=_add_block_details_schema(block_type),
            description_placeholders={
                "block_type": BLOCK_DEFINITIONS[block_type].label,
            },
        )

    def _add_block_basics_schema(self) -> vol.Schema:
        block_options = [
            selector.SelectOptionDict(value=k, label=v.label)
            for k, v in BLOCK_DEFINITIONS.items()
        ]
        return _add_block_basics_schema(block_options=block_options)

    def _timing_schema(self) -> vol.Schema:
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
            }
        )

    def _options_summary(self) -> dict[str, str]:
        opts = self.config_entry.options
        return {
            "block_count": str(len(opts.get(CONF_BLOCK_ENTITIES, []))),
            "control_point_count": str(len(opts.get(CONF_CONTROL_POINTS, []))),
            "poll_interval": str(
                opts.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
            "subscription_interval": str(
                opts.get(
                    CONF_SUBSCRIPTION_INTERVAL, DEFAULT_SUBSCRIPTION_INTERVAL
                )
            ),
        }


class CannotConnect(HomeAssistantError):
    """Unable to connect to Tesira."""
