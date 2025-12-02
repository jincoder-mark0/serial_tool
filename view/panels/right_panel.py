from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional

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
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        self.command_list_panel = CommandListPanel()
        self.command_list_panel.setToolTip("명령어 시퀀스를 관리하고 실행합니다.")
        
        self.packet_inspector = PacketInspector()
        self.packet_inspector.setToolTip("수신된 패킷을 상세 분석합니다.")
        
        self.tabs.addTab(self.command_list_panel, "Command List")
        self.tabs.addTab(self.packet_inspector, "Inspector")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
