from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit, QFileDialog, QComboBox
)
from PyQt5.QtCore import pyqtSlot
from typing import Optional
import datetime
from view.managers.language_manager import language_manager
from view.custom_qt.smart_list_view import QSmartListView
from view.managers.color_manager import color_manager

from constants import (
    DEFAULT_LOG_MAX_LINES
)

class SystemLogWidget(QWidget):
    """
    시스템 상태 메시지 및 에러 로그를 표시하는 위젯 클래스입니다.
    QTextEdit를 사용하여 여러 줄의 상태 이력을 관리합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        SystemLogWidget를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # ---------------------------------------------------------
        # 1. 상태 변수 초기화
        # ---------------------------------------------------------
        # UI Components
        self.sys_log_title = None
        self.sys_log_list = None
        self.sys_log_search_input = None
        self.sys_log_search_prev_btn = None
        self.sys_log_search_next_btn = None

        self.sys_log_toggle_logging_btn = None
        self.sys_log_clear_log_btn = None
        self.sys_log_filter_chk = None  # Filter Checkbox

        # State Variables
        self.filter_enabled: bool = False # Filter State

        # ---------------------------------------------------------
        # 2. UI 구성 및 시그널 연결
        # ---------------------------------------------------------
        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        self.setFixedHeight(100) # 위젯 전체 높이 고정

        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        # 1. 툴바 영역 (타이틀 + 도구들)
        # 타이틀 섹션
        self.sys_log_title = QLabel(language_manager.get_text("sys_log_title"))
        self.sys_log_title.setProperty("class", "section-title")  # 섹션 타이틀 스타일 적용

        # 도구 섹션 (검색, 옵션, 액션)
        # Search Bar
        self.sys_log_search_input = QLineEdit()
        self.sys_log_search_input.setPlaceholderText(language_manager.get_text("sys_log_input_search_placeholder"))
        self.sys_log_search_input.setToolTip(language_manager.get_text("sys_log_input_search_tooltip"))
        self.sys_log_search_input.setMaximumWidth(200)
        self.sys_log_search_input.returnPressed.connect(self.on_sys_log_search_next_clicked)
        # 검색어 변경 시 실시간 하이라이트 갱신
        self.sys_log_search_input.textChanged.connect(self.on_sys_log_search_text_changed)

        # Buttons
        self.sys_log_search_prev_btn = QPushButton()
        self.sys_log_search_prev_btn.setObjectName("sys_log_search_prev_btn")
        self.sys_log_search_prev_btn.setText("<") # 아이콘이 없을 경우를 대비한 텍스트
        self.sys_log_search_prev_btn.setToolTip(language_manager.get_text("sys_log_btn_search_prev_tooltip"))
        self.sys_log_search_prev_btn.setFixedWidth(30)
        self.sys_log_search_prev_btn.clicked.connect(self.on_sys_log_search_prev_clicked)

        self.sys_log_search_next_btn = QPushButton()
        self.sys_log_search_next_btn.setObjectName("sys_log_search_next_btn")
        self.sys_log_search_next_btn.setText(">") # 아이콘이 없을 경우를 대비한 텍스트
        self.sys_log_search_next_btn.setToolTip(language_manager.get_text("sys_log_btn_search_next_tooltip"))
        self.sys_log_search_next_btn.setFixedWidth(30)
        self.sys_log_search_next_btn.clicked.connect(self.on_sys_log_search_next_clicked)

        self.sys_log_clear_log_btn = QPushButton(language_manager.get_text("sys_log_btn_clear"))
        self.sys_log_clear_log_btn.setToolTip(language_manager.get_text("sys_log_btn_clear_tooltip"))
        self.sys_log_clear_log_btn.clicked.connect(self.on_clear_sys_log_clicked)

        self.sys_log_toggle_logging_btn = QPushButton(language_manager.get_text("sys_log_btn_toggle_logging"))
        self.sys_log_toggle_logging_btn.setToolTip(language_manager.get_text("sys_log_btn_toggle_logging_tooltip"))
        self.sys_log_toggle_logging_btn.setCheckable(True)  # 토글 버튼으로 변경
        self.sys_log_toggle_logging_btn.toggled.connect(self.on_sys_log_logging_toggled)

        # Options
        self.sys_log_filter_chk = QCheckBox(language_manager.get_text("sys_log_chk_filter"))
        self.sys_log_filter_chk.setToolTip(language_manager.get_text("sys_log_chk_filter_tooltip"))
        self.sys_log_filter_chk.stateChanged.connect(self.on_sys_log_filter_changed)
        # 2. 로그 뷰 영역
        # self.sys_log_list = QTextEdit()
        self.sys_log_list = QSmartListView()
        self.sys_log_list.set_max_lines(DEFAULT_LOG_MAX_LINES)
        self.sys_log_list.setReadOnly(True)
        self.sys_log_list.setPlaceholderText(language_manager.get_text("sys_log_list_log_placeholder"))
        self.sys_log_list.setToolTip(language_manager.get_text("sys_log_list_log_tooltip"))
        self.sys_log_list.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        # Layout 배치
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.sys_log_title)
        toolbar_layout.addWidget(self.sys_log_search_input)
        toolbar_layout.addWidget(self.sys_log_search_prev_btn)
        toolbar_layout.addWidget(self.sys_log_search_next_btn)
        toolbar_layout.addWidget(self.sys_log_filter_chk) # Filter Checkbox
        toolbar_layout.addWidget(self.sys_log_clear_log_btn)
        toolbar_layout.addWidget(self.sys_log_toggle_logging_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.sys_log_list)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 현재 언어 설정에 맞게 업데이트합니다."""
        # Labels & Tooltips
        self.sys_log_title.setText(language_manager.get_text("sys_log_title"))
        self.sys_log_list.setToolTip(language_manager.get_text("sys_log_list_log_tooltip"))
        self.sys_log_list.setPlaceholderText(language_manager.get_text("sys_log_list_log_placeholder"))

        # Search Components
        self.sys_log_search_input.setPlaceholderText(language_manager.get_text("sys_log_input_search_placeholder"))
        self.sys_log_search_input.setToolTip(language_manager.get_text("sys_log_input_search_tooltip"))
        self.sys_log_search_prev_btn.setToolTip(language_manager.get_text("sys_log_btn_search_prev_tooltip"))
        self.sys_log_search_next_btn.setToolTip(language_manager.get_text("sys_log_btn_search_next_tooltip"))

        # Checkboxes
        self.sys_log_filter_chk.setText(language_manager.get_text("sys_log_chk_filter"))
        self.sys_log_filter_chk.setToolTip(language_manager.get_text("sys_log_chk_filter_tooltip"))

        # Buttons
        self.sys_log_clear_log_btn.setText(language_manager.get_text("sys_log_btn_clear"))
        self.sys_log_clear_log_btn.setToolTip(language_manager.get_text("sys_log_btn_clear_tooltip"))

        # 로깅 버튼 텍스트는 상태에 따라 달라짐 (토글 시)
        if not self.sys_log_toggle_logging_btn.isChecked():
            self.sys_log_toggle_logging_btn.setText(language_manager.get_text("sys_log_btn_toggle_logging"))
        self.sys_log_toggle_logging_btn.setToolTip(language_manager.get_text("sys_log_btn_toggle_logging_tooltip"))

    def log(self, message: str, level: str = "INFO") -> None:
        """
        상태 메시지를 로그에 추가합니다.

        Args:
            message (str): 표시할 메시지.
            level (str): 로그 레벨 (INFO, ERROR, WARN, SUCCESS). 기본값은 "INFO".
        """
        # 1. 메시지 포맷팅: [LEVEL] Message
        text = f"[{level}] {message}"

        # 2. 타임스탬프 추가
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        full_text = f"{timestamp} {text}"

        # 3. 색상 규칙 적용 (ColorManager 활용)
        # ColorManager에 SYS_INFO, TIMESTAMP 등의 규칙이 정의되어 있어야 함
        full_text = color_manager.apply_rules(full_text)

        # 4. 뷰에 추가
        self.sys_log_list.append(full_text)

    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.sys_log_list.clear()

    # -------------------------------------------------------------------------
    # 사용자 액션 처리 (검색, 옵션, 버튼)
    # -------------------------------------------------------------------------
    @pyqtSlot()
    def on_sys_log_search_next_clicked(self) -> None:
        """검색창의 텍스트로 다음 항목을 찾습니다."""
        text = self.sys_log_search_input.text()
        if text:
            # 패턴 설정은 textChanged에서 실시간으로 되지만 안전을 위해 호출
            self.sys_log_list.set_search_pattern(text)
            self.sys_log_list.find_next(text)

    @pyqtSlot()
    def on_sys_log_search_prev_clicked(self) -> None:
        """검색창의 텍스트로 이전 항목을 찾습니다."""
        text = self.sys_log_search_input.text()
        if text:
            self.sys_log_list.find_prev(text)

    @pyqtSlot(str)
    def on_sys_log_search_text_changed(self, text: str) -> None:
        """검색어가 변경되면 하이라이트 패턴을 즉시 업데이트합니다."""
        self.sys_log_list.set_search_pattern(text)

    @pyqtSlot()
    def on_clear_sys_log_clicked(self) -> None:
        """화면에 표시된 로그와 대기 중인 버퍼를 모두 지웁니다."""
        self.sys_log_list.clear()

    @pyqtSlot(bool)
    def on_sys_log_logging_toggled(self, checked: bool) -> None:
        """
        로깅 시작/중단 토글을 처리합니다.

        Args:
            checked: 버튼 체크 상태 (True=로깅 시작, False=로깅 중단)
        """
        if checked:
            # 파일 저장 대화상자
            title = language_manager.get_text("sys_log_btn_toggle_logging")
            if self.tab_name:
                title = f"{self.tab_name}::{title}"

            filename, _ = QFileDialog.getSaveFileName(
                self,
                title,
                "",
                "Binary Files (*.bin);;All Files (*)"
            )

            if filename:
                # 로깅 시작 시그널
                self.sys_logging_started.emit(filename)
                # 버튼 스타일 변경
                self.sys_log_toggle_logging_btn.setText("● REC")
                self.sys_log_toggle_logging_btn.setStyleSheet("color: red;")
            else:
                # 취소 시 버튼 복구
                self.sys_log_toggle_logging_btn.setChecked(False)
        else:
            # 로깅 중단 시그널
            self.sys_logging_stopped.emit()
            # 버튼 스타일 복구
            self.sys_log_toggle_logging_btn.setText(language_manager.get_text("sys_log_btn_toggle_logging"))
            self.sys_log_toggle_logging_btn.setStyleSheet("")


    @pyqtSlot(int)
    def on_sys_log_filter_changed(self, state: int) -> None:
        """
        필터 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.filter_enabled = (state == Qt.Checked)
        self.sys_log_list.set_filter_mode(self.filter_enabled)

    # -------------------------------------------------------------------------
    # 설정 및 상태 관리
    # -------------------------------------------------------------------------
    def save_state(self) -> dict:
        """
        현재 위젯의 UI 상태를 딕셔너리로 반환합니다 (설정 저장용).

        Returns:
            dict: {search_text, filter_enabled}
        """
        state = {
            "search_text": self.sys_log_search_input.text(),
            "filter_enabled": self.filter_enabled,
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
        self.sys_log_filter_chk.setChecked(state.get("filter_enabled", False))
        self.sys_log_search_input.setText(state.get("search_text", ""))

    def closeEvent(self, event) -> None:
        """위젯 종료 시 타이머를 안전하게 정지합니다."""
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()
        super().closeEvent(event)
