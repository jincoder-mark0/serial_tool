from PyQt5.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, Dict, Any, List
from view.managers.lang_manager import lang_manager

from view.panels.port_panel import PortPanel
from view.panels.manual_ctrl_panel import ManualCtrlPanel
from view.panels.port_tab_panel import PortTabPanel

class MainLeftSection(QWidget):
    """
    MainWindow의 좌측 영역을 담당하는 패널 클래스입니다.
    여러 포트 탭(PortTabs)과 전역 수동 제어(ManualCtrlPanel)를 포함합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        LeftSection을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.port_tabs = None
        self.manual_ctrl = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 포트 탭 (Port Tabs)
        self.port_tabs = PortTabPanel()
        self.port_tabs.tab_added.connect(self._on_tab_added)

        # 수동 제어 패널 (현재 포트에 대한 전역 제어)
        self.manual_ctrl = ManualCtrlPanel()

        layout.addWidget(self.port_tabs, 1)  # 탭이 남은 공간 차지
        layout.addWidget(self.manual_ctrl)   # 수동 제어는 하단에 위치

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        # 하위 컴포넌트들이 자체적으로 처리하므로 비워둠
        pass

    def add_new_port_tab(self) -> None:
        """새로운 포트 탭을 추가합니다."""
        self.port_tabs.add_new_port_tab()

    def open_current_port(self) -> None:
        """현재 활성화된 탭의 포트를 엽니다."""
        current_index = self.port_tabs.currentIndex()
        current_widget = self.port_tabs.widget(current_index)
        if isinstance(current_widget, PortPanel):
            if not current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_port(self) -> None:
        """현재 활성화된 탭의 포트를 닫습니다."""
        current_index = self.port_tabs.currentIndex()
        current_widget = self.port_tabs.widget(current_index)
        if isinstance(current_widget, PortPanel):
            if current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_tab(self) -> None:
        """현재 활성화된 탭을 닫습니다."""
        current_index = self.port_tabs.currentIndex()
        # 마지막 탭(플러스 탭)은 닫을 수 없음
        if current_index == self.port_tabs.count() - 1:
            return

        if current_index >= 0:
            self.port_tabs.removeTab(current_index)

    def _on_tab_added(self, panel: PortPanel) -> None:
        """새 탭이 추가되었을 때 호출되는 핸들러"""
        # 포트 설정의 연결 상태 변경 시그널을 수동 제어 위젯에 연결
        panel.port_settings_widget.port_connection_changed.connect(
            self._on_port_connection_changed
        )

    def save_state(self) -> Dict[str, Any]:
        """
        모든 하위 위젯의 상태를 수집하여 반환합니다.
        SettingsManager에 직접 접근하지 않습니다.

        Returns:
            Dict[str, Any]: {'ports': [...], 'manual_ctrl': {...}} 구조의 상태 데이터.
        """
        # 1. ManualControl 상태 수집
        manual_state = self.manual_ctrl.save_state()

        # 2. Port Tabs 상태 수집
        port_states = []
        count = self.port_tabs.count()
        for i in range(count):
            # 마지막 탭(+) 제외
            if i == count - 1:
                continue
            widget = self.port_tabs.widget(i)
            if isinstance(widget, PortPanel):
                port_states.append(widget.save_state())

        # 통합된 상태 반환
        return {
            "manual_ctrl": manual_state,
            "ports": port_states
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """
        저장된 상태 딕셔너리를 기반으로 복원합니다.

        Args:
            state (Dict[str, Any]): {'ports': [...], 'manual_ctrl': {...}} 구조의 데이터.
        """
        # 1. ManualControl 상태 복원
        manual_state = state.get("manual_ctrl", {})
        if manual_state:
            self.manual_ctrl.load_state(manual_state)

        # 2. Port Tabs 상태 복원
        port_states = state.get("ports", [])

        # 시그널 차단
        self.port_tabs.blockSignals(True)
        try:
            # 기존 탭 제거 (플러스 탭 제외하고 역순으로 제거)
            # 역순으로 제거해야 인덱스 문제 없음, 단 플러스 탭은 유지
            count = self.port_tabs.count()
            for i in range(count - 2, -1, -1): # 마지막 탭(count-1)은 +탭이므로 제외
                self.port_tabs.removeTab(i)

            # 저장된 상태가 없으면 기본 탭 하나 추가
            if not port_states:
                self.port_tabs.add_new_port_tab()
                return

            # 상태 복원
            for state in port_states:
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
            if current_widget and hasattr(current_widget, 'port_settings_widget'):
                if current_widget.port_settings_widget == sender_widget:
                    # 현재 탭의 변경이면 ManualControl 업데이트
                    self.manual_ctrl.set_controls_enabled(connected)
