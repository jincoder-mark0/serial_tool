"""
수동 제어 프레젠터

View의 사용자 의도를 받아 DTO를 만들고, 명령 전송 유스케이스는
CommandTransmissionService에 위임합니다. Presenter는 UI 상태/알림 정책과
RTS/DTR/Auto Tx orchestration만 담당합니다.
"""
from typing import Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import ManualCommand, ManualControlState
from common.enums import TransmissionErrorCode
from core.logger import logger
from model.auto_tx import AutoTxScheduler
from model.command_transmission_service import CommandTransmissionService, TransmissionResult
from model.connection_controller import ConnectionController
from view.managers.language_manager import language_manager
from view.panels.manual_control_panel import ManualControlPanel


class ManualControlPresenter(QObject):
    """수동 전송, Auto Tx, RTS/DTR UI orchestration을 담당합니다."""

    broadcast_changed = pyqtSignal(bool)
    send_error = pyqtSignal(str, str, bool)

    def __init__(
        self,
        panel: ManualControlPanel,
        connection_controller: ConnectionController,
        transmission_service: CommandTransmissionService,
        local_echo_callback: Callable[[bytes], None],
        get_active_port_callback: Callable[[], Optional[str]],
    ) -> None:
        super().__init__()
        self.panel = panel
        self.connection_controller = connection_controller
        self.transmission_service = transmission_service
        self.local_echo_callback = local_echo_callback
        self.get_active_port_callback = get_active_port_callback

        # 로컬 에코는 View/Preferences 상태이며 전송 서비스의 책임이 아니다.
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
        """
        전송 유스케이스를 서비스에 위임하고 성공/실패의 UI 후처리만 담당합니다.
        """
        active_port = None if command.broadcast_enabled else self.get_active_port_callback()
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
            self.local_echo_callback(result.data)

        return True

    @staticmethod
    def _resolve_error_message(result: TransmissionResult) -> str:
        """서비스의 실패 분류를 현재 언어의 사용자 메시지로 변환합니다."""
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
        """단발/반복 전송에 따른 오류 알림 정책을 적용합니다."""
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

        self.auto_tx_scheduler.stop()

    def _on_connection_closed(self, _event=None) -> None:
        if not self.connection_controller.has_active_connection:
            self.auto_tx_scheduler.stop()
            self.panel.set_auto_tx_checked(False)

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
        self.local_echo_enabled = state.local_echo_enabled
        self.panel.apply_state(state)
