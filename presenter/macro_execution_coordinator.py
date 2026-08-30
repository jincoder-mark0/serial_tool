"""
매크로 실행의 cross-component 전송 조정자.

MacroPresenter는 매크로 UI와 Runner 제어에 집중하고, MainPresenter는 전역 표시만
담당합니다. 반복 실행 target snapshot, worker-thread send handler, 단일 Row send,
대상 포트 종료 시 중단 정책은 이 coordinator가 소유합니다.
"""
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import MacroSendResult, ManualCommand, PortConnectionEvent
from model.command_transmission_service import CommandTransmissionService
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from view.sections.main_left_section import MainLeftSection


class MacroExecutionCoordinator(QObject):
    """MacroRunner와 명령 전송/활성 포트 사이의 application orchestration을 관리합니다."""

    local_echo_requested = pyqtSignal(bytes)
    execution_interrupted = pyqtSignal(str)

    def __init__(
        self,
        runner: MacroRunner,
        connection_controller: ConnectionController,
        transmission_service: CommandTransmissionService,
        port_view: MainLeftSection,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._connection_controller = connection_controller
        self._transmission_service = transmission_service
        self._port_view = port_view
        self._target_port: Optional[str] = None

        # macro_started는 MacroRunner.start() 호출 thread(UI thread)에서 QThread 시작 전에
        # emit되므로 이 슬롯에서 QWidget facade를 안전하게 읽고 문자열만 snapshot합니다.
        self._runner.macro_started.connect(self._on_macro_started)
        self._runner.macro_finished.connect(self._on_macro_finished)
        self._runner.send_requested.connect(self.on_single_send_requested)
        self._runner.set_send_handler(self.deliver_repeated_command)
        self._connection_controller.connection_closed.connect(self.on_connection_closed)

    @property
    def target_port(self) -> Optional[str]:
        """진단/테스트용 반복 실행 target snapshot입니다."""
        return self._target_port

    def _on_macro_started(self) -> None:
        """반복 실행 시작 시 현재 포트를 UI thread에서 문자열로 snapshot합니다."""
        self._target_port = self._port_view.get_current_port_name() or None

    def _on_macro_finished(self) -> None:
        self._target_port = None

    def deliver_repeated_command(self, command: ManualCommand) -> MacroSendResult:
        """
        MacroRunner worker thread에서 View 접근 없이 snapshot target으로 전송합니다.
        """
        active_port = None if command.broadcast_enabled else self._target_port
        result = self._transmission_service.send(
            command,
            active_port=active_port,
        )
        return MacroSendResult(
            success=result.success,
            message=result.message,
            data=result.data,
        )

    def on_single_send_requested(self, command: ManualCommand) -> None:
        """UI thread의 개별 Row Send를 현재 활성 포트 또는 broadcast 대상으로 전송합니다."""
        active_port = None
        if not command.broadcast_enabled:
            active_port = self._port_view.get_current_port_name() or None

        result = self._transmission_service.send(command, active_port=active_port)
        if not result.success:
            self._interrupt(result.message)
            return
        if result.data:
            self.local_echo_requested.emit(result.data)

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        """실행 대상이 사라졌을 때 반복 매크로를 중지하고 사유를 상위에 전달합니다."""
        if not self._runner.isRunning():
            return

        if not self._runner.broadcast_enabled:
            if self._target_port == event.port:
                self._interrupt(
                    f"Target port '{event.port}' closed. Macro stopped."
                )
            return

        if not self._connection_controller.has_active_broadcast_ports():
            self._interrupt("No active ports left. Macro stopped.")

    def _interrupt(self, message: str) -> None:
        """Runner를 중지한 뒤 presentation 계층에 중단 사유를 알립니다."""
        self._runner.stop()
        self.execution_interrupted.emit(message)
