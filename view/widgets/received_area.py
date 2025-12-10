from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLabel, QLineEdit
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QTextCursor, QTextDocument
from typing import Optional
import datetime
from view.tools.color_rules import ColorRulesManager
from view.tools.lang_manager import lang_manager

class ReceivedAreaWidget(QWidget):
    """
    수신된 시리얼 데이터를 표시하는 위젯 클래스입니다.
    텍스트/HEX 모드 전환, 일시 정지, 타임스탬프 표시, 로그 저장 및 지우기 기능을 제공합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ReceivedArea를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.recv_search_prev_btn = None
        self.recv_search_input = None
        self.recv_save_log_btn = None
        self.recv_pause_chk = None
        self.recv_timestamp_chk = None
        self.recv_hex_chk = None
        self.recv_clear_log_btn = None
        self.hex_mode: bool = False
        self.paused: bool = False
        self.batch_buffer: list[str] = []
        self.max_lines: int = 2000
        self.trim_chunk_size: int = 5   # 20%
        self.timestamp_enabled: bool = False

        # 색상 규칙 관리자
        self.color_manager = ColorRulesManager()

        self.init_ui()

        # 배치 렌더링 타이머 (성능 최적화)
        self.batch_timer: QTimer = QTimer()
        self.batch_timer.setInterval(50) # 50ms 간격
        self.batch_timer.timeout.connect(self.flush_batch)
        self.batch_timer.start()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 툴바 (Toolbar)
        toolbar = QHBoxLayout()

        self.recv_clear_log_btn = QPushButton(lang_manager.get_text("recv_btn_clear"))
        self.recv_clear_log_btn.setToolTip(lang_manager.get_text("recv_btn_clear_tooltip"))
        self.recv_clear_log_btn.clicked.connect(self.on_clear_recv_log_clicked)

        self.recv_hex_chk = QCheckBox(lang_manager.get_text("recv_chk_hex"))
        self.recv_hex_chk.setToolTip(lang_manager.get_text("recv_chk_hex_tooltip"))
        self.recv_hex_chk.stateChanged.connect(self.on_recv_hex_mode_changed)

        self.recv_timestamp_chk = QCheckBox(lang_manager.get_text("recv_chk_timestamp"))
        self.recv_timestamp_chk.setToolTip(lang_manager.get_text("recv_chk_timestamp_tooltip"))
        self.recv_timestamp_chk.stateChanged.connect(self.on_recv_timestamp_changed)

        self.recv_pause_chk = QCheckBox(lang_manager.get_text("recv_chk_pause"))
        self.recv_pause_chk.setToolTip(lang_manager.get_text("recv_chk_pause_tooltip"))
        self.recv_pause_chk.stateChanged.connect(self.on_recv_pause_changed)

        self.recv_save_log_btn = QPushButton(lang_manager.get_text("recv_btn_save"))
        self.recv_save_log_btn.setToolTip(lang_manager.get_text("recv_btn_save_tooltip"))

        # 검색 바 (Search Bar)
        self.recv_search_input = QLineEdit()
        self.recv_search_input.setPlaceholderText(lang_manager.get_text("recv_input_search_placeholder"))
        self.recv_search_input.setToolTip(lang_manager.get_text("recv_input_search_tooltip"))
        self.recv_search_input.returnPressed.connect(self.on_recv_search_next_clicked)
        self.recv_search_input.setMaximumWidth(200)

        self.recv_search_prev_btn = QPushButton()
        self.recv_search_prev_btn.setObjectName("recv_search_prev_btn")
        self.recv_search_prev_btn.setToolTip(lang_manager.get_text("recv_btn_search_prev_tooltip"))
        self.recv_search_prev_btn.setFixedWidth(30)
        self.recv_search_prev_btn.clicked.connect(self.on_recv_search_prev_clicked)

        self.recv_search_next_btn = QPushButton()
        self.recv_search_next_btn.setObjectName("recv_search_next_btn")
        self.recv_search_next_btn.setToolTip(lang_manager.get_text("recv_btn_search_next_tooltip"))
        self.recv_search_next_btn.setFixedWidth(30)
        self.recv_search_next_btn.clicked.connect(self.on_recv_search_next_clicked)

        self.recv_log_title = QLabel(lang_manager.get_text("recv_title"))
        self.recv_log_title.setProperty("class", "section-title")  # 섹션 타이틀 스타일 적용

        toolbar.addWidget(self.recv_log_title)
        toolbar.addStretch()
        toolbar.addWidget(self.recv_search_input)
        toolbar.addWidget(self.recv_search_prev_btn)
        toolbar.addWidget(self.recv_search_next_btn)
        toolbar.addWidget(self.recv_hex_chk)
        toolbar.addWidget(self.recv_timestamp_chk)
        toolbar.addWidget(self.recv_pause_chk)
        toolbar.addWidget(self.recv_clear_log_btn)
        toolbar.addWidget(self.recv_save_log_btn)

        # 로그 표시 영역 (Log Display Area)
        self.recv_log_txt = QTextEdit()
        self.recv_log_txt.setReadOnly(True)
        self.recv_log_txt.setPlaceholderText(lang_manager.get_text("recv_txt_log_placeholder"))
        self.recv_log_txt.setToolTip(lang_manager.get_text("recv_title"))
        self.recv_log_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        layout.addLayout(toolbar)
        layout.addWidget(self.recv_log_txt)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.recv_clear_log_btn.setText(lang_manager.get_text("recv_btn_clear"))
        self.recv_clear_log_btn.setToolTip(lang_manager.get_text("recv_btn_clear_tooltip"))

        self.recv_hex_chk.setText(lang_manager.get_text("recv_chk_hex"))
        self.recv_hex_chk.setToolTip(lang_manager.get_text("recv_chk_hex_tooltip"))

        self.recv_timestamp_chk.setText(lang_manager.get_text("recv_chk_timestamp"))
        self.recv_timestamp_chk.setToolTip(lang_manager.get_text("recv_chk_timestamp_tooltip"))

        self.recv_pause_chk.setText(lang_manager.get_text("recv_chk_pause"))
        self.recv_pause_chk.setToolTip(lang_manager.get_text("recv_chk_pause_tooltip"))

        self.recv_save_log_btn.setText(lang_manager.get_text("recv_btn_save"))
        self.recv_save_log_btn.setToolTip(lang_manager.get_text("recv_btn_save_tooltip"))

        self.recv_search_input.setPlaceholderText(lang_manager.get_text("recv_input_search_placeholder"))
        self.recv_search_input.setToolTip(lang_manager.get_text("recv_input_search_tooltip"))

        self.recv_search_prev_btn.setToolTip(lang_manager.get_text("recv_btn_search_prev_tooltip"))
        self.recv_search_next_btn.setToolTip(lang_manager.get_text("recv_btn_search_next_tooltip"))

        self.recv_log_title.setText(lang_manager.get_text("recv_title"))

        self.recv_log_txt.setToolTip(lang_manager.get_text("recv_txt_log_tooltip"))
        self.recv_log_txt.setPlaceholderText(lang_manager.get_text("recv_txt_log_placeholder"))

    def on_recv_search_next_clicked(self) -> None:
        """다음 검색 결과를 찾습니다."""
        text = self.recv_search_input.text()
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

        found = self.recv_log_txt.find(text, options)
        if not found:
            # 처음부터 다시 검색 (Wrap around)
            self.recv_log_txt.moveCursor(QTextCursor.Start)
            self.recv_log_txt.find(text, options)

    def on_recv_search_prev_clicked(self) -> None:
        """이전 검색 결과를 찾습니다."""
        text = self.recv_search_input.text()
        if not text:
            return

        options = QTextDocument.FindBackward
        found = self.recv_log_txt.find(text, options)
        if not found:
            # 끝에서부터 다시 검색 (Wrap around)
            self.recv_log_txt.moveCursor(QTextCursor.End)
            self.recv_log_txt.find(text, options)

    def append_data(self, data: bytes) -> None:
        """
        수신된 데이터를 버퍼에 추가합니다.

        Args:
            data (bytes): 수신된 바이트 데이터.
        """
        if self.paused:
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
            text = f'<span style="color:#9E9E9E;">{ts}</span> {text}'

        # 색상 규칙 적용 (텍스트 모드일 때만)
        if not self.hex_mode:
            text = self.color_manager.apply_rules(text)

        self.batch_buffer.append(text)

    def flush_batch(self) -> None:
        """버퍼에 쌓인 데이터를 UI에 일괄 업데이트합니다."""
        if not self.batch_buffer:
            return

        text = "".join(self.batch_buffer)
        self.recv_log_txt.moveCursor(QTextCursor.End)
        self.recv_log_txt.insertHtml(text)  # 색상 지원을 위해 insertHtml 사용
        self.batch_buffer.clear()

        # 자동 스크롤 (Auto Scroll)
        sb = self.recv_log_txt.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        # 필요 시 오래된 로그 삭제 (Trim)
        self._trim_if_needed()

    def on_clear_recv_log_clicked(self) -> None:
        """로그 뷰와 버퍼를 초기화합니다."""
        self.recv_log_txt.clear()
        self.batch_buffer.clear()

    def on_recv_hex_mode_changed(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.hex_mode = (state == Qt.Checked)

    def on_recv_timestamp_changed(self, state: int) -> None:
        """
        타임스탬프 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)

    def on_recv_pause_changed(self, state: int) -> None:
        """
        일시 정지 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태.
        """
        self.paused = (state == Qt.Checked)

    def _trim_if_needed(self) -> None:
        """
        로그 라인 수가 최대치를 초과하면 상위 trim_chunk_size 비율로 선택 및 삭제합니다.
        """
        document = self.recv_log_txt.document()
        if document.blockCount() > self.max_lines:
            # 사용자가 스크롤 중인지 확인
            sb = self.recv_log_txt.verticalScrollBar()
            if sb:
                at_bottom = sb.value() >= (sb.maximum() - 10)

                if at_bottom:  # 자동 스크롤 모드일 때만 trim 수행
                    cursor = QTextCursor(document)
                    cursor.movePosition(QTextCursor.Start)
                    # 상위 trim_chunk_size 비율로 선택 및 삭제
                    for _ in range(int(self.max_lines / self.trim_chunk_size)):
                        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수 (기본값: 2000)
        """
        if max_lines > 0:
            self.max_lines = max_lines

    def save_state(self) -> dict:
        """
        현재 위젯 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태.
        """
        state = {
            "hex_mode": self.hex_mode,
            "timestamp": self.timestamp_enabled,
            "paused": self.paused,
            "search_text": self.recv_search_input.text()
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
        self.recv_hex_chk.setChecked(state.get("hex_mode", False))
        self.recv_timestamp_chk.setChecked(state.get("timestamp", False))
        self.recv_pause_chk.setChecked(state.get("paused", False))
        self.recv_search_input.setText(state.get("search_text", ""))

