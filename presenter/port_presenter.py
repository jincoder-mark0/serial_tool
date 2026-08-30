"""
포트 프레젠터 모듈.

MainLeftSection(View)과 ConnectionController(Model) 사이에서 포트 연결/상태와 스캔 결과를
중재합니다. SettingsManager와 PortScanManager는 composition root가 명시적으로 주입합니다.
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
from common.enums import LogLevel
from core.logger import logger
from core.settings_manager import SettingsManager
from model.connection_controller import ConnectionController
from model.port_scan_manager import PortScanManager
from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel
from view.sections.main_left_section import MainLeftSection


class PortPresenter(QObject):
    """PortPanel collection과 연결/스캔 Model 사이의 중재자."""

    def __init__(
        self,
        left_section: MainLeftSection,
        connection_controller: ConnectionController,
        settings_manager: SettingsManager,
        port_scan_manager: PortScanManager,
    ) -> None:
        super().__init__()
        self.left_section = left_section
        self.connection_controller = connection_controller
        self.settings_manager = settings_manager
        self.port_scan_manager = port_scan_manager
        self._connected_panels: WeakSet[PortPanel] = WeakSet()

        self.port_scan_manager.ports_found.connect(self._on_scan_finished)

        self.apply_max_log_lines(
            self.settings_manager.get(ConfigKeys.RX_MAX_LINES, DEFAULT_LOG_MAX_LINES)
        )

        self.scan_ports()
        for panel in self.left_section.get_port_panels():
            self._connect_tab_signals(panel)

        self.left_section.port_tab_added.connect(self._on_port_tab_added)
        self.left_section.port_tab_closed.connect(self.handle_tab_closed)
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def apply_max_log_lines(self, max_lines: int) -> None:
        """모든 PortPanel의 표시 로그 상한을 동일하게 적용합니다."""
        for panel in self.left_section.get_port_panels():
            panel.set_max_log_lines(max_lines)

    def _connect_tab_signals(self, panel: PortPanel) -> None:
        """이 Presenter가 아직 연결하지 않은 PortPanel에만 signal을 연결합니다."""
        if panel in self._connected_panels:
            return

        panel.port_scan_requested.connect(self.scan_ports)
        panel.connect_requested.connect(self.handle_open_request)
        panel.disconnect_requested.connect(
            lambda p=panel: self.handle_close_request(p.get_port_config())
        )
        panel.tx_broadcast_allowed_changed.connect(
            lambda state, p=panel: self.on_tx_broadcast_allowed_changed(p, state)
        )
        self._connected_panels.add(panel)

    def on_tx_broadcast_allowed_changed(self, panel: PortPanel, state: bool) -> None:
        port_name = panel.get_port_name()
        if port_name:
            self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        self._connect_tab_signals(panel)
        panel.set_max_log_lines(
            self.settings_manager.get(ConfigKeys.RX_MAX_LINES, DEFAULT_LOG_MAX_LINES)
        )
        self.scan_ports()

    def scan_ports(self) -> None:
        """비동기 스캔 시작 여부/worker 소유권은 PortScanManager에 위임합니다."""
        self.port_scan_manager.request_scan()

    def _on_scan_finished(self, port_list: List[PortInfo]) -> None:
        logger.debug(f"Scan finished. Found ports: {[item.device for item in port_list]}")
        self.left_section.set_port_list_for_all(port_list)

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

    def handle_open_request(self, config: PortConfig) -> None:
        self._apply_packet_parser_settings(config)
        self.connection_controller.open_connection(config)

    def handle_close_request(self, config: PortConfig) -> None:
        if config and config.port:
            self.connection_controller.close_connection(config.port)

    def handle_tab_closed(self, port_name: str) -> None:
        if port_name:
            self.connection_controller.close_connection(port_name)

    def _log_event(self, message: str, level: LogLevel) -> None:
        if hasattr(self.left_section, "log_system_message"):
            self.left_section.log_system_message(
                SystemLogEvent(message=message, level=level.value)
            )

    def on_connection_opened(self, event: PortConnectionEvent) -> None:
        self.left_section.set_port_connection_state(event.port, True)
        self._log_event(f"[{event.port}] Port opened", LogLevel.SUCCESS)

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        self.left_section.set_port_connection_state(event.port, False)
        self._log_event(f"[{event.port}] Port closed", LogLevel.INFO)

    def on_error(self, event: PortErrorEvent) -> None:
        logger.error(f"Port Error ({event.port}): {event.message}")
        self.left_section.set_port_connection_state(event.port, False)
        title = language_manager.get_text("port_title_error")
        detail = language_manager.get_text("port_msg_error_detail").format(
            event.port, event.message
        )
        self.left_section.show_error_message(title, detail)
        self._log_event(f"[{event.port}] Error: {event.message}", LogLevel.ERROR)

    def connect_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if not panel:
            return
        config = panel.get_port_config()
        if config.port and not self.connection_controller.is_connection_open(config.port):
            self._apply_packet_parser_settings(config)
            self.connection_controller.open_connection(config)
        elif not config.port:
            logger.warning("No port selected")

    def disconnect_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel:
            port_name = panel.get_port_name()
            if port_name and self.connection_controller.is_connection_open(port_name):
                self.connection_controller.close_connection(port_name)

    def clear_log_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel:
            panel.clear_data_log()
