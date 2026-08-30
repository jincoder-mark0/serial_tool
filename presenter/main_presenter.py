"""
애플리케이션 최상위 Presenter

하위 Presenter를 조율하고 전역 UI 상태/생명주기 이벤트를 연결합니다.
명령 가공과 전송 규칙은 CommandTransmissionService에 위임합니다.
"""
from typing import Optional

from PyQt5.QtCore import QCoreApplication, QDateTime, QObject, QTimer

from common.constants import ConfigKeys, EventTopics
from common.dtos import (
    FileCompletionEvent,
    FileErrorEvent,
    FontConfig,
    MacroErrorEvent,
    MacroSendResult,
    ManualCommand,
    PortConnectionEvent,
    PortDataEvent,
    PortErrorEvent,
    PortStatistics,
    PreferencesState,
    SystemLogEvent,
)
from common.enums import LogLevel
from core.data_logger import data_logger_manager
from core.logger import logger
from core.settings_manager import SettingsManager
from core.text_log_writer import TextLogWriter
from model.command_transmission_service import CommandTransmissionService
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from view.main_window import MainWindow
from view.managers.color_manager import color_manager
from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel

from .data_handler import DataTrafficHandler
from .event_router import EventRouter
from .file_presenter import FilePresenter
from .lifecycle_manager import AppLifecycleManager
from .logging_format_resolver import LoggingFormatResolver
from .macro_presenter import MacroPresenter
from .manual_control_presenter import ManualControlPresenter
from .packet_presenter import PacketPresenter
from .port_presenter import PortPresenter
from .preferences_coordinator import PreferencesCoordinator
from .shutdown_state_collector import ShutdownStateCollector


class MainPresenter(QObject):
    """애플리케이션 전역 Presenter 조정자."""

    def __init__(self, view: MainWindow) -> None:
        super().__init__()
        self.view = view
        self.settings_manager = SettingsManager()
        self.status_timer: Optional[QTimer] = None
        self._sys_log_writer: Optional[TextLogWriter] = None
        # MacroRunner worker thread에서는 QWidget을 조회하지 않는다.
        # 반복 시작 직전 UI thread에서 선택 포트를 문자열로 스냅샷한다.
        self._macro_target_port: Optional[str] = None

        self.lifecycle_manager = AppLifecycleManager(self)
        self.lifecycle_manager.initialize_app()
        self.view.connect_port_tab_changed(self._on_port_tab_changed)

    def _init_core_systems(self) -> None:
        self.connection_controller = ConnectionController()
        self.command_transmission_service = CommandTransmissionService(
            self.connection_controller,
            self.settings_manager,
        )
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()
        self.data_handler = DataTrafficHandler(self.view)

    def _init_sub_presenters(self) -> None:
        self.port_presenter = PortPresenter(
            self.view.port_view,
            self.connection_controller,
        )
        self.macro_presenter = MacroPresenter(self.view.macro_view, self.macro_runner)
        self.file_presenter = FilePresenter(self.connection_controller)
        self.packet_presenter = PacketPresenter(
            self.view.packet_view,
            self.event_router,
            self.settings_manager,
        )
        self.manual_control_presenter = ManualControlPresenter(
            self.view.manual_control_view,
            self.connection_controller,
            self.command_transmission_service,
            self.view.append_local_echo_data,
            self.port_presenter.get_active_port_name,
        )

    def _connect_signals(self) -> None:
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)
        self.event_router.data_sent.connect(self._on_data_sent_router)
        self.event_router.macro_started.connect(self.on_macro_started)
        self.event_router.macro_finished.connect(self.on_macro_finished)
        self.event_router.macro_error.connect(self.on_macro_error)
        self.event_router.file_transfer_completed.connect(self.on_file_transfer_completed)
        self.event_router.file_transfer_error.connect(self.on_file_transfer_error)
        self.event_router.settings_changed.connect(self.on_settings_change_requested)

        self.macro_runner.send_requested.connect(self.on_macro_send_requested)
        self.macro_runner.set_send_handler(self.deliver_macro_command)

        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.close_requested.connect(self.on_close_requested)
        self.view.preferences_requested.connect(self.on_preferences_requested)
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)
        self.view.file_transfer_dialog_opened.connect(
            self.file_presenter.on_file_transfer_dialog_opened
        )
        self.view.port_tab_added.connect(self._on_port_tab_added)

        self._connect_logging_signals()

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
        logger.info("Shutdown initiated...")

        if self.macro_runner.isRunning():
            logger.info("Stopping active macro runner...")
            self.macro_runner.stop()
            self.macro_runner.wait(1000)

        self.port_presenter.stop_pending_scan()
        self.data_handler.stop()
        self.packet_presenter.stop()
        if self.status_timer:
            self.status_timer.stop()

        self._close_sys_log_writer()

        state = self.view.get_window_state()
        manual_state_dto = self.manual_control_presenter.get_state()
        ShutdownStateCollector.collect_and_apply(
            self.settings_manager,
            state,
            manual_state_dto,
        )
        self.settings_manager.save_settings()

        if self.connection_controller.has_active_connection:
            self.connection_controller.close_connection()

        QCoreApplication.processEvents()
        data_logger_manager.stop_all()
        logger.info("Shutdown completed.")

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        PreferencesCoordinator.apply_state(self.settings_manager, new_state)
        self.settings_manager.save_settings()

        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)

        # TODO(refactor): 포트 컬렉션 순회는 MainWindow facade로 이동할 대상이다.
        count = self.view.get_port_tabs_count()
        for index in range(count):
            widget = self.view.get_port_tab_widget(index)
            if hasattr(widget, "set_max_log_lines"):
                widget.set_max_log_lines(new_state.max_log_lines)

        self.manual_control_presenter.update_local_echo_setting(
            new_state.local_echo_enabled
        )

        from core.event_bus import event_bus

        event_bus.publish(EventTopics.SETTINGS_CHANGED, new_state)
        settings_updated_msg = language_manager.get_text(
            "main_status_msg_settings_updated"
        )
        self.view.show_status_message(settings_updated_msg, 2000)
        self._log_info(settings_updated_msg)

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        settings = self.settings_manager
        settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        settings.save_settings()
        logger.info("Font settings saved successfully.")

    def _on_data_sent_router(self, event: PortDataEvent) -> None:
        self.data_handler.on_data_sent(event)

    def on_port_opened(self, event: PortConnectionEvent) -> None:
        self.view.update_status_bar_port(event.port, True)
        self.view.show_status_message(f"Connected to {event.port}", 3000)
        self._update_controls_state_for_current_tab()

    def on_port_closed(self, event: PortConnectionEvent) -> None:
        port_name = event.port

        if self.macro_runner.isRunning():
            if (
                not self.macro_runner.broadcast_enabled
                and self._macro_target_port == port_name
            ):
                self._notify_macro_error(
                    f"Target port '{port_name}' closed. Macro stopped."
                )
            elif (
                self.macro_runner.broadcast_enabled
                and not self.connection_controller.has_active_broadcast_ports()
            ):
                self._notify_macro_error("No active ports left. Macro stopped.")

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
        # EventBus publish는 MacroRunner.start()가 QThread.start()를 호출하기 전에
        # UI thread에서 발생한다. 이 시점에만 View를 읽고 문자열을 저장한다.
        self._macro_target_port = self.port_presenter.get_active_port_name()
        self._log_info("Macro started")
        self.view.show_status_message(
            language_manager.get_text("main_status_msg_macro_running"),
            0,
        )

    def on_macro_finished(self) -> None:
        self._macro_target_port = None
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

    def deliver_macro_command(self, manual_command: ManualCommand) -> MacroSendResult:
        """Worker thread에서 View 접근 없이 스냅샷 대상에 명령을 전송합니다."""
        active_port = None if manual_command.broadcast_enabled else self._macro_target_port
        result = self.command_transmission_service.send(
            manual_command,
            active_port=active_port,
        )
        return MacroSendResult(
            success=result.success,
            message=result.message,
            data=result.data,
        )

    def on_macro_send_requested(self, manual_command: ManualCommand) -> None:
        """개별 Row Send는 UI thread이므로 현재 포트를 즉시 조회해 전송합니다."""
        active_port = (
            None
            if manual_command.broadcast_enabled
            else self.port_presenter.get_active_port_name()
        )
        result = self.command_transmission_service.send(
            manual_command,
            active_port=active_port,
        )
        if not result.success:
            self._notify_macro_error(result.message)
            return
        self.show_local_echo(result.data)

    def show_local_echo(self, data: bytes) -> None:
        if not data:
            return
        if self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False):
            self.view.append_local_echo_data(data)

    def _notify_macro_error(self, message: str) -> None:
        logger.error(f"Macro stopped: {message}")
        self.macro_runner.stop()
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
        stats = PortStatistics(
            rx_bytes=self.data_handler.rx_byte_count,
            tx_bytes=self.data_handler.tx_byte_count,
            bps=0,
        )
        self.view.update_status_bar_stats(stats)
        self.data_handler.reset_counts()
        self.view.update_status_bar_time(
            QDateTime.currentDateTime().toString("HH:mm:ss")
        )

    def on_shortcut_connect(self) -> None:
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        self.port_presenter.clear_log_current_port()

    def _connect_logging_signals(self) -> None:
        count = self.view.get_port_tabs_count()
        for index in range(count):
            self._connect_single_port_logging(self.view.get_port_tab_widget(index))
        self._connect_system_logging_signals()

    def _connect_system_logging_signals(self) -> None:
        left_view = self.view.port_view
        left_view.sys_logging_start_requested.connect(
            self._on_sys_logging_start_requested
        )
        left_view.sys_logging_stop_requested.connect(
            self._on_sys_logging_stop_requested
        )
        left_view.system_log_line_appended.connect(
            self._on_system_log_line_appended
        )

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        self._connect_single_port_logging(panel)
        panel.set_data_log_color_rules(color_manager.rules)

    def _connect_single_port_logging(self, panel: PortPanel) -> None:
        if not hasattr(panel, "logging_start_requested"):
            return

        try:
            panel.logging_start_requested.disconnect()
            panel.logging_stop_requested.disconnect()
        except TypeError:
            pass

        panel.logging_start_requested.connect(
            lambda: self._on_logging_start_requested(panel)
        )
        panel.logging_stop_requested.connect(
            lambda: self._on_logging_stop_requested(panel)
        )

    @staticmethod
    def _start_log_capture_dialog(widget) -> Optional[str]:
        file_path = widget.show_save_log_dialog()
        if not file_path:
            widget.set_logging_active(False)
            return None
        return file_path

    def _on_logging_start_requested(self, panel: PortPanel) -> None:
        file_path = self._start_log_capture_dialog(panel)
        if file_path is None:
            return

        port = panel.get_port_name()
        if not port:
            panel.set_logging_active(False)
            return

        log_format = LoggingFormatResolver.resolve(file_path)
        if data_logger_manager.start_logging(port, file_path, log_format):
            panel.set_logging_active(True)
            self._log_info(
                f"[{port}] Logging started ({log_format.value}): {file_path}"
            )
        else:
            panel.set_logging_active(False)
            self._log_error(f"[{port}] Failed to start logging")

    def _on_logging_stop_requested(self, panel: PortPanel) -> None:
        port = panel.get_port_name()
        if port:
            data_logger_manager.stop_logging(port)
        panel.set_logging_active(False)
        self._log_info(f"[{port}] Logging stopped")

    def _on_sys_logging_start_requested(self) -> None:
        left_view = self.view.port_view
        file_path = self._start_log_capture_dialog(left_view)
        if file_path is None:
            return

        writer = TextLogWriter()
        try:
            writer.open(file_path)
        except OSError as exc:
            left_view.set_logging_active(False)
            self._log_error(
                f"Failed to start system log recording ({file_path}): {exc}"
            )
            return

        self._sys_log_writer = writer
        left_view.set_logging_active(True)
        self._log_info(f"System log recording enabled: {file_path}")

    def _on_sys_logging_stop_requested(self) -> None:
        left_view = self.view.port_view
        self._close_sys_log_writer()
        left_view.set_logging_active(False)
        self._log_info("System log recording stopped")

    def _close_sys_log_writer(self) -> None:
        if self._sys_log_writer is not None:
            self._sys_log_writer.close()
            self._sys_log_writer = None

    def _on_system_log_line_appended(self, text: str) -> None:
        if self._sys_log_writer is None:
            return

        writer = self._sys_log_writer
        try:
            writer.write_line(text)
        except OSError as exc:
            self._sys_log_writer = None
            writer.close()
            self.view.port_view.set_logging_active(False)
            self._log_error(f"System log write failed, recording stopped: {exc}")
