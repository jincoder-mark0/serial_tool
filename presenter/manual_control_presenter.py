"""Unified manual-control Presenter.

Serial commands keep the established CommandTransmissionService path. SPI/I2C
requests use TransactionManager while sharing the same Manual Control area and
current PortPanel selection.
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
    """Serial manual TX and SPI/I2C transaction execution orchestration."""

    broadcast_changed = pyqtSignal(bool)
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

        self.auto_tx_scheduler = AutoTxScheduler()
        self.auto_tx_scheduler.send_requested.connect(self._on_auto_tx_send_requested)
        self._auto_tx_failing = False

        self.panel.send_requested.connect(self.on_send_requested)
        transaction_signal = getattr(self.panel, "transaction_execute_requested", None)
        if transaction_signal is not None:
            transaction_signal.connect(self.on_transaction_execute_requested)
        self.panel.dtr_changed.connect(self.on_dtr_changed)
        self.panel.rts_changed.connect(self.on_rts_changed)
        self.panel.broadcast_changed.connect(self.broadcast_changed.emit)
        self.panel.auto_tx_toggled.connect(self.on_auto_tx_toggled)
        self.connection_controller.connection_closed.connect(self._on_connection_closed)
        self.port_view.current_tab_changed.connect(self.sync_protocol_from_current_tab)

        if self.transaction_manager is not None:
            self.transaction_manager.transaction_completed.connect(
                self._on_transaction_completed
            )
            self.transaction_manager.transaction_failed.connect(
                self._on_transaction_failed
            )

        self.sync_protocol_from_current_tab()

    # ------------------------------------------------------------------
    # Current protocol / enable facade
    # ------------------------------------------------------------------
    def current_protocol(self) -> str:
        current_panel = self.port_view.get_current_port_panel()
        if current_panel is None:
            return ConnectionProtocol.SERIAL
        getter = getattr(current_panel, "current_protocol", None)
        return getter() if getter is not None else ConnectionProtocol.SERIAL

    def sync_protocol_from_current_tab(self, *_args) -> None:
        protocol = self.current_protocol()
        setter = getattr(self.panel, "set_protocol", None)
        if setter is not None:
            setter(protocol)
        if protocol != ConnectionProtocol.SERIAL:
            self.stop_auto_tx()

    def set_enabled(self, enabled: bool) -> None:
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            return False
        return self.panel.is_broadcast_enabled()

    # ------------------------------------------------------------------
    # Serial path
    # ------------------------------------------------------------------
    def on_send_requested(self, _=None) -> None:
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            return
        command = self._build_command_from_panel()
        if command is not None:
            self._process_and_send(command)

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

    def _process_and_send(
        self,
        command: ManualCommand,
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
    # Transaction path
    # ------------------------------------------------------------------
    def on_transaction_execute_requested(self) -> None:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            return
        if self.transaction_manager is None:
            self._report_transaction_error("Transaction runtime is unavailable")
            return

        current_panel = self.port_view.get_current_port_panel()
        if current_panel is None or not current_panel.is_connected():
            self._report_transaction_error("Transaction adapter is not connected")
            return

        session_name = self._panel_endpoint_name(current_panel)
        try:
            if protocol == TransactionProtocol.SPI.value:
                tx_data, rx_length, keep_cs = self.panel.get_spi_transaction_input()
                request = SpiTransactionRequest(
                    tx_data=tx_data,
                    rx_length=rx_length,
                    keep_cs_asserted=keep_cs,
                )
            else:
                write_data, read_length, repeated_start = (
                    self.panel.get_i2c_transaction_input()
                )
                request = I2cTransactionRequest(
                    write_data=write_data,
                    read_length=read_length,
                    repeated_start=repeated_start,
                )
        except (ValueError, TypeError) as exc:
            self._report_transaction_error(str(exc))
            return

        request_id = self.transaction_manager.execute(session_name, request)
        if request_id is None:
            self._report_transaction_error(
                f"Transaction session is not ready: {session_name}"
            )
            return
        logger.debug(
            f"Transaction request queued: session={session_name}, id={request_id}"
        )

    def _on_transaction_completed(
        self,
        session_name: str,
        request_id: int,
        result,
    ) -> None:
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

    def _on_transaction_failed(
        self,
        session_name: str,
        request_id: int,
        error: Exception,
    ) -> None:
        logger.error(
            f"Transaction failed: session={session_name}, id={request_id}: {error}"
        )
        self._report_transaction_error(str(error))

    def _append_data_to_endpoint(self, session_name: str, data: bytes) -> None:
        for port_panel in self.port_view.get_port_panels():
            if self._panel_endpoint_name(port_panel) == session_name:
                port_panel.append_log_data(data)
                return

    @staticmethod
    def _panel_endpoint_name(port_panel) -> str:
        getter = getattr(port_panel, "get_connection_display_name", None)
        return getter() if getter is not None else port_panel.get_port_name()

    def _report_transaction_error(self, message: str) -> None:
        logger.warning(f"Manual transaction rejected: {message}")
        self.send_error.emit(
            language_manager.get_text("manual_control_title_send_error"),
            message,
            True,
        )

    # ------------------------------------------------------------------
    # Serial automation / modem controls
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
        if self.current_protocol() == ConnectionProtocol.SERIAL:
            self._process_and_send(command, is_auto_tx=True)

    def on_auto_tx_toggled(self, enabled: bool) -> None:
        if self.current_protocol() != ConnectionProtocol.SERIAL:
            self.stop_auto_tx()
            return

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
        if not self.connection_controller.has_active_connection:
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
    # Persistent Serial manual-control preferences
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
