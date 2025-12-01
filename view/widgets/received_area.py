from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLabel
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QTextCursor
from typing import Optional
import datetime
from view.color_rules import ColorRulesManager

class ReceivedArea(QWidget):
    """
    수신된 시리얼 데이터를 표시하는 위젯입니다.
    텍스트/HEX 모드, 일시 정지, 로그 저장 기능을 지원합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ReceivedArea 초기화.
        
        Args:
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.hex_mode: bool = False
        self.paused: bool = False
        self.batch_buffer: list[str] = []
        self.max_lines: int = 2000
        self.timestamp_enabled: bool = False
        
        # Color rules manager
        self.color_manager = ColorRulesManager()
        
        self.init_ui()
        
        # Batch Rendering Timer
        self.batch_timer: QTimer = QTimer()
        self.batch_timer.setInterval(50) # 50ms
        self.batch_timer.timeout.connect(self.flush_batch)
        self.batch_timer.start()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Clear log view")
        self.clear_btn.clicked.connect(self.clear_log)
        
        self.hex_check = QCheckBox("HEX")
        self.hex_check.setToolTip("Show data in Hexadecimal format")
        self.hex_check.stateChanged.connect(self.toggle_hex_mode)
        
        self.timestamp_check = QCheckBox("TS")
        self.timestamp_check.setToolTip("Show timestamp prefix")
        self.timestamp_check.stateChanged.connect(self.toggle_timestamp)
        
        self.pause_check = QCheckBox("Pause")
        self.pause_check.setToolTip("Pause log updates (Data is still buffered)")
        self.pause_check.stateChanged.connect(self.toggle_pause)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save log to file")
        
        toolbar.addWidget(QLabel("RX Log"))
        toolbar.addStretch()
        toolbar.addWidget(self.hex_check)
        toolbar.addWidget(self.timestamp_check)
        toolbar.addWidget(self.pause_check)
        toolbar.addWidget(self.clear_btn)
        toolbar.addWidget(self.save_btn)
        
        # Log View
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setToolTip("Received data display area")
        
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)
        # self.text_edit.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")
        
        layout.addLayout(toolbar)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def append_data(self, data: bytes) -> None:
        """
        수신된 데이터를 버퍼에 추가합니다.
        
        Args:
            data: 수신된 바이트 데이터
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
        
        # Add timestamp if enabled
        if self.timestamp_enabled:
            ts = datetime.datetime.now().strftime("[%H:%M:%S]")
            text = f'<span style="color:#9E9E9E;">{ts}</span> {text}'
        
        # Apply color rules (only in text mode)
        if not self.hex_mode:
            text = self.color_manager.apply_rules(text)
                
        self.batch_buffer.append(text)

    def flush_batch(self) -> None:
        """버퍼에 쌓인 데이터를 UI에 일괄 업데이트합니다."""
        if not self.batch_buffer:
            return
            
        text = "".join(self.batch_buffer)
        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.insertHtml(text)  # Use insertHtml for color support
        self.batch_buffer.clear()
        
        # Auto Scroll
        sb = self.text_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
        
        # Trim if needed
        self._trim_if_needed()

    def clear_log(self) -> None:
        """로그 뷰와 버퍼를 초기화합니다."""
        self.text_edit.clear()
        self.batch_buffer.clear()

    def toggle_hex_mode(self, state: int) -> None:
        """
        HEX 모드 토글 처리.
        
        Args:
            state: 체크박스 상태 (Qt.Checked 등)
        """
        self.hex_mode = (state == Qt.Checked)
    
    def toggle_timestamp(self, state: int) -> None:
        """
        타임스탬프 토글 처리.
        
        Args:
            state: 체크박스 상태
        """
        self.timestamp_enabled = (state == Qt.Checked)

    def toggle_pause(self, state: int) -> None:
        """
        일시 정지 토글 처리.
        
        Args:
            state: 체크박스 상태
        """
        self.paused = (state == Qt.Checked)
    
    def _trim_if_needed(self) -> None:
        """
        2000줄 초과 시 상위 20% (400줄) 제거.
        Implementation_Specification.md 섹션 18.3.2 기준.
        """
        document = self.text_edit.document()
        if document.blockCount() > self.max_lines:
            # 사용자가 스크롤 중인지 확인
            sb = self.text_edit.verticalScrollBar()
            if sb:
                at_bottom = sb.value() >= (sb.maximum() - 10)
                
                if at_bottom:  # 자동 스크롤 모드일 때만 trim
                    cursor = QTextCursor(document)
                    cursor.movePosition(QTextCursor.Start)
                    # 상위 20% (400줄) 선택 및 삭제
                    for _ in range(400):
                        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
