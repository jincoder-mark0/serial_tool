"""
환경설정(Preferences) DTO 조립/적용 통합 모듈

## WHY
* `PreferencesState`의 DTO 속성 <-> `SettingsManager` 키 매핑이 종전에는
  MainPresenter의 읽기/쓰기 경로에 중복되어 있었습니다.
* 기본값까지 이 모듈에서 리터럴로 다시 정의하면 `common.defaults`와 값이
  어긋날 수 있으므로, 설정 기본값은 공통 정본을 참조합니다.

## WHAT
* `PreferencesCoordinator.build_state(settings)` — 저장된 설정으로부터
  `PreferencesState` DTO를 조립합니다.
* `PreferencesCoordinator.apply_state(settings, state)` — DTO 값을
  `SettingsManager`에 반영합니다.
* S-072 프레이밍 설정(length field/gap)도 동일 매핑 테이블에 포함합니다.

## HOW
* (DTO 속성명, ConfigKeys 키, 기본값, 읽기 변환 함수, 쓰기 변환 함수)로 구성된
  단일 테이블을 읽기/쓰기 양방향에서 재사용합니다.
"""
from typing import Any, Callable, List, NamedTuple

from common.constants import ConfigKeys, DEFAULT_BAUDRATE, DEFAULT_LOG_MAX_LINES
from common.defaults import (
    DEFAULT_COMMAND_PREFIX,
    DEFAULT_COMMAND_SUFFIX,
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
    DEFAULT_PORT_LOCAL_ECHO,
    DEFAULT_PORT_NEWLINE,
    DEFAULT_PORT_SCAN_INTERVAL_MS,
    DEFAULT_PROP_FONT_SIZE,
    DEFAULT_THEME,
)
from common.dtos import PreferencesState
from core.settings_manager import SettingsManager


def _identity(value: Any) -> Any:
    """변환이 필요 없는 필드의 기본 변환 함수."""
    return value


class _FieldSpec(NamedTuple):
    """PreferencesState의 필드 하나와 SettingsManager 키 사이의 매핑 규칙."""
    attr: str
    key: str
    default: Any
    to_state: Callable[[Any], Any] = _identity
    to_settings: Callable[[Any], Any] = _identity


class PreferencesCoordinator:
    """
    PreferencesState DTO의 조립(읽기)과 적용(쓰기)을 한 곳에서 담당합니다.

    Qt/View에 의존하지 않으므로 인스턴스 생성 없이 클래스 메서드로만 사용합니다.
    """

    _FIELDS: List[_FieldSpec] = [
        # Theme 값은 DTO/설정 모두 ThemeType.value 형식(lowercase)을 사용한다.
        # View가 표시할 때만 필요한 대소문자 변환을 수행해야 하며, 상태 계층에서
        # `dark` -> `Dark`로 바꾸면 PreferencesState() 직접 생성과 표현이 갈라진다.
        _FieldSpec("theme", ConfigKeys.THEME, DEFAULT_THEME),
        _FieldSpec("language", ConfigKeys.LANGUAGE, DEFAULT_LANGUAGE),
        _FieldSpec("font_size", ConfigKeys.PROP_FONT_SIZE, DEFAULT_PROP_FONT_SIZE),
        _FieldSpec("max_log_lines", ConfigKeys.RX_MAX_LINES, DEFAULT_LOG_MAX_LINES),
        _FieldSpec("baudrate", ConfigKeys.PORT_BAUDRATE, DEFAULT_BAUDRATE),
        _FieldSpec("newline", ConfigKeys.PORT_NEWLINE, DEFAULT_PORT_NEWLINE, to_state=str),
        _FieldSpec("local_echo_enabled", ConfigKeys.PORT_LOCAL_ECHO, DEFAULT_PORT_LOCAL_ECHO),
        _FieldSpec("scan_interval_ms", ConfigKeys.PORT_SCAN_INTERVAL, DEFAULT_PORT_SCAN_INTERVAL_MS),
        _FieldSpec("command_prefix", ConfigKeys.COMMAND_PREFIX, DEFAULT_COMMAND_PREFIX),
        _FieldSpec("command_suffix", ConfigKeys.COMMAND_SUFFIX, DEFAULT_COMMAND_SUFFIX),
        _FieldSpec("log_dir", ConfigKeys.LOG_PATH, DEFAULT_LOG_PATH),
        _FieldSpec("parser_type", ConfigKeys.PACKET_PARSER_TYPE, DEFAULT_PACKET_PARSER_TYPE),
        _FieldSpec("delimiters", ConfigKeys.PACKET_DELIMITERS, list(DEFAULT_PACKET_DELIMITERS)),
        _FieldSpec("packet_length", ConfigKeys.PACKET_LENGTH, DEFAULT_PACKET_LENGTH),
        _FieldSpec(
            "length_field_offset",
            ConfigKeys.PACKET_LENGTH_FIELD_OFFSET,
            DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
        ),
        _FieldSpec(
            "length_field_size",
            ConfigKeys.PACKET_LENGTH_FIELD_SIZE,
            DEFAULT_PACKET_LENGTH_FIELD_SIZE,
        ),
        _FieldSpec(
            "length_field_endian",
            ConfigKeys.PACKET_LENGTH_FIELD_ENDIAN,
            DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
        ),
        _FieldSpec(
            "length_includes_header",
            ConfigKeys.PACKET_LENGTH_INCLUDES_HEADER,
            DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
        ),
        _FieldSpec("gap_ms", ConfigKeys.PACKET_GAP_MS, DEFAULT_PACKET_GAP_MS),
        _FieldSpec("at_color_ok", ConfigKeys.AT_COLOR_OK, DEFAULT_PACKET_AT_COLOR_OK),
        _FieldSpec("at_color_error", ConfigKeys.AT_COLOR_ERROR, DEFAULT_PACKET_AT_COLOR_ERROR),
        _FieldSpec("at_color_urc", ConfigKeys.AT_COLOR_URC, DEFAULT_PACKET_AT_COLOR_URC),
        _FieldSpec("at_color_prompt", ConfigKeys.AT_COLOR_PROMPT, DEFAULT_PACKET_AT_COLOR_PROMPT),
        _FieldSpec("packet_buffer_size", ConfigKeys.PACKET_BUFFER_SIZE, DEFAULT_PACKET_BUFFER_SIZE),
        _FieldSpec("packet_realtime", ConfigKeys.PACKET_REALTIME, DEFAULT_PACKET_REALTIME),
        _FieldSpec("packet_autoscroll", ConfigKeys.PACKET_AUTOSCROLL, DEFAULT_PACKET_AUTOSCROLL),
    ]

    @classmethod
    def build_state(cls, settings: SettingsManager) -> PreferencesState:
        """
        저장된 설정으로부터 PreferencesState DTO를 조립합니다.

        Args:
            settings (SettingsManager): 설정 조회에 사용할 매니저.

        Returns:
            PreferencesState: 조립된 환경설정 상태 DTO.
        """
        kwargs = {}
        for spec in cls._FIELDS:
            raw_value = settings.get(spec.key, spec.default)
            kwargs[spec.attr] = spec.to_state(raw_value)
        return PreferencesState(**kwargs)

    @classmethod
    def apply_state(cls, settings: SettingsManager, state: PreferencesState) -> None:
        """
        PreferencesState DTO 값을 SettingsManager에 반영합니다.

        `save_settings()` 호출은 호출부 책임입니다. 다른 필드 저장과 한 번에
        원자적으로 저장하기 위해 여기서는 메모리 상태만 갱신합니다.

        Args:
            settings (SettingsManager): 값을 반영할 매니저.
            state (PreferencesState): 반영할 환경설정 상태 DTO.
        """
        for spec in cls._FIELDS:
            value = getattr(state, spec.attr)
            settings.set(spec.key, spec.to_settings(value))
