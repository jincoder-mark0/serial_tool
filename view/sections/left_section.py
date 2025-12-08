from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from typing import Optional
from view.language_manager import language_manager

from view.panels.port_panel import PortPanel
from view.panels.manual_control_panel import ManualControlPanel
from view.widgets.port_tab_widget import PortTabWidget
from core.settings_manager import SettingsManager

class LeftSection(QWidget):
    """
    MainWindow의 좌측 영역을 담당하는 패널 클래스입니다.
    여러 포트 탭(PortTabs)과 전역 수동 제어(ManualControlWidget)를 포함합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        LeftSection을 초기화합니다.

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

        # 포트 탭 (Port Tabs) - PortTabWidget 사용
        self.port_tabs = PortTabWidget()
        self.port_tabs.tab_added.connect(self._on_tab_added)

        # 수동 제어 패널 (현재 포트에 대한 전역 제어)
        self.manual_control = ManualControlPanel()

        layout.addWidget(self.port_tabs, 1) # 탭이 남은 공간 차지
        layout.addWidget(self.manual_control) # 수동 제어는 하단에 위치

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        # PortTabWidget 내부에서 처리됨
        pass

    def add_new_port_tab(self) -> None:
        """새로운 포트 탭을 추가합니다. (외부 호출용 래퍼)"""
        self.port_tabs.add_new_port_tab()

    def _on_tab_added(self, panel: PortPanel) -> None:
        """새 탭이 추가되었을 때 호출되는 핸들러"""
        # 포트 설정의 연결 상태 변경 시그널을 수동 제어 위젯에 연결
        panel.port_settings.connection_state_changed.connect(
            self._on_port_connection_changed
        )

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
            # 마지막 탭(+) 제외
            if i == count - 1:
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

        # 시그널 차단
        self.port_tabs.blockSignals(True)
        try:
            # 기존 탭 모두 제거 (플러스 탭 제외)
            # 역순으로 제거해야 인덱스 문제 없음, 단 플러스 탭은 유지
            count = self.port_tabs.count()
            for i in range(count - 2, -1, -1): # 마지막 탭(count-1)은 +탭이므로 제외
                self.port_tabs.removeTab(i)

            # 저장된 상태가 없으면 기본 탭 하나 추가
            if not states:
                self.port_tabs.add_new_port_tab()
                return

            # 상태 복원
            for state in states:
                panel = self.port_tabs.add_new_port_tab()
                panel.load_state(state)
        finally:
            self.port_tabs.blockSignals(False)

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
