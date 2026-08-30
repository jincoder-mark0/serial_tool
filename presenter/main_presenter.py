"""
애플리케이션 최상위 Presenter.

조립된 runtime component를 받아 전역 이벤트와 UI 상태를 중재합니다. 구체 객체 생성과
View 초기 상태 복원 순서는 application_bootstrap.py가 소유하고, MainPresenter는 완성된
runtime graph의 public signal을 연결하고 사용자 표시 상태를 조정합니다.
"""
from typing import Optional

from PyQt5.QtCore import QDateTime, QObject, QTimer

from application_bootstrap import ApplicationBootstrapper, ApplicationComponents
from common.constants import ConfigKeys
from common.dtos import (
    FileCompletionEvent,
    FileErrorEvent,
    FontConfig,
    MacroErrorEvent,
    PortConnectionEvent,
    PortDataEvent,
    PortErrorEvent,
    PreferencesState,
    SystemLogEvent,
)
from common.enums import LogLevel
from core.logger import logger
from core.settings_manager import SettingsManager
from view.main_window import MainWindow
from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel

from .preferences_coordinator import PreferencesCoordinator
from .shutdown_coordinator import ShutdownCoordinator


class MainPresenter(QObject):
    """애플리케이션 전역 표시 상태와 상위 이벤트를 조정합니다."""

    def __init__(
        self,
        view: MainWindow,
        settings_manager: Optional[SettingsManager] = None,
        components: Optional[ApplicationComponents] = None,
    ) -> None:
        super().__init__()
        self.view = view
        self.settings_manager = settings_manager or SettingsManager()
        self.status_timer: Optional[QTimer] = None

        runtime = components or ApplicationBootstrapper(
            self.view,
            self.settings_manager,
        ).build()
        self._apply_components(runtime)

        self.manual_control_presenter.apply_state(
            self.lifecycle_manager.create_manual_control_state()
        )
        self.connection_controller.data_received.connect(
            self.data_handler.on_fast_data_received
        )

        self.logging_coordinator.info_requested.connect(self._log_info)
        self.logging_coordinator.error_requested.connect(self._log_error)
        self.logging_coordinator.connect_signals()

        self.status_timer = self.lifecycle_manager.create_status_timer(
            self.update_status_bar
        )
        self.shutdown_coordinator = ShutdownCoordinator(
            view=self.view,
            settings_manager=self.settings_manager,
            connection_controller=self.connection_controller,
            file_transfer_manager=self.file_transfer_manager,
            macro_runner=self.macro_runner,
            macro_script_manager=self.macro_script_manager,
            port_scan_manager=self.port_scan_manager,
            manual_control_presenter=self.manual_control_presenter,
            packet_presenter=self.packet_presenter,
            data_handler=self.data_handler,
            close_system_log=self.logging_coordinator.close_system_log,
            status_timer=self.status_timer,
        )

        self._connect_signals()
        self.view.connect_port_tab_changed(self._on_port_tab_changed)
        self.lifecycle_manager.log_initialized()

    def _apply_components(self, components: ApplicationComponents) -> None:
        """Bootstrapper가 생성한 runtime component를 Presenter 필드에 배치합니다."""
        self.lifecycle_manager = components.lifecycle_manager
        self.connection_controller = components.connection_controller
        self.file_transfer_manager = components.file_transfer_manager
        self.port_scan_manager = components.port_scan_manager
        self.macro_runner = components.macro_runner
        self.macro_script_manager = components.macro_script_manager
        self.macro_execution_coordinator = components.macro_execution_coordinator
        self.traffic_monitor = components.traffic_monitor
        self.data_handler = components.data_handler
        self.logging_coordinator = components.logging_coordinator
        self.port_presenter = components.port_presenter
        self.macro_presenter = components.macro_presenter
        self.file_presenter = components.file_presenter
        self.packet_presenter = components.packet_presenter
        self.manual_control_presenter = components.manual_control_presenter

    @property
    def _sys_log_writer(self):
        """S-055 기존 테스트/외부 코드 호환용 읽기 전용 alias."""
        return self.logging_coordinator.system_log_writer

    def _connect_signals(self) -> None:
        self.connection_controller.connection_opened.connect(self.on_port_opened)
        self.connection_controller.connection_closed.connect(self.on_port_closed)
        self.connection_controller.error_occurred.connect(self.on_port_error)
        self.connection_controller.data_sent.connect(self._on_data_sent)
        self.connection_controller.data_received.connect(self.macro_runner.on_data_received)

        self.macro_runner.macro_started.connect(self.on_macro_started)
        self.macro_runner.macro_finished.connect(self.on_macro_finished)
        self.macro_runner.error_occurred.connect(self.on_macro_error)
        self.macro_execution_coordinator.local_echo_requested.connect(
            self.show_local_echo
        )
        self.macro_execution_coordinator.execution_interrupted.connect(
            self._notify_macro_error
        )

        self.file_presenter.transfer_completed.connect(self.on_file_transfer_completed)
        self.file_presenter.transfer_error.connect(self.on_file_transfer_error)

        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.theme_change_requested.connect(self.on_theme_change_requested)
        self.view.language_change_requested.connect(self.on_language_change_requested)
        self.view.close_requested.connect(self.on_close_requested)
        self.view.preferences_requested.connect(self.on_preferences_requested)
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)
        self.view.file_transfer_dialog_opened.connect(
            self.file_presenter.on_file_transfer_dialog_opened
        )

        self.manual_control_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )
        self.manual_control_presenter.send_error.connect(self._on_manual_send_error)
        self.macro_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )

    def _log_info(self, message: str) -> None:
        self.view.log_system_message(
            SystemLogEvent(message=message, level=LogLevel.INFO.value)
        )

    def _log_error(self, message: str) -> None:
        self.view.log_system_message(
            SystemLogEvent(message=message, level=LogLevel.ERROR.value)
        )

    def _log_success(self, message: str) -> None:
        self.view.log_system_message(
            SystemLogEvent(message=message, level=LogLevel.SUCCESS.value)
        )

    def on_preferences_requested(self) -> None:
        self.view.open_preferences_dialog(
            PreferencesCoordinator.build_state(self.settings_manager)
        )

    def on_close_requested(self) -> None:
        self.shutdown_coordinator.shutdown()

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        PreferencesCoordinator.apply_state(self.settings_manager, new_state)
        self.settings_manager.save_settings()

        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)
        self.port_presenter.apply_max_log_lines(new_state.max_log_lines)
        self.manual_control_presenter.update_local_echo_setting(
            new_state.local_echo_enabled
        )
        self.packet_presenter.on_settings_changed(new_state)

        settings_updated_msg = language_manager.get_text(
            "main_status_msg_settings_updated"
        )
        self.view.show_status_message(settings_updated_msg, 2000)
        self._log_info(settings_updated_msg)

    def on_theme_change_requested(self, theme_name: str) -> None:
        normalized = theme_name.lower()
        self.settings_manager.set(ConfigKeys.THEME, normalized)
        self.settings_manager.save_settings()
        self.view.switch_theme(normalized)

    def on_language_change_requested(self, language_code: str) -> None:
        self.settings_manager.set(ConfigKeys.LANGUAGE, language_code)
        self.settings_manager.save_settings()
        language_manager.set_language(language_code)

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        settings = self.settings_manager
        settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        settings.save_settings()
        logger.info("Font settings saved successfully.")

    def _on_data_sent(self, event: PortDataEvent) -> None:
        self.data_handler.on_data_sent(event)

    def on_port_opened(self, event: PortConnectionEvent) -> None:
        self.view.update_status_bar_port(event.port, True)
        self.view.show_status_message(f"Connected to {event.port}", 3000)
        self._update_controls_state_for_current_tab()

    def on_port_closed(self, event: PortConnectionEvent) -> None:
        self.view.update_status_bar_port(event.port, False)
        self.view.show_status_message(f"Disconnected from {event.port}", 3000)
        self._update_controls_state_for_current_tab()

    def on_port_error(self, event: PortErrorEvent) -> None:
        self.view.show_status_message(
            f"Error ({event.port}): {event.message}",
            5000,
        )

    def _on_port_tab_changed(self, _index: int) -> None:
        self._update_controls_state_for_current_tab()

    def _update_controls_state_for_current_tab(self) -> None:
        is_current_connected = self.view.is_current_port_connected()
        has_any_connection = self.connection_controller.has_active_connection

        if self.manual_control_presenter:
            is_broadcast = self.manual_control_presenter.is_broadcast_enabled()
            self.manual_control_presenter.set_enabled(
                is_current_connected or (is_broadcast and has_any_connection)
            )

        if self.macro_presenter:
            is_broadcast = self.macro_presenter.is_broadcast_enabled()
            self.macro_presenter.set_enabled(
                is_current_connected or (is_broadcast and has_any_connection)
            )

    def on_macro_started(self) -> None:
        self._log_info("Macro started")
        self.view.show_status_message(
            language_manager.get_text("main_status_msg_macro_running"),
            0,
        )

    def on_macro_finished(self) -> None:
        self._log_success("Macro finished")
        self.view.show_status_message(
            language_manager.get_text("main_status_msg_macro_finished"),
            3000,
        )

    def on_macro_error(self, event: MacroErrorEvent) -> None:
        row_info = f"(Row {event.row_index})" if event.row_index >= 0 else ""
        msg = f"Macro Error {row_info}: {event.message}"
        self._log_error(msg)
        self.view.show_status_message(msg, 5000)

    def show_local_echo(self, data: bytes) -> None:
        if not data:
            return
        if self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False):
            self.view.append_local_echo_data(data)

    def _notify_macro_error(self, message: str) -> None:
        logger.error(f"Macro stopped: {message}")
        self.view.show_status_message(
            language_manager.get_text("main_status_msg_macro_stopped").format(message),
            5000,
        )
        self.view.show_alert_message(
            language_manager.get_text("main_title_macro_error"),
            message,
        )

    def _on_manual_send_error(
        self,
        title: str,
        message: str,
        show_dialog: bool,
    ) -> None:
        self._log_error(f"Manual send failed: {message}")
        self.view.show_status_message(message, 5000)
        if show_dialog:
            self.view.show_alert_message(title, message)

    def on_file_transfer_completed(self, event: FileCompletionEvent) -> None:
        status_key = (
            "file_prog_lbl_status_completed"
            if event.success
            else "file_prog_lbl_status_failed"
        )
        status_text = language_manager.get_text(status_key)
        msg = language_manager.get_text("main_msg_file_transfer_result").format(
            status_text,
            event.message,
        )
        if event.success:
            self._log_success(msg)
        else:
            self._log_error(msg)

        self.view.show_status_message(
            language_manager.get_text(
                "main_status_msg_file_transfer_result"
            ).format(status_text),
            3000,
        )

    def on_file_transfer_error(self, event: FileErrorEvent) -> None:
        self._log_error(f"File Transfer Error: {event.message}")

    def update_status_bar(self) -> None:
        self.view.update_status_bar_stats(self.traffic_monitor.take_statistics())
        self.view.update_status_bar_time(
            QDateTime.currentDateTime().toString("HH:mm:ss")
        )

    def on_shortcut_connect(self) -> None:
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        self.port_presenter.clear_log_current_port()

    # ------------------------------------------------------------------
    # Compatibility delegates — 구현 책임은 LoggingCoordinator가 소유합니다.
    # ------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        self.logging_coordinator.connect_signals()

    def _connect_single_port_logging(self, panel: PortPanel) -> None:
        self.logging_coordinator.connect_port_panel(panel)

    def _on_logging_start_requested(self, panel: PortPanel) -> None:
        self.logging_coordinator.on_port_logging_start_requested(panel)

    def _on_logging_stop_requested(self, panel: PortPanel) -> None:
        self.logging_coordinator.on_port_logging_stop_requested(panel)

    def _on_sys_logging_start_requested(self) -> None:
        self.logging_coordinator.on_system_logging_start_requested()

    def _on_sys_logging_stop_requested(self) -> None:
        self.logging_coordinator.on_system_logging_stop_requested()

    def _close_sys_log_writer(self) -> None:
        self.logging_coordinator.close_system_log()

    def _on_system_log_line_appended(self, text: str) -> None:
        self.logging_coordinator.on_system_log_line_appended(text)
