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
from PyQt5.QtWidgets import QMessageBox

from view.sections.main_left_section import MainLeftSection
from view.panels.port_panel import PortPanel
from model.connection_controller import ConnectionController
from model.port_scanner import PortScanWorker
from core.settings_manager import SettingsManager
from core.logger import logger
from common.constants import ConfigKeys
from common.dtos import (
    PortConfig,
    PortInfo,
    PortErrorEvent,
    PortConnectionEvent,
    SystemLogEvent
)


class PortPresenter(QObject):
    """
    포트 설정 및 제어 프레젠터

    PortSettingsWidget(View)와 ConnectionController(Model)를 연결하고,
    포트 스캔, 연결, 해제 등의 로직을 제어합니다.
    """

    def __init__(self, left_section: MainLeftSection, connection_controller: ConnectionController) -> None:
        """
        PortPresenter 초기화

        Logic:
            - 멤버 변수 초기화
            - 초기 포트 스캔 수행
            - 기존 탭 및 새 탭에 대한 시그널 연결
            - Model(ConnectionController) 시그널 연결

        Args:
            left_section (MainLeftSection): 좌측 패널 (포트 탭 및 설정 포함).
            connection_controller (ConnectionController): 포트 제어기 Model.
        """
        super().__init__()
        self.left_section = left_section
        self.connection_controller = connection_controller

        # 스캔 워커 (비동기 실행을 위해 멤버로 유지)
        self._scan_worker: Optional[PortScanWorker] = None

        # 현재 활성 포트 패널 참조
        self.current_port_panel: Optional[PortPanel] = None
        self.update_current_port_panel()

        # 로그 라인 수 설정 적용 (초기화 시)
        settings = SettingsManager()
        max_lines = settings.get(ConfigKeys.RX_MAX_LINES, 2000)

        # LoD 준수: 패널 내부 위젯에 직접 접근하지 않고 Facade 메서드 사용
        if self.current_port_panel:
            self.current_port_panel.set_max_log_lines(max_lines)

        # 초기 포트 스캔 (앱 시작 시점)
        self.scan_ports()

        # 기존 탭들에 대한 시그널 연결 (초기화 시점에 이미 존재하는 탭들)
        # LoD 준수: View가 제공하는 접근자 사용
        count = self.left_section.get_port_tabs_count()
        for i in range(count):
            widget = self.left_section.get_port_panel_at(i)
            if widget:
                self._connect_tab_signals(widget)

        # 새 탭 추가 시그널 연결 (View의 시그널 사용)
        self.left_section.port_tab_added.connect(self._on_port_tab_added)

        # 탭 변경 시 현재 패널 업데이트 (View의 시그널 사용)
        self.left_section.current_tab_changed.connect(self.update_current_port_panel)

        # Model Signal 연결 (DTO 수신)
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def get_active_port_name(self) -> Optional[str]:
        """
        현재 활성화된 탭의 포트 이름을 반환합니다.

        Logic:
            - 현재 활성 패널이 존재하면 해당 패널의 포트 이름 반환

        Returns:
            Optional[str]: 포트 이름. 활성 탭이 없거나 포트가 선택되지 않았으면 None.
        """
        if self.current_port_panel:
            return self.current_port_panel.get_port_name()
        return None

    def _connect_tab_signals(self, panel: PortPanel) -> None:
        """
        개별 포트 패널의 시그널을 Presenter 슬롯에 연결합니다.

        Logic:
            - 중복 연결 방지를 위해 기존 연결 해제 시도 (disconnect)
            - 설정 위젯의 스캔, 연결, 해제 시그널 연결
            - 브로드캐스트 변경 시그널 연결 (람다를 사용하여 위젯 컨텍스트 캡처)

        Args:
            panel (PortPanel): 시그널을 연결할 PortPanel 인스턴스.
        """
        # LoD 준수: Panel이 직접 제공하는 중계 시그널 사용

        # 중복 연결 방지 (안전하게 disconnect 시도)
        try:
            panel.port_scan_requested.disconnect(self.scan_ports)
            panel.connect_requested.disconnect(self.handle_open_request)
            panel.disconnect_requested.disconnect(self.handle_close_request)
        except TypeError:
            pass

        # 시그널 연결
        panel.port_scan_requested.connect(self.scan_ports)
        panel.connect_requested.connect(self.handle_open_request)
        panel.disconnect_requested.connect(self.handle_close_request)

        # Broadcast 체크박스 시그널 연결
        try:
            panel.tx_broadcast_allowed_changed.disconnect()
        except TypeError:
            pass

        # 람다로 위젯 캡처하여 핸들러에 전달
        panel.tx_broadcast_allowed_changed.connect(
            lambda state, w=panel: self.on_tx_broadcast_allowed_changed(w, state)
        )

    def on_tx_broadcast_allowed_changed(self, panel: PortPanel, state: bool) -> None:
        """
        브로드캐스트 허용 상태 변경 핸들러입니다.

        Logic:
            - 위젯에서 포트 이름을 획득 (Facade)
            - 컨트롤러를 통해 해당 포트의 브로드캐스트 상태 업데이트

        Args:
            panel (PortPanel): 시그널을 보낸 PortPanel.
            state (bool): 체크 여부 (True=허용, False=거부).
        """
        port_name = panel.get_port_name()
        if port_name:
            self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        """
        새 탭이 추가되었을 때 호출되는 슬롯입니다.

        Logic:
            - 새 탭의 시그널 연결
            - 전체 탭의 포트 목록 최신화 (일관성 유지)

        Args:
            panel (PortPanel): 추가된 PortPanel.
        """
        self._connect_tab_signals(panel)
        # 탭 추가 시에도 포트 리스트 최신화 (새 탭에 빈 목록이 뜨지 않도록)
        self.scan_ports()

    def update_current_port_panel(self) -> None:
        """
        현재 활성 포트 패널 참조를 업데이트합니다.

        Logic:
            - View(LeftSection)를 통해 현재 활성 패널 획득 (Facade)
            - current_port_panel 멤버 변수 갱신
        """
        # LoD 준수: View의 Facade 메서드 사용
        self.current_port_panel = self.left_section.get_current_port_panel()

    def scan_ports(self) -> None:
        """
        사용 가능한 시리얼 포트 비동기 스캔을 요청합니다.

        Logic:
            1. 이전 스캔이 진행 중이면 중단하지 않고 로그 출력 후 리턴
            2. PortScanWorker 스레드 생성 및 시그널 연결
            3. Worker 시작

        Note:
            Windows 등에서 포트 스캔은 I/O 블로킹을 유발할 수 있으므로 반드시 비동기로 수행해야 합니다.
        """
        if self._scan_worker and self._scan_worker.isRunning():
            logger.debug("Port scan already in progress.")
            return

        logger.debug("Starting async port scan...")
        self._scan_worker = PortScanWorker()
        self._scan_worker.ports_found.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_finished(self, port_list: List[PortInfo]) -> None:
        """
        포트 스캔 완료 핸들러 (UI 업데이트).

        Logic:
            - View 인터페이스를 통해 모든 포트 패널의 목록 갱신
            - DTO(PortInfo) 리스트를 View에 전달

        Args:
            port_list (List[PortInfo]): 검색된 포트 정보 DTO 리스트.
        """
        # 로그용: device 이름만 추출
        port_names = [p.device for p in port_list]
        logger.debug(f"Scan finished. Found ports: {port_names}")

        # LoD 준수: LeftSection을 통해 모든 패널 업데이트 (순회는 View가 하거나 여기서 getter로 순회)
        count = self.left_section.get_port_tabs_count()
        for i in range(count):
            panel = self.left_section.get_port_panel_at(i)
            if panel:
                panel.set_port_list(port_list)

        # 워커 참조 해제
        self._scan_worker = None

    def handle_open_request(self, config: PortConfig) -> None:
        """
        포트 열기 요청 처리 (View Signal Slot).

        Args:
            config (PortConfig): 포트 설정 DTO.
        """
        self.connection_controller.open_connection(config)

    def handle_close_request(self) -> None:
        """
        포트 닫기 요청 처리 (View Signal Slot).

        Logic:
            - 요청을 보낸 위젯(sender)을 식별
            - 해당 위젯에서 현재 설정(포트명) 추출 (Facade)
            - Controller에 닫기 요청
        """
        sender = self.sender()

        # sender가 PortPanel이라고 가정하고 인터페이스 호출 (시그널 중계로 인해 sender는 PortPanel임)
        if sender and hasattr(sender, 'get_port_config'):
            config = sender.get_port_config()
            if config and config.port:
                self.connection_controller.close_connection(config.port)

    def _log_event(self, message: str, level: str) -> None:
        """
        시스템 로그에 이벤트를 기록합니다 (DTO 사용).

        Args:
            message (str): 로그 메시지.
            level (str): 로그 레벨 (SUCCESS, INFO, ERROR 등).
        """
        # LoD 준수: View(LeftSection)의 로깅 인터페이스 사용
        if hasattr(self.left_section, 'log_system_message'):
            event = SystemLogEvent(message=message, level=level)
            self.left_section.log_system_message(event)

    def on_connection_opened(self, event: PortConnectionEvent) -> None:
        """
        포트 열림 이벤트 처리.

        Logic:
            - 해당 포트 이름을 사용하는 탭을 검색
            - UI 연결 상태(버튼 스타일 등)를 'Connected'로 업데이트
            - 시스템 로그에 성공 메시지 기록 (SystemLogEvent)

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        port_name = event.port

        # LoD 준수: LeftSection을 통해 패널 검색
        count = self.left_section.get_port_tabs_count()
        for i in range(count):
            panel = self.left_section.get_port_panel_at(i)
            if panel and panel.get_port_name() == port_name:
                panel.set_connected(True)
                # 탭 제목 업데이트는 Panel 내부 시그널 -> LeftSection 흐름으로 자동 처리됨
                break

        # 시스템 로그 기록
        self._log_event(f"[{port_name}] Port opened", "SUCCESS")

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        """
        포트 닫힘 이벤트 처리.

        Logic:
            - 해당 포트 이름을 사용하는 탭 검색
            - UI 연결 상태를 'Disconnected'로 업데이트
            - 시스템 로그 기록 (SystemLogEvent)

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        port_name = event.port

        # LoD 준수: LeftSection을 통해 패널 검색
        count = self.left_section.get_port_tabs_count()
        for i in range(count):
            panel = self.left_section.get_port_panel_at(i)
            if panel and panel.get_port_name() == port_name:
                panel.set_connected(False)
                break

        # 시스템 로그 기록
        self._log_event(f"[{port_name}] Port closed", "INFO")

    def on_error(self, event: PortErrorEvent) -> None:
        """
        에러 이벤트 처리.

        Logic:
            - 에러 로그(Logger) 기록
            - 연결 시도 중 에러 발생 시 UI 버튼 상태를 'Disconnected'로 복구
            - 사용자에게 팝업(MessageBox)으로 알림
            - 시스템 로그 위젯에 에러 기록 (SystemLogEvent)

        Args:
            event (PortErrorEvent): 포트 에러 이벤트 DTO (port, message).
        """
        logger.error(f"Port Error ({event.port}): {event.message}")

        # 연결 시도 중 에러 발생 시 UI 버튼 상태를 'Disconnected'로 강제 복구
        count = self.left_section.get_port_tabs_count()
        for i in range(count):
            panel = self.left_section.get_port_panel_at(i)
            if panel and panel.get_port_name() == event.port:
                panel.set_connected(False)
                break

        # View 계층을 통해 에러 메시지 표시
        if self.left_section:
            QMessageBox.critical(self.left_section, "Error", f"Port Error ({event.port}): {event.message}")

            # 시스템 로그 기록
            self._log_event(f"[{event.port}] Error: {event.message}", "ERROR")

    def connect_current_port(self) -> None:
        """
        현재 활성화된 탭의 포트 연결을 시도합니다. (단축키 F2 등에서 호출)
        """
        self.update_current_port_panel()
        if self.current_port_panel:
            config = self.current_port_panel.get_port_config()
            port_name = config.port
            if port_name and not self.connection_controller.is_connection_open(port_name):
                self.connection_controller.open_connection(config)
            elif not port_name:
                logger.warning("No port selected")

    def disconnect_current_port(self) -> None:
        """
        현재 활성화된 탭의 포트 연결을 해제합니다. (단축키 F3 등에서 호출)
        """
        self.update_current_port_panel()
        if self.current_port_panel:
            port_name = self.current_port_panel.get_port_name()
            if port_name and self.connection_controller.is_connection_open(port_name):
                self.connection_controller.close_connection(port_name)

    def clear_log_current_port(self) -> None:
        """
        현재 활성화된 탭의 데이터 로그를 지웁니다. (단축키 F5 등에서 호출)
        """
        self.update_current_port_panel()
        if self.current_port_panel:
            self.current_port_panel.clear_data_log()