from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional

from view.panels.command_list_panel import CommandListPanel
from view.widgets.packet_inspector import PacketInspector

class RightPanel(QWidget):
    """
    MainWindow의 우측 영역을 담당하는 패널입니다.
    Command List와 Packet Inspector를 탭으로 관리합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        self.command_list_panel = CommandListPanel()
        self.command_list_panel.setToolTip("Manage and execute command sequences")
        
        self.packet_inspector = PacketInspector()
        self.packet_inspector.setToolTip("Analyze received packets in detail")
        
        self.tabs.addTab(self.command_list_panel, "Command List")
        self.tabs.addTab(self.packet_inspector, "Inspector")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
