from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import Optional
import datetime
from view.language_manager import language_manager

class StatusAreaWidget(QWidget):
    """
    시스템 상태 메시지 및 에러 로그를 표시하는 위젯 클래스입니다.
    QTextEdit를 사용하여 여러 줄의 상태 이력을 관리합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        StatusArea를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.label = QLabel(language_manager.get_text("status_lbl_log"))
        # label.setStyleSheet("font-weight: bold; font-size: 10px;")

        self.log_txt = QTextEdit()
        self.log_txt.setReadOnly(True)
        self.log_txt.setMaximumHeight(100) # 높이 제한
        self.log_txt.setToolTip(language_manager.get_text("status_txt_log_tooltip"))
        self.log_txt.setPlaceholderText(language_manager.get_text("status_txt_log_placeholder"))
        self.log_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        layout.addWidget(self.label)
        layout.addWidget(self.log_txt)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.label.setText(language_manager.get_text("status_lbl_log"))
        self.log_txt.setToolTip(language_manager.get_text("status_txt_log_tooltip"))
        self.log_txt.setPlaceholderText(language_manager.get_text("status_txt_log_placeholder"))

    def log(self, message: str, level: str = "INFO") -> None:
        """
        상태 메시지를 로그에 추가합니다.

        Args:
            message (str): 표시할 메시지.
            level (str): 로그 레벨 (INFO, ERROR, WARN, SUCCESS). 기본값은 "INFO".
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = "black"
        if level == "ERROR":
            color = "red"
        elif level == "WARN":
            color = "orange"
        elif level == "SUCCESS":
            color = "green"

        # 색상 적용을 위한 HTML 포맷팅
        formatted_msg = f'<span style="color:gray;">[{timestamp}]</span> <span style="color:{color};">[{level}]</span> {message}'
        self.log_txt.append(formatted_msg)

    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.log_txt.clear()
