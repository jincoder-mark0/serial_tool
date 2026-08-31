"""통합 Port/Connection UI의 protocol routing Presenter.

UI 탭은 Serial/SPI/I2C가 공유하지만 runtime은 합치지 않습니다.
Serial stream은 ConnectionController, SPI/I2C transaction은 TransactionManager가 소유합니다.
"""
from typing import List
from weakref import WeakSet

from PyQt5.QtCore import QObject

from common.constants import ConfigKeys, DEFAULT_LOG_MAX_LINES
from common.defaults import (
    DEFAULT_PACKET_DELIMITERS,
    DEFAULT_PACKET_GAP_MS,
    DEFAULT_PACKET_LENGTH,
    DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
    DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
    DEFAULT_PACKET_LENGTH_FIELD_SIZE,
    DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
    DEFAULT_PACKET_PARSER_TYPE,
)
from common.dtos import PortConfig, PortConnectionEvent, PortErrorEvent, PortInfo, SystemLogEvent
from common.enums import ConnectionProtocol, LogLevel
from core.logger import logger
from core.settings_manager import SettingsManager
from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.dto import AdapterDescriptor
from model.connection_controller import ConnectionController
from model.port_scan_manager import PortScanManager
from model.transaction_manager import TransactionManager
from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel
from view.sections.main_left_section import MainLeftSection


class PortPresenter(QObject):
    """하나의 PortPanel collection을 두 runtime에 protocol 기준으로 라우팅합니다."""

    def __init__(
        self,
        left_section: MainLeftSection,
        connection_controller: ConnectionController,
        settings_manager: SettingsManager,
        port_scan_manager: PortScanManager,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        super().__init__()
        self.left_section = left_section
        self.connection_controller = connection_controller
        self.settings_manager = settings_manager
        self.port_scan_manager = port_scan_manager
        self.transaction_manager = transaction_manager
        self._connected_panels: WeakSet[PortPanel] = WeakSet()

        self.port_scan_manager.ports_found.connect(self._on_scan_finished)
        if self.transaction_manager is not None:
            self.transaction_manager.adapters_found.connect(self._on_adapters_found)
            self.transaction_manager.discovery_failed.connect(self._on_discovery_failed)
            self.transaction_manager.session_opened.connect(self._on_transaction_opened)
            self.transaction_manager.session_closed.connect(self._on_transaction_closed)
            self.transaction_manager.session_failed.connect(self._on_transaction_failed)

        self.apply_max_log_lines(
            self.settings_manager.get(ConfigKeys.RX_MAX_LINES, DEFAULT_LOG_MAX_LINES)
        )
        for panel in self.left_section.get_port_panels():
            self._connect_tab_signals(panel)

        self.left_section.port_tab_added.connect(self._on_port_tab_added)
        self.left_section.port_tab_closed.connect(self.handle_tab_closed)
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    @staticmethod
    def _panel_config(panel):
        getter = getattr(panel, "get_connection_config", None)
        return getter() if getter is not None else panel.get_port_config()

    @staticmethod
    def _panel_protocol(panel) -> str:
        getter = getattr(panel, "current_protocol", None)
        if getter is not None:
            return getter()
        config = PortPresenter._panel_config(panel)
        return getattr(config, "protocol", ConnectionProtocol.SERIAL)

    @staticmethod
    def _panel_endpoint_name(panel) -> str:
        getter = getattr(panel, "get_connection_display_name", None)
        return getter() if getter is not None else panel.get_port_name()

    def apply_max_log_lines(self, max_lines: int) -> None:
        for panel in self.left_section.get_port_panels():
            panel.set_max_log_lines(max_lines)

    def _connect_tab_signals(self, panel: PortPanel) -> None:
        if panel in self._connected_panels:
            return
        panel.port_scan_requested.connect(self.scan_ports)
        endpoint_refresh = getattr(panel, "endpoint_refresh_requested", None)
        if endpoint_refresh is not None:
            endpoint_refresh.connect(self.refresh_endpoints)
        panel.connect_requested.connect(self.handle_open_request)
        panel.disconnect_requested.connect(
            lambda p=panel: self.handle_close_request(self._panel_config(p))
        )
        panel.tx_broadcast_allowed_changed.connect(
            lambda state, p=panel: self.on_tx_broadcast_allowed_changed(p, state)
        )
        self._connected_panels.add(panel)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        self._connect_tab_signals(panel)
        panel.set_max_log_lines(
            self.settings_manager.get(ConfigKeys.RX_MAX_LINES, DEFAULT_LOG_MAX_LINES)
        )
        self.refresh_endpoints(self._panel_protocol(panel))

    # ------------------------------------------------------------------
    # Discovery routing
    # ------------------------------------------------------------------
    def refresh_endpoints(self, protocol: str = ConnectionProtocol.SERIAL) -> None:
        if protocol == ConnectionProtocol.SERIAL:
            self.scan_ports()
            return
        if self.transaction_manager is not None:
            self.transaction_manager.request_discovery()

    def scan_ports(self) -> None:
        self.port_scan_manager.request_scan()

    def _on_scan_finished(self, port_list: List[PortInfo]) -> None:
        logger.debug(f"Scan finished. Found ports: {[item.device for item in port_list]}")
        self.left_section.set_port_list_for_all(port_list)

    def _on_adapters_found(self, descriptors: List[AdapterDescriptor]) -> None:
        logger.debug(f"Transaction discovery finished: {len(descriptors)} endpoint(s)")
        for panel in self.left_section.get_port_panels():
            setter = getattr(panel, "set_adapter_descriptors", None)
            if setter is not None:
                setter(descriptors)

    def _on_discovery_failed(self, error: Exception) -> None:
        logger.warning(f"Transaction adapter discovery failed: {error}")
        self._log_event(f"Adapter discovery failed: {error}", LogLevel.WARNING)

    # ------------------------------------------------------------------
    # Open / close routing
    # ------------------------------------------------------------------
    def _apply_packet_parser_settings(self, config: PortConfig) -> None:
        settings = self.settings_manager
        config.parser_type = settings.get(ConfigKeys.PACKET_PARSER_TYPE, DEFAULT_PACKET_PARSER_TYPE)
        delimiters = settings.get(ConfigKeys.PACKET_DELIMITERS, list(DEFAULT_PACKET_DELIMITERS))
        config.packet_delimiter = delimiters[0] if delimiters else ""
        config.packet_length = settings.get(ConfigKeys.PACKET_LENGTH, DEFAULT_PACKET_LENGTH)
        config.length_field_offset = settings.get(
            ConfigKeys.PACKET_LENGTH_FIELD_OFFSET, DEFAULT_PACKET_LENGTH_FIELD_OFFSET
        )
        config.length_field_size = settings.get(
            ConfigKeys.PACKET_LENGTH_FIELD_SIZE, DEFAULT_PACKET_LENGTH_FIELD_SIZE
        )
        config.length_field_endian = settings.get(
            ConfigKeys.PACKET_LENGTH_FIELD_ENDIAN, DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
        )
        config.length_includes_header = settings.get(
            ConfigKeys.PACKET_LENGTH_INCLUDES_HEADER, DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
        )
        config.gap_ms = settings.get(ConfigKeys.PACKET_GAP_MS, DEFAULT_PACKET_GAP_MS)

    def handle_open_request(self, config) -> None:
        if isinstance(config, PortConfig):
            self._apply_packet_parser_settings(config)
            self.connection_controller.open_connection(config)
            return
        if isinstance(config, TransactionConnectionConfig):
            if self.transaction_manager is None:
                self._on_transaction_failed(
                    config.name, RuntimeError("Transaction runtime unavailable")
                )
                return
            self.transaction_manager.open_session(config)
            return
        logger.error(f"Unsupported connection config type: {type(config).__name__}")

    def handle_close_request(self, config) -> None:
        if isinstance(config, PortConfig):
            if config.port:
                self.connection_controller.close_connection(config.port)
            return
        if isinstance(config, TransactionConnectionConfig) and self.transaction_manager is not None:
            self.transaction_manager.close_session(config.name)

    def handle_tab_closed(self, endpoint_name: str) -> None:
        if not endpoint_name:
            return
        self.connection_controller.close_connection(endpoint_name)
        if self.transaction_manager is not None:
            self.transaction_manager.close_session(endpoint_name)

    # ------------------------------------------------------------------
    # State/result mapping
    # ------------------------------------------------------------------
    def _set_panel_connected(self, endpoint_name: str, connected: bool) -> None:
        for panel in self.left_section.get_port_panels():
            if self._panel_endpoint_name(panel) == endpoint_name:
                panel.set_connected(connected)
                return

    def on_connection_opened(self, event: PortConnectionEvent) -> None:
        self._set_panel_connected(event.port, True)
        self._log_event(f"[{event.port}] Port opened", LogLevel.SUCCESS)

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        self._set_panel_connected(event.port, False)
        self._log_event(f"[{event.port}] Port closed", LogLevel.INFO)

    def on_error(self, event: PortErrorEvent) -> None:
        logger.error(f"Port Error ({event.port}): {event.message}")
        self._set_panel_connected(event.port, False)
        title = language_manager.get_text("port_title_error")
        detail = language_manager.get_text("port_msg_error_detail").format(
            event.port, event.message
        )
        self.left_section.show_error_message(title, detail)
        self._log_event(f"[{event.port}] Error: {event.message}", LogLevel.ERROR)

    def _on_transaction_opened(self, session_name: str, _descriptor) -> None:
        self._set_panel_connected(session_name, True)
        self._log_event(f"[{session_name}] Transaction session opened", LogLevel.SUCCESS)

    def _on_transaction_closed(self, session_name: str) -> None:
        self._set_panel_connected(session_name, False)
        self._log_event(f"[{session_name}] Transaction session closed", LogLevel.INFO)

    def _on_transaction_failed(self, session_name: str, error: Exception) -> None:
        logger.error(f"Transaction session error ({session_name}): {error}")
        self._set_panel_connected(session_name, False)
        self._log_event(f"[{session_name}] Transaction error: {error}", LogLevel.ERROR)

    def _log_event(self, message: str, level: LogLevel) -> None:
        if hasattr(self.left_section, "log_system_message"):
            self.left_section.log_system_message(
                SystemLogEvent(message=message, level=level.value)
            )

    # ------------------------------------------------------------------
    # Existing Serial-only controls
    # ------------------------------------------------------------------
    def on_tx_broadcast_allowed_changed(self, panel: PortPanel, state: bool) -> None:
        if self._panel_protocol(panel) != ConnectionProtocol.SERIAL:
            return
        port_name = panel.get_port_name()
        if port_name:
            self.connection_controller.set_port_broadcast_state(port_name, state)

    def connect_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel and not panel.is_connected():
            try:
                self.handle_open_request(self._panel_config(panel))
            except Exception as exc:
                logger.warning(f"Connection request rejected: {exc}")

    def disconnect_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel and panel.is_connected():
            try:
                self.handle_close_request(self._panel_config(panel))
            except Exception as exc:
                logger.warning(f"Disconnect request rejected: {exc}")

    def clear_log_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel:
            panel.clear_data_log()
