"""
메인 윈도우 좌측 섹션 모듈.

PortTabPanel, ManualControlPanel, SystemLogWidget을 배치하고 Presenter가 사용할 View
facade/signal을 제공합니다. 연결 상태에 따른 제어 활성화 정책은 Presenter가 소유합니다.
"""
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from common.constants import LAYOUT_MARGIN_NONE
from common.dtos import ColorRule, LogDataBatch, PortInfo, SystemLogEvent
from view.managers.color_manager import ColorManager
from view.managers.language_manager import language_manager
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.port_panel import PortPanel
from view.managers.theme_manager import ThemeManager
from view.panels.port_tab_panel import PortTabPanel
from view.widgets.system_log import SystemLogWidget


class MainLeftSection(QWidget):
    """좌측 UI 컨테이너와 Presenter용 facade를 제공합니다."""

    send_requested = pyqtSignal(object)
    port_tab_added = pyqtSignal(object)
    port_tab_closed = pyqtSignal(str)
    current_tab_changed = pyqtSignal()

    sys_logging_start_requested = pyqtSignal()
    sys_logging_stop_requested = pyqtSignal()
    system_log_line_appended = pyqtSignal(str)

    def __init__(
        self,
        theme_manager: ThemeManager,
        color_manager: ColorManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._color_manager = color_manager
        self._port_tab_panel: Optional[PortTabPanel] = None
        self._manual_control_panel: Optional[ManualControlPanel] = None
        self._system_log_widget: Optional[SystemLogWidget] = None

        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """좌측 영역의 하위 View를 생성하고 순수 UI signal relay를 구성합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
        )
        layout.setSpacing(10)

        self._port_tab_panel = PortTabPanel(self._theme_manager)
        self._port_tab_panel.port_tab_added.connect(self._on_port_tab_added)
        self._port_tab_panel.port_tab_added.connect(self.port_tab_added.emit)
        self._port_tab_panel.port_tab_closed.connect(self.port_tab_closed.emit)
        self._port_tab_panel.currentChanged.connect(self.current_tab_changed.emit)

        # PortTabPanel 생성자에서 이미 만들어진 초기 탭에도 동일한 presentation
        # 정책을 적용합니다. 생성 시그널 연결 이전에 만들어진 탭을 놓치지 않습니다.
        for panel in self.get_port_panels():
            self._apply_port_panel_presentation(panel)

        self._manual_control_panel = ManualControlPanel()
        self._manual_control_panel.send_requested.connect(self.send_requested.emit)

        self._system_log_widget = SystemLogWidget()
        self._system_log_widget.sys_logging_start_requested.connect(
            self.sys_logging_start_requested.emit
        )
        self._system_log_widget.sys_logging_stop_requested.connect(
            self.sys_logging_stop_requested.emit
        )
        self._system_log_widget.system_log_line_appended.connect(
            self.system_log_line_appended.emit
        )

        layout.addWidget(self._port_tab_panel, 1)
        layout.addWidget(self._manual_control_panel)
        layout.addWidget(self._system_log_widget)
        self.setLayout(layout)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        """새 PortPanel에 View-only presentation 정책을 적용합니다."""
        self._apply_port_panel_presentation(panel)

    def _apply_port_panel_presentation(self, panel: PortPanel) -> None:
        panel.set_data_log_color_rules(self._color_manager.rules)

    def retranslate_ui(self) -> None:
        """섹션 자체에는 번역 대상 텍스트가 없고 하위 View가 각자 갱신합니다."""

    @property
    def manual_control_panel(self) -> ManualControlPanel:
        return self._manual_control_panel

    @property
    def port_tab_panel(self) -> PortTabPanel:
        return self._port_tab_panel

    # ------------------------------------------------------------------
    # Presenter facade
    # ------------------------------------------------------------------
    def is_current_port_connected(self) -> bool:
        current_widget = self._port_tab_panel.currentWidget()
        if isinstance(current_widget, PortPanel):
            return current_widget.is_connected()
        return False

    def connect_tab_changed_signal(self, slot: Callable[[int], None]) -> None:
        self._port_tab_panel.currentChanged.connect(slot)

    def get_port_tabs_count(self) -> int:
        return self._port_tab_panel.count()

    def get_port_panel_at(self, index: int) -> Optional[PortPanel]:
        widget = self._port_tab_panel.widget(index)
        return widget if isinstance(widget, PortPanel) else None

    def get_port_panels(self) -> List[PortPanel]:
        panels: List[PortPanel] = []
        for index in range(self._port_tab_panel.count()):
            panel = self.get_port_panel_at(index)
            if panel:
                panels.append(panel)
        return panels

    def get_current_port_panel(self) -> Optional[PortPanel]:
        widget = self._port_tab_panel.currentWidget()
        return widget if isinstance(widget, PortPanel) else None

    def get_current_port_name(self) -> str:
        panel = self.get_current_port_panel()
        return panel.get_port_name() if panel else ""

    def set_port_list_for_all(self, port_list: List[PortInfo]) -> None:
        for panel in self.get_port_panels():
            panel.set_port_list(port_list)

    def set_port_connection_state(self, port_name: str, connected: bool) -> None:
        for panel in self.get_port_panels():
            if panel.get_port_name() == port_name:
                panel.set_connected(connected)
                break

    def log_system_message(self, event: SystemLogEvent) -> None:
        self._system_log_widget.append_log(event)

    def show_error_message(self, title: str, message: str) -> None:
        """현재 호출 스택 종료 후 비재진입 오류 dialog를 표시합니다."""
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))

    def set_system_log_color_rules(self, rules: List[ColorRule]) -> None:
        self._system_log_widget.set_color_rules(rules)

    def show_save_log_dialog(self) -> str:
        return self._system_log_widget.show_save_log_dialog()

    def set_logging_active(self, active: bool) -> None:
        self._system_log_widget.set_logging_active(active)

    def trigger_current_port_log_save(self) -> None:
        panel = self.get_current_port_panel()
        if panel:
            panel.trigger_log_save()

    def clear_current_port_log(self) -> None:
        panel = self.get_current_port_panel()
        if panel:
            panel.clear_data_log()

    # ------------------------------------------------------------------
    # Port/tab View operations
    # ------------------------------------------------------------------
    def add_new_port_tab(self) -> None:
        self._port_tab_panel.add_new_port_tab()

    def add_new_tab(self, port: str) -> None:
        """복원용으로 지정 포트 이름의 View 탭을 추가합니다."""
        tab = PortPanel(port)
        self._apply_port_panel_presentation(tab)
        self._port_tab_panel.addTab(tab, port)
        self._port_tab_panel.setCurrentWidget(tab)

    def open_current_port(self) -> None:
        """현재 PortPanel의 사용자 Connect 동작을 트리거합니다."""
        current_widget = self.get_current_port_panel()
        if current_widget and not current_widget.is_connected():
            current_widget.toggle_connection()

    def close_current_port(self) -> None:
        """현재 PortPanel의 사용자 Disconnect 동작을 트리거합니다."""
        current_widget = self.get_current_port_panel()
        if current_widget and current_widget.is_connected():
            current_widget.toggle_connection()

    def close_current_tab(self) -> None:
        current_index = self._port_tab_panel.currentIndex()
        if current_index == self._port_tab_panel.count() - 1:
            return
        if current_index >= 0:
            self._port_tab_panel.close_port_tab(current_index)

    # ------------------------------------------------------------------
    # Data View facade
    # ------------------------------------------------------------------
    def append_data_to_current_port(self, data: bytes) -> None:
        current_widget = self.get_current_port_panel()
        if current_widget:
            current_widget.append_log_data(data)

    def append_rx_data(self, batch: LogDataBatch) -> None:
        self._port_tab_panel.append_rx_data(batch)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        manual_state = self._manual_control_panel.get_state()
        port_states = []

        for index in range(self._port_tab_panel.count()):
            if index == self._port_tab_panel.count() - 1:
                continue
            widget = self._port_tab_panel.widget(index)
            if isinstance(widget, PortPanel):
                port_states.append(widget.get_state())

        return {
            "manual_control": manual_state,
            "ports": port_states,
        }

    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        하위 View 상태를 복원합니다.

        ManualControl의 최종 DTO 복원은 AppLifecycleManager/ManualControlPresenter가
        담당합니다. 여기서는 포트 탭 View collection 복원에 집중합니다.
        """
        port_states = state.get("ports", [])

        self._port_tab_panel.blockSignals(True)
        try:
            count = self._port_tab_panel.count()
            for index in range(count - 2, -1, -1):
                self._port_tab_panel.removeTab(index)

            if not port_states:
                panel = self._port_tab_panel.add_new_port_tab()
                self._apply_port_panel_presentation(panel)
                return

            for port_state in port_states:
                panel = self._port_tab_panel.add_new_port_tab()
                panel.apply_state(port_state)
                self._apply_port_panel_presentation(panel)
        finally:
            self._port_tab_panel.blockSignals(False)
            if self._port_tab_panel.count() > 1:
                self._port_tab_panel.setCurrentIndex(0)
