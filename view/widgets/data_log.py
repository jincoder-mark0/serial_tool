"""
DataLogWidget 모듈

시리얼 포트 등 외부로부터 수신/송신된 데이터를 표시하고 관리하는 메인 위젯을 정의합니다.
QSmartListView를 기반으로 하여 대량의 데이터 처리 성능을 최적화하였으며,
검색, HEX 모드, 타임스탬프, 일시 정지 등의 편의 기능을 제공합니다.

## WHY
* 통신 데이터는 수신(RX)뿐만 아니라 Local Echo를 통한 송신(TX)도 포함하므로,
  'RX'만을 강조하는 기존 이름(RxLogWidget)을 통신 데이터 전반을 의미하는 이름으로 변경
* Model 계층의 DataLogger와 이름의 일관성 확보
* 향후 Full Duplex 통신 프로토콜 확장 대비

## WHAT
* QSmartListView 기반 통신 데이터 뷰어
* 데이터 필터링, HEX/ASCII 모드 전환, 타임스탬프 표시
* 로그 저장(DataLoggerManager와 연동) 및 화면 초기화 기능

## HOW
* QSmartListView 객체에 데이터 및 설정 위임
* QTimer를 사용한 데이터 버퍼링 및 UI 업데이트 최적화
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit, QFileDialog, QComboBox
)
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, Qt
from typing import Optional, List
from view.managers.language_manager import language_manager

from view.custom_qt.smart_list_view import QSmartListView

from common.constants import (
    DEFAULT_LOG_MAX_LINES,
    UI_REFRESH_INTERVAL_MS,
    FILE_FILTER_LOG, FILE_FILTER_ALL
)
from common.enums import NewlineMode
from common.dtos import ColorRule # Import DTO

class DataLogWidget(QWidget):
    """
    데이터를 표시하는 뷰어 위젯 클래스
    """

    tx_broadcast_allow_changed = pyqtSignal(bool)

    # 로깅 시그널 변경: 파일명 없이 의도만 전달
    logging_start_requested = pyqtSignal()
    logging_stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        DataLogWidget를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # ---------------------------------------------------------
        # 1. 상태 변수 초기화
        # ---------------------------------------------------------
        # UI Components
        self.data_log_title = None
        self.data_log_list = None
        self.data_log_search_prev_btn: Optional[QPushButton] = None
        self.data_log_search_next_btn: Optional[QPushButton] = None
        self.data_log_tx_broadcast_allow_chk: Optional[QCheckBox] = None
        self.data_log_search_input = None
        self.data_log_toggle_logging_btn: Optional[QPushButton] = None
        self.data_log_clear_log_btn: Optional[QPushButton] = None
        self.data_log_pause_chk: Optional[QCheckBox] = None
        self.data_log_timestamp_chk: Optional[QCheckBox] = None
        self.data_log_hex_chk: Optional[QCheckBox] = None
        self.data_log_filter_chk: Optional[QCheckBox] = None
        self.data_log_newline_combo: Optional[QComboBox] = None

        # State Variables
        self.tx_broadcast_allow_enabled: bool = True
        self.hex_mode: bool = False
        self.is_paused: bool = False
        self.timestamp_enabled: bool = False
        self.filter_enabled: bool = False
        self.ui_update_buffer: list = []

        self.max_lines: int = DEFAULT_LOG_MAX_LINES
        self.tab_name: str = ""

        # Removed self.color_manager = color_manager

        # ---------------------------------------------------------
        # 2. UI 구성 및 시그널 연결
        # ---------------------------------------------------------
        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

        # ---------------------------------------------------------
        # 3. 타이머 설정 (성능 최적화)
        # ---------------------------------------------------------
        self.ui_update_timer: QTimer = QTimer()
        self.ui_update_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self.ui_update_timer.timeout.connect(self.flush_buffer)
        self.ui_update_timer.start()

    def set_tab_name(self, name: str) -> None:
        """
        탭 이름 설정

        Args:
            name: 탭 이름
        """
        self.tab_name = name

    def set_color_rules(self, rules: List[ColorRule]) -> None:
        """
        색상 규칙 설정 (External Injection)

        Args:
            rules: ColorRule 리스트
        """
        self.data_log_list.set_color_rules(rules)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        # 1. 툴바 영역 (타이틀 + 도구들)
        # 타이틀 섹션
        self.data_log_title = QLabel(language_manager.get_text("data_log_title"))
        self.data_log_title.setProperty("class", "section-title")

        # 도구 섹션 (검색, 옵션, 액션)
        # TX Broadcast Checkbox
        self.data_log_tx_broadcast_allow_chk = QCheckBox(language_manager.get_text("data_log_chk_tx_broadcast_allow"))
        self.data_log_tx_broadcast_allow_chk.setToolTip(language_manager.get_text("data_log_chk_tx_broadcast_allow_tooltip"))
        self.data_log_tx_broadcast_allow_chk.stateChanged.connect(self.on_data_log_tx_broadcast_allow_changed)

        # Search Bar
        self.data_log_search_input = QLineEdit()
        self.data_log_search_input.setPlaceholderText(language_manager.get_text("data_log_input_search_placeholder"))
        self.data_log_search_input.setToolTip(language_manager.get_text("data_log_input_search_tooltip"))
        self.data_log_search_input.setMaximumWidth(200)
        self.data_log_search_input.returnPressed.connect(self.on_data_log_search_next_clicked)
        # 검색어 변경 시 실시간 하이라이트 갱신
        self.data_log_search_input.textChanged.connect(self.on_data_log_search_text_changed)

        # Buttons
        self.data_log_search_prev_btn = QPushButton()
        self.data_log_search_prev_btn.setObjectName("data_log_search_prev_btn")
        self.data_log_search_prev_btn.setText("<") # 아이콘이 없을 경우를 대비한 텍스트
        self.data_log_search_prev_btn.setToolTip(language_manager.get_text("data_log_btn_search_prev_tooltip"))
        self.data_log_search_prev_btn.setFixedWidth(30)
        self.data_log_search_prev_btn.clicked.connect(self.on_data_log_search_prev_clicked)

        self.data_log_search_next_btn = QPushButton()
        self.data_log_search_next_btn.setObjectName("data_log_search_next_btn")
        self.data_log_search_next_btn.setText(">") # 아이콘이 없을 경우를 대비한 텍스트
        self.data_log_search_next_btn.setToolTip(language_manager.get_text("data_log_btn_search_next_tooltip"))
        self.data_log_search_next_btn.setFixedWidth(30)
        self.data_log_search_next_btn.clicked.connect(self.on_data_log_search_next_clicked)

        self.data_log_clear_log_btn = QPushButton(language_manager.get_text("data_log_btn_clear"))
        self.data_log_clear_log_btn.setToolTip(language_manager.get_text("data_log_btn_clear_tooltip"))
        self.data_log_clear_log_btn.clicked.connect(self.on_clear_data_log_clicked)

        self.data_log_toggle_logging_btn = QPushButton(language_manager.get_text("data_log_btn_toggle_logging"))
        self.data_log_toggle_logging_btn.setToolTip(language_manager.get_text("data_log_btn_toggle_logging_tooltip"))
        self.data_log_toggle_logging_btn.setCheckable(True)  # 토글 버튼으로 변경
        self.data_log_toggle_logging_btn.toggled.connect(self.on_data_log_logging_toggled)

        # Options
        self.data_log_filter_chk = QCheckBox(language_manager.get_text("data_log_chk_filter"))
        self.data_log_filter_chk.setToolTip(language_manager.get_text("data_log_chk_filter_tooltip"))
        self.data_log_filter_chk.stateChanged.connect(self.on_data_log_filter_changed)

        self.data_log_hex_chk = QCheckBox(language_manager.get_text("data_log_chk_hex"))
        self.data_log_hex_chk.setToolTip(language_manager.get_text("data_log_chk_hex_tooltip"))
        self.data_log_hex_chk.stateChanged.connect(self.on_data_log_hex_mode_changed)

        self.data_log_timestamp_chk = QCheckBox(language_manager.get_text("data_log_chk_timestamp"))
        self.data_log_timestamp_chk.setToolTip(language_manager.get_text("data_log_chk_timestamp_tooltip"))
        self.data_log_timestamp_chk.stateChanged.connect(self.on_data_log_timestamp_changed)

        self.data_log_pause_chk = QCheckBox(language_manager.get_text("data_log_chk_pause"))
        self.data_log_pause_chk.setToolTip(language_manager.get_text("data_log_chk_pause_tooltip"))
        self.data_log_pause_chk.stateChanged.connect(self.on_data_log_pause_changed)

        # Newline Combo
        self.data_log_newline_combo = QComboBox()
        self.data_log_newline_combo.setToolTip(language_manager.get_text("data_log_combo_newline_tooltip"))
        self.data_log_newline_combo.addItem(language_manager.get_text("data_log_newline_raw"), NewlineMode.RAW.value)
        self.data_log_newline_combo.addItem(language_manager.get_text("data_log_newline_lf"), NewlineMode.LF.value)
        self.data_log_newline_combo.addItem(language_manager.get_text("data_log_newline_cr"), NewlineMode.CR.value)
        self.data_log_newline_combo.addItem(language_manager.get_text("data_log_newline_crlf"), NewlineMode.CRLF.value)
        self.data_log_newline_combo.setFixedWidth(100)

        # Log View
        self.data_log_list = QSmartListView()
        self.data_log_list.set_max_lines(DEFAULT_LOG_MAX_LINES)
        self.data_log_list.setReadOnly(True)
        # set_color_manager 호출 제거, rules는 나중에 주입됨
        self.data_log_list.set_hex_mode_enabled(self.hex_mode)
        self.data_log_list.set_timestamp_enabled(self.timestamp_enabled, timeout_ms=100)
        self.data_log_list.setPlaceholderText(language_manager.get_text("data_log_list_log_placeholder"))
        self.data_log_list.setToolTip(language_manager.get_text("data_log_list_log_tooltip"))
        self.data_log_list.setProperty("class", "fixed-font")

        # Components Init (Reuse existing initialization code)
        self.data_log_title = QLabel(language_manager.get_text("data_log_title"))
        self.data_log_title.setProperty("class", "section-title")
        self.data_log_tx_broadcast_allow_chk = QCheckBox(language_manager.get_text("data_log_chk_tx_broadcast_allow"))
        self.data_log_tx_broadcast_allow_chk.stateChanged.connect(self.on_data_log_tx_broadcast_allow_changed)
        self.data_log_search_input = QLineEdit()
        self.data_log_search_input.returnPressed.connect(self.on_data_log_search_next_clicked)
        self.data_log_search_input.textChanged.connect(self.on_data_log_search_text_changed)
        self.data_log_search_prev_btn = QPushButton("<")
        self.data_log_search_prev_btn.clicked.connect(self.on_data_log_search_prev_clicked)
        self.data_log_search_next_btn = QPushButton(">")
        self.data_log_search_next_btn.clicked.connect(self.on_data_log_search_next_clicked)
        self.data_log_clear_log_btn = QPushButton(language_manager.get_text("data_log_btn_clear"))
        self.data_log_clear_log_btn.clicked.connect(self.on_clear_data_log_clicked)
        self.data_log_toggle_logging_btn = QPushButton(language_manager.get_text("data_log_btn_toggle_logging"))
        self.data_log_toggle_logging_btn.setCheckable(True)
        self.data_log_toggle_logging_btn.toggled.connect(self.on_data_log_logging_toggled)
        self.data_log_filter_chk = QCheckBox(language_manager.get_text("data_log_chk_filter"))
        self.data_log_filter_chk.stateChanged.connect(self.on_data_log_filter_changed)
        self.data_log_hex_chk = QCheckBox(language_manager.get_text("data_log_chk_hex"))
        self.data_log_hex_chk.stateChanged.connect(self.on_data_log_hex_mode_changed)
        self.data_log_timestamp_chk = QCheckBox(language_manager.get_text("data_log_chk_timestamp"))
        self.data_log_timestamp_chk.stateChanged.connect(self.on_data_log_timestamp_changed)
        self.data_log_pause_chk = QCheckBox(language_manager.get_text("data_log_chk_pause"))
        self.data_log_pause_chk.stateChanged.connect(self.on_data_log_pause_changed)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.data_log_title)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.data_log_tx_broadcast_allow_chk)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.data_log_search_input)
        toolbar_layout.addWidget(self.data_log_search_prev_btn)
        toolbar_layout.addWidget(self.data_log_search_next_btn)
        toolbar_layout.addWidget(self.data_log_filter_chk)
        toolbar_layout.addWidget(self.data_log_newline_combo)
        toolbar_layout.addWidget(self.data_log_hex_chk)
        toolbar_layout.addWidget(self.data_log_timestamp_chk)
        toolbar_layout.addWidget(self.data_log_pause_chk)
        toolbar_layout.addWidget(self.data_log_clear_log_btn)
        toolbar_layout.addWidget(self.data_log_toggle_logging_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.data_log_list)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 현재 언어 설정에 맞게 업데이트합니다."""
        # Labels & Tooltips
        self.data_log_title.setText(language_manager.get_text("data_log_title"))
        self.data_log_list.setToolTip(language_manager.get_text("data_log_list_log_tooltip"))
        self.data_log_list.setPlaceholderText(language_manager.get_text("data_log_list_log_placeholder"))

        # TX Broadcast Components
        self.data_log_tx_broadcast_allow_chk.setText(language_manager.get_text("data_log_chk_tx_broadcast_allow"))
        self.data_log_tx_broadcast_allow_chk.setToolTip(language_manager.get_text("data_log_chk_tx_broadcast_allow_tooltip"))

        # Search Components
        self.data_log_search_input.setPlaceholderText(language_manager.get_text("data_log_input_search_placeholder"))
        self.data_log_search_input.setToolTip(language_manager.get_text("data_log_input_search_tooltip"))
        self.data_log_search_prev_btn.setToolTip(language_manager.get_text("data_log_btn_search_prev_tooltip"))
        self.data_log_search_next_btn.setToolTip(language_manager.get_text("data_log_btn_search_next_tooltip"))

        # Checkboxes
        self.data_log_filter_chk.setText(language_manager.get_text("data_log_chk_filter"))
        self.data_log_filter_chk.setToolTip(language_manager.get_text("data_log_chk_filter_tooltip"))
        self.data_log_hex_chk.setText(language_manager.get_text("data_log_chk_hex"))
        self.data_log_hex_chk.setToolTip(language_manager.get_text("data_log_chk_hex_tooltip"))
        self.data_log_timestamp_chk.setText(language_manager.get_text("data_log_chk_timestamp"))
        self.data_log_timestamp_chk.setToolTip(language_manager.get_text("data_log_chk_timestamp_tooltip"))
        self.data_log_pause_chk.setText(language_manager.get_text("data_log_chk_pause"))
        self.data_log_pause_chk.setToolTip(language_manager.get_text("data_log_chk_pause_tooltip"))

        # Buttons
        self.data_log_clear_log_btn.setText(language_manager.get_text("data_log_btn_clear"))
        self.data_log_clear_log_btn.setToolTip(language_manager.get_text("data_log_btn_clear_tooltip"))

        # 로깅 버튼 텍스트는 상태에 따라 달라짐 (토글 시)
        if not self.data_log_toggle_logging_btn.isChecked():
            self.data_log_toggle_logging_btn.setText(language_manager.get_text("data_log_btn_toggle_logging"))
        self.data_log_toggle_logging_btn.setToolTip(language_manager.get_text("data_log_btn_toggle_logging_tooltip"))

        # Newline Combo
        current_index = self.data_log_newline_combo.currentIndex()
        self.data_log_newline_combo.setItemText(0, language_manager.get_text("data_log_newline_raw"))
        self.data_log_newline_combo.setItemText(1, language_manager.get_text("data_log_newline_lf"))
        self.data_log_newline_combo.setItemText(2, language_manager.get_text("data_log_newline_cr"))
        self.data_log_newline_combo.setItemText(3, language_manager.get_text("data_log_newline_crlf"))
        self.data_log_newline_combo.setToolTip(language_manager.get_text("data_log_combo_newline_tooltip"))
        self.data_log_newline_combo.setCurrentIndex(current_index)

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
        newline_mode = self.data_log_newline_combo.currentData()

        if self.hex_mode or newline_mode == NewlineMode.RAW.value:
            newline_char = None
        else:
            newline_char = {
                NewlineMode.LF.value: "\n",
                NewlineMode.CR.value: "\r",
                NewlineMode.CRLF.value: "\r\n"
            }.get(newline_mode, "\n")

        self.data_log_list.set_newline_char(newline_char)

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
            self.data_log_list.append_bytes(data)

    # -------------------------------------------------------------------------
    # 사용자 액션 처리 (검색, 옵션, 버튼)
    # -------------------------------------------------------------------------
    @pyqtSlot()
    def on_data_log_search_next_clicked(self) -> None:
        """검색창의 텍스트로 다음 항목을 찾습니다."""
        text = self.data_log_search_input.text()

        if text:
            # 패턴 설정은 textChanged에서 실시간으로 되지만 안전을 위해 호출
            self.data_log_list.set_search_pattern(text)
            self.data_log_list.find_next(text)

    @pyqtSlot()
    def on_data_log_search_prev_clicked(self) -> None:
        """검색창의 텍스트로 이전 항목을 찾습니다."""
        text = self.data_log_search_input.text()
        if text:
            self.data_log_list.find_prev(text)

    @pyqtSlot(str)
    def on_data_log_search_text_changed(self, text: str) -> None:
        """검색어가 변경되면 하이라이트 패턴을 즉시 업데이트합니다."""
        self.data_log_list.set_search_pattern(text)

    @pyqtSlot()
    def on_clear_data_log_clicked(self) -> None:
        """화면에 표시된 로그와 대기 중인 버퍼를 모두 지웁니다."""
        self.data_log_list.clear()
        self.ui_update_buffer.clear()

    @pyqtSlot(bool)
    def on_data_log_logging_toggled(self, checked: bool) -> None:
        """
        로깅 버튼 토글 핸들러

        Logic:
            - UI 상태 변경 없이 오직 시그널만 발행
            - 실제 UI 변경은 Presenter가 set_logging_active를 호출할 때 수행
        """
        if checked:
            self.logging_start_requested.emit()
        else:
            self.logging_stop_requested.emit()

    def set_logging_active(self, active: bool) -> None:
        """
        외부(Presenter)에서 로깅 상태를 설정
        성공적으로 시작/중지되었을 때 호출됨

        Args:
            active (bool): 로깅 활성화 여부
        """
        self.data_log_toggle_logging_btn.blockSignals(True)
        self.data_log_toggle_logging_btn.setChecked(active)
        self.data_log_toggle_logging_btn.blockSignals(False)

        if active:
            self.data_log_toggle_logging_btn.setText("● REC")
            self.data_log_toggle_logging_btn.setStyleSheet("color: red;")
        else:
            self.data_log_toggle_logging_btn.setText(language_manager.get_text("data_log_btn_toggle_logging"))
            self.data_log_toggle_logging_btn.setStyleSheet("")

    def show_save_log_dialog(self) -> str:
        """
        파일 저장 다이얼로그 표시 (Presenter가 호출)

        Returns:
            str: 선택된 파일 경로 (취소 시 빈 문자열)
        """
        title = language_manager.get_text("data_log_btn_toggle_logging")
        if self.tab_name:
            title = f"{self.tab_name}::{title}"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            title,
            "",
            f"{FILE_FILTER_LOG};;{FILE_FILTER_ALL}"
        )
        return filename

    @pyqtSlot(int)
    def on_data_log_tx_broadcast_allow_changed(self, state: int) -> None:
        """
        TX Broadcast 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.tx_broadcast_allow_enabled = (state == Qt.Checked)
        self.tx_broadcast_allow_changed.emit(self.tx_broadcast_allow_enabled)

    @pyqtSlot(int)
    def on_data_log_filter_changed(self, state: int) -> None:
        """
        필터 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.filter_enabled = (state == Qt.Checked)
        self.data_log_list.set_filter_mode(self.filter_enabled)

    @pyqtSlot(int)
    def on_data_log_hex_mode_changed(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.hex_mode = (state == Qt.Checked)
        self.data_log_list.set_hex_mode_enabled(self.hex_mode)

    @pyqtSlot(int)
    def on_data_log_timestamp_changed(self, state: int) -> None:
        """
        Timestamp 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)
        self.data_log_list.set_timestamp_enabled(self.timestamp_enabled, timeout_ms=100)

    @pyqtSlot(int)
    def on_data_log_pause_changed(self, state: int) -> None:
        """
        Pause 토글을 처리

        Args:
            state (int): 체크박스 상태.
        """
        self.is_paused = (state == Qt.Checked)

    # -------------------------------------------------------------------------
    # 설정 및 상태 관리
    # -------------------------------------------------------------------------
    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수.
        """
        self.max_lines = max_lines
        self.data_log_list.set_max_lines(max_lines)

    @property
    def is_broadcast_enabled(self) -> bool:
        """
        TX Broadcast 토글의 상태를 반환

        Returns:
            bool: TX Broadcast 토글의 상태.
        """
        return self.tx_broadcast_allow_enabled

    def save_state(self) -> dict:
        """
        현재 상태를 저장 (설정 저장용)

        Returns:
            dict: 현재 상태.
        """
        return {
            "tx_broadcast_allow_enabled": self.tx_broadcast_allow_enabled,
            "hex_mode": self.hex_mode,
            "timestamp": self.timestamp_enabled,
            "is_paused": self.is_paused,
            "search_text": self.data_log_search_input.text(),
            "filter_enabled": self.filter_enabled,
            "newline_mode": self.data_log_newline_combo.currentData()
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
        self.data_log_tx_broadcast_allow_chk.setChecked(state.get("tx_broadcast_allow_enabled", False))
        self.data_log_hex_chk.setChecked(state.get("hex_mode", False))
        self.data_log_timestamp_chk.setChecked(state.get("timestamp", False))
        self.data_log_pause_chk.setChecked(state.get("is_paused", False))
        self.data_log_filter_chk.setChecked(state.get("filter_enabled", False))
        self.data_log_search_input.setText(state.get("search_text", ""))

        newline_mode = state.get("newline_mode", NewlineMode.RAW.value)
        index = self.data_log_newline_combo.findData(newline_mode)
        if index >= 0:
            self.data_log_newline_combo.setCurrentIndex(index)

    def closeEvent(self, event) -> None:
        """
        위젯 종료 시 타이머를 안전하게 정지

        Args:
            event (QCloseEvent): 종료 이벤트.
        """
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()
        super().closeEvent(event)
