from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem
from typing import Optional
from view.managers.lang_manager import lang_manager

class PacketInspectorWidget(QWidget):
    """
    패킷 구조를 트리 형태로 시각화하여 보여주는 위젯 클래스입니다.
    (현재는 더미 데이터로 구현되어 있으며, 추후 실제 패킷 분석 기능이 추가될 예정입니다.)
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PacketInspector를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.tree = None
        self.title_lbl = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(lang_manager.get_text("inspector_grp_title"))
        layout.addWidget(self.title_lbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            lang_manager.get_text("inspector_col_field"),
            lang_manager.get_text("inspector_col_value")
        ])

        # 더미 데이터 (Dummy Data)
        root = QTreeWidgetItem(self.tree)
        root.setText(0, "Packet #1")
        root.setText(1, "AT_OK")

        child1 = QTreeWidgetItem(root)
        child1.setText(0, "Raw")
        child1.setText(1, "OK\\r\\n")

        child2 = QTreeWidgetItem(root)
        child2.setText(0, "Timestamp")
        child2.setText(1, "14:30:00.123")

        self.tree.expandAll()

        layout.addWidget(self.tree)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.title_lbl.setText(lang_manager.get_text("inspector_grp_title"))
        self.tree.setHeaderLabels([
            lang_manager.get_text("inspector_col_field"),
            lang_manager.get_text("inspector_col_value")
        ])
