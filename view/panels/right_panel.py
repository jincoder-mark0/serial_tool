from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional
from view.language_manager import language_manager

from view.panels.command_list_panel import CommandListPanel
from view.widgets.packet_inspector import PacketInspector

class RightPanel(QWidget):
    """
    MainWindow의 우측 영역을 담당하는 패널 클래스입니다.
    Command List와 Packet Inspector를 탭으로 관리합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        RightPanel을 초기화합니다.

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

        self.tabs = QTabWidget()

        self.command_list_panel = CommandListPanel()
        self.command_list_panel.setToolTip(language_manager.get_text("right_tooltip_cmd_list"))

        self.packet_inspector = PacketInspector()
        self.packet_inspector.setToolTip(language_manager.get_text("right_tooltip_inspector"))

        self.tabs.addTab(self.command_list_panel, language_manager.get_text("right_tab_cmd_list"))
        self.tabs.addTab(self.packet_inspector, language_manager.get_text("right_tab_inspector"))

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.command_list_panel.setToolTip(language_manager.get_text("command_list_panel_tooltip"))
        self.packet_inspector.setToolTip(language_manager.get_text("packet_inspector_tooltip"))

        self.tabs.setTabText(0, language_manager.get_text("right_tab_cmd_list"))
        self.tabs.setTabText(1, language_manager.get_text("right_tab_inspector"))

    def save_state(self) -> None:
        """패널 상태를 저장합니다."""
        self.command_list_panel.save_state()
        # PacketInspector 상태 저장도 필요하다면 여기에 추가
