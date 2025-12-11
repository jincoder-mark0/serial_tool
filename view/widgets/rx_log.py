"""
RxLogWidget 모듈

시리얼 포트 등 외부로부터 수신된 데이터를 표시하고 관리하는 메인 위젯을 정의합니다.
QSmartListView를 기반으로 하여 대량의 데이터 처리 성능을 최적화하였으며,
검색, HEX 모드, 타임스탬프, 일시 정지 등의 편의 기능을 제공합니다.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit, QFileDialog, QComboBox
)
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, Qt
from typing import Optional
import datetime
from view.managers.color_manager import color_manager   # 전역 매니저 사용
from view.managers.lang_manager import lang_manager     # 전역 매니저 사용

from view.custom_qt.smart_list_view import QSmartListView

from constants import (
    DEFAULT_LOG_MAX_LINES,
    UI_REFRESH_INTERVAL_MS,
    LOG_COLOR_TIMESTAMP
)
from core.logger import logger

class RxLogWidget(QWidget):
    """
    수신된 시리얼 데이터를 표시하는 위젯 클래스입니다.
    텍스트/HEX 모드 전환, 일시 정지, 타임스탬프 표시, 로그 저장 및 지우기 기능을 제공합니다.
    """
    # 녹화 시그널 (포트명은 Presenter에서 관리)
    recording_started = pyqtSignal(str)  # filepath
    recording_stopped = pyqtSignal()
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        RxLogWidget를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # ---------------------------------------------------------
        # 1. 상태 변수 초기화
        # ---------------------------------------------------------
        # UI Components
        self.rx_search_prev_btn = None
        self.rx_search_next_btn = None
        self.rx_search_input = None
        self.rx_save_log_btn = None
        self.rx_clear_log_btn = None
        self.rx_pause_chk = None
        self.rx_timestamp_chk = None
        self.rx_hex_chk = None
        self.rx_filter_chk = None  # Filter Checkbox
        self.rx_newline_combo = None # Newline Combo
        self.rx_log_title = None
        self.rx_log_list = None

        # State Variables
        self.hex_mode: bool = False
        self.is_paused: bool = False
        self.timestamp_enabled: bool = False
        self.filter_enabled: bool = False # Filter State
        self.ui_update_buffer: list = []  # (text, formatter) 튜플 리스트

        self.max_lines: int = DEFAULT_LOG_MAX_LINES
        self.tab_name: str = ""  # 탭 이름 저장

        # 색상 규칙 관리자
        self.color_manager = color_manager

        # ---------------------------------------------------------
        # 2. UI 구성 및 시그널 연결
        # ---------------------------------------------------------
        self.init_ui()
        
        # QSmartListView 초기 설정
        self.rx_log_list.set_color_manager(self.color_manager)
        self.rx_log_list.set_hex_mode_enabled(self.hex_mode)
        self.rx_log_list.set_timestamp_enabled(self.timestamp_enabled, timeout_ms=100)

        # 언어 변경 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

        # ---------------------------------------------------------
        # 3. 타이머 설정 (성능 최적화)
        # ---------------------------------------------------------
        self.ui_update_timer: QTimer = QTimer()
        self.ui_update_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self.ui_update_timer.timeout.connect(self.flush_buffer)
        self.ui_update_timer.start()

    def set_tab_name(self, name: str) -> None:
        """탭 이름을 설정합니다."""
        self.tab_name = name

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. 툴바 영역 (타이틀 + 도구들)
        # 타이틀 섹션
        self.rx_log_title = QLabel(lang_manager.get_text("rx_title"))
        self.rx_log_title.setProperty("class", "section-title")  # 섹션 타이틀 스타일 적용


        # 도구 섹션 (검색, 옵션, 액션)

        # Search Bar
        self.rx_search_input = QLineEdit()
        self.rx_search_input.setPlaceholderText(lang_manager.get_text("rx_input_search_placeholder"))
        self.rx_search_input.setToolTip(lang_manager.get_text("rx_input_search_tooltip"))
        self.rx_search_input.setMaximumWidth(200)
        self.rx_search_input.returnPressed.connect(self.on_rx_search_next_clicked)
        # 검색어 변경 시 실시간 하이라이트 갱신
        self.rx_search_input.textChanged.connect(self.on_rx_search_text_changed)

        # Buttons
        self.rx_search_prev_btn = QPushButton()
        self.rx_search_prev_btn.setObjectName("rx_search_prev_btn")
        self.rx_search_prev_btn.setText("<") # 아이콘이 없을 경우를 대비한 텍스트
        self.rx_search_prev_btn.setToolTip(lang_manager.get_text("rx_btn_search_prev_tooltip"))
        self.rx_search_prev_btn.setFixedWidth(30)
        self.rx_search_prev_btn.clicked.connect(self.on_rx_search_prev_clicked)

        self.rx_search_next_btn = QPushButton()
        self.rx_search_next_btn.setObjectName("rx_search_next_btn")
        self.rx_search_next_btn.setText(">") # 아이콘이 없을 경우를 대비한 텍스트
        self.rx_search_next_btn.setToolTip(lang_manager.get_text("rx_btn_search_next_tooltip"))
        self.rx_search_next_btn.setFixedWidth(30)
        self.rx_search_next_btn.clicked.connect(self.on_rx_search_next_clicked)

        self.rx_clear_log_btn = QPushButton(lang_manager.get_text("rx_btn_clear"))
        self.rx_clear_log_btn.setToolTip(lang_manager.get_text("rx_btn_clear_tooltip"))
        self.rx_clear_log_btn.clicked.connect(self.on_clear_rx_log_clicked)

        self.rx_save_log_btn = QPushButton(lang_manager.get_text("rx_btn_save"))
        self.rx_save_log_btn.setToolTip(lang_manager.get_text("rx_btn_save_tooltip"))
        self.rx_save_log_btn.setCheckable(True)  # 토글 버튼으로 변경
        self.rx_save_log_btn.toggled.connect(self.on_recording_toggled)

        # Options
        self.rx_filter_chk = QCheckBox(lang_manager.get_text("rx_chk_filter"))
        self.rx_filter_chk.setToolTip(lang_manager.get_text("rx_chk_filter_tooltip"))
        self.rx_filter_chk.stateChanged.connect(self.on_rx_filter_changed)

        self.rx_hex_chk = QCheckBox(lang_manager.get_text("rx_chk_hex"))
        self.rx_hex_chk.setToolTip(lang_manager.get_text("rx_chk_hex_tooltip"))
        self.rx_hex_chk.stateChanged.connect(self.on_rx_hex_mode_changed)

        self.rx_timestamp_chk = QCheckBox(lang_manager.get_text("rx_chk_timestamp"))
        self.rx_timestamp_chk.setToolTip(lang_manager.get_text("rx_chk_timestamp_tooltip"))
        self.rx_timestamp_chk.stateChanged.connect(self.on_rx_timestamp_changed)

        self.rx_pause_chk = QCheckBox(lang_manager.get_text("rx_chk_pause"))
        self.rx_pause_chk.setToolTip(lang_manager.get_text("rx_chk_pause_tooltip"))
        self.rx_pause_chk.stateChanged.connect(self.on_rx_pause_changed)

        # Newline Combo
        self.rx_newline_combo = QComboBox()
        self.rx_newline_combo.setToolTip(lang_manager.get_text("rx_combo_newline_tooltip"))
        self.rx_newline_combo.addItem(lang_manager.get_text("rx_newline_raw"), "Raw")
        self.rx_newline_combo.addItem(lang_manager.get_text("rx_newline_lf"), "LF")
        self.rx_newline_combo.addItem(lang_manager.get_text("rx_newline_cr"), "CR")
        self.rx_newline_combo.addItem(lang_manager.get_text("rx_newline_crlf"), "CRLF")
        self.rx_newline_combo.setFixedWidth(100)



        # 2. 로그 뷰 영역
        # self.rx_log_list = QTextEdit()
        self.rx_log_list = QSmartListView()
        self.rx_log_list.set_max_lines(DEFAULT_LOG_MAX_LINES)
        self.rx_log_list.setReadOnly(True)
        self.rx_log_list.setPlaceholderText(lang_manager.get_text("rx_list_log_placeholder"))
        self.rx_log_list.setToolTip(lang_manager.get_text("rx_title"))
        self.rx_log_list.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        # Layout 배치
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.rx_log_title)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.rx_search_input)
        toolbar_layout.addWidget(self.rx_search_prev_btn)
        toolbar_layout.addWidget(self.rx_search_next_btn)
        toolbar_layout.addWidget(self.rx_filter_chk) # Filter Checkbox
        toolbar_layout.addWidget(self.rx_newline_combo) # Newline Combo
        toolbar_layout.addWidget(self.rx_hex_chk)
        toolbar_layout.addWidget(self.rx_timestamp_chk)
        toolbar_layout.addWidget(self.rx_pause_chk)
        toolbar_layout.addWidget(self.rx_clear_log_btn)
        toolbar_layout.addWidget(self.rx_save_log_btn)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.rx_log_list)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 현재 언어 설정에 맞게 업데이트합니다."""
        # Labels & Tooltips
        self.rx_log_title.setText(lang_manager.get_text("rx_title"))
        self.rx_log_list.setToolTip(lang_manager.get_text("rx_list_log_tooltip"))
        self.rx_log_list.setPlaceholderText(lang_manager.get_text("rx_list_log_placeholder"))

        # Search Components
        self.rx_search_input.setPlaceholderText(lang_manager.get_text("rx_input_search_placeholder"))
        self.rx_search_input.setToolTip(lang_manager.get_text("rx_input_search_tooltip"))
        self.rx_search_prev_btn.setToolTip(lang_manager.get_text("rx_btn_search_prev_tooltip"))
        self.rx_search_next_btn.setToolTip(lang_manager.get_text("rx_btn_search_next_tooltip"))

        # Checkboxes
        self.rx_filter_chk.setText(lang_manager.get_text("rx_chk_filter"))
        self.rx_filter_chk.setToolTip(lang_manager.get_text("rx_chk_filter_tooltip"))
        self.rx_hex_chk.setText(lang_manager.get_text("rx_chk_hex"))
        self.rx_hex_chk.setToolTip(lang_manager.get_text("rx_chk_hex_tooltip"))
        self.rx_timestamp_chk.setText(lang_manager.get_text("rx_chk_timestamp"))
        self.rx_timestamp_chk.setToolTip(lang_manager.get_text("rx_chk_timestamp_tooltip"))
        self.rx_pause_chk.setText(lang_manager.get_text("rx_chk_pause"))
        self.rx_pause_chk.setToolTip(lang_manager.get_text("rx_chk_pause_tooltip"))

        # Buttons
        self.rx_clear_log_btn.setText(lang_manager.get_text("rx_btn_clear"))
        self.rx_clear_log_btn.setToolTip(lang_manager.get_text("rx_btn_clear_tooltip"))
        self.rx_save_log_btn.setText(lang_manager.get_text("rx_btn_save"))
        self.rx_save_log_btn.setToolTip(lang_manager.get_text("rx_btn_save_tooltip"))

        # Newline Combo
        current_idx = self.rx_newline_combo.currentIndex()
        self.rx_newline_combo.setItemText(0, lang_manager.get_text("rx_newline_raw"))
        self.rx_newline_combo.setItemText(1, lang_manager.get_text("rx_newline_lf"))
        self.rx_newline_combo.setItemText(2, lang_manager.get_text("rx_newline_cr"))
        self.rx_newline_combo.setItemText(3, lang_manager.get_text("rx_newline_crlf"))
        self.rx_newline_combo.setToolTip(lang_manager.get_text("rx_combo_newline_tooltip"))
        self.rx_newline_combo.setCurrentIndex(current_idx)

    # -------------------------------------------------------------------------
    # 데이터 처리 및 버퍼링
    # -------------------------------------------------------------------------
    def append_data(self, data: bytes) -> None:
        """
        수신된 바이트 데이터를 버퍼에 추가합니다.

        Args:
            data (bytes): 수신된 원본 바이트 데이터.
        """
        # 일시 정지 상태면 데이터 무시
        if self.is_paused:
            return

        # Newline 문자 설정 (QSmartListView에 전달)
        newline_mode = self.rx_newline_combo.currentData()
        if self.hex_mode or newline_mode == "Raw":
            newline_char = None
        else:
            newline_char = {
                "LF": "\n",
                "CR": "\r",
                "CRLF": "\r\n"
            }.get(newline_mode, "\n")
        
        self.rx_log_list.set_newline_char(newline_char)
        
        # 버퍼에 추가 (bytes 그대로)
        self.ui_update_buffer.append(data)

    def flush_buffer(self) -> None:
        """
        타이머에 의해 주기적으로 호출되어 버퍼 내용을 UI에 반영합니다.
        각 bytes 데이터를 QSmartListView에 전달하여 자동으로 처리합니다.
        """
        if not self.ui_update_buffer:
            return

        # 버퍼 내용을 복사하고 즉시 비움
        buffer_items = self.ui_update_buffer[:]
        self.ui_update_buffer.clear()

        # 각 bytes를 QSmartListView에 전달
        for data in buffer_items:
            self.rx_log_list.append_bytes(data)

    # -------------------------------------------------------------------------
    # 사용자 액션 처리 (검색, 옵션, 버튼)
    # -------------------------------------------------------------------------
    @pyqtSlot()
    def on_rx_search_next_clicked(self) -> None:
        """검색창의 텍스트로 다음 항목을 찾습니다."""
        text = self.rx_search_input.text()
        if text:
            # 패턴 설정은 textChanged에서 실시간으로 되지만 안전을 위해 호출
            self.rx_log_list.set_search_pattern(text)
            self.rx_log_list.find_next(text)

    @pyqtSlot()
    def on_rx_search_prev_clicked(self) -> None:
        """검색창의 텍스트로 이전 항목을 찾습니다."""
        text = self.rx_search_input.text()
        if text:
            self.rx_log_list.find_prev(text)

    @pyqtSlot(str)
    def on_rx_search_text_changed(self, text: str) -> None:
        """검색어가 변경되면 하이라이트 패턴을 즉시 업데이트합니다."""
        self.rx_log_list.set_search_pattern(text)

    @pyqtSlot()
    def on_clear_rx_log_clicked(self) -> None:
        """화면에 표시된 로그와 대기 중인 버퍼를 모두 지웁니다."""
        self.rx_log_list.clear()
        self.ui_update_buffer.clear()

    @pyqtSlot(bool)
    def on_recording_toggled(self, checked: bool) -> None:
        """
        녹화 시작/중단 토글을 처리합니다.
        
        Args:
            checked: 버튼 체크 상태 (True=녹화 시작, False=녹화 중단)
        """
        if checked:
            # 파일 저장 대화상자
            title = lang_manager.get_text("rx_btn_save")
            if self.tab_name:
                title = f"{self.tab_name}::{title}"

            filename, _ = QFileDialog.getSaveFileName(
                self,
                title,
                "",
                "Binary Files (*.bin);;All Files (*)"
            )
            
            if filename:
                # 녹화 시작 시그널
                self.recording_started.emit(filename)
                # 버튼 스타일 변경
                self.rx_save_log_btn.setText("● REC")
                self.rx_save_log_btn.setStyleSheet("color: red;")
            else:
                # 취소 시 버튼 복구
                self.rx_save_log_btn.setChecked(False)
        else:
            # 녹화 중단 시그널
            self.recording_stopped.emit()
            # 버튼 스타일 복구
            self.rx_save_log_btn.setText(lang_manager.get_text("rx_btn_save"))
            self.rx_save_log_btn.setStyleSheet("")


    @pyqtSlot(int)
    def on_rx_filter_changed(self, state: int) -> None:
        """
        필터 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.filter_enabled = (state == Qt.Checked)
        self.rx_log_list.set_filter_mode(self.filter_enabled)

    @pyqtSlot(int)
    def on_rx_hex_mode_changed(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.hex_mode = (state == Qt.Checked)
        self.rx_log_list.set_hex_mode_enabled(self.hex_mode)

    @pyqtSlot(int)
    def on_rx_timestamp_changed(self, state: int) -> None:
        """
        타임스탬프 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)
        self.rx_log_list.set_timestamp_enabled(self.timestamp_enabled, timeout_ms=100)

    @pyqtSlot(int)
    def on_rx_pause_changed(self, state: int) -> None:
        """
        일시 정지 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.is_paused = (state == Qt.Checked)

    # -------------------------------------------------------------------------
    # 설정 및 상태 관리
    # -------------------------------------------------------------------------
    def set_max_lines(self, max_lines: int) -> None:
        """
        표시할 최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수.
        """
        self.max_lines = max_lines
        self.rx_log_list.set_max_lines(max_lines)

    def save_state(self) -> dict:
        """
        현재 위젯의 UI 상태를 딕셔너리로 반환합니다 (설정 저장용).

        Returns:
            dict: {hex_mode, timestamp, is_paused, search_text, filter_enabled}
        """
        state = {
            "hex_mode": self.hex_mode,
            "timestamp": self.timestamp_enabled,
            "is_paused": self.is_paused,
            "search_text": self.rx_search_input.text(),
            "filter_enabled": self.filter_enabled,
            "newline_mode": self.rx_newline_combo.currentData()
        }
        return state

    def load_state(self, state: dict) -> None:
        """
        저장된 상태 딕셔너리를 UI에 적용합니다.

        Args:
            state (dict): 복원할 상태 정보.
        """
        if not state:
            return

        # 체크박스 상태 업데이트 (시그널 발생으로 내부 변수도 업데이트됨)
        self.rx_hex_chk.setChecked(state.get("hex_mode", False))
        self.rx_timestamp_chk.setChecked(state.get("timestamp", False))
        self.rx_pause_chk.setChecked(state.get("is_paused", False))
        self.rx_filter_chk.setChecked(state.get("filter_enabled", False))
        self.rx_search_input.setText(state.get("search_text", ""))

        newline_mode = state.get("newline_mode", "Raw")
        index = self.rx_newline_combo.findData(newline_mode)
        if index >= 0:
            self.rx_newline_combo.setCurrentIndex(index)

    def closeEvent(self, event) -> None:
        """위젯 종료 시 타이머를 안전하게 정지합니다."""
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()
        super().closeEvent(event)
