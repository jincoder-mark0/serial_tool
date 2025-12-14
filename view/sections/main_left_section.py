"""
메인 윈도우 좌측 섹션 모듈

포트 탭과 수동 제어 패널을 포함하는 좌측 영역을 정의합니다.

## WHY
* 화면 레이아웃의 논리적 구획 분리
* 포트 관리와 제어 기능의 그룹화

## WHAT
* PortTabPanel 및 ManualControlPanel 배치
* SysLogWidget 배치
* 하위 패널 간 상호작용 중재 (View 레벨)

## HOW
* QVBoxLayout으로 수직 배치
* 시그널 중계를 통해 MainWindow와 통신
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional, Dict, Any
from view.managers.language_manager import language_manager

from view.panels.port_panel import PortPanel
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.port_tab_panel import PortTabPanel
from view.widgets.sys_log import SysLogWidget

class MainLeftSection(QWidget):
    """
    좌측 섹션 관리 클래스

    Attributes:
        port_tabs (PortTabPanel): 포트 탭 관리 패널
        manual_control (ManualControlPanel): 수동 제어 패널
        sys_log_widget (SysLogWidget): 시스템 로그 위젯
    """

    # 하위 패널 이벤트 상위 전달 시그널
    manual_command_send_requested = pyqtSignal(str, bool, bool, bool, bool)
    port_tab_added = pyqtSignal(object) # PortPanel 객체 전달

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MainLeftSection 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.port_tabs = None
        self.manual_control = None
        self.sys_log_widget = None
        self.init_ui()

        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ---------------------------------------------------------
        # 1. 포트 탭 (Port Tabs)
        # ---------------------------------------------------------
        self.port_tabs = PortTabPanel()
        self.port_tabs.tab_added.connect(self._on_tab_added)
        self.port_tabs.tab_added.connect(self.port_tab_added.emit) # 외부 전달

        # ---------------------------------------------------------
        # 2. 수동 제어 패널 (Manual Control)
        # ---------------------------------------------------------
        self.manual_control = ManualControlPanel()
        self.manual_control.manual_command_send_requested.connect(self.manual_command_send_requested.emit)

        # ---------------------------------------------------------
        # 3. 시스템 로그 (System Log)
        # ---------------------------------------------------------
        self.sys_log_widget = SysLogWidget()

        layout.addWidget(self.port_tabs, 1)
        layout.addWidget(self.manual_control)
        layout.addWidget(self.sys_log_widget)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """다국어 텍스트 업데이트"""
        # 하위 컴포넌트들이 자체적으로 처리하므로 비워둠
        pass

    def add_new_port_tab(self) -> None:
        """새 포트 탭 추가"""
        self.port_tabs.add_new_port_tab()

    def open_current_port(self) -> None:
        """현재 활성 탭의 포트 열기"""
        current_index = self.port_tabs.currentIndex()
        current_widget = self.port_tabs.widget(current_index)
        if isinstance(current_widget, PortPanel):
            if not current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_port(self) -> None:
        """현재 활성 탭의 포트 닫기"""
        current_index = self.port_tabs.currentIndex()
        current_widget = self.port_tabs.widget(current_index)
        if isinstance(current_widget, PortPanel):
            if current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_tab(self) -> None:
        """현재 활성 탭 닫기"""
        current_index = self.port_tabs.currentIndex()
        # 마지막 탭(플러스 탭)은 닫을 수 없음
        if current_index == self.port_tabs.count() - 1:
            return

        if current_index >= 0:
            self.port_tabs.removeTab(current_index)

    def append_data_to_current_port(self, data: bytes) -> None:
        """
        현재 활성화된 포트 탭의 로그창에 데이터를 추가합니다.

        Logic:
            - 현재 탭 인덱스 조회
            - 해당 위젯이 PortPanel인지 확인
            - DataLogWidget에 데이터 전달

        Args:
            data (bytes): 추가할 데이터
        """
        current_index = self.port_tabs.currentIndex()
        current_widget = self.port_tabs.widget(current_index)

        if isinstance(current_widget, PortPanel):
            if hasattr(current_widget, 'data_log_widget'):
                current_widget.data_log_widget.append_data(data)

    def _on_tab_added(self, panel: PortPanel) -> None:
        """
        탭 추가 시그널 핸들러

        Args:
            panel (PortPanel): 추가된 패널 객체
        """
        panel.port_settings_widget.port_connection_changed.connect(
            self._on_port_connection_changed
        )

    def save_state(self) -> Dict[str, Any]:
        """
        하위 위젯 상태 수집 및 반환

        Returns:
            Dict[str, Any]: 통합된 상태 데이터
        """
        manual_state = self.manual_control.save_state()
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
            "manual_control": manual_state,
            "ports": port_states
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """
        상태 데이터 복원

        Logic:
            - ManualCtrl 상태 복원
            - 기존 탭 제거 (초기화)
            - 저장된 포트 상태만큼 탭 생성 및 복원

        Args:
            state (Dict[str, Any]): 복원할 상태 데이터
        """
        # 1. ManualCtrl 상태 복원
        manual_state = state.get("manual_control", {})
        if manual_state:
            self.manual_control.load_state(manual_state)

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
        포트 연결 상태 변경 핸들러

        Logic:
            - 시그널 발생원이 현재 활성 탭인지 확인
            - 활성 탭일 경우 ManualCtrl 활성화 상태 동기화

        Args:
            connected (bool): 연결 여부
        """
        # 현재 활성 탭의 변경인지 확인
        sender_widget = self.sender()
        if sender_widget:
            # sender의 부모를 찾아서 현재 활성 탭인지 확인
            current_index = self.port_tabs.currentIndex()
            current_widget = self.port_tabs.widget(current_index)
            if current_widget and hasattr(current_widget, 'port_settings_widget'):
                if current_widget.port_settings_widget == sender_widget:
                    # 현재 탭의 변경이면 ManualCtrl 업데이트
                    self.manual_control.set_controls_enabled(connected)
