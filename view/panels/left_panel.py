from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTabBar
from PyQt5.QtCore import Qt
from typing import Optional

from view.panels.port_panel import PortPanel
from view.widgets.manual_control import ManualControlWidget

class LeftPanel(QWidget):
    """
    MainWindow의 좌측 영역을 담당하는 패널입니다.
    포트 탭(PortTabs)과 수동 제어(ManualControlWidget)를 포함합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Port Tabs
        self.port_tabs = QTabWidget()
        self.port_tabs.setTabsClosable(True)
        self.port_tabs.tabCloseRequested.connect(self.close_port_tab)
        self.port_tabs.currentChanged.connect(self.on_tab_changed)
        self.port_tabs.setToolTip("Manage multiple serial port connections")
        
        # Manual Control Widget (Global for current port)
        self.manual_control = ManualControlWidget()
        
        layout.addWidget(self.port_tabs, 1) # Tabs take remaining space
        layout.addWidget(self.manual_control) # Manual Control at bottom
        
        self.setLayout(layout)
        
        # Initialize Tabs
        self.add_new_port_tab()
        self.add_plus_tab()

    def add_new_port_tab(self) -> None:
        """새로운 포트 탭을 추가합니다."""
        panel = PortPanel()
        count = self.port_tabs.count()
        index = count - 1 if count > 0 else 0
        
        if count > 0 and self.port_tabs.tabText(count - 1) == "+":
             index = self.port_tabs.insertTab(count - 1, panel, "-")
        else:
             index = self.port_tabs.addTab(panel, "-")
             
        self.port_tabs.setCurrentIndex(index)
        
    def add_plus_tab(self) -> None:
        """'+' 탭을 추가합니다."""
        self.port_tabs.addTab(QWidget(), "+")
        self.disable_close_button_for_plus_tab()

    def disable_close_button_for_plus_tab(self) -> None:
        """'+' 탭의 닫기 버튼을 비활성화/제거합니다."""
        count = self.port_tabs.count()
        if count > 0 and self.port_tabs.tabText(count - 1) == "+":
            self.port_tabs.tabBar().setTabButton(count - 1, QTabBar.RightSide, None)
            self.port_tabs.tabBar().setTabButton(count - 1, QTabBar.LeftSide, None)

    def on_tab_changed(self, index: int) -> None:
        """탭 변경 시 처리"""
        if index == -1: return
        
        if self.port_tabs.tabText(index) == "+":
            self.add_new_port_tab()
            
    def close_port_tab(self, index: int) -> None:
        """탭 닫기 요청 처리"""
        if self.port_tabs.tabText(index) == "+":
            return
        self.port_tabs.removeTab(index)
        
    def update_tab_title(self, index: int, title: str) -> None:
        self.port_tabs.setTabText(index, title)
