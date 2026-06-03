"""Constants for the Biamp Tesira integration."""

DOMAIN = "biamp_tesira"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PROTOCOL = "protocol"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POLL_INTERVAL = "poll_interval"
CONF_SUBSCRIPTION_INTERVAL = "subscription_interval"
CONF_CONTROL_POINTS = "control_points"
CONF_BLOCK_ENTITIES = "block_entities"

PROTO_SSH = "ssh"
PROTO_TELNET = "telnet"

DEFAULT_SSH_PORT = 22
DEFAULT_TELNET_PORT = 23
DEFAULT_POLL_INTERVAL = 30
DEFAULT_SUBSCRIPTION_INTERVAL = 100
DEFAULT_USERNAME = "default"

ATTR_INSTANCE_TAG = "instance_tag"
ATTR_COMMAND = "command"
ATTR_ATTRIBUTE = "attribute"
ATTR_INDEX1 = "index1"
ATTR_INDEX2 = "index2"
ATTR_ENTITY_TYPE = "entity_type"
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_UNIT = "unit"
ATTR_OPTIONS = "options"
ATTR_PRESET = "preset"
ATTR_BLOCK_TYPE = "block_type"
ATTR_CHANNEL = "channel"
ATTR_SUBSCRIBE = "subscribe"
ATTR_MATRIX_INPUT = "matrix_input"
ATTR_MATRIX_OUTPUT = "matrix_output"

ENTITY_TYPE_NUMBER = "number"
ENTITY_TYPE_SWITCH = "switch"
ENTITY_TYPE_BUTTON = "button"
ENTITY_TYPE_SELECT = "select"

BLOCK_LEVEL = "level"
BLOCK_MUTE = "mute"
BLOCK_LOGIC_STATE = "logic_state"
BLOCK_SOURCE_SELECTOR = "source_selector"
BLOCK_PRESET = "preset"
BLOCK_SIGNAL_PRESENT = "signal_present_meter"
BLOCK_AUDIO_METER = "audio_meter"
BLOCK_MATRIX_CROSSPOINT = "matrix_crosspoint"
BLOCK_MATRIX_CROSSPOINT_LEVEL = "matrix_crosspoint_level"

MATRIX_BLOCK_TYPES = frozenset(
    {BLOCK_MATRIX_CROSSPOINT, BLOCK_MATRIX_CROSSPOINT_LEVEL}
)

PLATFORMS = [
    "binary_sensor",
    "button",
    "media_player",
    "number",
    "select",
    "sensor",
    "switch",
]

PROBE_DEVICE_INFO = "DEVICE get deviceInfo"
SESSION_VERBOSE_ON = "SESSION set verbose true"
SESSION_DETAILED_OFF = "SESSION set detailedResponse false"
SESSION_GET_ALIASES = "SESSION get aliases"

TELNET_IAC_WILL_ECHO = bytes([0xFF, 0xFE, 0x01])
TELNET_IAC_DONT_ECHO = bytes([0xFF, 0xFC, 0x01])

DISCOVERY_UDP_PORT = 12000
DISCOVERY_TIMEOUT = 3.0

MAX_SUBSCRIPTIONS = 32
