"""Manual/Macro control enable policy coordinator.

Manual Control follows the current unified Port tab, including SPI/I2C sessions.
Macro and broadcast remain Serial-only because their execution semantics are
stream-oriented and are not part of the transaction runtime contract.
"""
from PyQt5.QtCore import QObject

from common.enums import ConnectionProtocol
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

        self._port_view.current_tab_changed.connect(self.refresh)
        self._connection_controller.connection_opened.connect(self._on_connection_changed)
        self._connection_controller.connection_closed.connect(self._on_connection_changed)
        self._manual_presenter.broadcast_changed.connect(self._on_broadcast_changed)
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

    def refresh(self) -> None:
        """Recompute Manual/Macro enable state from the current tab and runtimes."""
        current_panel = self._port_view.get_current_port_panel()
        current_connected = bool(current_panel and current_panel.is_connected())
        current_protocol = ConnectionProtocol.SERIAL
        if current_panel is not None:
            getter = getattr(current_panel, "current_protocol", None)
            if getter is not None:
                current_protocol = getter()

        has_serial_connection = self._connection_controller.has_active_connection
        manual_enabled = current_connected or (
            self._manual_presenter.is_broadcast_enabled() and has_serial_connection
        )

        # Macro is intentionally Serial-only. A connected SPI/I2C tab must not
        # enable stream-oriented macro execution accidentally.
        current_serial_connected = (
            current_connected and current_protocol == ConnectionProtocol.SERIAL
        )
        macro_enabled = current_serial_connected or (
            self._macro_presenter.is_broadcast_enabled() and has_serial_connection
        )

        self._manual_presenter.set_enabled(manual_enabled)
        self._macro_presenter.set_enabled(macro_enabled)
