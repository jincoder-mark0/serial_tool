"""
포트 프레젠터 모듈

포트 설정 뷰(View)와 연결 컨트롤러(Model) 간의 중재자 역할을 수행합니다.

## WHY
* 포트 연결/해제 UI 이벤트 처리 및 상태 반영 로직의 분리
* 다중 포트 탭 관리 및 설정 동기화의 복잡성 관리
* 포트 스캔 비동기화 처리를 통한 UI 프리징 방지

## WHAT
* MainLeftSection(View)과 ConnectionController(Model) 연결
* 포트 스캔 (PortScanWorker) 관리 및 결과 UI 반영
* 연결/해제 요청 처리 및 상태 변경 이벤트(DTO) 처리
* 에러 핸들링 및 시스템 로그 기록

## HOW
* Model의 PortScanWorker를 사용하여 비동기 스캔 수행
* View의 Facade 메서드를 통해 하위 패널 제어 (LoD 준수)
* ConnectionController 메서드 호출 및 Signal 구독
* DTO(PortConfig, PortConnectionEvent, SystemLogEvent)를 사용하여 데이터 교환
"""
from typing import Optional, List

from PyQt5.QtCore import QObject

from view.sections.main_left_section import MainLeftSection
from view.panels.port_panel import PortPanel
from model.connection_controller import ConnectionController
from model.port_scanner import PortScanWorker
from core.settings_manager import SettingsManager
from core.logger import logger
from view.managers.language_manager import language_manager
from common.constants import ConfigKeys
from common.dtos import (
    PortConfig,
    PortInfo,
    PortErrorEvent,
    PortConnectionEvent,
    SystemLogEvent
)


class PortPresenter(QObject):
    """포트 설정 및 제어 프레젠터."""

    def __init__(self, left_section: MainLeftSection, connection_controller: ConnectionController) -> None:
        super().__init__()
        self.left_section = left_section
        self.connection_controller = connection_controller
        self._scan_worker: Optional[PortScanWorker] = None

        settings = SettingsManager()
        max_lines = settings.get(ConfigKeys.RX_MAX_LINES, 2000)
        current_panel = self.left_section.get_current_port_panel()
        if current_panel:
            current_panel.set_max_log_lines(max_lines)

        self.scan_ports()

        for panel in self.left_section.get_port_panels():
            self._connect_tab_signals(panel)

        self.left_section.port_tab_added.connect(self._on_port_tab_added)
        self.left_section.port_tab_closed.connect(self.handle_tab_closed)

        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def get_active_port_name(self) -> Optional[str]:
        panel = self.left_section.get_current_port_panel()
        return panel.get_port_name() if panel else None

    def _connect_tab_signals(self, panel: PortPanel) -> None:
        try:
            panel.port_scan_requested.disconnect(self.scan_ports)
            panel.connect_requested.disconnect(self.handle_open_request)
        except TypeError:
            pass

        panel.port_scan_requested.connect(self.scan_ports)
        panel.connect_requested.connect(self.handle_open_request)

        # disconnect_requested는 인자를 내보내지 않으므로, 연결 시점의 PortPanel을
        # 명시적으로 캡처해 현재 PortConfig를 Presenter 슬롯에 전달한다.
        # 이 방식은 QObject.sender() 런타임 추론에 의존하지 않는다.
        try:
            panel.disconnect_requested.disconnect()
        except TypeError:
            pass
        panel.disconnect_requested.connect(
            lambda p=panel: self.handle_close_request(p.get_port_config())
        )

        try:
            panel.tx_broadcast_allowed_changed.disconnect()
        except TypeError:
            pass
        panel.tx_broadcast_allowed_changed.connect(
            lambda state, p=panel: self.on_tx_broadcast_allowed_changed(p, state)
        )

    def on_tx_broadcast_allowed_changed(self, panel: PortPanel, state: bool) -> None:
        port_name = panel.get_port_name()
        if port_name:
            self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        self._connect_tab_signals(panel)
        self.scan_ports()

    def scan_ports(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            logger.debug("Port scan already in progress.")
            return
        logger.debug("Starting async port scan...")
        self._scan_worker = PortScanWorker()
        self._scan_worker.ports_found.connect(self._on_scan_finished)
        self._scan_worker.start()

    def stop_pending_scan(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            logger.debug("Waiting for pending port scan to finish before shutdown...")
            self._scan_worker.wait(2000)
        self._scan_worker = None

    def _on_scan_finished(self, port_list: List[PortInfo]) -> None:
        port_names = [p.device for p in port_list]
        logger.debug(f"Scan finished. Found ports: {port_names}")
        self.left_section.set_port_list_for_all(port_list)
        self._scan_worker = None

    def _apply_packet_parser_settings(self, config: PortConfig) -> None:
        settings = SettingsManager()
        config.parser_type = settings.get(ConfigKeys.PACKET_PARSER_TYPE, 0)
        delimiters = settings.get(ConfigKeys.PACKET_DELIMITERS, ["\\r\\n"])
        config.packet_delimiter = delimiters[0] if delimiters else ""
        config.packet_length = settings.get(ConfigKeys.PACKET_LENGTH, 64)
        config.length_field_offset = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_OFFSET, 0)
        config.length_field_size = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_SIZE, 1)
        config.length_field_endian = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_ENDIAN, "big")
        config.length_includes_header = settings.get(
            ConfigKeys.PACKET_LENGTH_INCLUDES_HEADER, False
        )
        config.gap_ms = settings.get(ConfigKeys.PACKET_GAP_MS, 5)

    def handle_open_request(self, config: PortConfig) -> None:
        self._apply_packet_parser_settings(config)
        self.connection_controller.open_connection(config)

    def handle_close_request(self, config: PortConfig) -> None:
        """명시적으로 전달된 PortConfig를 사용해 연결 해제를 요청한다."""
        if config and config.port:
            self.connection_controller.close_connection(config.port)

    def handle_tab_closed(self, port_name: str) -> None:
        if port_name:
            self.connection_controller.close_connection(port_name)

    def _log_event(self, message: str, level: str) -> None:
        if hasattr(self.left_section, 'log_system_message'):
            event = SystemLogEvent(message=message, level=level)
            self.left_section.log_system_message(event)

    def on_connection_opened(self, event: PortConnectionEvent) -> None:
        port_name = event.port
        self.left_section.set_port_connection_state(port_name, True)
        self._log_event(f"[{port_name}] Port opened", "SUCCESS")

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        port_name = event.port
        self.left_section.set_port_connection_state(port_name, False)
        self._log_event(f"[{port_name}] Port closed", "INFO")

    def on_error(self, event: PortErrorEvent) -> None:
        logger.error(f"Port Error ({event.port}): {event.message}")
        self.left_section.set_port_connection_state(event.port, False)
        if self.left_section:
            title = language_manager.get_text("port_title_error")
            detail = language_manager.get_text("port_msg_error_detail").format(
                event.port, event.message
            )
            self.left_section.show_error_message(title, detail)
            self._log_event(f"[{event.port}] Error: {event.message}", "ERROR")

    def connect_current_port(self) -> None:
        panel = self.left_section.get_current_port_panel()
        if panel:
            config = panel.get_port_config()
            port_name = config.port
            if port_name and not self.connection_controller.is_connection_open(port_name):
                self._apply_packet_parser_settings(config)
                self.connection_controller.open_connection(config)
            elif not port_name:
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