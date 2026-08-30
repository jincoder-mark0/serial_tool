"""
수동 제어 프레젠터.

ManualControlPanel의 사용자 의도를 받아 CommandTransmissionService에 전송을 위임합니다.
현재 포트는 MainLeftSection facade에서 명시적으로 조회하고 Local Echo는 signal로 요청합니다.
Auto Tx의 실행 여부는 세션성(transient) 상태로 취급하여 앱 재시작 시 자동 재개하지 않습니다.
"""
from dataclasses import replace
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import ManualCommand, ManualControlState
from common.enums import TransmissionErrorCode
from core.logger import logger
from model.auto_tx import AutoTxScheduler
from model.command_transmission_service import CommandTransmissionService, TransmissionResult
from model.connection_controller import ConnectionController
from view.managers.language_manager import language_manager
from view.panels.manual_control_panel import ManualControlPanel
from view.sections.main_left_section import MainLeftSection


class ManualControlPresenter(QObject):
    """수동 전송, Auto Tx, RTS/DTR UI orchestration을 담당합니다."""

    broadcast_changed = pyqtSignal(bool)
    send_error = pyqtSignal(str, str, bool)
    local_echo_requested = pyqtSignal(bytes)

    def __init__(
        self,
        panel: ManualControlPanel,
        port_view: MainLeftSection,
        connection_controller: ConnectionController,
        transmission_service: CommandTransmissionService,
    ) -> None:
        super().__init__()
        self.panel = panel
        self.port_view = port_view
        self.connection_controller = connection_controller
        self.transmission_service = transmission_service
        self.local_echo_enabled = self.panel.is_local_echo_enabled()

        self.auto_tx_scheduler = AutoTxScheduler()
        self.auto_tx_scheduler.send_requested.connect(self._on_auto_tx_send_requested)
        self._auto_tx_failing = False

        self.panel.send_requested.connect(self.on_send_requested)
        self.panel.dtr_changed.connect(self.on_dtr_changed)
        self.panel.rts_changed.connect(self.on_rts_changed)
        self.panel.broadcast_changed.connect(self.broadcast_changed.emit)
        self.panel.auto_tx_toggled.connect(self.on_auto_tx_toggled)
        self.connection_controller.connection_closed.connect(self._on_connection_closed)

    def set_enabled(self, enabled: bool) -> None:
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        return self.panel.is_broadcast_enabled()

    def on_send_requested(self, _=None) -> None:
        command = self._build_command_from_panel()
        if command is not None:
            self._process_and_send(command)

    def _build_command_from_panel(self) -> Optional[ManualCommand]:
        """View facade 상태를 ManualCommand DTO로 스냅샷합니다."""
        try:
            return ManualCommand(
                command=self.panel.get_input_text(),
                hex_mode=self.panel.is_hex_mode(),
                prefix_enabled=self.panel.is_prefix_enabled(),
                suffix_enabled=self.panel.is_suffix_enabled(),
                local_echo_enabled=self.panel.is_local_echo_enabled(),
                broadcast_enabled=self.panel.is_broadcast_enabled(),
            )
        except AttributeError as exc:
            logger.error(f"Failed to gather state from ManualControlPanel: {exc}")
            return None

    def _process_and_send(self, command: ManualCommand, is_auto_tx: bool = False) -> bool:
        """전송 유스케이스 결과에 대한 UI 정책만 담당합니다."""
        active_port = None
        if not command.broadcast_enabled:
            active_port = self.port_view.get_current_port_name() or None

        result = self.transmission_service.send(command, active_port=active_port)
        if not result.success:
            logger.warning(f"Command transmission failed: {result.message}")
            self._report_send_error(
                is_auto_tx,
                language_manager.get_text("manual_control_title_send_error"),
                self._resolve_error_message(result),
            )
            return False

        if is_auto_tx:
            self._auto_tx_failing = False

        if self.local_echo_enabled and result.data:
            self.local_echo_requested.emit(result.data)

        return True

    @staticmethod
    def _resolve_error_message(result: TransmissionResult) -> str:
        if result.error_code is TransmissionErrorCode.INVALID_COMMAND:
            return language_manager.get_text("manual_control_msg_invalid_command").format(
                result.message
            )
        if result.error_code in (
            TransmissionErrorCode.NO_BROADCAST_TARGET,
            TransmissionErrorCode.BROADCAST_SEND_FAILED,
        ):
            return language_manager.get_text("manual_control_msg_no_broadcast_target")
        if result.error_code in (
            TransmissionErrorCode.NO_ACTIVE_PORT,
            TransmissionErrorCode.PORT_NOT_OPEN,
            TransmissionErrorCode.SEND_FAILED,
        ):
            return language_manager.get_text("manual_control_msg_port_not_connected")
        return result.message

    def _report_send_error(self, is_auto_tx: bool, title: str, message: str) -> None:
        if is_auto_tx:
            if self._auto_tx_failing:
                return
            self._auto_tx_failing = True
            self.send_error.emit(title, message, False)
            return
        self.send_error.emit(title, message, True)

    def _on_auto_tx_send_requested(self, command: ManualCommand) -> None:
        self._process_and_send(command, is_auto_tx=True)

    def on_auto_tx_toggled(self, enabled: bool) -> None:
        if enabled:
            command = self._build_command_from_panel()
            if command is None:
                self.panel.set_auto_tx_checked(False)
                return
            self._auto_tx_failing = False
            self.auto_tx_scheduler.start(
                command,
                interval_ms=self.panel.get_auto_tx_interval_ms(),
            )
            return

        self.stop_auto_tx()

    def stop_auto_tx(self) -> None:
        """Auto Tx scheduler와 UI 체크 상태를 idempotent하게 함께 정지합니다."""
        self.auto_tx_scheduler.stop()
        self._auto_tx_failing = False
        self.panel.set_auto_tx_checked(False)

    def _on_connection_closed(self, _event=None) -> None:
        if not self.connection_controller.has_active_connection:
            self.stop_auto_tx()

    def on_dtr_changed(self, state: bool) -> None:
        self.connection_controller.set_dtr(state)
        logger.info(f"DTR set to {state}")

    def on_rts_changed(self, state: bool) -> None:
        self.connection_controller.set_rts(state)
        logger.info(f"RTS set to {state}")

    def update_local_echo_setting(self, enabled: bool) -> None:
        self.local_echo_enabled = enabled
        self.panel.set_local_echo_checked(enabled)

    def get_state(self) -> ManualControlState:
        if not self.panel:
            return ManualControlState()

        return ManualControlState(
            input_text=self.panel.get_input_text(),
            hex_mode=self.panel.is_hex_mode(),
            prefix_enabled=self.panel.is_prefix_enabled(),
            suffix_enabled=self.panel.is_suffix_enabled(),
            rts_enabled=self.panel.is_rts_enabled(),
            dtr_enabled=self.panel.is_dtr_enabled(),
            local_echo_enabled=self.local_echo_enabled,
            broadcast_enabled=self.panel.is_broadcast_enabled(),
            auto_tx_enabled=self.panel.is_auto_tx_enabled(),
            auto_tx_interval_ms=self.panel.get_auto_tx_interval_ms(),
        )

    def apply_state(self, state: ManualControlState) -> None:
        """지속 설정을 복원하되 Auto Tx 실행 상태는 항상 꺼진 상태로 시작합니다."""
        restored = replace(state, auto_tx_enabled=False)
        self.local_echo_enabled = restored.local_echo_enabled
        self.panel.apply_state(restored)
