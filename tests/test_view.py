"""
View 컴포넌트 테스트 애플리케이션
개별 위젯들을 독립적으로 테스트할 수 있습니다.
"""
import sys
import os

# 부모 디렉토리를 경로에 추가하여 모듈 import 가능하게 함 (import 전에 실행)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel, QTextEdit
from PyQt5.QtWidgets import QPushButton, QHBoxLayout

from view.widgets.data_log_view import DataLogViewWidget
from view.widgets.manual_ctrl import ManualCtrlWidget
from view.widgets.macro_list import MacroListWidget
from view.widgets.sys_log_view import SysLogViewWidget
from view.panels.port_panel import PortPanel
from view.managers.theme_manager import ThemeManager
from view.managers.lang_manager import lang_manager
from view.dialogs.preferences_dialog import PreferencesDialog
from view.dialogs.about_dialog import AboutDialog
from view.widgets.file_progress import FileProgressWidget
from core.settings_manager import SettingsManager
from view.custom_qt.smart_list_view import QSmartListView
from view.managers.color_manager import color_manager
import time

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
        theme = self.settings.get('settings.theme', 'dark')
        self.theme_manager = ThemeManager()
        self.theme_manager.apply_theme(QApplication.instance(), theme)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # 테스트용 탭 위젯 (Tab Widget for different tests)
        tabs = QTabWidget()

        # Test 1: DataLogView (색상 규칙, Trim, 타임스탬프 테스트)
        tabs.addTab(self.create_data_log_view_test(), "DataLogView Test")

        # Test 2: ManualCtrl (입력, 파일 전송 테스트)
        tabs.addTab(self.create_manual_ctrl_test(), "ManualCtrl Test")

        # Test 3: CommandList (커맨드 리스트 테스트)
        tabs.addTab(self.create_macro_list_test(), "CommandList Test")

        # Test 4: StatusArea (상태 로그 테스트)
        tabs.addTab(self.create_sys_log_view_test(), "StatusArea Test")

        # Test 5: PortPanel (전체 패널 테스트)
        tabs.addTab(self.create_port_panel_test(), "PortPanel Test")

        # Test 6: Dialogs (Preferences, About)
        tabs.addTab(self.create_dialog_test(), "Dialogs Test")

        # Test 7: FileProgress (파일 전송 진행률)
        tabs.addTab(self.create_file_progress_test(), "FileProgress Test")


        # Test 8: SmartListView (새 기능 테스트)
        tabs.addTab(self.create_smart_list_view_test(), "SmartListView Test")

        # Test 9: Language (다국어 지원)
        tabs.addTab(self.create_language_test(), "Language Test")

        layout.addWidget(tabs)

        # 상태 표시줄 (Status bar)
        self.statusBar().showMessage("Ready - View Components Test")

    def create_data_log_view_test(self) -> QWidget:
        """
        DataLogViewWidget 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """


        widget = QWidget()
        layout = QVBoxLayout(widget)

        # DataLogViewWidget 인스턴스
        self.data_log_view_widget = DataLogViewWidget()
        layout.addWidget(self.data_log_view_widget)

        # 테스트 버튼 (Test buttons)
        button_layout = QHBoxLayout()

        # 테스트 데이터 버튼
        btn_ok = QPushButton("Add OK")
        btn_ok.clicked.connect(lambda: self.data_log_view_widget.append_data(b"AT\r\nOK\r\n"))
        button_layout.addWidget(btn_ok)

        btn_error = QPushButton("Add ERROR")
        btn_error.clicked.connect(lambda: self.data_log_view_widget.append_data(b"AT+TEST\r\nERROR\r\n"))
        button_layout.addWidget(btn_error)

        btn_urc = QPushButton("Add URC")
        btn_urc.clicked.connect(lambda: self.data_log_view_widget.append_data(b"+CREG: 1,5\r\n"))
        button_layout.addWidget(btn_urc)

        btn_many = QPushButton("Add 100 Lines")
        btn_many.clicked.connect(self.add_many_lines)
        button_layout.addWidget(btn_many)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.data_log_view_widget.on_clear_data_log_view_clicked)
        button_layout.addWidget(btn_clear)

        layout.addLayout(button_layout)

        # 정보 레이블
        info = QLabel("✅ 테스트: 색상 규칙 (OK=녹색, ERROR=빨강), Trim (2000줄 제한), 타임스탬프 (TS 체크박스)")
        layout.addWidget(info)

        return widget

    def add_many_lines(self) -> None:
        """많은 라인을 추가하여 Trim 기능을 테스트합니다."""
        for i in range(100):
            self.data_log_view_widget.append_data(f"Line {i+1}: Test data\r\n".encode())

    def create_manual_ctrl_test(self) -> QWidget:
        """
        ManualCtrl 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ManualCtrl 인스턴스
        self.manual_ctrl = ManualCtrlWidget()
        layout.addWidget(self.manual_ctrl)

        # 출력 영역 (Output area)
        self.manual_output = QTextEdit()
        self.manual_output.setReadOnly(True)
        self.manual_output.setMaximumHeight(150)
        self.manual_output.setPlaceholderText("전송된 명령어 출력 및 이벤트 로그")
        layout.addWidget(QLabel("📤 Output Log:"))
        layout.addWidget(self.manual_output)

        # 시그널 연결
        self.manual_ctrl.manual_cmd_send_requested.connect(
            lambda text, hex_mode, prefix, suffix, local_echo: self.manual_output.append(
                f"✅ Send: '{text}' (hex={hex_mode}, prefix={prefix}, suffix={suffix}, echo={local_echo})"
            )
        )
        self.manual_ctrl.transfer_file_selected.connect(
            lambda path: self.manual_output.append(f"📁 File selected: {path}")
        )
        self.manual_ctrl.transfer_file_send_requested.connect(
            lambda path: self.manual_output.append(f"📤 Send file requested: {path}")
        )

        # 히스토리 테스트 버튼들
        history_layout = QHBoxLayout()

        btn_add_at = QPushButton("Add 'AT'")
        btn_add_at.clicked.connect(lambda: self.manual_ctrl.add_to_history("AT"))
        history_layout.addWidget(btn_add_at)

        btn_add_ok = QPushButton("Add 'AT+GMR'")
        btn_add_ok.clicked.connect(lambda: self.manual_ctrl.add_to_history("AT+GMR"))
        history_layout.addWidget(btn_add_ok)

        btn_add_custom = QPushButton("Add 'AT+CREG?'")
        btn_add_custom.clicked.connect(lambda: self.manual_ctrl.add_to_history("AT+CREG?"))
        history_layout.addWidget(btn_add_custom)

        btn_show_history = QPushButton("Show History")
        btn_show_history.clicked.connect(self.show_manual_history)
        history_layout.addWidget(btn_show_history)

        layout.addWidget(QLabel("📜 History Test:"))
        layout.addLayout(history_layout)

        # 정보 레이블
        info = QLabel(
            "✅ 테스트:\n"
            "1. Send 버튼: 명령어 전송 및 시그널 확인\n"
            "2. HEX 모드: 체크박스로 전환\n"
            "3. 히스토리: Up/Down 버튼으로 이전 명령어 탐색 (Ctrl+Up/Down 키보드 단축키)\n"
            "4. 파일 선택/전송: Transfer 버튼들 테스트\n"
            "5. 제어 활성화/비활성화: Enable/Disable Controls 버튼"
        )
        layout.addWidget(info)

        # 제어 활성화/비활성화 테스트
        btn_layout = QHBoxLayout()
        btn_enable = QPushButton("Enable Controls")
        btn_enable.clicked.connect(lambda: self.manual_ctrl.set_controls_enabled(True))
        btn_layout.addWidget(btn_enable)

        btn_disable = QPushButton("Disable Controls")
        btn_disable.clicked.connect(lambda: self.manual_ctrl.set_controls_enabled(False))
        btn_layout.addWidget(btn_disable)

        layout.addLayout(btn_layout)

        return widget

    def show_manual_history(self) -> None:
        """히스토리 목록을 출력 영역에 표시합니다."""
        history = self.manual_ctrl.cmd_history
        if history:
            self.manual_output.append("\n📜 Command History:")
            for i, cmd in enumerate(history):
                self.manual_output.append(f"  [{i+1}] {cmd}")
            self.manual_output.append(f"Current Index: {self.manual_ctrl.history_index}\n")
        else:
            self.manual_output.append("📜 History is empty\n")

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
            {"cmd": "LOADED_CMD_1", "delay": "200", "enabled": True},
            {"cmd": "LOADED_CMD_2", "delay": "500", "enabled": False}
        ]))

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_load)
        layout.addLayout(btn_layout)

        return widget

    def create_sys_log_view_test(self) -> QWidget:
        """
        StatusArea 테스트 위젯을 생성합니다.

        Returns:
            QWidget: 테스트 위젯.
        """


        widget = QWidget()
        layout = QVBoxLayout(widget)

        # StatusArea 인스턴스
        self.sys_log_view_widget = SysLogViewWidget()
        layout.addWidget(self.sys_log_view_widget)

        # 테스트 버튼
        button_layout = QHBoxLayout()

        btn_info = QPushButton("Log INFO")
        btn_info.clicked.connect(lambda: self.sys_log_view_widget.log("This is an info message", "INFO"))
        button_layout.addWidget(btn_info)

        btn_error = QPushButton("Log ERROR")
        btn_error.clicked.connect(lambda: self.sys_log_view_widget.log("This is an error message", "ERROR"))
        button_layout.addWidget(btn_error)

        btn_warn = QPushButton("Log WARN")
        btn_warn.clicked.connect(lambda: self.sys_log_view_widget.log("This is a warning message", "WARN"))
        button_layout.addWidget(btn_warn)

        btn_success = QPushButton("Log SUCCESS")
        btn_success.clicked.connect(lambda: self.sys_log_view_widget.log("This is a success message", "SUCCESS"))
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
        info = QLabel("✅ 테스트: 전체 포트 패널 (설정 + DataLogView + StatusArea)")
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

        # 취소 버튼 시그널 연결
        self.file_progress.transfer_cancelled.connect(self.cancel_mock_transfer)

        btn_start = QPushButton("Start Mock Transfer")
        btn_start.clicked.connect(self.start_mock_transfer)

        layout.addWidget(btn_start)
        layout.addWidget(QLabel("✅ 테스트: 진행률 바, 속도, ETA 업데이트 및 취소 버튼"))
        layout.addStretch()

        return widget

    def cancel_mock_transfer(self) -> None:
        """모의 전송을 취소합니다."""
        if hasattr(self, 'transfer_timer') and self.transfer_timer.isActive():
            self.transfer_timer.stop()
            print("Transfer cancelled by user")

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


    def create_smart_list_view_test(self) -> QWidget:
        """QSmartListView 새 기능 테스트 위젯을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # QSmartListView 인스턴스
        self.smart_list = QSmartListView()
        self.smart_list.set_color_manager(color_manager)

        layout.addWidget(self.smart_list)

        # 테스트 버튼들
        button_layout = QHBoxLayout()

        # HEX 모드 테스트
        btn_hex = QPushButton("Send Bytes (Normal)")
        btn_hex.clicked.connect(lambda: self.smart_list.append_bytes(b"Normal text\n"))
        button_layout.addWidget(btn_hex)

        btn_hex_mode = QPushButton("Toggle HEX Mode")
        btn_hex_mode.setCheckable(True)
        btn_hex_mode.toggled.connect(self.smart_list.set_hex_mode_enabled)
        button_layout.addWidget(btn_hex_mode)

        # 타임스탬프 테스트
        btn_timestamp = QPushButton("Toggle Timestamp")
        btn_timestamp.setCheckable(True)
        btn_timestamp.toggled.connect(lambda checked: self.smart_list.set_timestamp_enabled(checked, timeout_ms=100))
        button_layout.addWidget(btn_timestamp)

        layout.addLayout(button_layout)

        # 두 번째 줄 버튼
        button_layout2 = QHBoxLayout()

        # Newline 모드 테스트
        btn_newline = QPushButton("Send Multiline (LF)")
        btn_newline.clicked.connect(lambda: self.smart_list.append_bytes(b"Line1\nLine2\nLine3\n"))
        button_layout2.addWidget(btn_newline)

        # Raw 모드 테스트 (타임스탬프 timeout)
        btn_raw = QPushButton("Raw Mode Test")
        btn_raw.clicked.connect(self.test_raw_mode_timestamp)
        button_layout2.addWidget(btn_raw)

        # 색상 테스트
        btn_color = QPushButton("Send AT Commands")
        btn_color.clicked.connect(lambda: [
            self.smart_list.append_bytes(b"AT\r\n"),
            self.smart_list.append_bytes(b"OK\r\n"),
            self.smart_list.append_bytes(b"ERROR\r\n"),
            self.smart_list.append_bytes(b"+CREG: 1,5\r\n")
        ])
        button_layout2.addWidget(btn_color)

        # 대량 데이터 성능 테스트
        btn_many = QPushButton("Add 1000 Lines (Performance)")
        btn_many.clicked.connect(self.test_large_data)
        button_layout2.addWidget(btn_many)

        # Clear
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.smart_list.clear)
        button_layout2.addWidget(btn_clear)

        layout.addLayout(button_layout2)

        # 정보 레이블
        info = QLabel(
            "✅ 테스트:\n"
            "1. HEX 모드: bytes를 HEX 문자열로 표시\n"
            "2. 타임스탬프: Newline 모드에서는 각 줄마다, Raw 모드에서는 100ms 간격\n"
            "3. 색상 규칙: AT 명령(OK, ERROR, URC) 색상 적용\n"
            "4. 성능: UniformItemSizes=True로 대량 데이터 처리 최적화"
        )
        layout.addWidget(info)

        return widget

    def test_raw_mode_timestamp(self) -> None:
        """Raw 모드 타임스탬프를 테스트합니다 (간격 체크)."""
        # Newline 제거 (Raw 모드)
        self.smart_list.set_newline_char(None)

        # 빠르게 연속으로 전송 (타임스탬프 없어야 함)
        self.smart_list.append_bytes(b"Data1")
        time.sleep(0.05)  # 50ms
        self.smart_list.append_bytes(b"Data2")  # 같은 줄에 붙음

        # 충분한 간격 후 전송 (타임스탬프 추가되어야 함)
        time.sleep(0.15)  # 150ms (> 100ms threshold)
        self.smart_list.append_bytes(b"Data3")  # 새 줄로 시작

        # Newline 복구
        self.smart_list.set_newline_char("\n")

    def test_large_data(self) -> None:
        """대량 데이터 성능 테스트 (1000줄)."""
        start = time.time()

        for i in range(1000):
            self.smart_list.append_bytes(f"[{i+1:04d}] Performance test line {i+1}\n".encode())

        elapsed = time.time() - start
        print(f"Added 1000 lines in {elapsed:.2f}s ({1000/elapsed:.0f} lines/sec)")

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
