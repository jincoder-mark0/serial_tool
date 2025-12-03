from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTabBar
from PyQt5.QtCore import Qt
from typing import Optional
from view.language_manager import language_manager

from view.panels.port_panel import PortPanel
from view.widgets.manual_control import ManualControlWidget
from core.settings_manager import SettingsManager

class LeftPanel(QWidget):
    """
    MainWindow의 좌측 영역을 담당하는 패널 클래스입니다.
    여러 포트 탭(PortTabs)과 전역 수동 제어(ManualControlWidget)를 포함합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        LeftPanel을 초기화합니다.
        
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
        layout.setSpacing(5)
        
        # 포트 탭 (Port Tabs)
        self.port_tabs = QTabWidget()
        self.port_tabs.setTabsClosable(True)
        self.port_tabs.tabCloseRequested.connect(self.close_port_tab)
        self.port_tabs.currentChanged.connect(self.on_tab_changed)
        self.port_tabs.setToolTip(language_manager.get_text("port_tab_tooltip"))
        
        # 수동 제어 위젯 (현재 포트에 대한 전역 제어)
        self.manual_control = ManualControlWidget()
        
        layout.addWidget(self.port_tabs, 1) # 탭이 남은 공간 차지
        layout.addWidget(self.manual_control) # 수동 제어는 하단에 위치
        
        self.setLayout(layout)
        
        # 탭 초기화
        # self.add_new_port_tab() # MainWindow에서 load_state 호출 시 처리됨
        self.add_plus_tab()

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.port_tabs.setToolTip(language_manager.get_text("port_tab_tooltip"))

    def add_new_port_tab(self) -> None:
        """새로운 포트 탭을 추가합니다."""
        panel = PortPanel()
        count = self.port_tabs.count()
        index = count - 1 if count > 0 else 0
        
        if count > 0 and self.port_tabs.tabText(count - 1) == "+":
             index = self.port_tabs.insertTab(count - 1, panel, "-")
        else:
             index = self.port_tabs.addTab(panel, "-")
        
        # 포트 설정의 연결 상태 변경 시그널을 수동 제어 위젯에 연결
        panel.port_settings.connection_state_changed.connect(
            self._on_port_connection_changed
        )
             
        self.port_tabs.setCurrentIndex(index)

    def add_plus_tab(self) -> None:
        """탭 추가를 위한 '+' 탭을 생성합니다."""
        self.port_tabs.addTab(QWidget(), "+")
        self.disable_close_button_for_plus_tab()

    def disable_close_button_for_plus_tab(self) -> None:
        """'+' 탭의 닫기 버튼을 비활성화/제거합니다."""
        count = self.port_tabs.count()
        if count > 0 and self.port_tabs.tabText(count - 1) == "+":
            self.port_tabs.tabBar().setTabButton(count - 1, QTabBar.RightSide, None)
            self.port_tabs.tabBar().setTabButton(count - 1, QTabBar.LeftSide, None)

    def on_tab_changed(self, index: int) -> None:
        """
        탭 변경 시 처리 핸들러입니다.
        
        Args:
            index (int): 변경된 탭의 인덱스.
        """
        if index == -1: return
        
        if self.port_tabs.tabText(index) == "+":
            self.add_new_port_tab()
            


    def save_state(self) -> list:
        """
        모든 포트 탭의 상태를 리스트로 저장합니다.
        또한 ManualControlWidget의 상태를 별도로 저장합니다.
        
        Returns:
            list: 탭 상태 리스트.
        """
        # ManualControl 상태 저장
        settings = SettingsManager()
        manual_state = self.manual_control.save_state()
        settings.set("ports.manual_control", manual_state)
        
        states = []
        count = self.port_tabs.count()
        for i in range(count):
            if self.port_tabs.tabText(i) == "+":
                continue
            widget = self.port_tabs.widget(i)
            if isinstance(widget, PortPanel):
                state = widget.save_state()
                states.append(state)
        return states
        
    def load_state(self, states: list) -> None:
        """
        저장된 상태 리스트를 기반으로 탭을 복원합니다.
        또한 ManualControlWidget의 상태를 복원합니다.
        
        Args:
            states (list): 탭 상태 리스트.
        """
        # ManualControl 상태 복원
        settings = SettingsManager()
        manual_state = settings.get("ports.manual_control", {})
        if manual_state:
            self.manual_control.load_state(manual_state)
                   
        # 시그널 차단 (탭 삭제/추가 시 on_tab_changed가 호출되어 불필요한 탭이 생성되는 것을 방지)
        self.port_tabs.blockSignals(True)
        try:
            # 기존 탭 모두 제거 (플러스 탭 제외)
            # 역순으로 제거해야 인덱스 문제 없음, 단 플러스 탭은 유지
            count = self.port_tabs.count()
            for i in range(count - 1, -1, -1):
                if self.port_tabs.tabText(i) == "+":
                    continue
                self.port_tabs.removeTab(i)
                
            # 저장된 상태가 없으면 기본 탭 하나 추가
            if not states:
                self.add_new_port_tab()
                return
                
            # 상태 복원
            for i, state in enumerate(states):
                self.add_new_port_tab()
                # 방금 추가된 탭 가져오기 (플러스 탭 바로 앞)
                current_count = self.port_tabs.count()
                # 플러스 탭이 있으면 마지막은 플러스 탭이므로 그 앞의 탭
                # 플러스 탭이 없으면(혹시라도) 마지막 탭
                target_index = current_count - 2 if current_count > 1 else 0
                
                widget = self.port_tabs.widget(target_index)
                if isinstance(widget, PortPanel):
                    widget.load_state(state)
        finally:
            self.port_tabs.blockSignals(False)
            
    def close_port_tab(self, index: int) -> None:
        """
        탭 닫기 요청 처리 핸들러입니다.
        
        Args:
            index (int): 닫을 탭의 인덱스.
        """
        if self.port_tabs.tabText(index) == "+":
            return
        self.port_tabs.removeTab(index)
        
    def update_tab_title(self, index: int, title: str) -> None:
        """
        탭의 제목을 업데이트합니다.
        
        Args:
            index (int): 탭 인덱스.
            title (str): 새로운 제목.
        """
        self.port_tabs.setTabText(index, title)
    
    def _on_port_connection_changed(self, connected: bool) -> None:
        """
        포트 연결 상태 변경 핸들러입니다.
        현재 활성 탭의 연결 상태가 변경되면 ManualControl을 활성화/비활성화합니다.
        
        Args:
            connected (bool): 연결 여부.
        """
        # 현재 활성 탭의 변경인지 확인
        sender_widget = self.sender()
        if sender_widget:
            # sender의 부모를 찾아서 현재 활성 탭인지 확인
            current_index = self.port_tabs.currentIndex()
            current_widget = self.port_tabs.widget(current_index)
            if current_widget and hasattr(current_widget, 'port_settings'):
                if current_widget.port_settings == sender_widget:
                    # 현재 탭의 변경이면 ManualControl 업데이트
                    self.manual_control.set_controls_enabled(connected)
