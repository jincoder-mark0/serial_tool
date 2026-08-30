"""
애플리케이션 생명주기 관리자 모듈

MainPresenter의 초기화 순서를 분리하고 설정/상태 복원을 담당합니다.
"""
from typing import Any, Dict, TYPE_CHECKING

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
from view.managers.language_manager import language_manager

if TYPE_CHECKING:
    from presenter.main_presenter import MainPresenter


class AppLifecycleManager:
    """애플리케이션 초기화 및 View 상태 복원을 관리합니다."""

    def __init__(self, main_presenter: "MainPresenter") -> None:
        self.mp = main_presenter
        self.view = main_presenter.view
        self.settings_manager = SettingsManager()

    def initialize_app(self) -> None:
        logger.info("Starting application initialization sequence...")
        self._init_settings_and_view()
        self.mp._init_core_systems()
        self.mp._init_sub_presenters()
        self._restore_sub_presenter_states()
        self.mp.connection_controller.data_received.connect(
            self.mp.data_handler.on_fast_data_received
        )
        self.mp._connect_signals()
        self._start_services()
        logger.debug("Application initialization sequence completed.")

    def _init_settings_and_view(self) -> None:
        if self.settings_manager.config_was_reset:
            reason = self.settings_manager.reset_reason
            self.view.show_alert_message(
                language_manager.get_text("lifecycle_title_settings_reset"),
                language_manager.get_text("lifecycle_msg_settings_reset").format(reason),
            )
        self._initialize_view_from_settings()

    def _initialize_view_from_settings(self) -> None:
        window_state, font_config = self._create_initial_states(
            self.settings_manager.get_all_settings()
        )
        self.view.apply_state(window_state, font_config)

    def _restore_sub_presenter_states(self) -> None:
        window_state, _ = self._create_initial_states(self.settings_manager.get_all_settings())
        manual_settings = window_state.left_section_state.get("manual_control", {}).get(
            "manual_control_widget", {}
        )
        defaults = DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]
        manual_state_dto = ManualControlState(
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
            auto_tx_enabled=manual_settings.get("auto_tx_enabled", defaults["auto_tx_enabled"]),
            auto_tx_interval_ms=manual_settings.get(
                "auto_tx_interval_ms", DEFAULT_MACRO_INTERVAL_MS
            ),
        )
        self.mp.manual_control_presenter.apply_state(manual_state_dto)

    def _start_services(self) -> None:
        self.mp.status_timer = QTimer()
        self.mp.status_timer.timeout.connect(self.mp.update_status_bar)
        self.mp.status_timer.start(STATUS_BAR_UPDATE_INTERVAL_MS)
        self.view.log_system_message(
            SystemLogEvent(
                message="Application initialized",
                level=LogLevel.INFO.value,
            )
        )

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

        window_state = MainWindowState(
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
        )
        font_config = FontConfig(
            prop_family=get_val(ConfigKeys.PROP_FONT_FAMILY, DEFAULT_PROP_FONT_FAMILY),
            prop_size=get_val(ConfigKeys.PROP_FONT_SIZE, DEFAULT_PROP_FONT_SIZE),
            fixed_family=get_val(ConfigKeys.FIXED_FONT_FAMILY, DEFAULT_FIXED_FONT_FAMILY),
            fixed_size=get_val(ConfigKeys.FIXED_FONT_SIZE, DEFAULT_FIXED_FONT_SIZE),
        )
        return window_state, font_config
