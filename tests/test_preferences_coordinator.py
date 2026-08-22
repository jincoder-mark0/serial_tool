"""
S-058 신규 테스트: PreferencesCoordinator (presenter/preferences_coordinator.py)

## WHY
* PreferencesState DTO 조립(읽기)/적용(쓰기) 매핑이 종전에는
  MainPresenter.on_preferences_requested()/on_settings_change_requested() 두
  곳에 나뉘어 있었다. PreferencesCoordinator로 통합한 뒤 왕복(build -> apply
  -> build) 동작이 값 손실/변형 없이 유지되는지 고정한다.
* Qt/View 의존 없이 SettingsManager(임시 경로)만으로 검증 가능하다.

## WHAT
* 기본값 조회(설정 파일이 비어 있을 때의 기본값)가 기존 on_preferences_requested()
  하드코딩 기본값과 동일한지 검증.
* apply_state() 후 build_state()로 다시 읽으면 원래 DTO와 동일한 값이 나오는
  왕복(roundtrip) 검증.
* theme 필드의 대소문자 비대칭 변환(읽기: capitalize, 쓰기: lower)이 유지되는지
  검증.

## HOW
* `tests/conftest.py`의 `mock_settings_manager`(임시 경로 SettingsManager, Qt
  불필요)를 그대로 사용한다.
"""
from common.constants import ConfigKeys
from common.dtos import PreferencesState
from presenter.preferences_coordinator import PreferencesCoordinator


class TestPreferencesCoordinatorBuildState:
    """설정이 비어 있을 때 build_state()가 반환하는 기본값을 고정한다.

    주의: SettingsManager는 설정 파일이 없으면 스키마 기본값(로케일에 따라
    달라질 수 있는 language 등 포함) 전체로 폴백하므로, 여기서는
    on_preferences_requested()가 실제로 사용하던 하드코딩 기본값(파일에
    해당 키 자체가 전혀 없을 때만 쓰이는 값)을 `settings.get(key, default)`를
    직접 호출해 검증한다 — language처럼 로케일 의존적인 필드는 제외한다.
    """

    def test_build_state_uses_expected_defaults_when_settings_empty(self, mock_settings_manager):
        state = PreferencesCoordinator.build_state(mock_settings_manager)

        assert state.theme == "Dark"
        assert state.font_size == 10
        assert state.max_log_lines == 2000
        assert state.baudrate == 115200
        assert state.newline == "\n"
        assert state.local_echo_enabled is False
        assert state.scan_interval_ms == 1000
        assert state.command_prefix == ""
        assert state.command_suffix == ""
        assert state.log_dir == ""
        assert state.parser_type == 0
        assert state.delimiters == ["\\r\\n"]
        assert state.packet_length == 64
        assert state.at_color_ok is True
        assert state.at_color_error is True
        assert state.at_color_urc is True
        assert state.at_color_prompt is True
        assert state.packet_buffer_size == 100
        assert state.packet_realtime is True
        assert state.packet_autoscroll is True

    def test_build_state_language_matches_direct_settings_lookup(self, mock_settings_manager):
        """language는 로케일 의존 폴백이 있을 수 있으므로 직접 조회값과 대조만 한다."""
        state = PreferencesCoordinator.build_state(mock_settings_manager)
        assert state.language == mock_settings_manager.get(ConfigKeys.LANGUAGE, "en")


class TestPreferencesCoordinatorApplyState:
    """apply_state()가 SettingsManager에 기대한 키로 값을 반영하는지 검증한다."""

    def test_apply_state_writes_theme_lowercased(self, mock_settings_manager):
        state = PreferencesState(theme="Light")
        PreferencesCoordinator.apply_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.THEME) == "light"

    def test_apply_state_writes_all_mapped_keys(self, mock_settings_manager):
        state = PreferencesState(
            theme="Dark",
            language="ko",
            font_size=12,
            max_log_lines=5000,
            baudrate=9600,
            newline="CRLF",
            local_echo_enabled=True,
            scan_interval_ms=2000,
            command_prefix="AT+",
            command_suffix="\r\n",
            log_dir="C:/logs",
            parser_type=2,
            delimiters=[";"],
            packet_length=128,
            at_color_ok=False,
            at_color_error=False,
            at_color_urc=False,
            at_color_prompt=False,
            packet_buffer_size=200,
            packet_realtime=False,
            packet_autoscroll=False,
        )
        PreferencesCoordinator.apply_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.LANGUAGE) == "ko"
        assert mock_settings_manager.get(ConfigKeys.PROP_FONT_SIZE) == 12
        assert mock_settings_manager.get(ConfigKeys.RX_MAX_LINES) == 5000
        assert mock_settings_manager.get(ConfigKeys.PORT_BAUDRATE) == 9600
        assert mock_settings_manager.get(ConfigKeys.PORT_NEWLINE) == "CRLF"
        assert mock_settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO) is True
        assert mock_settings_manager.get(ConfigKeys.PORT_SCAN_INTERVAL) == 2000
        assert mock_settings_manager.get(ConfigKeys.COMMAND_PREFIX) == "AT+"
        assert mock_settings_manager.get(ConfigKeys.COMMAND_SUFFIX) == "\r\n"
        assert mock_settings_manager.get(ConfigKeys.LOG_PATH) == "C:/logs"
        assert mock_settings_manager.get(ConfigKeys.PACKET_PARSER_TYPE) == 2
        assert mock_settings_manager.get(ConfigKeys.PACKET_DELIMITERS) == [";"]
        assert mock_settings_manager.get(ConfigKeys.PACKET_LENGTH) == 128
        assert mock_settings_manager.get(ConfigKeys.AT_COLOR_OK) is False
        assert mock_settings_manager.get(ConfigKeys.AT_COLOR_ERROR) is False
        assert mock_settings_manager.get(ConfigKeys.AT_COLOR_URC) is False
        assert mock_settings_manager.get(ConfigKeys.AT_COLOR_PROMPT) is False
        assert mock_settings_manager.get(ConfigKeys.PACKET_BUFFER_SIZE) == 200
        assert mock_settings_manager.get(ConfigKeys.PACKET_REALTIME) is False
        assert mock_settings_manager.get(ConfigKeys.PACKET_AUTOSCROLL) is False


class TestPreferencesCoordinatorRoundtrip:
    """apply_state() 후 build_state()로 되읽으면 원본과 같은 값이 나온다."""

    def test_roundtrip_preserves_values(self, mock_settings_manager):
        original = PreferencesState(
            theme="Light",
            language="ko",
            font_size=14,
            max_log_lines=3000,
            baudrate=57600,
            newline="CR",
            local_echo_enabled=True,
            scan_interval_ms=1500,
            command_prefix="PFX",
            command_suffix="SFX",
            log_dir="D:/data",
            parser_type=1,
            delimiters=["\\n"],
            packet_length=32,
            at_color_ok=False,
            at_color_error=True,
            at_color_urc=False,
            at_color_prompt=True,
            packet_buffer_size=50,
            packet_realtime=False,
            packet_autoscroll=True,
        )

        PreferencesCoordinator.apply_state(mock_settings_manager, original)
        restored = PreferencesCoordinator.build_state(mock_settings_manager)

        assert restored == original
