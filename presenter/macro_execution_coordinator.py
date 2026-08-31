"""매크로 실행의 cross-component 전송 조정자.

반복 실행 시작 시 View에서 protocol/endpoint target을 snapshot하고, worker thread에서는
QWidget에 접근하지 않은 채 ProtocolCommandRouter를 통해 Serial/SPI/I2C로 전달합니다.
"""
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.constants import ConfigKeys
from common.dtos import MacroSendResult, ManualCommand, PortConnectionEvent
from common.enums import ConnectionProtocol
from core.settings_manager import SettingsManager
from core.transport.transaction.dto import TransactionProtocol
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from model.protocol_command_router import ProtocolCommandRouter, ProtocolCommandTarget
from view.sections.main_left_section import MainLeftSection


class MacroExecutionCoordinator(QObject):
    """MacroRunner와 protocol-independent command delivery를 연결합니다."""

    local_echo_requested = pyqtSignal(bytes)
    execution_interrupted = pyqtSignal(str)

    def __init__(
        self,
        runner: MacroRunner,
        connection_controller: ConnectionController,
        command_router: ProtocolCommandRouter,
        port_view: MainLeftSection,
        settings_manager: SettingsManager,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._connection_controller = connection_controller
        self._command_router = command_router
        self._port_view = port_view
        self._settings = settings_manager
        self._target: Optional[ProtocolCommandTarget] = None
        self._broadcast_transaction_targets: tuple[ProtocolCommandTarget, ...] = ()

        self._runner.macro_started.connect(self._on_macro_started)
        self._runner.macro_finished.connect(self._on_macro_finished)
        self._runner.send_requested.connect(self.on_single_send_requested)
        self._runner.set_send_handler(self.deliver_repeated_command)
        self._connection_controller.connection_closed.connect(self.on_connection_closed)

    @property
    def target_port(self) -> Optional[str]:
        """Legacy/diagnostic facade: 현재 snapshot endpoint 이름."""
        return self._target.name if self._target is not None else None

    @staticmethod
    def _normalize_protocol(value) -> str:
        supported = {
            ConnectionProtocol.SERIAL,
            TransactionProtocol.SPI.value,
            TransactionProtocol.I2C.value,
        }
        return value if isinstance(value, str) and value in supported else ConnectionProtocol.SERIAL

    @classmethod
    def _target_from_panel(cls, panel) -> Optional[ProtocolCommandTarget]:
        if panel is None or not panel.is_connected():
            return None
        protocol = cls._normalize_protocol(panel.current_protocol())
        name = panel.get_connection_display_name()
        if not name:
            return None
        return ProtocolCommandTarget(name=name, protocol=protocol)

    def _snapshot_broadcast_transaction_targets(self) -> tuple[ProtocolCommandTarget, ...]:
        targets: list[ProtocolCommandTarget] = []
        for panel in self._port_view.get_port_panels():
            target = self._target_from_panel(panel)
            if target is None or target.protocol == ConnectionProtocol.SERIAL:
                continue
            targets.append(target)
        return tuple(targets)

    def _on_macro_started(self) -> None:
        # 이 signal은 QThread 시작 전에 UI thread에서 emit되므로 View 접근 가능.
        self._target = self._target_from_panel(self._port_view.get_current_port_panel())
        self._broadcast_transaction_targets = self._snapshot_broadcast_transaction_targets()

    def _on_macro_finished(self) -> None:
        self._target = None
        self._broadcast_transaction_targets = ()

    def deliver_repeated_command(self, command: ManualCommand) -> MacroSendResult:
        """Worker thread에서 snapshot target만 사용하여 command를 전달합니다."""
        if command.broadcast_enabled:
            result = self._command_router.broadcast(
                command,
                self._broadcast_transaction_targets,
            )
        elif self._target is None:
            return MacroSendResult(False, "No connected target is selected.")
        else:
            result = self._command_router.send(command, self._target)

        return MacroSendResult(
            success=result.success,
            message=result.message,
            data=result.data,
        )

    def on_single_send_requested(self, command: ManualCommand) -> None:
        """UI thread의 개별 Row Send도 현재 Serial/SPI/I2C target으로 전달합니다."""
        if command.broadcast_enabled:
            targets = self._snapshot_broadcast_transaction_targets()
            result = self._command_router.broadcast(command, targets)
        else:
            target = self._target_from_panel(self._port_view.get_current_port_panel())
            if target is None:
                self._interrupt("No connected target is selected.")
                return
            result = self._command_router.send(command, target)

        if not result.success:
            self._interrupt(result.message)
            return

        if result.data and self._settings.get(ConfigKeys.PORT_LOCAL_ECHO, False):
            self.local_echo_requested.emit(result.data)

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        """Serial target close 시 실행을 중지합니다. Transaction close는 별도 session signal에서 보강 가능."""
        if not self._runner.isRunning():
            return

        if not self._runner.broadcast_enabled:
            if self._target and self._target.protocol == ConnectionProtocol.SERIAL:
                if self._target.name == event.port:
                    self._interrupt(f"Target port '{event.port}' closed. Macro stopped.")
            return

        serial_available = self._connection_controller.has_active_broadcast_ports()
        if not serial_available and not self._broadcast_transaction_targets:
            self._interrupt("No active targets left. Macro stopped.")

    def _interrupt(self, message: str) -> None:
        self._runner.stop()
        self.execution_interrupted.emit(message)
