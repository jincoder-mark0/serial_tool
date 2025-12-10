from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional
from view.tools.lang_manager import lang_manager

from view.panels.macro_panel import MacroPanel
from view.panels.packet_inspector_panel import PacketInspectorPanel

class MainRightSection(QWidget):
    """
    MainWindow의 우측 영역을 담당하는 패널 클래스입니다.
    Macro List와 Packet Inspector를 탭으로 관리합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        RightSection을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.packet_inspector = None
        self.macro_panel = None
        self.tabs = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        self.macro_panel = MacroPanel()
        self.macro_panel.setToolTip(lang_manager.get_text("right_tooltip_macro_list"))

        self.packet_inspector = PacketInspectorPanel()
        self.packet_inspector.setToolTip(lang_manager.get_text("right_tooltip_packet"))

        self.tabs.addTab(self.macro_panel, lang_manager.get_text("right_tab_macro_list"))
        self.tabs.addTab(self.packet_inspector, lang_manager.get_text("right_tab_packet"))

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.macro_panel.setToolTip(lang_manager.get_text("right_tooltip_macro_list"))
        self.packet_inspector.setToolTip(lang_manager.get_text("right_tooltip_packet"))

        self.tabs.setTabText(0, lang_manager.get_text("right_tab_macro_list"))
        self.tabs.setTabText(1, lang_manager.get_text("right_tab_packet"))

    def save_state(self) -> None:
        """패널 상태를 저장합니다."""
        self.macro_panel.save_state()
        # PacketInspector 상태 저장도 필요하다면 여기에 추가
