"""
Manual/Macro 제어 활성화 정책 조정자.

현재 탭 연결 상태, 전체 연결 존재 여부, Manual/Macro broadcast 모드를 조합해
두 제어 영역의 enabled 상태를 계산합니다. View는 정책을 소유하지 않고 facade만
제공하며 MainPresenter도 이 상태 계산을 알지 않습니다.
"""
from PyQt5.QtCore import QObject

from model.connection_controller import ConnectionController
from presenter.macro_presenter import MacroPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from view.sections.main_left_section import MainLeftSection


class ControlStateCoordinator(QObject):
    """연결/탭/broadcast 변화에 따라 Manual/Macro control 상태를 동기화합니다."""

    def __init__(
        self,
        port_view: MainLeftSection,
        connection_controller: ConnectionController,
        manual_presenter: ManualControlPresenter,
        macro_presenter: MacroPresenter,
    ) -> None:
        super().__init__()
        self._port_view = port_view
        self._connection_controller = connection_controller
        self._manual_presenter = manual_presenter
        self._macro_presenter = macro_presenter

        self._port_view.current_tab_changed.connect(self.refresh)
        self._connection_controller.connection_opened.connect(self._on_connection_changed)
        self._connection_controller.connection_closed.connect(self._on_connection_changed)
        self._manual_presenter.broadcast_changed.connect(self._on_broadcast_changed)
        self._macro_presenter.broadcast_changed.connect(self._on_broadcast_changed)

        self.refresh()

    def _on_connection_changed(self, _event) -> None:
        self.refresh()

    def _on_broadcast_changed(self, _enabled: bool) -> None:
        self.refresh()

    def refresh(self) -> None:
        """현재 연결/broadcast 상태에서 각 control의 enabled 값을 다시 계산합니다."""
        current_connected = self._port_view.is_current_port_connected()
        has_any_connection = self._connection_controller.has_active_connection

        manual_enabled = current_connected or (
            self._manual_presenter.is_broadcast_enabled() and has_any_connection
        )
        macro_enabled = current_connected or (
            self._macro_presenter.is_broadcast_enabled() and has_any_connection
        )

        self._manual_presenter.set_enabled(manual_enabled)
        self._macro_presenter.set_enabled(macro_enabled)
