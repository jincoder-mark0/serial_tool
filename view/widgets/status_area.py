from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import Optional
import datetime

class StatusArea(QWidget):
    """
    시스템 상태 메시지 및 에러 로그를 표시하는 위젯입니다.
    QTextEdit를 사용하여 여러 줄의 상태 이력을 관리합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        StatusArea 초기화.
        
        Args:
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        label = QLabel("Status Log")
        # label.setStyleSheet("font-weight: bold; font-size: 10px;")
        
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(100) # 높이 제한
        self.log_edit.setToolTip("System status and error log")
        self.log_edit.setPlaceholderText("System status and error log")
        self.log_edit.setProperty("class", "fixed-font")  # Apply fixed-width font
        
        layout.addWidget(label)
        layout.addWidget(self.log_edit)
        self.setLayout(layout)
        
    def log(self, message: str, level: str = "INFO") -> None:
        """
        상태 메시지를 로그에 추가합니다.
        
        Args:
            message: 표시할 메시지
            level: 로그 레벨 (INFO, ERROR, WARN 등)
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = "black"
        if level == "ERROR":
            color = "red"
        elif level == "WARN":
            color = "orange"
        elif level == "SUCCESS":
            color = "green"
            
        # HTML formatting for color
        formatted_msg = f'<span style="color:gray;">[{timestamp}]</span> <span style="color:{color};">[{level}]</span> {message}'
        self.log_edit.append(formatted_msg)
        
    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.log_edit.clear()
