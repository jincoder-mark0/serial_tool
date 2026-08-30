"""DTO 기본값/상태 정본 계약 테스트.

DTO가 `common.defaults`/`common.enums`와 다른 리터럴 기본값을 다시 갖지 않도록
실제 기본 생성 결과와 역직렬화 결과를 검증합니다.
"""
from common.constants import DEFAULT_BAUDRATE, DEFAULT_LOG_MAX_LINES
from common.defaults import (
    DEFAULT_COMMAND_PREFIX,
    DEFAULT_COMMAND_SUFFIX,
    DEFAULT_FIXED_FONT_FAMILY,
    DEFAULT_FIXED_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_LOG_PATH,
    DEFAULT_PACKET_AT_COLOR_ERROR,
    DEFAULT_PACKET_AT_COLOR_OK,
    DEFAULT_PACKET_AT_COLOR_PROMPT,
    DEFAULT_PACKET_AT_COLOR_URC,
    DEFAULT_PACKET_AUTOSCROLL,
    DEFAULT_PACKET_BUFFER_SIZE,
    DEFAULT_PACKET_DELIMITERS,
    DEFAULT_PACKET_GAP_MS,
    DEFAULT_PACKET_LENGTH,
    DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
    DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
    DEFAULT_PACKET_LENGTH_FIELD_SIZE,
    DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
    DEFAULT_PACKET_PARSER_TYPE,
    DEFAULT_PACKET_REALTIME,
    DEFAULT_PORT_BYTESIZE,
    DEFAULT_PORT_LOCAL_ECHO,
    DEFAULT_PORT_NEWLINE,
    DEFAULT_PORT_PROTOCOL,
    DEFAULT_PORT_SCAN_INTERVAL_MS,
    DEFAULT_PROP_FONT_FAMILY,
    DEFAULT_PROP_FONT_SIZE,
    DEFAULT_RIGHT_PANEL_VISIBLE,
    DEFAULT_SPI_MODE,
    DEFAULT_SPI_SPEED,
    DEFAULT_THEME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from common.dtos import (
    ErrorContext,
    FontConfig,
    MacroStepEvent,
    MainWindowState,
    PortConfig,
    PreferencesState,
    SystemLogEvent,
)
from common.enums import LogLevel, MacroStepType


def test_port_config_defaults_follow_canonical_values():
    config = PortConfig(port="COM_TEST")

    assert config.protocol == DEFAULT_PORT_PROTOCOL
    assert config.baudrate == DEFAULT_BAUDRATE
    assert config.bytesize == DEFAULT_PORT_BYTESIZE
    assert config.speed == DEFAULT_SPI_SPEED
    assert config.mode == DEFAULT_SPI_MODE
    assert config.parser_type == DEFAULT_PACKET_PARSER_TYPE
    assert config.packet_delimiter == DEFAULT_PACKET_DELIMITERS[0]
    assert config.packet_length == DEFAULT_PACKET_LENGTH
    assert config.length_field_offset == DEFAULT_PACKET_LENGTH_FIELD_OFFSET
    assert config.length_field_size == DEFAULT_PACKET_LENGTH_FIELD_SIZE
    assert config.length_field_endian == DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
    assert config.length_includes_header is DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
    assert config.gap_ms == DEFAULT_PACKET_GAP_MS


def test_port_config_from_dict_preserves_extended_parser_fields():
    config = PortConfig.from_dict({
        "port": "COM7",
        "length_field_offset": 3,
        "length_field_size": 4,
        "length_field_endian": "little",
        "length_includes_header": True,
        "gap_ms": 17,
    })

    assert config.length_field_offset == 3
    assert config.length_field_size == 4
    assert config.length_field_endian == "little"
    assert config.length_includes_header is True
    assert config.gap_ms == 17


def test_port_config_from_empty_dict_uses_canonical_defaults():
    config = PortConfig.from_dict({"port": "COM_TEST"})
    direct = PortConfig(port="COM_TEST")

    assert config == direct


def test_preferences_state_defaults_follow_fallback_defaults():
    state = PreferencesState()

    assert state.theme == DEFAULT_THEME
    assert state.language == DEFAULT_LANGUAGE
    assert state.font_size == DEFAULT_PROP_FONT_SIZE
    assert state.max_log_lines == DEFAULT_LOG_MAX_LINES
    assert state.baudrate == DEFAULT_BAUDRATE
    assert state.newline == DEFAULT_PORT_NEWLINE
    assert state.local_echo_enabled is DEFAULT_PORT_LOCAL_ECHO
    assert state.scan_interval_ms == DEFAULT_PORT_SCAN_INTERVAL_MS
    assert state.command_prefix == DEFAULT_COMMAND_PREFIX
    assert state.command_suffix == DEFAULT_COMMAND_SUFFIX
    assert state.log_dir == DEFAULT_LOG_PATH
    assert state.parser_type == DEFAULT_PACKET_PARSER_TYPE
    assert state.delimiters == DEFAULT_PACKET_DELIMITERS
    assert state.delimiters is not DEFAULT_PACKET_DELIMITERS
    assert state.packet_length == DEFAULT_PACKET_LENGTH
    assert state.length_field_offset == DEFAULT_PACKET_LENGTH_FIELD_OFFSET
    assert state.length_field_size == DEFAULT_PACKET_LENGTH_FIELD_SIZE
    assert state.length_field_endian == DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
    assert state.length_includes_header is DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
    assert state.gap_ms == DEFAULT_PACKET_GAP_MS
    assert state.at_color_ok is DEFAULT_PACKET_AT_COLOR_OK
    assert state.at_color_error is DEFAULT_PACKET_AT_COLOR_ERROR
    assert state.at_color_urc is DEFAULT_PACKET_AT_COLOR_URC
    assert state.at_color_prompt is DEFAULT_PACKET_AT_COLOR_PROMPT
    assert state.packet_buffer_size == DEFAULT_PACKET_BUFFER_SIZE
    assert state.packet_realtime is DEFAULT_PACKET_REALTIME
    assert state.packet_autoscroll is DEFAULT_PACKET_AUTOSCROLL


def test_window_and_font_dto_fallbacks_follow_canonical_values():
    window = MainWindowState()
    font = FontConfig.from_dict({})

    assert window.width == DEFAULT_WINDOW_WIDTH
    assert window.height == DEFAULT_WINDOW_HEIGHT
    assert window.right_panel_visible is DEFAULT_RIGHT_PANEL_VISIBLE
    assert font.prop_family == DEFAULT_PROP_FONT_FAMILY
    assert font.prop_size == DEFAULT_PROP_FONT_SIZE
    assert font.fixed_family == DEFAULT_FIXED_FONT_FAMILY
    assert font.fixed_size == DEFAULT_FIXED_FONT_SIZE


def test_event_dto_default_strings_come_from_enums():
    assert SystemLogEvent("x").level == LogLevel.INFO.value
    assert ErrorContext("E", "m", "tb").level == LogLevel.CRITICAL.value
    assert MacroStepEvent(0).type == MacroStepType.STARTED.value
