"""
종료 시 View/Presenter 상태를 SettingsManager 경로로 변환하는 adapter.

View state의 key(`ports`, `macro_panel.commands`)와 SettingsManager의 dotted path
(`ports.tabs`, `macro_list.commands`)는 서로 다른 표현입니다. 이 클래스가 두 표현 사이의
경계를 명시적으로 변환합니다.
"""
from common.constants import ConfigKeys
from common.dtos import MainWindowState, ManualControlState
from core.settings_manager import SettingsManager


class ShutdownStateCollector:
    """종료 상태 DTO/View dict를 영속 설정 경로로 변환합니다."""

    _VIEW_MANUAL_KEY = "manual_control"
    _VIEW_PORTS_KEY = "ports"
    _VIEW_MACRO_PANEL_KEY = "macro_panel"
    _VIEW_MACRO_COMMANDS_KEY = "commands"
    _VIEW_MACRO_CONTROL_KEY = "control_state"

    @staticmethod
    def merge_manual_control_state(
        window_state: MainWindowState,
        manual_state: ManualControlState,
    ) -> None:
        """ManualControlState DTO를 View state와 동일한 nested shape로 병합합니다."""
        window_state.left_section_state[ShutdownStateCollector._VIEW_MANUAL_KEY] = {
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

    @classmethod
    def apply_window_state(
        cls,
        settings: SettingsManager,
        state: MainWindowState,
    ) -> None:
        """MainWindowState의 View 표현을 SettingsManager path 표현으로 저장합니다."""
        settings.set(ConfigKeys.WINDOW_WIDTH, state.width)
        settings.set(ConfigKeys.WINDOW_HEIGHT, state.height)
        settings.set(ConfigKeys.WINDOW_X, state.x)
        settings.set(ConfigKeys.WINDOW_Y, state.y)
        settings.set(ConfigKeys.SPLITTER_STATE, state.splitter_state)
        settings.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.right_panel_visible)

        if state.right_section_width is not None:
            settings.set(ConfigKeys.SAVED_RIGHT_WIDTH, state.right_section_width)

        left_state = state.left_section_state or {}
        manual_state = left_state.get(cls._VIEW_MANUAL_KEY)
        if manual_state is not None:
            settings.set(ConfigKeys.MANUAL_CONTROL_STATE, manual_state)

        port_states = left_state.get(cls._VIEW_PORTS_KEY)
        if port_states is not None:
            settings.set(ConfigKeys.PORTS_TABS_STATE, port_states)

        right_state = state.right_section_state or {}
        macro_panel_state = right_state.get(cls._VIEW_MACRO_PANEL_KEY)
        if isinstance(macro_panel_state, dict):
            commands = macro_panel_state.get(cls._VIEW_MACRO_COMMANDS_KEY)
            if commands is not None:
                settings.set(ConfigKeys.MACRO_COMMANDS, commands)

            control_state = macro_panel_state.get(cls._VIEW_MACRO_CONTROL_KEY)
            if control_state is not None:
                settings.set(ConfigKeys.MACRO_CONTROL_STATE, control_state)

    @classmethod
    def collect_and_apply(
        cls,
        settings: SettingsManager,
        window_state: MainWindowState,
        manual_state: ManualControlState,
    ) -> None:
        """Manual DTO를 병합한 뒤 전체 상태를 영속 설정 경로에 반영합니다."""
        cls.merge_manual_control_state(window_state, manual_state)
        cls.apply_window_state(settings, window_state)
