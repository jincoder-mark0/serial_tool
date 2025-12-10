from PyQt5.QtWidgets import QWidget, QVBoxLayout
from typing import Optional
from view.widgets.manual_ctrl import ManualCtrlWidget

class ManualCtrlPanel(QWidget):
    """
    ManualCtrlWidget을 감싸는 패널 클래스입니다.
    Section -> Panel -> Widget 계층 구조를 준수하기 위해 사용됩니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.manual_ctrl_widget = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.manual_ctrl_widget = ManualCtrlWidget()
        layout.addWidget(self.manual_ctrl_widget)

        self.setLayout(layout)

    def save_state(self) -> dict:
        """위젯의 상태를 저장합니다."""
        return self.manual_ctrl_widget.save_state()

    def load_state(self, state: dict) -> None:
        """위젯의 상태를 복원합니다."""
        self.manual_ctrl_widget.load_state(state)

    def set_controls_enabled(self, enabled: bool) -> None:
        """제어 위젯의 활성화 상태를 설정합니다."""
        self.manual_ctrl_widget.set_controls_enabled(enabled)
