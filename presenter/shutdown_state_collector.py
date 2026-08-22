"""
종료 시 상태 수집/저장 모듈

애플리케이션 종료(`MainPresenter.on_close_requested()`) 시 View/하위 Presenter로부터
모은 상태 DTO를 SettingsManager에 반영하는 로직을 담당합니다 (S-058 — MainPresenter
God object 분해 3번 후보).

## WHY
* 기존에는 이 DTO->dict 수동 변환·병합·SettingsManager 반영 로직이
  `on_close_requested()` 안에 그대로 인라인되어 있어, 종료 경로 전체(연결 종료,
  로거 정리 등)와 뒤섞여 있었다. 필드가 늘어날수록 실수가 나기 쉬운 지점이다.
* Qt/View에 의존하지 않는 순수 변환 로직이므로 분리해 가독성과 테스트 용이성을
  높인다.

## WHAT
* `ShutdownStateCollector.merge_manual_control_state()` — ManualControlState DTO를
  MainWindowState.left_section_state 하위 dict로 병합한다(제자리 수정).
* `ShutdownStateCollector.apply_window_state()` — MainWindowState를
  SettingsManager 키에 반영한다.
* `ShutdownStateCollector.collect_and_apply()` — 위 두 단계를 순서대로 수행하는
  편의 메서드.

## HOW
* 기존 `on_close_requested()`의 DTO->dict 변환·`settings.set(...)` 나열을 그대로
  옮긴 것으로, 키 문자열·조건문·순서를 전혀 바꾸지 않는다(설정 저장 키 불변 조건).
"""
from common.constants import ConfigKeys
from common.dtos import MainWindowState, ManualControlState
from core.settings_manager import SettingsManager


class ShutdownStateCollector:
    """
    종료 시 View/하위 Presenter 상태를 SettingsManager에 반영하는 순수 로직 클래스.

    Model/View/Qt에 의존하지 않으므로 인스턴스 생성 없이 클래스 메서드로만
    사용한다.
    """

    @staticmethod
    def merge_manual_control_state(
        window_state: MainWindowState, manual_state: ManualControlState
    ) -> None:
        """
        ManualControlState DTO를 MainWindowState.left_section_state에 병합합니다.

        Args:
            window_state (MainWindowState): 병합 대상 (제자리에서 수정됨).
            manual_state (ManualControlState): ManualControlPresenter로부터 얻은
                수동 제어 위젯 상태 DTO.
        """
        window_state.left_section_state["manual_control"] = {
            "manual_control_widget": {
                "input_text": manual_state.input_text,
                "hex_mode": manual_state.hex_mode,
                "prefix_enabled": manual_state.prefix_enabled,
                "suffix_enabled": manual_state.suffix_enabled,
                "rts_enabled": manual_state.rts_enabled,
                "dtr_enabled": manual_state.dtr_enabled,
                "local_echo_enabled": manual_state.local_echo_enabled,
                "broadcast_enabled": manual_state.broadcast_enabled,
                "auto_tx_enabled": manual_state.auto_tx_enabled,
                "auto_tx_interval_ms": manual_state.auto_tx_interval_ms,
            }
        }

    @staticmethod
    def apply_window_state(settings: SettingsManager, state: MainWindowState) -> None:
        """
        MainWindowState를 SettingsManager 키에 반영합니다.

        `save_settings()` 호출은 호출부 책임이다(연결 종료 등 나머지 종료
        시퀀스와 함께 한 번에 저장하기 위함 — 기존 동작과 동일).

        Args:
            settings (SettingsManager): 값을 반영할 매니저.
            state (MainWindowState): 반영할 윈도우 상태 DTO
                (`merge_manual_control_state()` 적용 이후여야 함).
        """
        settings.set(ConfigKeys.WINDOW_WIDTH, state.width)
        settings.set(ConfigKeys.WINDOW_HEIGHT, state.height)
        settings.set(ConfigKeys.WINDOW_X, state.x)
        settings.set(ConfigKeys.WINDOW_Y, state.y)
        settings.set(ConfigKeys.SPLITTER_STATE, state.splitter_state)
        settings.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.right_panel_visible)

        if state.right_section_width is not None:
            settings.set(ConfigKeys.SAVED_RIGHT_WIDTH, state.right_section_width)

        # 하위 위젯 상태 저장
        if ConfigKeys.MANUAL_CONTROL_STATE in state.left_section_state:
            settings.set(
                ConfigKeys.MANUAL_CONTROL_STATE,
                state.left_section_state[ConfigKeys.MANUAL_CONTROL_STATE],
            )
        if ConfigKeys.PORTS_TABS_STATE in state.left_section_state:
            settings.set(
                ConfigKeys.PORTS_TABS_STATE,
                state.left_section_state[ConfigKeys.PORTS_TABS_STATE],
            )
        if ConfigKeys.MACRO_COMMANDS in state.right_section_state:
            settings.set(
                ConfigKeys.MACRO_COMMANDS,
                state.right_section_state[ConfigKeys.MACRO_COMMANDS],
            )
        if ConfigKeys.MACRO_CONTROL_STATE in state.right_section_state:
            settings.set(
                ConfigKeys.MACRO_CONTROL_STATE,
                state.right_section_state[ConfigKeys.MACRO_CONTROL_STATE],
            )

    @classmethod
    def collect_and_apply(
        cls,
        settings: SettingsManager,
        window_state: MainWindowState,
        manual_state: ManualControlState,
    ) -> None:
        """
        ManualControlState 병합 후 MainWindowState를 SettingsManager에 반영합니다.

        Args:
            settings (SettingsManager): 값을 반영할 매니저.
            window_state (MainWindowState): View로부터 얻은 윈도우 상태 DTO
                (제자리에서 수정됨).
            manual_state (ManualControlState): ManualControlPresenter로부터 얻은
                수동 제어 위젯 상태 DTO.
        """
        cls.merge_manual_control_state(window_state, manual_state)
        cls.apply_window_state(settings, window_state)
