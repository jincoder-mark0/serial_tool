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
* SettingsManager의 버전 값과 defaults.py의 설정 버전이 어긋나지 않는지 검증
* SerialTransport가 이미 존재하는 timeout/flow-control 정의를 우회하지 않는지 검증
* settings schema의 theme/language 허용값이 common enum과 일치하는지 검증
* ConnectionWorker가 이미 존재하는 sleep 타이밍 상수를 사용하는지 검증
* PortConfig에서 사용할 protocol/bytesize/SPI 기본 정책과 공통 상태 enum을 고정
"""
import inspect
from unittest.mock import patch

from common.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_LOG_MAX_LINES,
    DEFAULT_PORT_TIMEOUT,
    WRITE_TIMEOUT_S,
)
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
    DEFAULT_PORT_BYTESIZE,
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
    SETTINGS_VERSION,
    create_fallback_settings,
)
from common.dtos import PortConfig
from common.enums import (
    ConnectionEventState,
    ConnectionProtocol,
    LanguageType,
    LogLevel,
    MacroStepType,
    SerialFlowControl,
    ThemeType,
)
from core.settings_manager import SettingsManager
from core.settings_schema import CORE_SETTINGS_SCHEMA
from core.transport.serial_transport import SerialTransport
from model.connection_worker import ConnectionWorker
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


def test_settings_manager_version_matches_canonical_default_version():
    """마이그레이션 버전과 fallback 파일 버전이 서로 갈라지면 안 된다."""
    assert SettingsManager.CURRENT_VERSION == SETTINGS_VERSION


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


def test_serial_transport_uses_common_timeout_and_flow_control_values():
    """SerialTransport가 constants/enums의 정본을 실제 pyserial 인자로 사용해야 한다."""
    config = PortConfig(port="COM_TEST", flowctrl=SerialFlowControl.RTS_CTS.value)

    with patch("core.transport.serial_transport.serial.Serial") as serial_ctor:
        serial_ctor.return_value.is_open = True
        transport = SerialTransport(config)
        assert transport.open() is True

    kwargs = serial_ctor.call_args.kwargs
    assert kwargs["timeout"] == DEFAULT_PORT_TIMEOUT
    assert kwargs["write_timeout"] == WRITE_TIMEOUT_S
    assert kwargs["rtscts"] is True
    assert kwargs["xonxoff"] is False


def test_settings_schema_uses_common_theme_and_language_enums():
    settings_schema = CORE_SETTINGS_SCHEMA["properties"]["settings"]["properties"]

    assert set(settings_schema["theme"]["enum"]) == {item.value for item in ThemeType}
    assert set(settings_schema["language"]["enum"]) == {item.value for item in LanguageType}


def test_connection_worker_uses_common_sleep_timing_constants():
    """Worker wait policy가 1/100 같은 magic timing literal을 다시 사용하지 않게 고정한다."""
    source = inspect.getsource(ConnectionWorker._wait_for_next_iteration)

    assert "msleep(WORKER_IDLE_WAIT_MS)" in source
    assert "usleep(WORKER_BUSY_WAIT_US)" in source


def test_port_dto_policy_defaults_are_named_and_protocol_backed():
    """PortConfig용 기본 정책값이 의미 없는 literal이 아니라 이름 있는 정본을 갖는다."""
    assert DEFAULT_PORT_PROTOCOL == ConnectionProtocol.SERIAL
    assert DEFAULT_PORT_BYTESIZE == 8
    assert DEFAULT_SPI_SPEED == 1_000_000
    assert DEFAULT_SPI_MODE == 0


def test_common_event_state_values_are_stable():
    """DTO/event producer가 사용할 공통 문자열 상태의 저장 형식을 고정한다."""
    assert ConnectionEventState.OPENED.value == "opened"
    assert ConnectionEventState.CLOSED.value == "closed"
    assert MacroStepType.STARTED.value == "started"
    assert MacroStepType.COMPLETED.value == "completed"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.SUCCESS.value == "SUCCESS"
    assert LogLevel.CRITICAL.value == "CRITICAL"


def test_fallback_blocks_are_independent_across_calls():
    """
    호출마다 독립된 중첩 객체를 돌려줘야 한다.

    얕은 복사로 돌려주면 중첩 dict/list가 모듈 전역 DEFAULT_* 와 같은 객체가 되어,
    한 쪽을 고치면 "기본값"이 통째로 바뀐다.
    """
    first = create_fallback_settings()
    second = create_fallback_settings()

    nested_paths = [
        ("manual_control", "manual_control_widget"),
        ("macro_list", "control_state"),
    ]
    for block, key in nested_paths:
        assert first[block][key] is not second[block][key], (
            f"{block}.{key}가 호출 간에 같은 객체다 — 한 곳의 수정이 기본값 전체에 번진다"
        )

    for block, key in [("macro_list", "commands"), ("ports", "tabs"), ("packet", "delimiters")]:
        assert first[block][key] is not second[block][key], (
            f"{block}.{key} 리스트가 호출 간에 공유된다"
        )


def test_loading_user_settings_does_not_mutate_canonical_defaults(tmp_path):
    """
    사용자 설정을 로드해도 모듈 전역 기본값은 그대로여야 한다.

    ## WHY
    `create_fallback_settings()`가 얕은 복사를 돌려주던 때는
    `SettingsManager._merge_settings`의 재귀 병합이 사용자 값을 모듈 전역
    DEFAULT_* 에 그대로 써 넣었다. 실측: 전체 테스트 스위트를 한 번 돌리는 것만으로
    `DEFAULT_MANUAL_CONTROL_STATE`의 prefix/suffix/broadcast가 False -> True로 바뀌었다.

    피해가 두 갈래다. 런타임에서는 설정 파일이 손상돼 fallback으로 복구할 때 진짜
    기본값이 아니라 **직전 사용자 값**이 되살아난다 — "기본값으로 복구했다"는
    로그를 남기면서. 테스트에서는 한 케이스가 만든 값이 전역에 남아 이후 케이스로
    새어나가 결과가 실행 순서에 의존하게 된다.
    """
    import copy
    import json

    from common import defaults as defaults_module
    from core.resource_path import ResourcePath
    from core.settings_manager import SettingsManager

    pristine = copy.deepcopy(defaults_module.DEFAULT_MANUAL_CONTROL_STATE)

    resource_path = ResourcePath(tmp_path)
    resource_path.config_dir.mkdir(parents=True, exist_ok=True)

    user_settings = create_fallback_settings()
    user_settings["manual_control"]["manual_control_widget"].update(
        {"input_text": "AT+USER", "hex_mode": True, "broadcast_enabled": True}
    )
    resource_path.user_settings_file.write_text(
        json.dumps(user_settings), encoding="utf-8"
    )

    SettingsManager(resource_path)

    assert defaults_module.DEFAULT_MANUAL_CONTROL_STATE == pristine, (
        "사용자 설정 로드가 모듈 전역 기본값을 덮어썼다 — 손상 복구 시 진짜 기본값 대신 "
        "직전 사용자 값이 되살아나고, 테스트 격리도 깨진다"
    )
