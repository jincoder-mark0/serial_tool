"""
애플리케이션 최상위 Presenter.

MainPresenter가 필요한 의존성 contract를 이 모듈이 직접 정의합니다. Composition root는
이 contract를 조립해서 주입할 뿐이며, Presenter는 application_bootstrap 모듈이나 전체
runtime graph를 알지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt5.QtCore import QObject

from common.dtos import (
    FileCompletionEvent,
    FileErrorEvent,
    MacroErrorEvent,
    PortConnectionEvent,
    PortErrorEvent,
    SystemLogEvent,
)
from common.enums import LogLevel
from core.logger import logger
from view.main_window import MainWindow
from view.managers.language_manager import language_manager

if TYPE_CHECKING:
    from model.connection_controller import ConnectionController
    from model.macro_runner import MacroRunner
    from presenter.file_presenter import FilePresenter
    from presenter.lifecycle_manager import AppLifecycleManager
    from presenter.logging_coordinator import LoggingCoordinator
    from presenter.macro_execution_coordinator import MacroExecutionCoordinator
    from presenter.macro_presenter import MacroPresenter
    from presenter.manual_control_presenter import ManualControlPresenter
    from presenter.packet_presenter import PacketPresenter
    from presenter.port_presenter import PortPresenter
    from presenter.shutdown_coordinator import ShutdownCoordinator


@dataclass(frozen=True)
class MainPresenterDependencies:
    """MainPresenter가 실제로 사용하는 최소 runtime dependency contract."""

    lifecycle_manager: AppLifecycleManager
    connection_controller: ConnectionController
    macro_runner: MacroRunner
    macro_execution_coordinator: MacroExecutionCoordinator
    logging_coordinator: LoggingCoordinator
    shutdown_coordinator: ShutdownCoordinator
    port_presenter: PortPresenter
    macro_presenter: MacroPresenter
    file_presenter: FilePresenter
    packet_presenter: PacketPresenter
    manual_control_presenter: ManualControlPresenter


class MainPresenter(QObject):
    """애플리케이션 전역 표시 상태와 상위 이벤트를 조정합니다."""

    def __init__(
        self,
        view: MainWindow,
        dependencies: MainPresenterDependencies,
    ) -> None:
        super().__init__()
        self.view = view
        self._apply_dependencies(dependencies)

        self.manual_control_presenter.apply_state(
            self.lifecycle_manager.create_manual_control_state()
        )

        self.logging_coordinator.info_requested.connect(self._log_info)
        self.logging_coordinator.error_requested.connect(self._log_error)
        self.logging_coordinator.connect_signals()

        self._connect_signals()
        self.view.connect_port_tab_changed(self._on_port_tab_changed)
        self.lifecycle_manager.log_initialized()

    def _apply_dependencies(self, dependencies: MainPresenterDependencies) -> None:
        """Presenter contract에 정의된 의존성만 보관합니다."""
        self.lifecycle_manager = dependencies.lifecycle_manager
        self.connection_controller = dependencies.connection_controller
        self.macro_runner = dependencies.macro_runner
        self.macro_execution_coordinator = dependencies.macro_execution_coordinator
        self.logging_coordinator = dependencies.logging_coordinator
        self.shutdown_coordinator = dependencies.shutdown_coordinator
        self.port_presenter = dependencies.port_presenter
        self.macro_presenter = dependencies.macro_presenter
        self.file_presenter = dependencies.file_presenter
        self.packet_presenter = dependencies.packet_presenter
        self.manual_control_presenter = dependencies.manual_control_presenter

    def _connect_signals(self) -> None:
        self.connection_controller.connection_opened.connect(self.on_port_opened)
        self.connection_controller.connection_closed.connect(self.on_port_closed)
        self.connection_controller.error_occurred.connect(self.on_port_error)

        self.macro_runner.macro_started.connect(self.on_macro_started)
        self.macro_runner.macro_finished.connect(self.on_macro_finished)
        self.macro_runner.error_occurred.connect(self.on_macro_error)
        self.macro_execution_coordinator.execution_interrupted.connect(
            self._notify_macro_error
        )

        self.file_presenter.transfer_completed.connect(self.on_file_transfer_completed)
        self.file_presenter.transfer_error.connect(self.on_file_transfer_error)

        self.view.close_requested.connect(self.on_close_requested)
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

    def on_close_requested(self) -> None:
        self.shutdown_coordinator.shutdown()

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

        is_manual_broadcast = self.manual_control_presenter.is_broadcast_enabled()
        self.manual_control_presenter.set_enabled(
            is_current_connected or (is_manual_broadcast and has_any_connection)
        )

        is_macro_broadcast = self.macro_presenter.is_broadcast_enabled()
        self.macro_presenter.set_enabled(
            is_current_connected or (is_macro_broadcast and has_any_connection)
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

    def on_shortcut_connect(self) -> None:
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        self.port_presenter.clear_log_current_port()
