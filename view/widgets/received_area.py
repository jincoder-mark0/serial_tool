from PyQt5.QtWidgets import (
    QTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit, QScrollBar
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QTextCursor, QTextDocument
from typing import Optional
import datetime
from view.managers.color_manager import color_manager   # 전역 매니저 사용
from view.managers.lang_manager import lang_manager     # 전역 매니저 사용

from core.constants import (
    DEFAULT_LOG_MAX_LINES,
    TRIM_CHUNK_RATIO,
    UI_REFRESH_INTERVAL_MS,
    LOG_COLOR_TIMESTAMP
)

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
        self.rx_log_txt = None

        # State Variables
        self.hex_mode: bool = False
        self.is_paused: bool = False
        self.timestamp_enabled: bool = False
        self.ui_update_buffer: list[str] = []
        self.max_lines: int = DEFAULT_LOG_MAX_LINES
        self.trim_chunk_size: int = int(self.max_lines * TRIM_CHUNK_RATIO)

        # 색상 규칙 관리자
        self.color_manager = color_manager

        # UI Setup
        self.init_ui()

        # UI Update Timer (성능 최적화)
        self.ui_update_timer: QTimer = QTimer()
        self.ui_update_timer.setInterval(UI_REFRESH_INTERVAL_MS) # 50ms 간격
        self.ui_update_timer.timeout.connect(self.flush_batch)
        self.ui_update_timer.start()

        # 언어 변경 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

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
        self.rx_search_input.returnPressed.connect(self.on_rx_search_next_clicked)
        self.rx_search_input.setMaximumWidth(200)

        # Buttons
        self.rx_search_prev_btn = QPushButton()
        self.rx_search_prev_btn.setObjectName("rx_search_prev_btn")
        self.rx_search_prev_btn.setToolTip(lang_manager.get_text("rx_btn_search_prev_tooltip"))
        self.rx_search_prev_btn.setFixedWidth(30)
        self.rx_search_prev_btn.clicked.connect(self.on_rx_search_prev_clicked)

        self.rx_search_next_btn = QPushButton()
        self.rx_search_next_btn.setObjectName("rx_search_next_btn")
        self.rx_search_next_btn.setToolTip(lang_manager.get_text("rx_btn_search_next_tooltip"))
        self.rx_search_next_btn.setFixedWidth(30)
        self.rx_search_next_btn.clicked.connect(self.on_rx_search_next_clicked)

        self.rx_clear_log_btn = QPushButton(lang_manager.get_text("rx_btn_clear"))
        self.rx_clear_log_btn.setToolTip(lang_manager.get_text("rx_btn_clear_tooltip"))
        self.rx_clear_log_btn.clicked.connect(self.on_clear_rx_log_clicked)

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

        self.rx_save_log_btn = QPushButton(lang_manager.get_text("rx_btn_save"))
        self.rx_save_log_btn.setToolTip(lang_manager.get_text("rx_btn_save_tooltip"))

        # 2. 로그 뷰 영역
        self.rx_log_txt = QTextEdit()
        self.rx_log_txt.setReadOnly(True)
        self.rx_log_txt.setPlaceholderText(lang_manager.get_text("rx_txt_log_placeholder"))
        self.rx_log_txt.setToolTip(lang_manager.get_text("rx_title"))
        self.rx_log_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

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
        layout.addWidget(self.rx_log_txt)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        # Titles & Placeholders
        self.rx_log_title.setText(lang_manager.get_text("rx_title"))
        self.rx_log_txt.setToolTip(lang_manager.get_text("rx_txt_log_tooltip"))
        self.rx_log_txt.setPlaceholderText(lang_manager.get_text("rx_txt_log_placeholder"))

        # Search
        self.rx_search_input.setPlaceholderText(lang_manager.get_text("rx_input_search_placeholder"))
        self.rx_search_input.setToolTip(lang_manager.get_text("rx_input_search_tooltip"))
        self.rx_search_prev_btn.setToolTip(lang_manager.get_text("rx_btn_search_prev_tooltip"))
        self.rx_search_next_btn.setToolTip(lang_manager.get_text("rx_btn_search_next_tooltip"))

        # Options
        self.rx_hex_chk.setText(lang_manager.get_text("rx_chk_hex"))
        self.rx_hex_chk.setToolTip(lang_manager.get_text("rx_chk_hex_tooltip"))
        self.rx_timestamp_chk.setText(lang_manager.get_text("rx_chk_timestamp"))
        self.rx_timestamp_chk.setToolTip(lang_manager.get_text("rx_chk_timestamp_tooltip"))
        self.rx_pause_chk.setText(lang_manager.get_text("rx_chk_pause"))
        self.rx_pause_chk.setToolTip(lang_manager.get_text("rx_chk_pause_tooltip"))

        # Actions
        self.rx_clear_log_btn.setText(lang_manager.get_text("rx_btn_clear"))
        self.rx_clear_log_btn.setToolTip(lang_manager.get_text("rx_btn_clear_tooltip"))
        self.rx_save_log_btn.setText(lang_manager.get_text("rx_btn_save"))
        self.rx_save_log_btn.setToolTip(lang_manager.get_text("rx_btn_save_tooltip"))



    def on_rx_search_next_clicked(self) -> None:
        """다음 검색 결과를 찾습니다."""
        text = self.rx_search_input.text()
        if not text:
            return

        # 정규식 검색 옵션 설정
        options = QTextDocument.FindFlags()

        # 정규식 사용 시도
        import re
        try:
            re.compile(text)
            # Qt의 FindRegularExpression 플래그 사용 (PyQt5 버전에 따라 다를 수 있음)
            # 여기서는 간단히 일반 텍스트 검색으로 구현하고 추후 확장
            # Note: 향후 QRegularExpression을 사용한 정규식 검색 지원 예정
            # 현재는 일반 텍스트 검색만 지원
        except re.error:
            pass # 정규식 오류 시 일반 텍스트로 취급

        found = self.rx_log_txt.find(text, options)
        if not found:
            # 처음부터 다시 검색 (Wrap around)
            self.rx_log_txt.moveCursor(QTextCursor.Start)
            self.rx_log_txt.find(text, options)

    def on_rx_search_prev_clicked(self) -> None:
        """이전 검색 결과를 찾습니다."""
        text = self.rx_search_input.text()
        if not text:
            return

        options = QTextDocument.FindBackward
        found = self.rx_log_txt.find(text, options)
        if not found:
            # 끝에서부터 다시 검색 (Wrap around)
            self.rx_log_txt.moveCursor(QTextCursor.End)
            self.rx_log_txt.find(text, options)

    def append_data(self, data: bytes) -> None:
        """
        수신된 데이터를 버퍼에 추가합니다.

        Args:
            data (bytes): 수신된 바이트 데이터.
        """
        if self.is_paused:
            return

        text: str = ""
        if self.hex_mode:
            text = " ".join([f"{b:02X}" for b in data]) + " "
        else:
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)

        # 타임스탬프 추가
        if self.timestamp_enabled:
            ts = datetime.datetime.now().strftime("[%H:%M:%S]")
            text = f'<span style="color:{LOG_COLOR_TIMESTAMP};">{ts}</span> {text}'

        # 색상 규칙 적용 (텍스트 모드일 때만)
        if not self.hex_mode:
            text = self.color_manager.apply_rules(text)

        self.ui_update_buffer.append(text)

    def flush_batch(self) -> None:
        """버퍼에 쌓인 데이터를 UI에 일괄 업데이트합니다."""
        if not self.ui_update_buffer:
            return

        text = "".join(self.ui_update_buffer)
        self.rx_log_txt.moveCursor(QTextCursor.End)
        self.rx_log_txt.insertHtml(text)  # 색상 지원을 위해 insertHtml 사용
        self.ui_update_buffer.clear()

        # 자동 스크롤 (Auto Scroll)
        sb = self.rx_log_txt.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        # 필요 시 오래된 로그 삭제 (Trim)
        self._trim_if_needed()

    def on_clear_rx_log_clicked(self) -> None:
        """로그 뷰와 버퍼를 초기화합니다."""
        self.rx_log_txt.clear()
        self.ui_update_buffer.clear()

    def on_rx_hex_mode_changed(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.hex_mode = (state == Qt.Checked)

    def on_rx_timestamp_changed(self, state: int) -> None:
        """
        타임스탬프 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)

    def on_rx_pause_changed(self, state: int) -> None:
        """
        일시 정지 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.is_paused = (state == Qt.Checked)

    def _trim_if_needed(self) -> None:
        """
        로그 라인 수가 최대치를 초과하면 상위 trim_chunk_size 만큼 삭제합니다.
        """
        document = self.rx_log_txt.document()
        if document.blockCount() > self.max_lines:
            # 사용자가 스크롤 중인지 확인
            sb: QScrollBar = self.rx_log_txt.verticalScrollBar()
            if sb:
                # 스크롤이 맨 아래 근처에 있을 때만 자동 삭제 (사용자가 위를 보고 있으면 삭제 보류)
                at_bottom = sb.value() >= (sb.maximum() - 100) # 여유분 약간 증가

                if at_bottom:  # 자동 스크롤 모드일 때만 trim 수행
                    cursor = QTextCursor(document)
                    cursor.movePosition(QTextCursor.Start)

                    # 계산된 청크 사이즈만큼 삭제
                    for _ in range(self.trim_chunk_size):
                        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수
        """
        if max_lines > 0:
            self.max_lines = max_lines
            self.trim_chunk_size = int(self.max_lines * TRIM_CHUNK_RATIO)
            self.trim_chunk_size = max(1, self.trim_chunk_size)

    def save_state(self) -> dict:
        """
        현재 위젯 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태.
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
        저장된 상태를 위젯에 적용합니다.

        Args:
            state (dict): 위젯 상태.
        """
        if not state:
            return

        # 체크박스 상태 업데이트 (시그널 발생으로 내부 변수도 업데이트됨)
        self.rx_hex_chk.setChecked(state.get("hex_mode", False))
        self.rx_timestamp_chk.setChecked(state.get("timestamp", False))
        self.rx_pause_chk.setChecked(state.get("is_paused", False))
        self.rx_search_input.setText(state.get("search_text", ""))

