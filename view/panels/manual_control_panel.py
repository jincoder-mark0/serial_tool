"""Unified Manual Control panel.

Serial/SPI/I2C는 같은 Command 입력 UI를 공유합니다. Protocol별 차이는 payload가 아니라
bus control option이므로 Serial은 RTS/DTR, SPI는 Keep CS, I2C는 Repeated Start만 전환합니다.
"""
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from common.constants import LAYOUT_MARGIN_NONE, LAYOUT_SPACING_DEFAULT
from common.dtos import ManualControlState
from common.enums import ConnectionProtocol
from view.managers.language_manager import language_manager
from view.widgets.manual_control import ManualControlWidget


class ManualControlPanel(QWidget):
    """One payload editor with a small protocol-specific option surface."""

    send_requested = pyqtSignal(object)
    broadcast_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)
    rts_changed = pyqtSignal(bool)
    auto_tx_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.title_lbl: Optional[QLabel] = None
        self._manual_control_widget = ManualControlWidget()
        self._protocol = ConnectionProtocol.SERIAL

        self._keep_cs_chk = QCheckBox("Keep CS")
        self._repeated_start_chk = QCheckBox("Repeated Start")
        self._repeated_start_chk.setChecked(True)

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

        protocol_option_row = QHBoxLayout()
        protocol_option_row.setContentsMargins(0, 0, 0, 0)
        protocol_option_row.addWidget(self._keep_cs_chk)
        protocol_option_row.addWidget(self._repeated_start_chk)
        protocol_option_row.addStretch()

        layout.addWidget(self.title_lbl)
        layout.addWidget(self._manual_control_widget)
        layout.addLayout(protocol_option_row)
        layout.addStretch()
        self.setLayout(layout)

        self.set_protocol(ConnectionProtocol.SERIAL)

    def retranslate_ui(self) -> None:
        self.title_lbl.setText(language_manager.get_text("manual_panel_title"))

    # ------------------------------------------------------------------
    # Protocol selection
    # ------------------------------------------------------------------
    def set_protocol(self, protocol: str) -> None:
        """Protocol별 bus-control option만 전환하고 payload UI는 그대로 유지합니다."""
        self._protocol = protocol
        is_serial = protocol == ConnectionProtocol.SERIAL
        is_spi = protocol == ConnectionProtocol.SPI
        is_i2c = protocol == ConnectionProtocol.I2C

        # ManualControlWidget이 기존 Serial contract의 RTS/DTR을 소유하므로,
        # Panel은 child ownership 경계 안에서 표시 여부만 전환합니다.
        self._manual_control_widget.rts_chk.setVisible(is_serial)
        self._manual_control_widget.dtr_chk.setVisible(is_serial)
        self._keep_cs_chk.setVisible(is_spi)
        self._repeated_start_chk.setVisible(is_i2c)

    def current_protocol(self) -> str:
        return self._protocol

    def is_keep_cs_enabled(self) -> bool:
        return self._keep_cs_chk.isChecked()

    def is_repeated_start_enabled(self) -> bool:
        return self._repeated_start_chk.isChecked()

    # ------------------------------------------------------------------
    # Shared enable policy
    # ------------------------------------------------------------------
    def set_controls_enabled(self, enabled: bool) -> None:
        self._manual_control_widget.set_controls_enabled(enabled)
        self._keep_cs_chk.setEnabled(enabled)
        self._repeated_start_chk.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Existing Manual Control facade
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
    # Existing Manual Control state persistence
    # ------------------------------------------------------------------
    def get_state(self) -> ManualControlState:
        return self._manual_control_widget.get_state()

    def apply_state(self, state: ManualControlState) -> None:
        if isinstance(state, ManualControlState):
            self._manual_control_widget.apply_state(state)
