"""Unified Manual Control Presenter.

Manual Control은 Protocol과 무관하게 동일한 Command 입력을 사용합니다.
ASCII/HEX 및 Prefix/Suffix 처리는 CommandTransmissionService.prepare()에서 공통 수행하고,
현재 Port의 Protocol에 따라 Serial write 또는 SPI/I2C transaction으로 routing합니다.
"""
from dataclasses import replace
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import ManualCommand, ManualControlState
from common.enums import ConnectionProtocol, TransmissionErrorCode
from core.logger import logger
from core.transport.transaction.dto import (
    I2cTransactionRequest,
    I2cTransactionResult,
    SpiTransactionRequest,
    SpiTransactionResult,
    TransactionProtocol,
)
from model.auto_tx import AutoTxScheduler
from model.command_transmission_service import CommandTransmissionService, TransmissionResult
from model.connection_controller import ConnectionController
from model.transaction_manager import TransactionManager
from view.managers.language_manager import language_manager
from view.panels.manual_control_panel import ManualControlPanel
from view.sections.main_left_section import MainLeftSection


class ManualControlPresenter(QObject):
    """공통 payload 입력과 Protocol별 I/O semantics를 연결합니다."""

    broadcast_changed = pyqtSignal(bool)
    protocol_changed = pyqtSignal(str)
    send_error = pyqtSignal(str, str, bool)
    local_echo_requested = pyqtSignal(bytes)

    def __init__(
        self,
        panel: ManualControlPanel,
        port_view: MainLeftSection,
        connection_controller: ConnectionController,
        transmission_service: CommandTransmissionService,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        super().__init__()
        self.panel = panel
        self.port_view = port_view
        self.connection_controller = connection_controller
        self.transmission_service = transmission_service
        self.transaction_manager = transaction_manager
        self.local_echo_enabled = self.panel.is_local_echo_enabled()
        self._protocol_connected_panel_ids: set[int] = set()

        self.auto_tx_scheduler = AutoTxScheduler()
        self.auto_tx_scheduler.send_requested.connect(self._on_auto_tx_send_requested)
        self._auto_tx_failing = False

        self.panel.send_requested.connect(self.on_send_requested)
        self.panel.dtr_changed.connect(self.on_dtr_changed)
        self.panel.rts_changed.connect(self.on_rts_changed)
        self.panel.broadcast_changed.connect(self.broadcast_changed.emit)
        self.panel.auto_tx_toggled.connect(self.on_auto_tx_toggled)
        self.connection_controller.connection_closed.connect(self._on_connection_closed)

        tab_changed = getattr(self.port_view, "current_tab_changed", None)
        if tab_changed is not None:
            tab_changed.connect(self.sync_protocol_from_current_tab)
        tab_added = getattr(self.port_view, "port_tab_added", None)
        if tab_added is not None:
            tab_added.connect(self._on_port_tab_added)

        get_panels = getattr(self.port_view, "get_port_panels", None)
        if get_panels is not None:
            for port_panel in get_panels():
                self._connect_port_panel_protocol(port_panel)

        if self.transaction_manager is not None:
            self.transaction_manager.transaction_completed.connect(
                self._on_transaction_completed
            )
            self.transaction_manager.transaction_failed.connect(
                self._on_transaction_failed
            )

        self.sync_protocol_from_current_tab()

    # ------------------------------------------------------------------
    # Current protocol / view synchronization
    # ------------------------------------------------------------------
    def _connect_port_panel_protocol(self, port_panel) -> None:
        panel_id = id(port_panel)
        if panel_id in self._protocol_connected_panel_ids:
            return
        signal = getattr(port_panel, "protocol_changed", None)
        if signal is not None:
            signal.connect(
                lambda _protocol, panel=port_panel: self._on_panel_protocol_changed(panel)
            )
        self._protocol_connected_panel_ids.add(panel_id)

    def _on_port_tab_added(self, port_panel) -> None:
        self._connect_port_panel_protocol(port_panel)
        if self._get_current_port_panel() is port_panel:
            self.sync_protocol_from_current_tab()

    def _on_panel_protocol_changed(self, port_panel) -> None:
        if self._get_current_port_panel() is port_panel:
            self.sync_protocol_from_current_tab()

    def _get_current_port_panel(self):
        getter = getattr(self.port_view, "get_current_port_panel", None)
        return getter() if getter is not None else None

    @staticmethod
    def _normalize_protocol(protocol) -> str:
        supported = {
            ConnectionProtocol.SERIAL,
            TransactionProtocol.SPI.value,
            TransactionProtocol.I2C.value,
        }
        return protocol if isinstance(protocol, str) and protocol in supported else ConnectionProtocol.SERIAL

    def current_protocol(self) -> str:
        current_panel = self._get_current_port_panel()
        if current_panel is None:
            return ConnectionProtocol.SERIAL
        getter = getattr(current_panel, "current_protocol", None)
        if getter is None:
            return ConnectionProtocol.SERIAL
        return self._normalize_protocol(getter())

    def sync_protocol_from_current_tab(self, *_args) -> None:
        protocol = self.current_protocol()
        setter = getattr(self.panel, "set_protocol", None)
        if setter is not None:
            setter(protocol)
        self.protocol_changed.emit(protocol)

    def set_enabled(self, enabled: bool) -> None:
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        # Transaction broadcast는 아직 runtime contract가 없으므로 Serial에서만 enable policy에 사용.
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            return False
        return self.panel.is_broadcast_enabled()

    # ------------------------------------------------------------------
    # Common Manual Send path
    # ------------------------------------------------------------------
    def on_send_requested(self, command=None) -> None:
        manual_command = command if isinstance(command, ManualCommand) else self._build_command_from_panel()
        if manual_command is not None:
            self._send_manual_command(manual_command)

    def _build_command_from_panel(self) -> Optional[ManualCommand]:
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

    def _send_manual_command(self, command: ManualCommand, *, is_auto_tx: bool = False) -> bool:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            return self._process_and_send_serial(command, is_auto_tx=is_auto_tx)
        return self._process_and_send_transaction(command, protocol, is_auto_tx=is_auto_tx)

    def _process_and_send_serial(
        self,
        command: ManualCommand,
        *,
        is_auto_tx: bool = False,
    ) -> bool:
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

    def _process_and_send_transaction(
        self,
        command: ManualCommand,
        protocol: str,
        *,
        is_auto_tx: bool = False,
    ) -> bool:
        if self.transaction_manager is None:
            self._report_transaction_error("Transaction runtime is unavailable")
            return False
        if command.broadcast_enabled:
            self._report_transaction_error("Transaction broadcast is not supported yet")
            return False

        current_panel = self._get_current_port_panel()
        if current_panel is None or not current_panel.is_connected():
            self._report_transaction_error("Transaction adapter is not connected")
            return False

        processed = self.transmission_service.prepare(command)
        if not processed.success or not processed.data:
            self._report_send_error(
                is_auto_tx,
                language_manager.get_text("manual_control_title_send_error"),
                self._resolve_error_message(processed),
            )
            return False

        payload = processed.data
        if protocol == TransactionProtocol.SPI.value:
            request = SpiTransactionRequest(
                tx_data=payload,
                rx_length=len(payload),
                keep_cs_asserted=self.panel.is_keep_cs_enabled(),
            )
        else:
            request = I2cTransactionRequest(
                write_data=payload,
                read_length=0,
                repeated_start=self.panel.is_repeated_start_enabled(),
            )

        session_name = self._panel_endpoint_name(current_panel)
        request_id = self.transaction_manager.execute(session_name, request)
        if request_id is None:
            self._report_transaction_error(
                f"Transaction session is not ready: {session_name}"
            )
            return False

        if is_auto_tx:
            self._auto_tx_failing = False
        if self.local_echo_enabled:
            self.local_echo_requested.emit(payload)
        logger.debug(
            f"Transaction request queued: session={session_name}, id={request_id}"
        )
        return True

    @staticmethod
    def _resolve_error_message(result: TransmissionResult) -> str:
        if result.error_code is TransmissionErrorCode.INVALID_COMMAND:
            return language_manager.get_text(
                "manual_control_msg_invalid_command"
            ).format(result.message)
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

    # ------------------------------------------------------------------
    # Transaction result path
    # ------------------------------------------------------------------
    def _on_transaction_completed(self, session_name: str, request_id: int, result) -> None:
        data = b""
        actual_frequency = None
        if isinstance(result, SpiTransactionResult):
            data = result.rx_data
            actual_frequency = result.actual_frequency_hz
        elif isinstance(result, I2cTransactionResult):
            data = result.read_data
            actual_frequency = result.actual_frequency_hz

        if data:
            self._append_data_to_endpoint(session_name, data)
        logger.info(
            "Transaction completed: "
            f"session={session_name}, id={request_id}, "
            f"rx={len(data)} bytes, actual_frequency={actual_frequency} Hz"
        )

    def _on_transaction_failed(self, session_name: str, request_id: int, error: Exception) -> None:
        logger.error(
            f"Transaction failed: session={session_name}, id={request_id}: {error}"
        )
        self._report_transaction_error(str(error))

    def _append_data_to_endpoint(self, session_name: str, data: bytes) -> None:
        get_panels = getattr(self.port_view, "get_port_panels", None)
        if get_panels is None:
            return
        for port_panel in get_panels():
            if self._panel_endpoint_name(port_panel) == session_name:
                append = getattr(port_panel, "append_log_data", None)
                if append is not None:
                    append(data)
                return

    @staticmethod
    def _panel_endpoint_name(port_panel) -> str:
        getter = getattr(port_panel, "get_connection_display_name", None)
        if getter is not None:
            return getter()
        fallback = getattr(port_panel, "get_port_name", None)
        return fallback() if fallback is not None else ""

    def _report_transaction_error(self, message: str) -> None:
        logger.warning(f"Manual transaction rejected: {message}")
        self.send_error.emit(
            language_manager.get_text("manual_control_title_send_error"),
            message,
            True,
        )

    # ------------------------------------------------------------------
    # Automation / Serial modem controls
    # ------------------------------------------------------------------
    def _report_send_error(self, is_auto_tx: bool, title: str, message: str) -> None:
        if is_auto_tx:
            if self._auto_tx_failing:
                return
            self._auto_tx_failing = True
            self.send_error.emit(title, message, False)
            return
        self.send_error.emit(title, message, True)

    def _on_auto_tx_send_requested(self, command: ManualCommand) -> None:
        self._send_manual_command(command, is_auto_tx=True)

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
        self.auto_tx_scheduler.stop()
        self._auto_tx_failing = False
        self.panel.set_auto_tx_checked(False)

    def _on_connection_closed(self, _event=None) -> None:
        if not self.connection_controller.has_active_connection and not (
            self.transaction_manager and self.transaction_manager.has_active_session
        ):
            self.stop_auto_tx()

    def on_dtr_changed(self, state: bool) -> None:
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            return
        self.connection_controller.set_dtr(state)
        logger.info(f"DTR set to {state}")

    def on_rts_changed(self, state: bool) -> None:
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            return
        self.connection_controller.set_rts(state)
        logger.info(f"RTS set to {state}")

    # ------------------------------------------------------------------
    # Persistent Manual Control preferences
    # ------------------------------------------------------------------
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
        restored = replace(state, auto_tx_enabled=False)
        self.local_echo_enabled = restored.local_echo_enabled
        self.panel.apply_state(restored)
