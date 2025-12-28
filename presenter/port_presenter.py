"""
포트 프레젠터 모듈

포트 설정 뷰(View Interface)와 연결 컨트롤러(Model) 간의 중재자 역할을 수행합니다.
구체적인 UI 구현체(Panel, Section) 대신 인터페이스(Protocol)에 의존하여 결합도를 낮춥니다.

## WHY
* 포트 연결/해제 UI 이벤트 처리 및 상태 반영 로직의 분리 (MVP)
* 다중 포트 탭 관리 및 설정 동기화의 복잡성 관리
* 포트 스캔 비동기화 처리를 통한 UI 프리징 방지
* View 구현체 교체 시에도 비즈니스 로직 보존 (DIP 준수)

## WHAT
* IPortContainerView(View)와 ConnectionController(Model) 연결
* 포트 스캔 (PortScanWorker) 관리 및 결과 UI 반영
* 연결/해제 요청 처리 및 상태 변경 이벤트(DTO) 처리
* 에러 핸들링 및 시스템 로그 기록

## HOW
* IPortContainerView 및 IPortView 인터페이스를 통해 UI 제어
* Model의 PortScanWorker를 사용하여 비동기 스캔 수행
* ConnectionController 메서드 호출 및 Signal 구독
* DTO(PortConfig, PortConnectionEvent, SystemLogEvent)를 사용하여 데이터 교환
"""
from typing import Optional, List, cast

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QMessageBox, QWidget

from view.interfaces import IPortContainerView, IPortView
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

    def __init__(self, view: IPortContainerView, connection_controller: ConnectionController) -> None:
        """
        PortPresenter 초기화

        Logic:
            - 멤버 변수 초기화
            - 초기 포트 스캔 수행
            - 기존 탭 및 새 탭에 대한 시그널 연결
            - Model(ConnectionController) 시그널 연결

        Args:
            view (IPortContainerView): 포트 탭 컨테이너 뷰 인터페이스.
            connection_controller (ConnectionController): 포트 제어기 Model.
        """
        super().__init__()
        self.view = view
        self.connection_controller = connection_controller

        # 스캔 워커 (비동기 실행을 위해 멤버로 유지)
        self._scan_worker: Optional[PortScanWorker] = None

        # 현재 활성 포트 뷰 참조
        self.current_port_view: Optional[IPortView] = None
        self.update_current_port_view()

        # 로그 라인 수 설정 적용 (초기화 시)
        settings = SettingsManager()
        max_lines = settings.get(ConfigKeys.RX_MAX_LINES, 2000)

        # LoD 준수: 패널 내부 위젯에 직접 접근하지 않고 Interface 메서드 사용
        if self.current_port_view:
            self.current_port_view.set_max_log_lines(max_lines)

        # 초기 포트 스캔 (앱 시작 시점)
        self.scan_ports()

        # 기존 탭들에 대한 시그널 연결 (초기화 시점에 이미 존재하는 탭들)
        # LoD 준수: View가 제공하는 접근자 사용
        count = self.view.get_port_tabs_count()
        for i in range(count):
            port_view = self.view.get_port_panel_at(i)
            if port_view:
                self._connect_tab_signals(port_view)

        # 새 탭 추가 시그널 연결 (View Interface 시그널)
        self.view.port_tab_added.connect(self._on_port_tab_added)

        # 탭 변경 시 현재 패널 업데이트 (View Interface 시그널)
        self.view.current_tab_changed.connect(self.update_current_port_view)

        # Model Signal 연결 (DTO 수신)
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def get_active_port_name(self) -> Optional[str]:
        """
        현재 활성화된 탭의 포트 이름을 반환합니다.

        Logic:
            - 현재 활성 뷰가 존재하면 해당 뷰의 포트 이름 반환

        Returns:
            Optional[str]: 포트 이름. 활성 탭이 없거나 포트가 선택되지 않았으면 None.
        """
        if self.current_port_view:
            return self.current_port_view.get_port_name()
        return None

    def _connect_tab_signals(self, port_view: IPortView) -> None:
        """
        개별 포트 뷰(탭)의 시그널을 Presenter 슬롯에 연결합니다.

        Logic:
            - 중복 연결 방지를 위해 기존 연결 해제 시도 (disconnect)
            - 설정 위젯의 스캔, 연결, 해제 시그널 연결
            - 브로드캐스트 변경 시그널 연결 (람다를 사용하여 위젯 컨텍스트 캡처)

        Args:
            port_view (IPortView): 시그널을 연결할 포트 뷰 인터페이스.
        """
        # Interface Signal 사용

        # 중복 연결 방지 (안전하게 disconnect 시도)
        try:
            port_view.port_scan_requested.disconnect(self.scan_ports)
            port_view.connect_requested.disconnect(self.handle_open_request)
            port_view.disconnect_requested.disconnect(self.handle_close_request)
        except TypeError:
            pass

        # 시그널 연결
        port_view.port_scan_requested.connect(self.scan_ports)
        port_view.connect_requested.connect(self.handle_open_request)
        port_view.disconnect_requested.connect(self.handle_close_request)

        # Broadcast 체크박스 시그널 연결
        try:
            port_view.tx_broadcast_allowed_changed.disconnect()
        except TypeError:
            pass

        # 람다로 뷰 인스턴스 캡처하여 핸들러에 전달
        port_view.tx_broadcast_allowed_changed.connect(
            lambda state, v=port_view: self.on_tx_broadcast_allowed_changed(v, state)
        )

    def on_tx_broadcast_allowed_changed(self, port_view: IPortView, state: bool) -> None:
        """
        브로드캐스트 허용 상태 변경 핸들러입니다.

        Logic:
            - 뷰에서 포트 이름을 획득 (Interface)
            - 컨트롤러를 통해 해당 포트의 브로드캐스트 상태 업데이트

        Args:
            port_view (IPortView): 시그널을 보낸 뷰.
            state (bool): 체크 여부 (True=허용, False=거부).
        """
        port_name = port_view.get_port_name()
        if port_name:
            self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, port_view: IPortView) -> None:
        """
        새 탭이 추가되었을 때 호출되는 슬롯입니다.

        Logic:
            - 새 탭의 시그널 연결
            - 전체 탭의 포트 목록 최신화 (일관성 유지)

        Args:
            port_view (IPortView): 추가된 포트 뷰.
        """
        self._connect_tab_signals(port_view)
        # 탭 추가 시에도 포트 리스트 최신화 (새 탭에 빈 목록이 뜨지 않도록)
        self.scan_ports()

    def update_current_port_view(self) -> None:
        """
        현재 활성 포트 뷰 참조를 업데이트합니다.

        Logic:
            - View(IPortContainerView)를 통해 현재 활성 뷰 획득
            - current_port_view 멤버 변수 갱신
        """
        # LoD 준수: View의 Interface 메서드 사용
        self.current_port_view = self.view.get_current_port_panel()

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

        # LoD 준수: View Interface를 통해 모든 패널 업데이트
        count = self.view.get_port_tabs_count()
        for i in range(count):
            panel = self.view.get_port_panel_at(i)
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
            - 요청을 보낸 객체(sender)를 식별
            - 해당 객체(View Interface)에서 현재 설정(포트명) 추출
            - Controller에 닫기 요청
        """
        sender = self.sender()

        # sender가 IPortView 인터페이스를 구현한다고 가정 (Duck Typing)
        # Protocol은 hasattr로 체크하기 어려울 수 있으나, 런타임 객체는 메서드를 가짐
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
        # LoD 준수: View(Container)의 로깅 인터페이스 사용
        event = SystemLogEvent(message=message, level=level)
        self.view.log_system_message(event)

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

        # LoD 준수: View Interface를 통해 패널 검색
        count = self.view.get_port_tabs_count()
        for i in range(count):
            panel = self.view.get_port_panel_at(i)
            if panel and panel.get_port_name() == port_name:
                panel.set_connected(True)
                # 탭 제목 업데이트는 View 내부 로직(Signal Chain)으로 자동 처리됨
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

        # LoD 준수: View Interface를 통해 패널 검색
        count = self.view.get_port_tabs_count()
        for i in range(count):
            panel = self.view.get_port_panel_at(i)
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
        count = self.view.get_port_tabs_count()
        for i in range(count):
            panel = self.view.get_port_panel_at(i)
            if panel and panel.get_port_name() == event.port:
                panel.set_connected(False)
                break

        # View 인터페이스를 통해 에러 메시지 표시
        self.view.show_error("Error", f"Port Error ({event.port}): {event.message}")

        # 시스템 로그 기록
        self._log_event(f"[{event.port}] Error: {event.message}", "ERROR")
