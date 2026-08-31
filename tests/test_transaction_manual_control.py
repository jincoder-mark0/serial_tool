"""Manual transaction editor regression tests."""
import pytest

from common.enums import ConnectionProtocol
from core.transport.transaction.dto import TransactionProtocol
from view.panels.manual_control_panel import ManualControlPanel
from view.widgets.transaction_manual_control import (
    TransactionManualControlWidget,
    parse_hex_bytes,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9f", b"\x9f"),
        ("9F 00 01", b"\x9f\x00\x01"),
        ("9f0001", b"\x9f\x00\x01"),
        ("", b""),
    ],
)
def test_parse_hex_bytes_accepts_compact_and_spaced_input(text, expected):
    assert parse_hex_bytes(text) == expected


def test_parse_hex_bytes_rejects_invalid_input():
    with pytest.raises(ValueError, match="even number"):
        parse_hex_bytes("ABC")
    with pytest.raises(ValueError, match="invalid"):
        parse_hex_bytes("GG")


def test_transaction_widget_returns_spi_fields(qtbot):
    widget = TransactionManualControlWidget()
    qtbot.addWidget(widget)
    widget.set_protocol(TransactionProtocol.SPI)
    widget.spi_tx_edit.setText("9F")
    widget.spi_rx_length_edit.setText("3")
    widget.spi_keep_cs_chk.setChecked(True)

    assert widget.spi_input() == (b"\x9f", 3, True)


def test_transaction_widget_returns_i2c_fields(qtbot):
    widget = TransactionManualControlWidget()
    qtbot.addWidget(widget)
    widget.set_protocol(TransactionProtocol.I2C)
    widget.i2c_write_edit.setText("00 10")
    widget.i2c_read_length_edit.setText("4")
    widget.i2c_repeated_start_chk.setChecked(False)

    assert widget.i2c_input() == (b"\x00\x10", 4, False)


def test_manual_control_panel_switches_protocol_without_replacing_serial_state(qtbot):
    panel = ManualControlPanel()
    qtbot.addWidget(panel)
    panel.set_input_text("AT")

    panel.set_protocol(TransactionProtocol.SPI.value)
    assert panel.current_protocol() == "SPI"

    panel.set_protocol(TransactionProtocol.I2C.value)
    assert panel.current_protocol() == "I2C"

    panel.set_protocol(ConnectionProtocol.SERIAL)
    assert panel.current_protocol() == ConnectionProtocol.SERIAL
    assert panel.get_input_text() == "AT"
