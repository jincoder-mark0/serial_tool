from PyQt5.QtCore import QObject
import serial.tools.list_ports

from view.sections.main_left_section import MainLeftSection
from model.port_controller import PortController
from core.settings_manager import SettingsManager

class PortPresenter(QObject):
    """
    포트 설정 및 제어를 위한 Presenter 클래스입니다.
    PortSettingsWidget(View)와 PortController(Model)를 연결합니다.
    """
    def __init__(self, left_panel: MainLeftSection, port_controller: PortController) -> None:
        """
        PortPresenter를 초기화합니다.

        Args:
            left_panel (MainLeftSection): 좌측 패널 (포트 탭 및 설정 포함).
            port_controller (PortController): 포트 제어기 모델.
        """
        super().__init__()
        self.left_panel = left_panel

        # 현재 활성 포트 패널 가져오기
        self.current_port_panel = None
        self.update_current_port_panel()

        self.port_controller = port_controller

        # 설정에서 max_lines 읽어서 적용
        settings = SettingsManager()
        max_lines = settings.get('settings.rx_max_lines', 2000)
        if self.current_port_panel and hasattr(self.current_port_panel, 'received_area_widget'):
            self.current_port_panel.received_area_widget.set_max_lines(max_lines)

        # 초기 포트 스캔
        self.scan_ports()

        # View 시그널 연결 (현재 포트 패널의 설정 위젯에서)
        if self.current_port_panel:
            self.current_port_panel.port_settings_widgets.port_scan_requested.connect(self.scan_ports)
            # 참고: connect_btn은 자체 핸들러가 있지만, 여기서 직접 연결하여 오버라이드합니다.
            # 기존 핸들러 연결 해제
            try:
                self.current_port_panel.port_settings_widgets.connect_btn.clicked.disconnect()
            except:
                pass
            self.current_port_panel.port_settings_widgets.connect_btn.clicked.connect(self.handle_connect_click)

        # Model 시그널 연결
        self.port_controller.port_opened.connect(self.on_port_opened)
        self.port_controller.port_closed.connect(self.on_port_closed)
        self.port_controller.error_occurred.connect(self.on_error)

    def update_current_port_panel(self) -> None:
        """현재 활성 포트 패널에 대한 참조를 업데이트합니다."""
        index = self.left_panel.port_tabs.currentIndex()
        if index >= 0:
            widget = self.left_panel.port_tabs.widget(index)
            if hasattr(widget, 'port_settings_widgets'):
                self.current_port_panel = widget

    def scan_ports(self) -> None:
        """사용 가능한 시리얼 포트를 스캔하여 UI에 표시합니다."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if self.current_port_panel:
            self.current_port_panel.port_settings_widgets.set_port_list(ports)

    def handle_connect_click(self) -> None:
        """
        연결 버튼 클릭을 처리합니다.
        포트가 열려있으면 닫고, 닫혀있으면 엽니다.
        """
        if not self.current_port_panel:
            return

        if self.port_controller.is_open:
            self.port_controller.close_port()
        else:
            port = self.current_port_panel.port_settings_widgets.port_combo.currentText()
            try:
                baudrate = int(self.current_port_panel.port_settings_widgets.baudrate_combo.currentText())
            except ValueError:
                print("Invalid baudrate")
                return

            if port:
                self.port_controller.open_port(port, baudrate)
            else:
                print("No port selected")

    def on_port_opened(self, port_name: str) -> None:
        """
        포트 열림 이벤트를 처리합니다.
        UI를 연결됨 상태로 업데이트하고 탭 제목을 변경합니다.

        Args:
            port_name (str): 열린 포트의 이름.
        """
        if self.current_port_panel:
            self.current_port_panel.port_settings_widgets.set_connected(True)
            # 탭 제목 업데이트
            index = self.left_panel.port_tabs.currentIndex()
            self.left_panel.update_tab_title(index, port_name)

    def on_port_closed(self, port_name: str) -> None:
        """
        포트 닫힘 이벤트를 처리합니다.
        UI를 연결 해제됨 상태로 업데이트하고 탭 제목을 기본값으로 변경합니다.

        Args:
            port_name (str): 닫힌 포트의 이름.
        """
        if self.current_port_panel:
            self.current_port_panel.port_settings_widgets.set_connected(False)
            # 탭 제목 업데이트
            index = self.left_panel.port_tabs.currentIndex()
            self.left_panel.update_tab_title(index, "-")

    def on_error(self, message: str) -> None:
        """
        에러 이벤트를 처리합니다.
        현재는 콘솔에 출력하며, 향후 상태바에 표시할 예정입니다.

        Args:
            message (str): 에러 메시지.
        """
        # Note: 향후 MainWindow의 status_bar를 통해 에러 메시지 표시 예정
        print(f"Port Error: {message}")
        # 열기/닫기 중 에러 발생 시 UI 동기화 보장
        if not self.port_controller.is_open and self.current_port_panel:
            self.current_port_panel.port_settings_widgets.set_connected(False)
