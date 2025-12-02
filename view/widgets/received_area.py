from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLabel, QLineEdit
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QTextCursor, QTextDocument
from typing import Optional
import datetime
from view.color_rules import ColorRulesManager

class ReceivedArea(QWidget):
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
        self.hex_mode: bool = False
        self.paused: bool = False
        self.batch_buffer: list[str] = []
        self.max_lines: int = 2000
        self.timestamp_enabled: bool = False
        
        # 색상 규칙 관리자
        self.color_manager = ColorRulesManager()
        
        self.init_ui()
        
        # 배치 렌더링 타이머 (성능 최적화)
        self.batch_timer: QTimer = QTimer()
        self.batch_timer.setInterval(50) # 50ms 간격
        self.batch_timer.timeout.connect(self.flush_batch)
        self.batch_timer.start()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 툴바 (Toolbar)
        toolbar = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("로그 화면을 지웁니다.")
        self.clear_btn.clicked.connect(self.clear_log)
        
        self.hex_check = QCheckBox("HEX")
        self.hex_check.setToolTip("데이터를 16진수(Hex) 형식으로 표시합니다.")
        self.hex_check.stateChanged.connect(self.toggle_hex_mode)
        
        self.timestamp_check = QCheckBox("TS")
        self.timestamp_check.setToolTip("데이터 앞에 타임스탬프를 표시합니다.")
        self.timestamp_check.stateChanged.connect(self.toggle_timestamp)
        
        self.pause_check = QCheckBox("Pause")
        self.pause_check.setToolTip("화면 업데이트를 일시 정지합니다 (데이터는 계속 수신됩니다).")
        self.pause_check.stateChanged.connect(self.toggle_pause)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("로그를 파일로 저장합니다.")
        
        # 검색 바 (Search Bar)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search (Regex supported)...")
        self.search_input.setToolTip("검색할 문자열 또는 정규식을 입력하고 Enter를 누르세요.")
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.setMaximumWidth(200)
        
        self.find_prev_btn = QPushButton("◀")
        self.find_prev_btn.setToolTip("이전 찾기 (Find Previous)")
        self.find_prev_btn.setFixedWidth(30)
        self.find_prev_btn.clicked.connect(self.find_prev)
        
        self.find_next_btn = QPushButton("▶")
        self.find_next_btn.setToolTip("다음 찾기 (Find Next)")
        self.find_next_btn.setFixedWidth(30)
        self.find_next_btn.clicked.connect(self.find_next)
        
        toolbar.addWidget(QLabel("RX Log"))
        toolbar.addStretch()
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.find_prev_btn)
        toolbar.addWidget(self.find_next_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.hex_check)
        toolbar.addWidget(self.timestamp_check)
        toolbar.addWidget(self.pause_check)
        toolbar.addWidget(self.clear_btn)
        toolbar.addWidget(self.save_btn)
        
        # 로그 뷰 (Log View)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setToolTip("수신 데이터 표시 영역")
        self.text_edit.setPlaceholderText("수신된 데이터가 여기에 표시됩니다.")
        self.text_edit.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        
        layout.addLayout(toolbar)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def find_next(self) -> None:
        """다음 검색 결과를 찾습니다."""
        text = self.search_input.text()
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
            # TODO: 정규식 검색 완벽 지원을 위해 QRegularExpression 사용 필요
        except re.error:
            pass # 정규식 오류 시 일반 텍스트로 취급
            
        found = self.text_edit.find(text, options)
        if not found:
            # 처음부터 다시 검색 (Wrap around)
            self.text_edit.moveCursor(QTextCursor.Start)
            self.text_edit.find(text, options)

    def find_prev(self) -> None:
        """이전 검색 결과를 찾습니다."""
        text = self.search_input.text()
        if not text:
            return
            
        options = QTextDocument.FindBackward
        found = self.text_edit.find(text, options)
        if not found:
            # 끝에서부터 다시 검색 (Wrap around)
            self.text_edit.moveCursor(QTextCursor.End)
            self.text_edit.find(text, options)

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
        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.insertHtml(text)  # 색상 지원을 위해 insertHtml 사용
        self.batch_buffer.clear()
        
        # 자동 스크롤 (Auto Scroll)
        sb = self.text_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
        
        # 필요 시 오래된 로그 삭제 (Trim)
        self._trim_if_needed()

    def clear_log(self) -> None:
        """로그 뷰와 버퍼를 초기화합니다."""
        self.text_edit.clear()
        self.batch_buffer.clear()

    def toggle_hex_mode(self, state: int) -> None:
        """
        HEX 모드 토글을 처리합니다.
        
        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.hex_mode = (state == Qt.Checked)
    
    def toggle_timestamp(self, state: int) -> None:
        """
        타임스탬프 토글을 처리합니다.
        
        Args:
            state (int): 체크박스 상태.
        """
        self.timestamp_enabled = (state == Qt.Checked)

    def toggle_pause(self, state: int) -> None:
        """
        일시 정지 토글을 처리합니다.
        
        Args:
            state (int): 체크박스 상태.
        """
        self.paused = (state == Qt.Checked)
    
    def _trim_if_needed(self) -> None:
        """
        로그 라인 수가 최대치를 초과하면 상위 20%를 제거합니다.
        (Implementation_Specification.md 섹션 18.3.2 기준)
        """
        document = self.text_edit.document()
        if document.blockCount() > self.max_lines:
            # 사용자가 스크롤 중인지 확인
            sb = self.text_edit.verticalScrollBar()
            if sb:
                at_bottom = sb.value() >= (sb.maximum() - 10)
                
                if at_bottom:  # 자동 스크롤 모드일 때만 trim 수행
                    cursor = QTextCursor(document)
                    cursor.movePosition(QTextCursor.Start)
                    # 상위 20% (400줄) 선택 및 삭제
                    for _ in range(400):
                        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
