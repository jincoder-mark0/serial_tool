"""
View 컴포넌트 테스트 애플리케이션
개별 위젯들을 독립적으로 테스트할 수 있습니다.
"""
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import Qt

import os

# 부모 디렉토리를 경로에 추가하여 모듈 import 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from view.widgets.received_area import ReceivedArea
from view.widgets.manual_control import ManualControlWidget
from view.widgets.command_list import CommandListWidget
from view.widgets.status_area import StatusArea
from view.panels.port_panel import PortPanel
from view.theme_manager import ThemeManager
from core.settings_manager import SettingsManager

class ViewTestWindow(QMainWindow):
    """View 컴포넌트 테스트용 윈도우 클래스입니다."""
    
    def __init__(self) -> None:
        """ViewTestWindow를 초기화합니다."""
        super().__init__()
        self.setWindowTitle("View Components Test")
        self.resize(1200, 800)
        
        # 설정 관리자 테스트 (Settings Manager Test)
        self.settings = SettingsManager()
        
        self.init_ui()
        
        # 테마 적용 (Apply theme)
        theme = self.settings.get('global.theme', 'dark')
        self.theme_manager = ThemeManager()
        self.theme_manager.apply_theme(QApplication.instance(), theme)
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 테스트용 탭 위젯 (Tab Widget for different tests)
        tabs = QTabWidget()
        
        # Test 1: ReceivedArea (색상 규칙, Trim, 타임스탬프 테스트)
        tabs.addTab(self.create_received_area_test(), "ReceivedArea Test")
        
        # Test 2: ManualControl (입력, 파일 전송 테스트)
        tabs.addTab(self.create_manual_control_test(), "ManualControl Test")
        
        # Test 3: CommandList (커맨드 리스트 테스트)
        tabs.addTab(self.create_command_list_test(), "CommandList Test")
        
        # Test 4: StatusArea (상태 로그 테스트)
        tabs.addTab(self.create_status_area_test(), "StatusArea Test")
        
        # Test 5: PortPanel (전체 패널 테스트)
        tabs.addTab(self.create_port_panel_test(), "PortPanel Test")
        
        layout.addWidget(tabs)
        
        # 상태 표시줄 (Status bar)
        self.statusBar().showMessage("Ready - View Components Test")
    
    def create_received_area_test(self) -> QWidget:
        """
        ReceivedArea 테스트 위젯을 생성합니다.
        
        Returns:
            QWidget: 테스트 위젯.
        """
        from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ReceivedArea 인스턴스
        self.received_area = ReceivedArea()
        layout.addWidget(self.received_area)
        
        # 테스트 버튼 (Test buttons)
        button_layout = QHBoxLayout()
        
        # 테스트 데이터 버튼
        btn_ok = QPushButton("Add OK")
        btn_ok.clicked.connect(lambda: self.received_area.append_data(b"AT\r\nOK\r\n"))
        button_layout.addWidget(btn_ok)
        
        btn_error = QPushButton("Add ERROR")
        btn_error.clicked.connect(lambda: self.received_area.append_data(b"AT+TEST\r\nERROR\r\n"))
        button_layout.addWidget(btn_error)
        
        btn_urc = QPushButton("Add URC")
        btn_urc.clicked.connect(lambda: self.received_area.append_data(b"+CREG: 1,5\r\n"))
        button_layout.addWidget(btn_urc)
        
        btn_many = QPushButton("Add 100 Lines")
        btn_many.clicked.connect(self.add_many_lines)
        button_layout.addWidget(btn_many)
        
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.received_area.clear_log)
        button_layout.addWidget(btn_clear)
        
        layout.addLayout(button_layout)
        
        # 정보 레이블
        info = QLabel("✅ 테스트: 색상 규칙 (OK=녹색, ERROR=빨강), Trim (2000줄 제한), 타임스탬프 (TS 체크박스)")
        layout.addWidget(info)
        
        return widget
    
    def add_many_lines(self) -> None:
        """많은 라인을 추가하여 Trim 기능을 테스트합니다."""
        for i in range(100):
            self.received_area.append_data(f"Line {i+1}: Test data\r\n".encode())
    
    def create_manual_control_test(self) -> QWidget:
        """
        ManualControl 테스트 위젯을 생성합니다.
        
        Returns:
            QWidget: 테스트 위젯.
        """
        from PyQt5.QtWidgets import QTextEdit
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ManualControl 인스턴스
        self.manual_control = ManualControlWidget()
        layout.addWidget(self.manual_control)
        
        # 출력 영역 (Output area)
        self.manual_output = QTextEdit()
        self.manual_output.setReadOnly(True)
        self.manual_output.setMaximumHeight(200)
        layout.addWidget(self.manual_output)
        
        # 시그널 연결
        self.manual_control.send_command_requested.connect(
            lambda text, hex_mode, enter: self.manual_output.append(
                f"Send: {text} (hex={hex_mode}, enter={enter})"
            )
        )
        self.manual_control.file_selected.connect(
            lambda path: self.manual_output.append(f"File selected: {path}")
        )
        self.manual_control.send_file_requested.connect(
            lambda: self.manual_output.append("Send file requested")
        )
        
        # 정보 레이블
        from PyQt5.QtWidgets import QLabel
        info = QLabel("✅ 테스트: Send 버튼, HEX 모드, Enter 추가, 파일 선택/전송")
        layout.addWidget(info)
        
        # 제어 활성화/비활성화 테스트
        from PyQt5.QtWidgets import QPushButton, QHBoxLayout
        btn_layout = QHBoxLayout()
        btn_enable = QPushButton("Enable Controls")
        btn_enable.clicked.connect(lambda: self.manual_control.set_controls_enabled(True))
        btn_layout.addWidget(btn_enable)
        
        btn_disable = QPushButton("Disable Controls")
        btn_disable.clicked.connect(lambda: self.manual_control.set_controls_enabled(False))
        btn_layout.addWidget(btn_disable)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def create_command_list_test(self) -> QWidget:
        """
        CommandList 테스트 위젯을 생성합니다.
        
        Returns:
            QWidget: 테스트 위젯.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # CommandList 인스턴스
        self.command_list = CommandListWidget()
        layout.addWidget(self.command_list)
        
        # 정보 레이블
        from PyQt5.QtWidgets import QLabel
        info = QLabel("✅ 테스트: 행 추가/삭제/이동, Select All, Send 버튼")
        layout.addWidget(info)
        
        return widget
    
    def create_status_area_test(self) -> QWidget:
        """
        StatusArea 테스트 위젯을 생성합니다.
        
        Returns:
            QWidget: 테스트 위젯.
        """
        from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # StatusArea 인스턴스
        self.status_area = StatusArea()
        layout.addWidget(self.status_area)
        
        # 테스트 버튼
        button_layout = QHBoxLayout()
        
        btn_info = QPushButton("Log INFO")
        btn_info.clicked.connect(lambda: self.status_area.log("This is an info message", "INFO"))
        button_layout.addWidget(btn_info)
        
        btn_error = QPushButton("Log ERROR")
        btn_error.clicked.connect(lambda: self.status_area.log("This is an error message", "ERROR"))
        button_layout.addWidget(btn_error)
        
        btn_warn = QPushButton("Log WARN")
        btn_warn.clicked.connect(lambda: self.status_area.log("This is a warning message", "WARN"))
        button_layout.addWidget(btn_warn)
        
        btn_success = QPushButton("Log SUCCESS")
        btn_success.clicked.connect(lambda: self.status_area.log("This is a success message", "SUCCESS"))
        button_layout.addWidget(btn_success)
        
        layout.addLayout(button_layout)
        
        # 정보 레이블
        info = QLabel("✅ 테스트: 로그 레벨별 색상 (INFO=파랑, ERROR=빨강, WARN=주황, SUCCESS=녹색)")
        layout.addWidget(info)
        
        return widget
    
    def create_port_panel_test(self) -> QWidget:
        """
        PortPanel 전체 테스트 위젯을 생성합니다.
        
        Returns:
            QWidget: 테스트 위젯.
        """
        from PyQt5.QtWidgets import QLabel
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # PortPanel 인스턴스
        self.port_panel = PortPanel()
        layout.addWidget(self.port_panel)
        
        # 정보 레이블
        info = QLabel("✅ 테스트: 전체 포트 패널 (설정 + ReceivedArea + StatusArea)")
        layout.addWidget(info)
        
        return widget
    
    def closeEvent(self, event) -> None:
        """
        종료 시 설정을 저장합니다.
        
        Args:
            event: 종료 이벤트.
        """
        self.settings.set('ui.window_width', self.width())
        self.settings.set('ui.window_height', self.height())
        self.settings.save_settings()
        event.accept()


def main() -> None:
    """메인 함수입니다."""
    app = QApplication(sys.argv)
    app.setApplicationName("SerialTool View Test")
    
    window = ViewTestWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
