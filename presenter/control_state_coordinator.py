"""Manual/Macro control enable policy coordinator.

Manual Control follows the current unified Port tab, including SPI/I2C sessions.
Macro and Serial broadcast keep their established stream-oriented policy.
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
        """Older PortView/test doubles use only the established Serial facade."""
        try:
            return bool(self._port_view.is_current_port_connected())
        except AttributeError:
            return False

    def refresh(self) -> None:
        """Recompute Manual/Macro enable state from the current tab and runtimes."""
        current_panel = self._current_panel()
        current_protocol = ConnectionProtocol.SERIAL

        if current_panel is not None:
            protocol_getter = getattr(current_panel, "current_protocol", None)
            raw_protocol = protocol_getter() if protocol_getter is not None else None
            if self._is_known_protocol(raw_protocol):
                current_protocol = raw_protocol
                current_connected = bool(current_panel.is_connected())
            else:
                # MagicMock/legacy facade처럼 새 protocol contract가 없는 객체는
                # 기존 Serial 연결 판정 API를 사용해 이전 동작을 보존합니다.
                current_connected = self._legacy_current_connected()
        else:
            current_connected = self._legacy_current_connected()

        has_serial_connection = self._connection_controller.has_active_connection
        manual_enabled = current_connected or (
            self._manual_presenter.is_broadcast_enabled() and has_serial_connection
        )

        current_serial_connected = (
            current_connected and current_protocol == ConnectionProtocol.SERIAL
        )
        macro_enabled = current_serial_connected or (
            self._macro_presenter.is_broadcast_enabled() and has_serial_connection
        )

        self._manual_presenter.set_enabled(manual_enabled)
        self._macro_presenter.set_enabled(macro_enabled)
