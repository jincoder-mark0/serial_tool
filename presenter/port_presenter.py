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

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtWidgets import QMessageBox

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

        # 탭 닫기 시 연결 정리 (좀비 연결 방지, S-040)
        # MainLeftSection에는 아직 전용 중계 시그널이 없어(범위 밖 변경 최소화),
        # 기존에 이미 공개된 port_tab_panel 접근자(Facade property, LoD 상 허용된
        # 기존 패턴 — MainLeftSection.port_tab_panel은 view/main_window.py 등에서도
        # 직접 사용 중)를 통해 PortTabPanel의 시그널을 직접 구독한다.
        self.left_section.port_tab_panel.port_tab_closed.connect(self.handle_tab_closed)

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

    def stop_pending_scan(self) -> None:
        """
        진행 중인 포트 스캔 스레드를 정리합니다 (앱 종료 시, S-062).

        Logic:
            - 스캔 워커가 없거나 이미 끝났으면 아무 것도 하지 않는다.
            - 실행 중이면 결과를 기다린다(온디맨드 초단명 스레드라 `wait()`이
              곧 반환된다). 종료 도중 스캔이 겹쳐 QThread가 실행 중인 채로
              파괴되면 Qt 경고("QThread: Destroyed while thread is still
              running")나 드문 크래시로 이어질 수 있어(S-059 조사에서 발견),
              앱 종료 전에 반드시 완료를 기다린 뒤 참조를 해제한다.
            - `ports_found` 시그널 연결은 끊지 않는다 — `wait()` 이후에도
              큐잉된 시그널이 있다면 `_on_scan_finished`가 정상적으로 View를
              갱신하는 편이 안전하다(종료 시퀀스는 아직 View를 파괴하지 않는다).

        Note:
            데이터 유실과 무관한 UI 편의 스레드이므로, 종료 순서상 어디에
            두어도 안전하다 — `on_close_requested`에서는 매크로 러너 정리와
            같은 그룹(맨 앞, 백그라운드 스레드 정리 단계)에 배치해 RX 로거의
            "연결 종료 -> processEvents -> 로거 정리" 순서(S-059)를 건드리지
            않는다.
        """
        if self._scan_worker and self._scan_worker.isRunning():
            logger.debug("Waiting for pending port scan to finish before shutdown...")
            self._scan_worker.wait(2000)
        self._scan_worker = None

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

    def _apply_packet_parser_settings(self, config: PortConfig) -> None:
        """
        Preferences에 저장된 패킷 파서 설정을 PortConfig에 실어 보냅니다.

        Logic:
            - PortSettingsWidget(View)에는 파서 설정 UI가 없다(패킷 파서는
              Preferences 다이얼로그의 전역 설정이다). 계층 규율상 Model은
              SettingsManager를 직접 읽지 않으므로, Presenter가 조회한 값을
              DTO에 실어 open_connection()에 전달한다(S-041).
            - 구분자는 목록(PACKET_DELIMITERS) 중 첫 번째 값만 사용한다
              (DelimiterParser는 단일 구분자만 지원).

        Args:
            config (PortConfig): 값을 채워 넣을 연결 설정 DTO (in-place 수정).
        """
        settings = SettingsManager()
        config.parser_type = settings.get(ConfigKeys.PACKET_PARSER_TYPE, 0)
        delimiters = settings.get(ConfigKeys.PACKET_DELIMITERS, ["\\r\\n"])
        config.packet_delimiter = delimiters[0] if delimiters else ""
        config.packet_length = settings.get(ConfigKeys.PACKET_LENGTH, 64)
        # 프레이밍 확장 (S-072)
        config.length_field_offset = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_OFFSET, 0)
        config.length_field_size = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_SIZE, 1)
        config.length_field_endian = settings.get(ConfigKeys.PACKET_LENGTH_FIELD_ENDIAN, "big")
        config.length_includes_header = settings.get(
            ConfigKeys.PACKET_LENGTH_INCLUDES_HEADER, False
        )
        config.gap_ms = settings.get(ConfigKeys.PACKET_GAP_MS, 5)

    def handle_open_request(self, config: PortConfig) -> None:
        """
        포트 열기 요청 처리 (View Signal Slot).

        Args:
            config (PortConfig): 포트 설정 DTO.
        """
        self._apply_packet_parser_settings(config)
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

    def handle_tab_closed(self, port_name: str) -> None:
        """
        포트 탭이 닫혔을 때 처리 (View Signal Slot, S-040).

        Logic:
            - 탭이 닫히면 View에 남아있는 위젯 참조와 무관하게 해당 이름의 연결을
              정리해 좀비 연결(재시도 시 "Connection is already open." 오류)을 방지한다.
            - 해당 이름이 미연결 상태여도 Controller.close_connection()은 무해하게
              통과하므로 별도 방어 로직이 필요 없다.

        Args:
            port_name (str): 닫힌 탭에 설정되어 있던 포트 이름.
        """
        if port_name:
            self.connection_controller.close_connection(port_name)

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

        # View 계층을 통해 에러 메시지 표시.
        # 현재 호출 스택이 풀린 뒤에 띄운다 (S-082) — 포트 에러는 워커를 정리하는
        # 도중에도 발행되므로, 여기서 곧바로 모달을 열면 중첩 이벤트 루프가 돌면서
        # 정리 중이던 객체가 발밑에서 파괴된다.
        if self.left_section:
            parent = self.left_section
            title = language_manager.get_text("port_title_error")
            detail = language_manager.get_text("port_msg_error_detail").format(
                event.port, event.message
            )
            QTimer.singleShot(0, lambda: QMessageBox.critical(parent, title, detail))

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
                self._apply_packet_parser_settings(config)
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