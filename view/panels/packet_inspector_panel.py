from PyQt5.QtWidgets import QWidget, QVBoxLayout
from typing import Optional
from view.language_manager import language_manager
from view.widgets.packet_inspector import PacketInspectorWidget

class PacketInspectorPanel(QWidget):
    """
    PacketInspectorWidget을 감싸는 패널 클래스입니다.
    Section -> Panel -> Widget 계층 구조를 준수하기 위해 사용됩니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()

        # 언어 변경 시 툴팁 업데이트 등을 위해 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.packet_inspector_widget = PacketInspectorWidget()
        layout.addWidget(self.packet_inspector_widget)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        # 패널 자체의 툴팁이나 타이틀이 있다면 여기서 업데이트
        # 현재는 RightSection에서 탭 툴팁을 관리하므로 여기서는 위젯 내부 갱신만 트리거될 수 있음
        pass

    def setToolTip(self, text: str) -> None:
        """패널의 툴팁을 설정합니다 (주로 탭 툴팁용)."""
        super().setToolTip(text)
