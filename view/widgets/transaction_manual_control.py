"""Manual SPI/I2C transaction input used inside the existing Manual Control area."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.transport.transaction.dto import TransactionProtocol


def parse_hex_bytes(text: str) -> bytes:
    """Parse compact or whitespace-separated HEX without protocol side effects."""
    compact = "".join(text.split())
    if not compact:
        return b""
    if len(compact) % 2:
        raise ValueError("HEX input must contain an even number of digits")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise ValueError("HEX input contains invalid characters") from exc


class TransactionManualControlWidget(QWidget):
    """Protocol-aware SPI/I2C request editor; execution stays in Presenter/Manager."""

    execute_requested = pyqtSignal()
    input_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._protocol = TransactionProtocol.SPI
        self._stack = QStackedWidget()
        self._execute_btn = QPushButton("Execute")

        self.spi_tx_edit = QLineEdit()
        self.spi_rx_length_edit = QLineEdit("0")
        self.spi_keep_cs_chk = QCheckBox("Keep CS asserted")

        self.i2c_write_edit = QLineEdit()
        self.i2c_read_length_edit = QLineEdit("0")
        self.i2c_repeated_start_chk = QCheckBox("Repeated Start")
        self.i2c_repeated_start_chk.setChecked(True)

        self._init_ui()

    def _init_ui(self) -> None:
        self.spi_tx_edit.setPlaceholderText("HEX TX, e.g. 9F or 9F 00 00 00")
        self.i2c_write_edit.setPlaceholderText("HEX Write, e.g. 00 10")
        self.spi_rx_length_edit.setValidator(QIntValidator(0, 1_000_000))
        self.i2c_read_length_edit.setValidator(QIntValidator(0, 1_000_000))

        self._stack.addWidget(self._create_spi_page())
        self._stack.addWidget(self._create_i2c_page())
        self._execute_btn.setProperty("class", "accent")
        self._execute_btn.clicked.connect(self.execute_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self._execute_btn)
        layout.addLayout(button_row)

    def _create_spi_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("TX (HEX)"))
        row.addWidget(self.spi_tx_edit, 1)
        row.addWidget(QLabel("RX Length"))
        row.addWidget(self.spi_rx_length_edit)
        row.addWidget(self.spi_keep_cs_chk)
        return page

    def _create_i2c_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Write (HEX)"))
        row.addWidget(self.i2c_write_edit, 1)
        row.addWidget(QLabel("Read Length"))
        row.addWidget(self.i2c_read_length_edit)
        row.addWidget(self.i2c_repeated_start_chk)
        return page

    def set_protocol(self, protocol: TransactionProtocol) -> None:
        self._protocol = protocol
        self._stack.setCurrentIndex(0 if protocol is TransactionProtocol.SPI else 1)

    def set_controls_enabled(self, enabled: bool) -> None:
        self._stack.setEnabled(enabled)
        self._execute_btn.setEnabled(enabled)

    def spi_input(self) -> tuple[bytes, int, bool]:
        return (
            parse_hex_bytes(self.spi_tx_edit.text()),
            int(self.spi_rx_length_edit.text() or "0"),
            self.spi_keep_cs_chk.isChecked(),
        )

    def i2c_input(self) -> tuple[bytes, int, bool]:
        return (
            parse_hex_bytes(self.i2c_write_edit.text()),
            int(self.i2c_read_length_edit.text() or "0"),
            self.i2c_repeated_start_chk.isChecked(),
        )
