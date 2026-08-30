"""
애플리케이션 초기 상태 복원 지원 모듈

View 초기 상태, 수동 제어 복원 상태, 상태바 타이머 생성만 담당합니다.
객체 생성/Presenter 배선 순서는 MainPresenter가 소유하며 이 클래스는 MainPresenter의
private 메서드를 역호출하지 않습니다.
"""
from typing import Any, Callable, Dict

from PyQt5.QtCore import QTimer

from common.constants import ConfigKeys, DEFAULT_MACRO_INTERVAL_MS, STATUS_BAR_UPDATE_INTERVAL_MS
from common.defaults import (
    DEFAULT_FIXED_FONT_FAMILY,
    DEFAULT_FIXED_FONT_SIZE,
    DEFAULT_MANUAL_CONTROL_STATE,
    DEFAULT_PROP_FONT_FAMILY,
    DEFAULT_PROP_FONT_SIZE,
    DEFAULT_RIGHT_PANEL_VISIBLE,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from common.dtos import FontConfig, MainWindowState, ManualControlState, SystemLogEvent
from common.enums import LogLevel
from core.logger import logger
from core.settings_manager import SettingsManager
from view.main_window import MainWindow
from view.managers.language_manager import language_manager


class AppLifecycleManager:
    """설정 기반 초기 View/Presenter 상태 복원을 담당합니다."""

    def __init__(self, view: MainWindow, settings_manager: SettingsManager) -> None:
        self.view = view
        self.settings_manager = settings_manager

    def initialize_view(self) -> None:
        """설정 파일을 기준으로 MainWindow 초기 상태를 적용합니다."""
        logger.info("Starting application view initialization...")
        if self.settings_manager.config_was_reset:
            reason = self.settings_manager.reset_reason
            self.view.show_alert_message(
                language_manager.get_text("lifecycle_title_settings_reset"),
                language_manager.get_text("lifecycle_msg_settings_reset").format(reason),
            )

        window_state, font_config = self._create_initial_states(
            self.settings_manager.get_all_settings()
        )
        self.view.apply_state(window_state, font_config)

    def create_manual_control_state(self) -> ManualControlState:
        """저장된 설정에서 ManualControlState DTO를 생성합니다."""
        window_state, _ = self._create_initial_states(
            self.settings_manager.get_all_settings()
        )
        manual_settings = window_state.left_section_state.get("manual_control", {}).get(
            "manual_control_widget", {}
        )
        defaults = DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]

        return ManualControlState(
            input_text=manual_settings.get("input_text", defaults["input_text"]),
            hex_mode=manual_settings.get("hex_mode", defaults["hex_mode"]),
            prefix_enabled=manual_settings.get("prefix_enabled", defaults["prefix_enabled"]),
            suffix_enabled=manual_settings.get("suffix_enabled", defaults["suffix_enabled"]),
            rts_enabled=manual_settings.get("rts_enabled", defaults["rts_enabled"]),
            dtr_enabled=manual_settings.get("dtr_enabled", defaults["dtr_enabled"]),
            local_echo_enabled=manual_settings.get(
                "local_echo_enabled", defaults["local_echo_enabled"]
            ),
            broadcast_enabled=manual_settings.get(
                "broadcast_enabled", defaults["broadcast_enabled"]
            ),
            auto_tx_enabled=manual_settings.get(
                "auto_tx_enabled", defaults["auto_tx_enabled"]
            ),
            auto_tx_interval_ms=manual_settings.get(
                "auto_tx_interval_ms", DEFAULT_MACRO_INTERVAL_MS
            ),
        )

    def create_status_timer(self, callback: Callable[[], None]) -> QTimer:
        """상태바 갱신용 QTimer를 생성하고 시작합니다."""
        timer = QTimer()
        timer.timeout.connect(callback)
        timer.start(STATUS_BAR_UPDATE_INTERVAL_MS)
        return timer

    def log_initialized(self) -> None:
        """초기화 완료 메시지를 View의 시스템 로그에 기록합니다."""
        self.view.log_system_message(
            SystemLogEvent(
                message="Application initialized",
                level=LogLevel.INFO.value,
            )
        )
        logger.debug("Application initialization sequence completed.")

    def _create_initial_states(
        self, settings: Dict[str, Any]
    ) -> tuple[MainWindowState, FontConfig]:
        def get_val(path: str, default: Any = None) -> Any:
            value: Any = settings
            try:
                for key in path.split("."):
                    value = value.get(key, {})
                return value if value != {} else default
            except AttributeError:
                return default

        return (
            MainWindowState(
                width=get_val(ConfigKeys.WINDOW_WIDTH, DEFAULT_WINDOW_WIDTH),
                height=get_val(ConfigKeys.WINDOW_HEIGHT, DEFAULT_WINDOW_HEIGHT),
                x=get_val(ConfigKeys.WINDOW_X),
                y=get_val(ConfigKeys.WINDOW_Y),
                splitter_state=get_val(ConfigKeys.SPLITTER_STATE),
                right_panel_visible=get_val(
                    ConfigKeys.RIGHT_PANEL_VISIBLE, DEFAULT_RIGHT_PANEL_VISIBLE
                ),
                right_section_width=get_val(ConfigKeys.SAVED_RIGHT_WIDTH),
                left_section_state={
                    "manual_control": get_val(ConfigKeys.MANUAL_CONTROL_STATE, {}),
                    "ports": get_val(ConfigKeys.PORTS_TABS_STATE, []),
                },
                right_section_state={
                    "macro_panel": {
                        "commands": get_val(ConfigKeys.MACRO_COMMANDS, []),
                        "control_state": get_val(ConfigKeys.MACRO_CONTROL_STATE, {}),
                    }
                },
            ),
            FontConfig(
                prop_family=get_val(
                    ConfigKeys.PROP_FONT_FAMILY, DEFAULT_PROP_FONT_FAMILY
                ),
                prop_size=get_val(ConfigKeys.PROP_FONT_SIZE, DEFAULT_PROP_FONT_SIZE),
                fixed_family=get_val(
                    ConfigKeys.FIXED_FONT_FAMILY, DEFAULT_FIXED_FONT_FAMILY
                ),
                fixed_size=get_val(ConfigKeys.FIXED_FONT_SIZE, DEFAULT_FIXED_FONT_SIZE),
            ),
        )
