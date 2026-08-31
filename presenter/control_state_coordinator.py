"""Manual/Macro control enable policy coordinator.

Manual Control과 Macro/명령 리스트는 현재 unified Port tab의 Serial/SPI/I2C 연결을 모두
사용할 수 있습니다. Broadcast도 Serial connection 또는 transaction session이 하나라도
활성화되어 있으면 protocol-aware router를 통해 실행할 수 있습니다.
"""
from PyQt5.QtCore import QObject

from common.enums import ConnectionProtocol
from core.transport.transaction.dto import TransactionProtocol
from model.connection_controller import ConnectionController
from model.transaction_manager import TransactionManager
from presenter.macro_presenter import MacroPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from view.sections.main_left_section import MainLeftSection


class ControlStateCoordinator(QObject):
    """Synchronize control availability across Serial and transaction runtimes."""

    def __init__(
        self,
        port_view: MainLeftSection,
        connection_controller: ConnectionController,
        manual_presenter: ManualControlPresenter,
        macro_presenter: MacroPresenter,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        super().__init__()
        self._port_view = port_view
        self._connection_controller = connection_controller
        self._manual_presenter = manual_presenter
        self._macro_presenter = macro_presenter
        self._transaction_manager = transaction_manager

        tab_changed = getattr(self._port_view, "current_tab_changed", None)
        if tab_changed is not None:
            tab_changed.connect(self.refresh)
        self._connection_controller.connection_opened.connect(self._on_connection_changed)
        self._connection_controller.connection_closed.connect(self._on_connection_changed)
        self._manual_presenter.broadcast_changed.connect(self._on_broadcast_changed)
        protocol_changed = getattr(self._manual_presenter, "protocol_changed", None)
        if protocol_changed is not None:
            protocol_changed.connect(self._on_protocol_changed)
        self._macro_presenter.broadcast_changed.connect(self._on_broadcast_changed)

        if self._transaction_manager is not None:
            self._transaction_manager.session_opened.connect(self._on_transaction_changed)
            self._transaction_manager.session_closed.connect(self._on_transaction_changed)
            self._transaction_manager.session_failed.connect(self._on_transaction_changed)

        self.refresh()

    def _on_connection_changed(self, _event) -> None:
        self.refresh()

    def _on_transaction_changed(self, *_args) -> None:
        self.refresh()

    def _on_broadcast_changed(self, _enabled: bool) -> None:
        self.refresh()

    def _on_protocol_changed(self, _protocol: str) -> None:
        self.refresh()

    def _current_panel(self):
        getter = getattr(self._port_view, "get_current_port_panel", None)
        return getter() if getter is not None else None

    @staticmethod
    def _is_known_protocol(value) -> bool:
        return isinstance(value, str) and value in {
            ConnectionProtocol.SERIAL,
            TransactionProtocol.SPI.value,
            TransactionProtocol.I2C.value,
        }

    def _legacy_current_connected(self) -> bool:
        try:
            return bool(self._port_view.is_current_port_connected())
        except AttributeError:
            return False

    def refresh(self) -> None:
        """현재 target 또는 broadcast target 존재 여부로 Manual/Macro 상태를 계산합니다."""
        current_panel = self._current_panel()
        if current_panel is not None:
            protocol_getter = getattr(current_panel, "current_protocol", None)
            raw_protocol = protocol_getter() if protocol_getter is not None else None
            if self._is_known_protocol(raw_protocol):
                current_connected = bool(current_panel.is_connected())
            else:
                current_connected = self._legacy_current_connected()
        else:
            current_connected = self._legacy_current_connected()

        has_serial_connection = self._connection_controller.has_active_connection
        has_transaction_session = bool(
            self._transaction_manager and self._transaction_manager.has_active_session
        )
        has_any_target = has_serial_connection or has_transaction_session

        manual_enabled = current_connected or (
            self._manual_presenter.is_broadcast_enabled() and has_any_target
        )
        macro_enabled = current_connected or (
            self._macro_presenter.is_broadcast_enabled() and has_any_target
        )

        self._manual_presenter.set_enabled(manual_enabled)
        self._macro_presenter.set_enabled(macro_enabled)
