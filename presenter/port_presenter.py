"""
포트 프레젠터 모듈

포트 설정 뷰(PortSettingsWidget)와 연결 컨트롤러(ConnectionController) 간의 중재자 역할을 수행합니다.

## WHY
* 포트 연결/해제 UI 이벤트 처리 및 상태 반영 로직의 분리
* 다중 포트 탭 관리 및 설정 동기화의 복잡성 관리
* 포트 스캔 비동기화 처리를 통한 UI 프리징 방지
* 시스템 로그 및 에러 메시지의 통합 관리

## WHAT
* PortSettingsWidget(View)와 ConnectionController(Model) 연결
* 포트 스캔 (PortScanWorker) 관리 및 결과 UI 반영
* 연결/해제 요청 처리 및 상태 변경 이벤트(DTO) 처리
* 에러 핸들링 및 시스템 로그 기록

## HOW
* Model의 PortScanWorker를 사용하여 비동기 스캔 수행
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
        if self.current_port_panel and hasattr(self.current_port_panel, 'data_log_widget'):
            self.current_port_panel.data_log_widget.set_max_lines(max_lines)

        # 초기 포트 스캔 (앱 시작 시점)
        self.scan_ports()

        # 기존 탭들에 대한 시그널 연결 (초기화 시점에 이미 존재하는 탭들)
        for i in range(self.left_section.port_tab_panel.count()):
            widget = self.left_section.port_tab_panel.widget(i)
            self._connect_tab_signals(widget)

        # 새 탭 추가 시그널 연결
        self.left_section.port_tab_panel.port_tab_added.connect(self._on_port_tab_added)

        # 탭 변경 시 현재 패널 업데이트
        self.left_section.port_tab_panel.currentChanged.connect(self.update_current_port_panel)

        # Model Signal 연결 (DTO 수신)
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def get_active_port_name(self) -> Optional[str]:
        """
        현재 활성화된 탭의 포트 이름을 반환합니다.

        Returns:
            Optional[str]: 포트 이름. 활성 탭이 없거나 포트가 선택되지 않았으면 None.
        """
        if self.current_port_panel and hasattr(self.current_port_panel, 'get_port_name'):
            return self.current_port_panel.get_port_name()
        return None

    def _connect_tab_signals(self, widget: PortPanel) -> None:
        """
        개별 포트 패널의 시그널을 Presenter 슬롯에 연결합니다.

        Logic:
            - 중복 연결 방지를 위해 기존 연결 해제 시도 (disconnect)
            - 설정 위젯의 스캔, 연결, 해제 시그널 연결
            - 브로드캐스트 변경 시그널 연결 (람다를 사용하여 위젯 컨텍스트 캡처)

        Args:
            widget (PortPanel): 시그널을 연결할 PortPanel 인스턴스.
        """
        if hasattr(widget, 'port_settings_widget'):
            settings_widget = widget.port_settings_widget

            # 중복 연결 방지를 위해 disconnect 시도 (실패 시 무시)
            try:
                settings_widget.port_scan_requested.disconnect(self.scan_ports)
                settings_widget.connect_requested.disconnect(self.handle_open_request)
                settings_widget.disconnect_requested.disconnect(self.handle_close_request)
            except TypeError:
                pass

            # 시그널 연결
            settings_widget.port_scan_requested.connect(self.scan_ports)
            settings_widget.connect_requested.connect(self.handle_open_request)
            settings_widget.disconnect_requested.connect(self.handle_close_request)

        # Broadcast 체크박스 시그널 연결
        if hasattr(widget, 'tx_broadcast_allowed_changed'):
            try:
                # widget 파라미터를 lambda로 캡처하여 어떤 탭인지 식별
                widget.tx_broadcast_allowed_changed.disconnect()
            except TypeError:
                pass

            # 람다로 위젯 캡처하여 핸들러에 전달
            widget.tx_broadcast_allowed_changed.connect(
                lambda state, w=widget: self.on_tx_broadcast_allowed_changed(w, state)
            )

    def on_tx_broadcast_allowed_changed(self, widget: PortPanel, state: bool) -> None:
        """
        브로드캐스트 허용 상태 변경 핸들러입니다.

        Logic:
            - 위젯에서 포트 이름을 획득
            - 컨트롤러를 통해 해당 포트의 브로드캐스트 상태 업데이트

        Args:
            widget (PortPanel): 시그널을 보낸 PortPanel.
            state (bool): 체크 여부 (True=허용, False=거부).
        """
        if hasattr(widget, 'get_port_name'):
            port_name = widget.get_port_name()
            if port_name:
                self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, widget: PortPanel) -> None:
        """
        새 탭이 추가되었을 때 호출되는 슬롯입니다.

        Logic:
            - 새 탭의 시그널 연결
            - 전체 탭의 포트 목록 최신화 (일관성 유지)

        Args:
            widget (PortPanel): 추가된 PortPanel.
        """
        self._connect_tab_signals(widget)
        # 탭 추가 시에도 포트 리스트 최신화 (새 탭에 빈 목록이 뜨지 않도록)
        self.scan_ports()

    def update_current_port_panel(self) -> None:
        """
        현재 활성 포트 패널 참조를 업데이트합니다.

        Logic:
            - View(PortTabPanel)에서 현재 인덱스의 위젯을 가져옴
            - current_port_panel 멤버 변수 갱신
        """
        index = self.left_section.port_tab_panel.currentIndex()
        if index >= 0:
            widget = self.left_section.port_tab_panel.widget(index)
            if isinstance(widget, PortPanel):
                self.current_port_panel = widget
            else:
                self.current_port_panel = None

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
            - 모든 포트 패널(탭)을 순회하며 콤보박스 목록 갱신
            - DTO(PortInfo) 리스트를 View에 전달

        Args:
            port_list (List[PortInfo]): 검색된 포트 정보 DTO 리스트.
        """
        # 로그용: device 이름만 추출
        port_names = [p.device for p in port_list]
        logger.debug(f"Scan finished. Found ports: {port_names}")

        # 모든 포트 패널의 리스트를 업데이트
        count = self.left_section.port_tab_panel.count()
        for i in range(count):
            widget = self.left_section.port_tab_panel.widget(i)
            # PortPanel인지 확인 (플러스 탭 제외)
            if hasattr(widget, 'port_settings_widget'):
                widget.port_settings_widget.set_port_list(port_list)

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
            - 해당 위젯의 현재 설정에서 포트 이름을 추출
            - Controller에 닫기 요청
        """
        sender = self.sender()

        if sender and hasattr(sender, 'get_current_config'):
            config = sender.get_current_config()
            port_name = config.port
            if port_name:
                self.connection_controller.close_connection(port_name)

    def _log_event(self, message: str, level: str) -> None:
        """
        시스템 로그에 이벤트를 기록합니다 (DTO 사용).

        Args:
            message (str): 로그 메시지.
            level (str): 로그 레벨 (SUCCESS, INFO, ERROR 등).
        """
        if hasattr(self.left_section, 'system_log_widget'):
            event = SystemLogEvent(message=message, level=level)
            self.left_section.system_log_widget.append_log(event)

    def on_connection_opened(self, event: PortConnectionEvent) -> None:
        """
        포트 열림 이벤트 처리.

        Logic:
            - 해당 포트 이름을 사용하는 탭을 검색
            - UI 연결 상태(버튼 스타일 등)를 'Connected'로 업데이트
            - 탭 제목에 포트 이름 반영
            - 시스템 로그에 성공 메시지 기록 (SystemLogEvent)

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        port_name = event.port
        # 모든 탭을 순회하며 해당 포트를 사용하는 패널 찾기
        for i in range(self.left_section.port_tab_panel.count()):
            widget = self.left_section.port_tab_panel.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(True)

                # 탭 제목 업데이트
                self.left_section.port_tab_panel.setTabText(i, widget.get_tab_title())
                break

        # 시스템 로그 기록
        self._log_event(f"[{port_name}] Port opened", "SUCCESS")

    def on_connection_closed(self, event: PortConnectionEvent) -> None:
        """
        포트 닫힘 이벤트 처리.

        Logic:
            - 해당 포트 이름을 사용하는 탭 검색
            - UI 연결 상태를 'Disconnected'로 업데이트
            - 탭 제목 초기화
            - 시스템 로그 기록 (SystemLogEvent)

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        port_name = event.port
        for i in range(self.left_section.port_tab_panel.count()):
            widget = self.left_section.port_tab_panel.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(False)

                # 탭 제목 업데이트 (연결 해제 상태 반영)
                self.left_section.port_tab_panel.setTabText(i, widget.get_tab_title())
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
        # (Connecting 상태에서 에러가 났을 때 UI가 꼬이는 것을 방지)
        count = self.left_section.port_tab_panel.count()
        for i in range(count):
            widget = self.left_section.port_tab_panel.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == event.port:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(False)
                break

        # View 계층을 통해 에러 메시지 표시 (View가 없는 경우 대비)
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
            config = self.current_port_panel.port_settings_widget.get_current_config()
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
        if self.current_port_panel and hasattr(self.current_port_panel, 'data_log_widget'):
            self.current_port_panel.data_log_widget.on_clear_data_log_clicked()