from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from typing import Optional
import datetime
from view.managers.lang_manager import lang_manager

from core.constants import (
    LOG_COLOR_INFO,
    LOG_COLOR_ERROR,
    LOG_COLOR_WARN,
    LOG_COLOR_SUCCESS,
    LOG_COLOR_TIMESTAMP
)

class SystemLogWidget(QWidget):
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
        self.status_log_txt = None
        self.status_log_title = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.status_log_title = QLabel(lang_manager.get_text("status_title"))
        self.status_log_title.setProperty("class", "section-title")  # 섹션 타이틀 스타일 적용
        # status_log_title.setStyleSheet("font-weight: bold; font-size: 10px;")

        self.status_log_txt = QTextEdit()
        self.status_log_txt.setReadOnly(True)
        self.status_log_txt.setMaximumHeight(100) # 높이 제한
        self.status_log_txt.setToolTip(lang_manager.get_text("status_txt_log_tooltip"))
        self.status_log_txt.setPlaceholderText(lang_manager.get_text("status_txt_log_placeholder"))
        self.status_log_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        layout.addWidget(self.status_log_title)
        layout.addWidget(self.status_log_txt)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.status_log_title.setText(lang_manager.get_text("status_title"))
        self.status_log_txt.setToolTip(lang_manager.get_text("status_txt_log_tooltip"))
        self.status_log_txt.setPlaceholderText(lang_manager.get_text("status_txt_log_placeholder"))

    def log(self, message: str, level: str = "INFO") -> None:
        """
        상태 메시지를 로그에 추가합니다.

        Args:
            message (str): 표시할 메시지.
            level (str): 로그 레벨 (INFO, ERROR, WARN, SUCCESS). 기본값은 "INFO".
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        level_colors = {
            "INFO": LOG_COLOR_INFO,
            "ERROR": LOG_COLOR_ERROR,
            "WARN": LOG_COLOR_WARN,
            "SUCCESS": LOG_COLOR_SUCCESS
        }
        color = level_colors.get(level, LOG_COLOR_INFO)


        # 색상 적용을 위한 HTML 포맷팅
        formatted_msg = f'<span style="color:{LOG_COLOR_TIMESTAMP};">[{timestamp}]</span> <span style="color:{color};">[{level}]</span> {message}'
        self.status_log_txt.append(formatted_msg)

    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.status_log_txt.clear()
