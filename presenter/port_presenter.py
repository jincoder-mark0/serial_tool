"""
포트 프레젠터 모듈

포트 설정 및 제어를 위한 Presenter입니다.

## WHY
* 포트 연결/해제 UI 이벤트 처리
* 포트 상태 변경을 View에 반영
* 다중 포트 탭 관리
* 단축키 기능 제공

## WHAT
* PortSettingsWidget(View)와 PortController(Model) 연결
* 포트 스캔 및 목록 업데이트
* 연결/해제 토글 처리
* 포트 상태별 UI 업데이트
* 에러 처리 및 사용자 알림

## HOW
* MainLeftSection의 포트 탭 관리
* PortController Signal을 View 업데이트로 변환
* 현재 활성 탭 추적 및 설정 적용
* QMessageBox로 에러 알림
* 시스템 로그에 이벤트 기록
"""
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QMessageBox
import serial.tools.list_ports

from view.sections.main_left_section import MainLeftSection
from model.port_controller import PortController
from core.settings_manager import SettingsManager
from core.logger import logger
from constants import ConfigKeys

class PortPresenter(QObject):
    """
    포트 설정 및 제어 Presenter

    PortSettingsWidget(View)와 PortController(Model)를 연결합니다.
    """
    def __init__(self, left_panel: MainLeftSection, port_controller: PortController) -> None:
        """
        PortPresenter 초기화

        Args:
            left_panel: 좌측 패널 (포트 탭 및 설정 포함)
            port_controller: 포트 제어기 Model
        """
        super().__init__()
        self.left_panel = left_panel

        # 현재 활성 포트 패널 가져오기
        self.current_port_panel = None
        self.update_current_port_panel()

        self.port_controller = port_controller

        # 설정에서 max_lines 읽어서 적용
        settings = SettingsManager()
        max_lines = settings.get(ConfigKeys.RX_MAX_LINES, 2000)
        if self.current_port_panel and hasattr(self.current_port_panel, 'received_area_widget'):
            self.current_port_panel.received_area_widget.set_max_lines(max_lines)

        # 초기 포트 스캔
        self.scan_ports()

        # View Signal 연결 (현재 포트 패널의 설정 위젯에서)
        if self.current_port_panel:
            self.current_port_panel.port_settings_widget.port_scan_requested.connect(self.scan_ports)
            # 참고: connect_btn은 자체 핸들러가 있지만, 여기서 직접 연결하여 오버라이드
            # 기존 핸들러 연결 해제 후 재연결
            try:
                self.current_port_panel.port_settings_widget.connect_btn.clicked.disconnect()
            except:
                pass
            self.current_port_panel.port_settings_widget.connect_btn.clicked.connect(self.handle_connect_click)

        # Model Signal 연결
        self.port_controller.port_opened.connect(self.on_port_opened)
        self.port_controller.port_closed.connect(self.on_port_closed)
        self.port_controller.error_occurred.connect(self.on_error)

    def update_current_port_panel(self) -> None:
        """현재 활성 포트 패널 참조 업데이트"""
        index = self.left_panel.port_tabs.currentIndex()
        if index >= 0:
            widget = self.left_panel.port_tabs.widget(index)
            if hasattr(widget, 'port_settings_widget'):
                self.current_port_panel = widget

    def scan_ports(self) -> None:
        """사용 가능한 시리얼 포트 스캔 및 UI 업데이트"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if self.current_port_panel:
            self.current_port_panel.port_settings_widget.set_port_list(ports)

    def handle_connect_click(self) -> None:
        """
        연결 버튼 클릭 처리

        Logic:
            - 현재 탭의 포트 설정 가져오기
            - 포트 선택 여부 확인
            - 포트 열림 상태에 따라 연결/해제 토글
        """
        if not self.current_port_panel:
            return

        # 현재 패널의 설정 가져오기
        config = self.current_port_panel.port_settings_widget.get_current_config()
        port_name = config.get('port')

        if not port_name:
            logger.warning("No port selected")
            QMessageBox.warning(self.left_panel, "Warning", "No port selected.")
            return

        # 포트 열림 상태에 따라 토글
        if self.port_controller.is_port_open(port_name):
            self.port_controller.close_port(port_name)
        else:
            self.port_controller.open_port(config)

    def on_port_opened(self, port_name: str) -> None:
        """
        포트 열림 이벤트 처리

        Logic:
            - 해당 포트를 사용하는 탭 찾기
            - UI 연결 상태 업데이트
            - 탭 제목 업데이트
            - 시스템 로그 기록

        Args:
            port_name: 열린 포트 이름
        """
        # 모든 탭을 순회하며 해당 포트를 사용하는 패널 찾기
        for i in range(self.left_panel.port_tabs.count()):
            widget = self.left_panel.port_tabs.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(True)
                # 탭 제목 업데이트
                self.left_panel.update_tab_title(i, port_name)
                break

        # 시스템 로그 기록
        if hasattr(self.left_panel, 'system_log_widget'):
            self.left_panel.system_log_widget.log(f"[{port_name}] Port opened", "SUCCESS")

    def on_port_closed(self, port_name: str) -> None:
        """
        포트 닫힘 이벤트 처리

        Logic:
            - 해당 포트를 사용하는 탭 찾기
            - UI 연결 해제 상태 업데이트
            - 탭 제목 초기화
            - 시스템 로그 기록

        Args:
            port_name: 닫힌 포트 이름
        """
        for i in range(self.left_panel.port_tabs.count()):
            widget = self.left_panel.port_tabs.widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'port_settings_widget'):
                    widget.port_settings_widget.set_connected(False)
                # 탭 제목 초기화
                self.left_panel.update_tab_title(i, "-")
                break

        # 시스템 로그 기록
        if hasattr(self.left_panel, 'system_log_widget'):
            self.left_panel.system_log_widget.log(f"[{port_name}] Port closed", "INFO")

    def on_error(self, port_name: str, message: str) -> None:
        """
        에러 이벤트 처리

        Args:
            port_name: 에러 발생 포트
            message: 에러 메시지
        """
        logger.error(f"Port Error ({port_name}): {message}")
        QMessageBox.critical(self.left_panel, "Error", f"Port Error ({port_name}): {message}")

        # 시스템 로그 기록
        if hasattr(self.left_panel, 'system_log_widget'):
            self.left_panel.system_log_widget.log(f"[{port_name}] Error: {message}", "ERROR")

        # 에러 발생 시 해당 포트 UI 동기화 (닫힘 상태로 전환 등)
        # 필요 시 구현: 해당 포트 탭 찾아서 set_connected(False) 호출 등

    def connect_current_port(self) -> None:
        """현재 포트 연결 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel:
            config = self.current_port_panel.port_settings_widget.get_current_config()
            port_name = config.get('port')
            if port_name and not self.port_controller.is_port_open(port_name):
                self.port_controller.open_port(config)
            elif not port_name:
                logger.warning("No port selected")

    def disconnect_current_port(self) -> None:
        """현재 포트 연결 해제 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel:
            port_name = self.current_port_panel.get_port_name()
            if port_name and self.port_controller.is_port_open(port_name):
                self.port_controller.close_port(port_name)

    def clear_log_current_port(self) -> None:
        """현재 포트의 로그 지우기 (단축키용)"""
        self.update_current_port_panel()
        if self.current_port_panel and hasattr(self.current_port_panel, 'received_area_widget'):
            self.current_port_panel.received_area_widget.on_clear_rx_log_clicked()
