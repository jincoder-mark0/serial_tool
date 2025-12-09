"""
View 컴포넌트 테스트 애플리케이션
개별 위젯들을 독립적으로 테스트할 수 있습니다.
"""
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel, QTextEdit
from PyQt5.QtWidgets import QPushButton, QHBoxLayout

import os

from view.widgets.received_area import ReceivedAreaWidget
from view.widgets.manual_control import ManualControlWidget
from view.widgets.macro_list import MacroListWidget
from view.widgets.status_area import StatusAreaWidget
from view.panels.port_panel import PortPanel
from view.theme_manager import ThemeManager
from view.lang_manager import lang_manager
from view.dialogs.preferences_dialog import PreferencesDialog
from view.dialogs.about_dialog import AboutDialog
from view.widgets.file_progress import FileProgressWidget
from core.settings_manager import SettingsManager

# 부모 디렉토리를 경로에 추가하여 모듈 import 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

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
        theme = self.settings.get('ui.theme', 'dark')
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
        tabs.addTab(self.create_macro_list_test(), "CommandList Test")

        # Test 4: StatusArea (상태 로그 테스트)
        tabs.addTab(self.create_status_area_test(), "StatusArea Test")

        # Test 5: PortPanel (전체 패널 테스트)
        tabs.addTab(self.create_port_panel_test(), "PortPanel Test")

        # Test 6: Dialogs (Preferences, About)
        tabs.addTab(self.create_dialog_test(), "Dialogs Test")

        # Test 7: FileProgress (파일 전송 진행률)
        tabs.addTab(self.create_file_progress_test(), "FileProgress Test")

        # Test 8: Language (다국어 지원)
        tabs.addTab(self.create_language_test(), "Language Test")

        layout.addWidget(tabs)

        # 상태 표시줄 (Status bar)
        self.statusBar().showMessage("Ready - View Components Test")

    def create_received_area_test(self) -> QWidget:
        """
        ReceivedArea 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """


        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ReceivedArea 인스턴스
        self.received_area = ReceivedAreaWidget()
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
        btn_clear.clicked.connect(self.received_area.on_clear_rx_log_clicked)
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
        self.manual_control.manual_cmd_send_requested.connect(
            lambda text, hex_mode, prefix, suffix: self.manual_output.append(
                f"Send: {text} (hex={hex_mode}, prefix={prefix}, suffix={suffix})"
            )
        )
        self.manual_control.transfer_file_selected.connect(
            lambda path: self.manual_output.append(f"File selected: {path}")
        )
        self.manual_control.transfer_file_send_requested.connect(
            lambda path: self.manual_output.append(f"Send file requested: {path}")
        )

        # 정보 레이블

        info = QLabel("✅ 테스트: Send 버튼, HEX 모드, 파일 선택/전송 (Enter/Prefix/Suffix는 설정에서 관리)")
        layout.addWidget(info)

        # 제어 활성화/비활성화 테스트
        btn_layout = QHBoxLayout()
        btn_enable = QPushButton("Enable Controls")
        btn_enable.clicked.connect(lambda: self.manual_control.set_controls_enabled(True))
        btn_layout.addWidget(btn_enable)

        btn_disable = QPushButton("Disable Controls")
        btn_disable.clicked.connect(lambda: self.manual_control.set_controls_enabled(False))
        btn_layout.addWidget(btn_disable)

        layout.addLayout(btn_layout)

        return widget

    def create_macro_list_test(self) -> QWidget:
        """
        CommandList 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # CommandList 인스턴스
        self.macro_list = MacroListWidget()
        layout.addWidget(self.macro_list)

        # 정보 레이블

        info = QLabel("✅ 테스트: 행 추가/삭제/이동, Select All, Send 버튼, 데이터 유지(Persistence)")
        layout.addWidget(info)

        # Persistence Test Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save to Console")
        btn_save.clicked.connect(lambda: print(self.macro_list.get_macro_list()))

        btn_load = QPushButton("Load Dummy Data")
        btn_load.clicked.connect(lambda: self.macro_list.set_macro_list([
            {"command": "LOADED_CMD_1", "delay": "200", "enabled": True},
            {"command": "LOADED_CMD_2", "delay": "500", "enabled": False}
        ]))

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_load)
        layout.addLayout(btn_layout)

        return widget

    def create_status_area_test(self) -> QWidget:
        """
        StatusArea 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """


        widget = QWidget()
        layout = QVBoxLayout(widget)

        # StatusArea 인스턴스
        self.status_area = StatusAreaWidget()
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


        widget = QWidget()
        layout = QVBoxLayout(widget)

        # PortPanel 인스턴스
        self.port_panel = PortPanel()
        layout.addWidget(self.port_panel)

        # 정보 레이블
        info = QLabel("✅ 테스트: 전체 포트 패널 (설정 + ReceivedArea + StatusArea)")
        layout.addWidget(info)

        return widget

    def create_dialog_test(self) -> QWidget:
        """Dialog 테스트 위젯을 생성합니다."""


        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_pref = QPushButton("Open Preferences Dialog")
        btn_pref.clicked.connect(self.open_preferences)

        btn_about = QPushButton("Open About Dialog")
        btn_about.clicked.connect(self.open_about)

        layout.addWidget(btn_pref)
        layout.addWidget(btn_about)
        layout.addWidget(QLabel("✅ 테스트: 설정 다이얼로그 및 정보 다이얼로그 호출"))
        layout.addStretch()

        return widget

    def open_preferences(self) -> None:
        """설정 다이얼로그를 엽니다."""
        # 현재 설정 로드 (테스트용 임시 데이터)
        current_settings = self.settings.get_all_settings().get('global', {})
        # Serial/Logging 설정도 포함해야 하지만 여기선 간단히

        dlg = PreferencesDialog(self, self.settings.get_all_settings())
        if dlg.exec_():
            print("Preferences Saved")
            # 실제로는 여기서 설정을 저장하고 적용해야 함

    def open_about(self) -> None:
        """정보 다이얼로그를 엽니다."""
        dlg = AboutDialog(self)
        dlg.exec_()

    def create_file_progress_test(self) -> QWidget:
        """FileProgressWidget 테스트 위젯을 생성합니다."""


        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.file_progress = FileProgressWidget()
        layout.addWidget(self.file_progress)

        btn_start = QPushButton("Start Mock Transfer")
        btn_start.clicked.connect(self.start_mock_transfer)

        layout.addWidget(btn_start)
        layout.addWidget(QLabel("✅ 테스트: 진행률 바, 속도, ETA 업데이트 및 취소 버튼"))
        layout.addStretch()

        return widget

    def start_mock_transfer(self) -> None:
        """모의 파일 전송을 시작합니다."""
        self.mock_sent = 0
        self.mock_total = 1024 * 1024 * 10 # 10MB
        self.file_progress.reset()

        self.transfer_timer = QTimer(self)
        self.transfer_timer.timeout.connect(self.update_mock_transfer)
        self.transfer_timer.start(100) # 100ms 마다 업데이트

    def update_mock_transfer(self) -> None:
        """모의 전송 상태를 업데이트합니다."""
        chunk = 1024 * 100 # 100KB
        self.mock_sent += chunk

        if self.mock_sent >= self.mock_total:
            self.mock_sent = self.mock_total
            self.transfer_timer.stop()
            self.file_progress.set_complete(True, "Transfer Finished")

        # Mock speed calculation
        speed = chunk * 10 # 1MB/s
        eta = (self.mock_total - self.mock_sent) / speed

        self.file_progress.update_progress(self.mock_sent, self.mock_total, speed, eta)

    def create_language_test(self) -> QWidget:
        """LangManager 테스트 위젯을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.lang_label = QLabel(lang_manager.get_text("main_title"))
        self.lang_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        btn_en = QPushButton("English")
        btn_en.clicked.connect(lambda: self.change_language("en"))

        btn_ko = QPushButton("한국어")
        btn_ko.clicked.connect(lambda: self.change_language("ko"))

        layout.addWidget(self.lang_label)
        layout.addWidget(btn_en)
        layout.addWidget(btn_ko)
        layout.addWidget(QLabel("✅ 테스트: 버튼 클릭 시 앱 타이틀 언어 변경 확인"))
        layout.addStretch()

        return widget

    def change_language(self, lang: str) -> None:
        """언어를 변경하고 UI를 업데이트합니다."""
        lang_manager.set_language(lang)
        self.lang_label.setText(lang_manager.get_text("main_title"))

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
