from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from typing import Optional
import datetime
from view.managers.lang_manager import lang_manager
from view.custom_qt.smart_list_view import QSmartListView



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
        self.system_log_list = None
        self.system_log_title = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.system_log_title = QLabel(lang_manager.get_text("system_title"))
        self.system_log_title.setProperty("class", "section-title")  # 섹션 타이틀 스타일 적용
        # system_log_title.setStyleSheet("font-weight: bold; font-size: 10px;")

        # self.system_log_list = QTextEdit()
        self.system_log_list = QSmartListView()
        self.system_log_list.setReadOnly(True)
        self.system_log_list.setFixedHeight(100) # 높이 고정
        self.system_log_list.setToolTip(lang_manager.get_text("system_list_log_tooltip"))
        self.system_log_list.setPlaceholderText(lang_manager.get_text("system_list_log_placeholder"))
        self.system_log_list.setProperty("class", "fixed-font")  # 고정폭 폰트 적용

        layout.addWidget(self.system_log_title)
        layout.addWidget(self.system_log_list)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.system_log_title.setText(lang_manager.get_text("system_title"))
        self.system_log_list.setToolTip(lang_manager.get_text("system_list_log_tooltip"))
        self.system_log_list.setPlaceholderText(lang_manager.get_text("system_list_log_placeholder"))

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
        from view.managers.color_manager import color_manager
        full_text = color_manager.apply_rules(full_text)

        # 4. 뷰에 추가
        self.system_log_list.append(full_text)

    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.system_log_list.clear()
