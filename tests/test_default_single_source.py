"""
기본값 단일 정본 회귀 테스트

## WHY
설정 기본값이 defaults.py, Presenter, DTO, View 여러 곳에 리터럴로 복제되면서
설정 키가 누락된 경우 실행 경로에 따라 서로 다른 값이 적용되는 문제가 있었다.
대표적으로 창 크기는 1200x800과 1400x900이 동시에 fallback으로 존재했다.

## WHAT
* create_fallback_settings()가 canonical scalar default를 조립하는지 검증
* PreferencesCoordinator의 설정 fallback이 canonical default를 사용하는지 검증
* AppLifecycleManager의 누락 설정 fallback이 같은 창/폰트 기본값을 사용하는지 검증

## HOW
실제 설정 파일이나 GUI를 띄우지 않고 빈 설정/간단한 FakeSettings를 주입해
각 경로가 반환하는 DTO 값을 직접 비교한다.
"""
from common.constants import DEFAULT_BAUDRATE, DEFAULT_LOG_MAX_LINES
from common.defaults import (
    DEFAULT_FIXED_FONT_FAMILY,
    DEFAULT_FIXED_FONT_SIZE,
    DEFAULT_LANGUAGE,
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
    DEFAULT_PORT_NEWLINE,
    DEFAULT_PORT_SCAN_INTERVAL_MS,
    DEFAULT_PROP_FONT_FAMILY,
    DEFAULT_PROP_FONT_SIZE,
    DEFAULT_RIGHT_PANEL_VISIBLE,
    DEFAULT_THEME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    SETTINGS_VERSION,
    create_fallback_settings,
)
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.preferences_coordinator import PreferencesCoordinator


class _MissingSettings:
    """모든 설정 키가 누락된 상황을 재현하는 최소 FakeSettings."""

    def get(self, _key, default=None):
        return default


def test_fallback_configuration_is_built_from_canonical_defaults():
    settings = create_fallback_settings()

    assert settings["version"] == SETTINGS_VERSION
    assert settings["settings"]["theme"] == DEFAULT_THEME
    assert settings["settings"]["language"] == DEFAULT_LANGUAGE
    assert settings["settings"]["proportional_font_family"] == DEFAULT_PROP_FONT_FAMILY
    assert settings["settings"]["proportional_font_size"] == DEFAULT_PROP_FONT_SIZE
    assert settings["settings"]["fixed_font_family"] == DEFAULT_FIXED_FONT_FAMILY
    assert settings["settings"]["fixed_font_size"] == DEFAULT_FIXED_FONT_SIZE
    assert settings["settings"]["max_log_lines"] == DEFAULT_LOG_MAX_LINES
    assert settings["settings"]["port_baudrate"] == DEFAULT_BAUDRATE
    assert settings["settings"]["port_newline"] == DEFAULT_PORT_NEWLINE
    assert settings["settings"]["port_scan_interval_ms"] == DEFAULT_PORT_SCAN_INTERVAL_MS
    assert settings["ui"]["window_width"] == DEFAULT_WINDOW_WIDTH
    assert settings["ui"]["window_height"] == DEFAULT_WINDOW_HEIGHT
    assert settings["ui"]["right_section_visible"] is DEFAULT_RIGHT_PANEL_VISIBLE
    assert settings["logging"]["path"] == ""


def test_preferences_coordinator_uses_canonical_packet_defaults():
    state = PreferencesCoordinator.build_state(_MissingSettings())

    assert state.theme.lower() == DEFAULT_THEME
    assert state.language == DEFAULT_LANGUAGE
    assert state.font_size == DEFAULT_PROP_FONT_SIZE
    assert state.max_log_lines == DEFAULT_LOG_MAX_LINES
    assert state.baudrate == DEFAULT_BAUDRATE
    assert state.newline == DEFAULT_PORT_NEWLINE
    assert state.scan_interval_ms == DEFAULT_PORT_SCAN_INTERVAL_MS

    assert state.parser_type == DEFAULT_PACKET_PARSER_TYPE
    assert state.delimiters == DEFAULT_PACKET_DELIMITERS
    assert state.packet_length == DEFAULT_PACKET_LENGTH
    assert state.length_field_offset == DEFAULT_PACKET_LENGTH_FIELD_OFFSET
    assert state.length_field_size == DEFAULT_PACKET_LENGTH_FIELD_SIZE
    assert state.length_field_endian == DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
    assert state.length_includes_header is DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
    assert state.gap_ms == DEFAULT_PACKET_GAP_MS
    assert state.packet_buffer_size == DEFAULT_PACKET_BUFFER_SIZE
    assert state.packet_realtime is DEFAULT_PACKET_REALTIME
    assert state.packet_autoscroll is DEFAULT_PACKET_AUTOSCROLL


def test_lifecycle_missing_settings_uses_canonical_window_and_font_defaults():
    manager = object.__new__(AppLifecycleManager)

    window_state, font_config = manager._create_initial_states({})

    assert window_state.width == DEFAULT_WINDOW_WIDTH
    assert window_state.height == DEFAULT_WINDOW_HEIGHT
    assert window_state.right_panel_visible is DEFAULT_RIGHT_PANEL_VISIBLE

    assert font_config.prop_family == DEFAULT_PROP_FONT_FAMILY
    assert font_config.prop_size == DEFAULT_PROP_FONT_SIZE
    assert font_config.fixed_family == DEFAULT_FIXED_FONT_FAMILY
    assert font_config.fixed_size == DEFAULT_FIXED_FONT_SIZE
