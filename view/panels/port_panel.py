from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt5.QtCore import Qt
from typing import Optional

from view.widgets.port_settings import PortSettingsWidget
from view.widgets.received_area import ReceivedArea
from view.widgets.status_area import StatusArea

class PortPanel(QWidget):
    """
    개별 시리얼 포트 탭의 메인 위젯 클래스입니다.
    포트 설정(PortSettings), 수신 로그(ReceivedArea), 상태 로그(StatusArea) 영역을 포함합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortPanel을 초기화합니다.
        
        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 컴포넌트 생성
        self.port_settings = PortSettingsWidget()
        self.received_area = ReceivedArea()
        self.status_area = StatusArea()
        
        # 레이아웃 구성
        # 상단: 설정 (Top: Settings)
        layout.addWidget(self.port_settings)
        
        # 중간: 로그 (Middle: Log)
        layout.addWidget(self.received_area, 1) # Stretch 1
        
        # 하단: 상태 로그 영역 (Bottom: Status Log Area)
        layout.addWidget(self.status_area)
        
        self.setLayout(layout)

    def save_state(self) -> dict:
        """
        패널 상태를 저장합니다.
        
        Returns:
            dict: 패널 상태 데이터.
        """
        return {
            "port_settings": self.port_settings.save_state(),
            "received_area": self.received_area.save_state()
        }
        
    def load_state(self, state: dict) -> None:
        """
        패널 상태를 복원합니다.
        
        Args:
            state (dict): 패널 상태 데이터.
        """
        if not state:
            return
        self.port_settings.load_state(state.get("port_settings", {}))
        self.received_area.load_state(state.get("received_area", {}))
