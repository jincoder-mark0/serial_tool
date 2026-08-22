"""
환경설정(Preferences) DTO 조립/적용 통합 모듈

## WHY
* `PreferencesState`(60여 필드 중 이 DTO에 해당하는 부분)의
  DTO 속성 <-> `SettingsManager` 키 매핑이 종전에는 MainPresenter의
  `on_preferences_requested()`(읽기)와 `on_settings_change_requested()`(쓰기)
  두 곳에 각각 나열되어 있었다. 스키마(필드 추가/삭제)가 바뀌면 두 곳을 모두
  고쳐야 했고, 한쪽만 놓치면 조용히 어긋난 채로 남는다(S-058, 감사② C-7).
* 하나의 선언적 테이블로 통합해 스키마 변경 시 한 곳만 고치면 되게 한다.

## WHAT
* `PreferencesCoordinator.build_state(settings)` — 저장된 설정으로부터
  `PreferencesState` DTO를 조립한다(기존 `on_preferences_requested()` 로직).
* `PreferencesCoordinator.apply_state(settings, state)` — DTO 값을
  `SettingsManager`에 반영한다(기존 `on_settings_change_requested()`의
  `settings.set(...)` 나열 부분). `save_settings()` 호출과 UI 즉시 반영
  (테마 전환, 언어 전환, EventBus 발행 등)은 View/EventBus에 관여하므로
  호출부인 MainPresenter의 책임으로 남긴다.

## HOW
* (DTO 속성명, ConfigKeys 키, 기본값, 읽기 변환 함수, 쓰기 변환 함수)로 구성된
  단일 테이블을 읽기/쓰기 양방향에서 재사용한다. `theme`만 대소문자 변환이
  read(capitalize)/write(lower) 비대칭이라 개별 변환 함수를 가진다(기존 동작
  그대로 보존 — 저장 키 문자열과 raw 값 형식은 절대 변경하지 않는다).
"""
from typing import Any, Callable, List, NamedTuple

from common.constants import ConfigKeys
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
    PreferencesState DTO의 조립(읽기)과 적용(쓰기)을 한 곳에서 담당하는 클래스.

    Qt/View에 의존하지 않으므로 인스턴스 생성 없이 클래스 메서드로만 사용한다.
    """

    # 기존 on_preferences_requested()/on_settings_change_requested()와
    # 완전히 동일한 키·기본값·변환 규칙을 한 테이블로 통합한 것이다.
    _FIELDS: List[_FieldSpec] = [
        _FieldSpec(
            "theme", ConfigKeys.THEME, "Dark",
            to_state=lambda v: v.capitalize(), to_settings=lambda v: v.lower()
        ),
        _FieldSpec("language", ConfigKeys.LANGUAGE, "en"),
        _FieldSpec("font_size", ConfigKeys.PROP_FONT_SIZE, 10),
        _FieldSpec("max_log_lines", ConfigKeys.RX_MAX_LINES, 2000),
        _FieldSpec("baudrate", ConfigKeys.PORT_BAUDRATE, 115200),
        _FieldSpec("newline", ConfigKeys.PORT_NEWLINE, "\n", to_state=str),
        _FieldSpec("local_echo_enabled", ConfigKeys.PORT_LOCAL_ECHO, False),
        _FieldSpec("scan_interval_ms", ConfigKeys.PORT_SCAN_INTERVAL, 1000),
        _FieldSpec("command_prefix", ConfigKeys.COMMAND_PREFIX, ""),
        _FieldSpec("command_suffix", ConfigKeys.COMMAND_SUFFIX, ""),
        _FieldSpec("log_dir", ConfigKeys.LOG_PATH, ""),
        _FieldSpec("parser_type", ConfigKeys.PACKET_PARSER_TYPE, 0),
        _FieldSpec("delimiters", ConfigKeys.PACKET_DELIMITERS, ["\\r\\n"]),
        _FieldSpec("packet_length", ConfigKeys.PACKET_LENGTH, 64),
        _FieldSpec("at_color_ok", ConfigKeys.AT_COLOR_OK, True),
        _FieldSpec("at_color_error", ConfigKeys.AT_COLOR_ERROR, True),
        _FieldSpec("at_color_urc", ConfigKeys.AT_COLOR_URC, True),
        _FieldSpec("at_color_prompt", ConfigKeys.AT_COLOR_PROMPT, True),
        _FieldSpec("packet_buffer_size", ConfigKeys.PACKET_BUFFER_SIZE, 100),
        _FieldSpec("packet_realtime", ConfigKeys.PACKET_REALTIME, True),
        _FieldSpec("packet_autoscroll", ConfigKeys.PACKET_AUTOSCROLL, True),
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

        `save_settings()` 호출은 호출부 책임이다(다른 필드 저장과 한 번에
        원자적으로 저장하기 위함 — 기존 동작과 동일).

        Args:
            settings (SettingsManager): 값을 반영할 매니저.
            state (PreferencesState): 반영할 환경설정 상태 DTO.
        """
        for spec in cls._FIELDS:
            value = getattr(state, spec.attr)
            settings.set(spec.key, spec.to_settings(value))
