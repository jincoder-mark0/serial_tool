"""
애플리케이션 최상위 Presenter.

조립된 runtime component를 받아 전역 이벤트와 UI 상태를 중재합니다. 구체 객체 생성은
application_bootstrap.py, 초기 상태 복원/로그/종료 같은 독립 유스케이스는 전용 객체가 소유합니다.
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
from core.logger import logger
from core.settings_manager import SettingsManager
from view.main_window import MainWindow
from view.managers.color_manager import color_manager
from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel

from .lifecycle_manager import AppLifecycleManager
from .logging_coordinator import LoggingCoordinator
from .preferences_coordinator import PreferencesCoordinator
from .shutdown_coordinator import ShutdownCoordinator


class MainPresenter(QObject):
    """애플리케이션 전역 Presenter 조정자."""

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
        self._macro_target_port: Optional[str] = None

        # 1. 저장 설정을 View에 먼저 적용합니다.
        self.lifecycle_manager = AppLifecycleManager(
            self.view,
            self.settings_manager,
        )
        self.lifecycle_manager.initialize_view()

        # 2. Production은 main.py가 조립한 component를 주입합니다.
        # None fallback은 기존 단위 테스트/외부 생성 코드의 단계적 마이그레이션용입니다.
        runtime = components or ApplicationBootstrapper(
            self.view,
            self.settings_manager,
        ).build()
        self._apply_components(runtime)

        # 3. Presenter 상태와 RX fast path를 복원/연결합니다.
        self.manual_control_presenter.apply_state(
            self.lifecycle_manager.create_manual_control_state()
        )
        self.connection_controller.data_received.connect(
            self.data_handler.on_fast_data_received
        )

        # 4. 독립 coordinator를 구성합니다.
        self.logging_coordinator = LoggingCoordinator(
            port_view=self.view.port_view,
            log_info=self._log_info,
            log_error=self._log_error,
        )
        self.logging_coordinator.connect_signals()

        self.status_timer = self.lifecycle_manager.create_status_timer(
            self.update_status_bar
        )
        self.shutdown_coordinator = ShutdownCoordinator(
            view=self.view,
            settings_manager=self.settings_manager,
            connection_controller=self.connection_controller,
            macro_runner=self.macro_runner,
            port_presenter=self.port_presenter,
            manual_control_presenter=self.manual_control_presenter,
            packet_presenter=self.packet_presenter,
            data_handler=self.data_handler,
            close_system_log=self.logging_coordinator.close_system_log,
            status_timer=self.status_timer,
        )

        # 5. public signal을 배선하고 초기화 완료를 기록합니다.
        self._connect_signals()
        self.view.connect_port_tab_changed(self._on_port_tab_changed)
        self.lifecycle_manager.log_initialized()

    def _apply_components(self, components: ApplicationComponents) -> None:
        """Bootstrapper가 생성한 runtime component를 Presenter 필드에 배치합니다."""
        self.connection_controller = components.connection_controller
        self.command_transmission_service = components.command_transmission_service
        self.file_transfer_manager = components.file_transfer_manager
        self.macro_runner = components.macro_runner
        self.data_handler = components.data_handler
        self.port_presenter = components.port_presenter
        self.macro_presenter = components.macro_presenter
        self.file_presenter = components.file_presenter
        self.packet_presenter = components.packet_presenter
        self.manual_control_presenter = components.manual_control_presenter

    @property
    def _sys_log_writer(self):
        """S-055 기존 테스트/외부 코드 호환용 읽기 전용 alias."""
        coordinator = getattr(self, "logging_coordinator", None)
        return coordinator._system_log_writer if coordinator is not None else None

    def _connect_signals(self) -> None:
        """Model/Presenter/View public signal을 direct topology로 연결합니다."""
        self.connection_controller.connection_opened.connect(self.on_port_opened)
        self.connection_controller.connection_closed.connect(self.on_port_closed)
        self.connection_controller.error_occurred.connect(self.on_port_error)
        self.connection_controller.data_sent.connect(self._on_data_sent)
        self.connection_controller.data_received.connect(self.macro_runner.on_data_received)

        self.macro_runner.macro_started.connect(self.on_macro_started)
        self.macro_runner.macro_finished.connect(self.on_macro_finished)
        self.macro_runner.error_occurred.connect(self.on_macro_error)
        self.macro_runner.send_requested.connect(self.on_macro_send_requested)
        self.macro_runner.set_send_handler(self.deliver_macro_command)

        self.file_presenter.transfer_completed.connect(self.on_file_transfer_completed)
        self.file_presenter.transfer_error.connect(self.on_file_transfer_error)

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

        self.manual_control_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )
        self.manual_control_presenter.send_error.connect(self._on_manual_send_error)
        self.macro_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )

    # ------------------------------------------------------------------
    # System log presentation helpers
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Settings / lifecycle
    # ------------------------------------------------------------------
    def on_preferences_requested(self) -> None:
        self.view.open_preferences_dialog(
            PreferencesCoordinator.build_state(self.settings_manager)
        )

    def on_close_requested(self) -> None:
        """종료 세부 순서는 ShutdownCoordinator에 위임합니다."""
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

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        settings = self.settings_manager
        settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        settings.save_settings()
        logger.info("Font settings saved successfully.")

    # ------------------------------------------------------------------
    # Port / data
    # ------------------------------------------------------------------
    def _on_data_sent(self, event: PortDataEvent) -> None:
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

    # ------------------------------------------------------------------
    # Macro
    # ------------------------------------------------------------------
    def on_macro_started(self) -> None:
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

    # ------------------------------------------------------------------
    # File transfer
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # UI status / shortcuts
    # ------------------------------------------------------------------
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

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        """새 포트 패널의 횡단 관심사(logging/color)를 각 소유자에 전달합니다."""
        self.logging_coordinator.on_port_tab_added(panel)
        panel.set_data_log_color_rules(color_manager.rules)

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
