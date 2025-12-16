"""
포트 프레젠터 모듈

포트 설정 및 제어를 위한 Presenter입니다.

## WHY
* 포트 연결/해제 UI 이벤트 처리
* 포트 상태 변경을 View에 반영
* 다중 포트 탭 관리 및 설정 동기화
* 단축키 기능 제공

## WHAT
* PortSettingsWidget(View)와 ConnectionController(Model) 연결
* 포트 스캔 및 모든 탭 목록 동기화
* 연결/해제 토글 처리
* 포트 상태별 UI 업데이트
* 에러 처리 및 사용자 알림

## HOW
* MainLeftSection의 포트 탭 관리
* ConnectionController Signal을 View 업데이트로 변환
* 현재 활성 탭 추적 및 설정 적용
* QMessageBox로 에러 알림
* 시스템 로그에 이벤트 기록
"""
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QMessageBox
import serial.tools.list_ports
from typing import Optional

from view.sections.main_left_section import MainLeftSection
from model.connection_controller import ConnectionController
from core.settings_manager import SettingsManager
from core.logger import logger
from common.constants import ConfigKeys
from common.dtos import PortConfig

class PortPresenter(QObject):
    """
    포트 설정 및 제어 Presenter

    PortSettingsWidget(View)와 ConnectionController(Model)를 연결합니다.
    """
    def __init__(self, left_section: MainLeftSection, connection_controller: ConnectionController) -> None:
        """
        PortPresenter 초기화

        Args:
            left_section: 좌측 패널 (포트 탭 및 설정 포함)
            connection_controller: 포트 제어기 Model
        """
        super().__init__()
        self.left_section = left_section
        self.connection_controller = connection_controller

        # 현재 활성 포트 패널 가져오기
        self.current_port_panel = None
        self.update_current_port_panel()

        # 로그 라인 수 설정 적용
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

        # Model Signal 연결
        self.connection_controller.connection_opened.connect(self.on_connection_opened)
        self.connection_controller.connection_closed.connect(self.on_connection_closed)
        self.connection_controller.error_occurred.connect(self.on_error)

    def get_active_port_name(self) -> Optional[str]:
        """
        현재 활성화된 탭의 포트 이름을 반환

        Returns:
            Optional[str]: 포트 이름 (없으면 None)
        """
        if self.current_port_panel and hasattr(self.current_port_panel, 'get_port_name'):
            return self.current_port_panel.get_port_name()
        return None

    def _connect_tab_signals(self, widget) -> None:
        """
        개별 포트 패널의 시그널을 Presenter 슬롯에 연결

        Args:
            widget: PortPanel 인스턴스
        """
        if hasattr(widget, 'port_settings_widget'):
            settings_widget = widget.port_settings_widget

            # 중복 연결 방지를 위해 disconnect 시도
            try:
                settings_widget.port_scan_requested.disconnect(self.scan_ports)
                settings_widget.port_open_requested.disconnect(self.handle_open_request)
                settings_widget.port_close_requested.disconnect(self.handle_close_request)
            except TypeError:
                pass

            # 시그널 연결
            settings_widget.port_scan_requested.connect(self.scan_ports)
            settings_widget.port_open_requested.connect(self.handle_open_request)
            settings_widget.port_close_requested.connect(self.handle_close_request)

        # Broadcast 체크박스 시그널 연결
        if hasattr(widget, 'broadcast_allow_changed'):
            try:
                # widget 파라미터를 lambda로 캡처하여 어떤 탭인지 식별
                widget.broadcast_allow_changed.disconnect()
            except TypeError:
                pass

            # 람다로 위젯 캡처
            widget.broadcast_allow_changed.connect(lambda state, w=widget: self.on_broadcast_changed(w, state))

    def on_broadcast_changed(self, widget, state: bool) -> None:
        """
        브로드캐스트 허용 상태 변경 핸들러

        Args:
            widget: 시그널을 보낸 PortPanel
            state: 체크 여부
        """
        if hasattr(widget, 'get_port_name'):
            port_name = widget.get_port_name()
            if port_name:
                self.connection_controller.set_port_broadcast_state(port_name, state)

    def _on_port_tab_added(self, widget) -> None:
        """
        새 탭이 추가되었을 때 호출되는 슬롯

        Logic:
            - 시그널 연결
            - 전체 탭의 포트 목록 최신화 (일관성 유지)

        Args:
            widget: 추가된 PortPanel
        """
        self._connect_tab_signals(widget)
        self.scan_ports()

    def update_current_port_panel(self) -> None:
        """
        현재 활성 포트 패널 참조 업데이트 및 Model의 활성 연결 이름 업데이트

        Logic:
            - View에서 현재 활성 탭의 PortPanel을 가져옴
            - Model의 `set_active_connection`을 호출하여 활성 연결을 명시적으로 설정
        """
        index = self.left_section.port_tab_panel.currentIndex()
        if index >= 0:
            widget = self.left_section.port_tab_panel.widget(index)
            if hasattr(widget, 'port_settings_widget'):
                self.current_port_panel = widget

    def scan_ports(self) -> None:
        """
        사용 가능한 시리얼 포트 스캔 및 모든 탭의 UI 업데이트

        Logic:
            1. pyserial을 이용해 시스템의 COM 포트 목록을 가져옴
            2. 정렬 후 모든 포트 탭을 순회
            3. 각 탭의 set_port_list를 호출하여 목록 갱신
            4. 각 탭은 내부적으로 기존 선택값을 유지하려 시도함
        """
        logger.debug("Starting port scan...")   # 추후 제거
        ports = [port.device for port in serial.tools.list_ports.comports()]
        ports.sort()
        logger.debug(f"Found ports: {ports}")   # 추후 제거

        # 모든 포트 패널의 리스트를 업데이트
        count = self.left_section.port_tab_panel.count()
        for i in range(count):
            widget = self.left_section.port_tab_panel.widget(i)
            # PortPanel인지 확인 (플러스 탭 제외)
            if hasattr(widget, 'port_settings_widget'):
                widget.port_settings_widget.set_port_list(ports)

    def handle_open_request(self, config: PortConfig) -> None:
        """
        포트 열기 요청 처리 (View Signal Slot)

        Args:
            config (PortConfig): 포트 설정 DTO
        """
        self.connection_controller.open_connection(config)

    def handle_close_request(self) -> None:
        """
        포트 닫기 요청 처리 (View Signal Slot)

        요청을 보낸 위젯을 찾아 해당 포트를 닫습니다.
        """
        sender = self.sender()

        if sender and hasattr(sender, 'get_current_config'):
            config = sender.get_current_config()
            port_name = config.port
            if port_name:
                self.connection_controller.close_connection(port_name)

    def on_connection_opened(self, port_name: str) -> None:
        """
        포트 열림 이벤트 처리

        Logic:
            - 해당 포트를 사용하는 탭 찾기
            - UI 연결 상태 업데이트
            - 탭 제목 업데이트
            - 시스템 로그 기록

        Args:
            port_name (str): 열린 포트 이름
        """
        # 모든 탭을 순회하며 해당 포트를 사용하는 패널 찾기
        for i in range(self.left_section.port_tab_panel.count()):
            widget = self.left_section.port_tab_panel.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(True)

                # 탭 제목 업데이트
                self.left_section.update_tab_title(i, port_name)
                break

        # 시스템 로그 기록
        if hasattr(self.left_section, 'system_log_widget'):
            self.left_section.system_log_widget.log(f"[{port_name}] Port opened", "SUCCESS")

    def on_connection_closed(self, port_name: str) -> None:
        """
        포트 닫힘 이벤트 처리

        Logic:
            - 해당 포트를 사용하는 탭 찾기
            - UI 연결 해제 상태 업데이트
            - 탭 제목 초기화
            - 시스템 로그 기록

        Args:
            port_name (str): 닫힌 포트 이름
        """
        for i in range(self.left_section.port_tab_panel.count()):
            widget = self.left_section.port_tab_panel.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(False)

                # 탭 제목 초기화
                self.left_section.update_tab_title(i, "-")
                break

        # 시스템 로그 기록
        if hasattr(self.left_section, 'system_log_widget'):
            self.left_section.system_log_widget.log(f"[{port_name}] Port closed", "INFO")

    def on_error(self, port_name: str, message: str) -> None:
        """
        에러 이벤트 처리

        Args:
            port_name (str): 에러 발생 포트
            message (str): 에러 메시지
        """
        logger.error(f"Port Error ({port_name}): {message}")
        QMessageBox.critical(self.left_section, "Error", f"Port Error ({port_name}): {message}")

        # 시스템 로그 기록
        if hasattr(self.left_section, 'system_log_widget'):
            self.left_section.system_log_widget.log(f"[{port_name}] Error: {message}", "ERROR")

        # 에러 발생 시 해당 포트 UI 동기화 (필요 시)
        # on_connection_closed가 호출되지 않는 에러 상황(예: 열기 실패)에 대비해 UI 상태 리셋 가능

    def connect_current_port(self) -> None:
        """현재 포트 연결 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel:
            config = self.current_port_panel.port_settings_widget.get_current_config()
            port_name = config.port
            if port_name and not self.connection_controller.is_connection_open(port_name):
                self.connection_controller.open_connection(config)
            elif not port_name:
                logger.warning("No port selected")

    def disconnect_current_port(self) -> None:
        """현재 포트 연결 해제 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel:
            port_name = self.current_port_panel.get_port_name()
            if port_name and self.connection_controller.is_connection_open(port_name):
                self.connection_controller.close_connection(port_name)

    def clear_log_current_port(self) -> None:
        """현재 포트의 로그 지우기 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel and hasattr(self.current_port_panel, 'data_log_widget'):
            self.current_port_panel.data_log_widget.on_clear_data_log_clicked()
