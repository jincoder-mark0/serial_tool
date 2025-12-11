"""
ReceivedAreaWidget 모듈

시리얼 포트 등 외부로부터 수신된 데이터를 표시하고 관리하는 메인 위젯을 정의합니다.
QSmartListView를 기반으로 하여 대량의 데이터 처리 성능을 최적화하였으며,
검색, HEX 모드, 타임스탬프, 일시 정지 등의 편의 기능을 제공합니다.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit
)
from PyQt5.QtCore import QTimer, pyqtSlot, Qt
from typing import Optional
import datetime
from view.managers.color_manager import color_manager   # 전역 매니저 사용
from view.managers.lang_manager import lang_manager     # 전역 매니저 사용

from view.custom_widgets.smart_list_view import QSmartListView

from app_constants import (
    DEFAULT_LOG_MAX_LINES,
    UI_REFRESH_INTERVAL_MS,
    LOG_COLOR_TIMESTAMP
)
from core.logger import logger

class ReceivedAreaWidget(QWidget):
    """
    수신된 시리얼 데이터를 표시하는 위젯 클래스입니다.
    텍스트/HEX 모드 전환, 일시 정지, 타임스탬프 표시, 로그 저장 및 지우기 기능을 제공합니다.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ReceivedAreaWidget를 초기화합니다.

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
        self.rx_log_title = None
        self.rx_log_list = None

        # State Variables
        self.hex_mode: bool = False
        self.is_paused: bool = False
        self.timestamp_enabled: bool = False
        self.ui_update_buffer: list[str] = []
        self.max_lines: int = DEFAULT_LOG_MAX_LINES

        # 색상 규칙 관리자
        self.color_manager = color_manager

        # ---------------------------------------------------------
        # 2. UI 구성 및 시그널 연결
        # ---------------------------------------------------------
        self.init_ui()

        # 언어 변경 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

        # ---------------------------------------------------------
        # 3. 타이머 설정 (성능 최적화)
        # ---------------------------------------------------------
        self.ui_update_timer: QTimer = QTimer()
        self.ui_update_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self.ui_update_timer.timeout.connect(self.flush_buffer)
        self.ui_update_timer.start()

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
        self.rx_save_log_btn.clicked.connect(self.on_save_log_clicked)

        # Options
        self.rx_hex_chk = QCheckBox(lang_manager.get_text("rx_chk_hex"))
        self.rx_hex_chk.setToolTip(lang_manager.get_text("rx_chk_hex_tooltip"))
        self.rx_hex_chk.stateChanged.connect(self.on_rx_hex_mode_changed)

        self.rx_timestamp_chk = QCheckBox(lang_manager.get_text("rx_chk_timestamp"))
        self.rx_timestamp_chk.setToolTip(lang_manager.get_text("rx_chk_timestamp_tooltip"))
        self.rx_timestamp_chk.stateChanged.connect(self.on_rx_timestamp_changed)

        self.rx_pause_chk = QCheckBox(lang_manager.get_text("rx_chk_pause"))
        self.rx_pause_chk.setToolTip(lang_manager.get_text("rx_chk_pause_tooltip"))
        self.rx_pause_chk.stateChanged.connect(self.on_rx_pause_changed)



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

    # -------------------------------------------------------------------------
    # 데이터 처리 및 버퍼링
    # -------------------------------------------------------------------------
    def append_data(self, data: bytes) -> None:
        """
        수신된 바이트 데이터를 처리하여 버퍼에 추가합니다.

        Args:
            data (bytes): 수신된 원본 바이트 데이터.
        """
        # 일시 정지 상태면 데이터 무시
        if self.is_paused:
            return

        text: str = ""

        # 1. 포맷 변환 (Hex / Text)
        if self.hex_mode:
            text = " ".join([f"{b:02X}" for b in data]) + " "
        else:
            try:
                # UTF-8 디코딩 (에러 발생 시 대체 문자 사용)
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)

        # 2. 타임스탬프 추가
        if self.timestamp_enabled:
            ts = datetime.datetime.now().strftime("[%H:%M:%S]")
            # 타임스탬프 색상 적용 (상수 활용)
            text = f'<span style="color:{LOG_COLOR_TIMESTAMP};">{ts}</span> {text}'

        # 3. 색상 규칙 적용 (텍스트 모드일 때만)
        if not self.hex_mode:
            text = self.color_manager.apply_rules(text)

        # 4. 버퍼에 추가 (Lock 불필요: Python GIL 및 단일 GUI 스레드 환경)
        self.ui_update_buffer.append(text)

    def flush_buffer(self) -> None:
        """
        타이머에 의해 주기적으로 호출되어 버퍼 내용을 UI에 반영합니다.
        데이터를 한 번에 추가(Batch)하여 렌더링 부하를 줄입니다.
        """
        if not self.ui_update_buffer:
            return

        # 버퍼 내용을 복사하고 즉시 비움
        lines_to_add = self.ui_update_buffer[:]
        self.ui_update_buffer.clear()

        # QSmartListView의 배치 추가 메서드 호출
        # (내부적으로 최대 라인 수 제한 및 자동 스크롤 로직이 수행됨)
        self.rx_log_list.add_logs_batch(lines_to_add)

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

    @pyqtSlot()
    def on_save_log_clicked(self) -> None:
        """현재 표시된 로그 데이터를 파일로 저장합니다."""

        # 파일 저장 대화상자
        filename, _ = QFileDialog.getSaveFileName(
            self,
            lang_manager.get_text("rx_btn_save"),
            "",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                # QSmartListView에 새로 만든 메서드 호출
                # HTML 태그가 제거된 순수 텍스트를 한 번에 가져옴
                full_text = self.rx_log_list.get_all_text()

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(full_text)

            except Exception as e:
                logger.error(f"Error saving log: {e}")

    @pyqtSlot(int)
    def on_rx_hex_mode_changed(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.hex_mode = (state == Qt.Checked)

    @pyqtSlot(int)
    def on_rx_timestamp_changed(self, state: int) -> None:
        """
        타임스탬프 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)

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
            dict: {hex_mode, timestamp, is_paused, search_text}
        """
        state = {
            "hex_mode": self.hex_mode,
            "timestamp": self.timestamp_enabled,
            "is_paused": self.is_paused,
            "search_text": self.rx_search_input.text()
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
        self.rx_search_input.setText(state.get("search_text", ""))

    def closeEvent(self, event) -> None:
        """위젯 종료 시 타이머를 안전하게 정지합니다."""
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()
        super().closeEvent(event)