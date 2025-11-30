from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt5.QtCore import Qt
from typing import Optional

from view.widgets.port_settings import PortSettingsWidget
from view.widgets.received_area import ReceivedArea
from view.widgets.status_area import StatusArea

class PortPanel(QWidget):
    """
    개별 시리얼 포트 탭의 메인 위젯입니다.
    설정, 수신 로그, 상태 로그 영역을 포함합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortPanel 초기화.
        
        Args:
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Components
        self.port_settings = PortSettingsWidget()
        self.received_area = ReceivedArea()
        self.status_area = StatusArea()
        
        # Layout
        # Top: Settings
        layout.addWidget(self.port_settings)
        
        # Middle: Log
        layout.addWidget(self.received_area, 1) # Stretch 1
        
        # Bottom: Status Log Area
        layout.addWidget(self.status_area)
        
        self.setLayout(layout)
