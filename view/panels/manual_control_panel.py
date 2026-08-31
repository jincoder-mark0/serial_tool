"""Unified Manual Control panel.

The panel stays in the existing location. Serial keeps the established command
widget while SPI/I2C switch to a transaction-specific editor. Presenter code
uses facade methods and does not access child widget structure directly.
"""
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from common.constants import LAYOUT_MARGIN_NONE, LAYOUT_SPACING_DEFAULT
from common.dtos import ManualControlState
from common.enums import ConnectionProtocol
from core.transport.transaction.dto import TransactionProtocol
from view.managers.language_manager import language_manager
from view.widgets.manual_control import ManualControlWidget
from view.widgets.transaction_manual_control import TransactionManualControlWidget


class ManualControlPanel(QWidget):
    """One manual-control surface with protocol-specific content."""

    send_requested = pyqtSignal(object)
    transaction_execute_requested = pyqtSignal()

    broadcast_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)
    rts_changed = pyqtSignal(bool)
    auto_tx_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.title_lbl: Optional[QLabel] = None
        self._stack = QStackedWidget()
        self._manual_control_widget = ManualControlWidget()
        self._transaction_widget = TransactionManualControlWidget()
        self._protocol = ConnectionProtocol.SERIAL

        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    @property
    def manual_control_widget(self) -> ManualControlWidget:
        """Legacy public facade kept for existing tests/callers."""
        return self._manual_control_widget

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
        )
        layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.title_lbl = QLabel(language_manager.get_text("manual_panel_title"))
        self.title_lbl.setProperty("class", "section-title")

        self._manual_control_widget.send_requested.connect(self.send_requested.emit)
        self._manual_control_widget.broadcast_changed.connect(
            self.broadcast_changed.emit
        )
        self._manual_control_widget.dtr_changed.connect(self.dtr_changed.emit)
        self._manual_control_widget.rts_changed.connect(self.rts_changed.emit)
        self._manual_control_widget.auto_tx_toggled.connect(self.auto_tx_toggled.emit)
        self._transaction_widget.execute_requested.connect(
            self.transaction_execute_requested.emit
        )

        self._stack.addWidget(self._manual_control_widget)
        self._stack.addWidget(self._transaction_widget)

        layout.addWidget(self.title_lbl)
        layout.addWidget(self._stack)
        layout.addStretch()
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        self.title_lbl.setText(language_manager.get_text("manual_panel_title"))

    # ------------------------------------------------------------------
    # Protocol selection
    # ------------------------------------------------------------------
    def set_protocol(self, protocol: str) -> None:
        self._protocol = protocol
        if protocol == ConnectionProtocol.SERIAL:
            self._stack.setCurrentIndex(0)
            return

        self._stack.setCurrentIndex(1)
        self._transaction_widget.set_protocol(TransactionProtocol(protocol))

    def current_protocol(self) -> str:
        return self._protocol

    # ------------------------------------------------------------------
    # Shared enable policy
    # ------------------------------------------------------------------
    def set_controls_enabled(self, enabled: bool) -> None:
        if self._protocol == ConnectionProtocol.SERIAL:
            self._manual_control_widget.set_controls_enabled(enabled)
        else:
            self._transaction_widget.set_controls_enabled(enabled)

    # ------------------------------------------------------------------
    # Transaction facade
    # ------------------------------------------------------------------
    def get_spi_transaction_input(self) -> tuple[bytes, int, bool]:
        return self._transaction_widget.spi_input()

    def get_i2c_transaction_input(self) -> tuple[bytes, int, bool]:
        return self._transaction_widget.i2c_input()

    # ------------------------------------------------------------------
    # Existing Serial facade - preserved for current presenters/tests
    # ------------------------------------------------------------------
    def set_local_echo_checked(self, checked: bool) -> None:
        self._manual_control_widget.set_local_echo_state(checked)

    def get_input_text(self) -> str:
        return self._manual_control_widget.get_input_text()

    def set_input_text(self, text: str) -> None:
        self._manual_control_widget.set_input_text(text)

    def is_hex_mode(self) -> bool:
        return self._manual_control_widget.is_hex_mode()

    def is_prefix_enabled(self) -> bool:
        return self._manual_control_widget.is_prefix_enabled()

    def is_suffix_enabled(self) -> bool:
        return self._manual_control_widget.is_suffix_enabled()

    def is_rts_enabled(self) -> bool:
        return self._manual_control_widget.is_rts_enabled()

    def is_dtr_enabled(self) -> bool:
        return self._manual_control_widget.is_dtr_enabled()

    def is_local_echo_enabled(self) -> bool:
        return self._manual_control_widget.is_local_echo_enabled()

    def is_broadcast_enabled(self) -> bool:
        return self._manual_control_widget.is_broadcast_enabled()

    def is_auto_tx_enabled(self) -> bool:
        return self._manual_control_widget.is_auto_tx_enabled()

    def get_auto_tx_interval_ms(self) -> int:
        return self._manual_control_widget.get_auto_tx_interval_ms()

    def set_auto_tx_checked(self, checked: bool) -> None:
        self._manual_control_widget.set_auto_tx_checked(checked)

    def set_input_focus(self) -> None:
        self._manual_control_widget.set_input_focus()

    # ------------------------------------------------------------------
    # Existing Serial state persistence
    # ------------------------------------------------------------------
    def get_state(self) -> ManualControlState:
        return self._manual_control_widget.get_state()

    def apply_state(self, state: ManualControlState) -> None:
        if isinstance(state, ManualControlState):
            self._manual_control_widget.apply_state(state)
