"""Unified Manual Control protocol option regression tests."""

from common.enums import ConnectionProtocol
from core.transport.transaction.dto import TransactionProtocol
from view.panels.manual_control_panel import ManualControlPanel


def test_manual_control_panel_preserves_shared_payload_state(qtbot):
    panel = ManualControlPanel()
    qtbot.addWidget(panel)
    panel.set_input_text("9F 00 00 00")

    panel.set_protocol(TransactionProtocol.SPI.value)
    assert panel.current_protocol() == "SPI"
    assert panel.get_input_text() == "9F 00 00 00"

    panel.set_protocol(TransactionProtocol.I2C.value)
    assert panel.current_protocol() == "I2C"
    assert panel.get_input_text() == "9F 00 00 00"

    panel.set_protocol(ConnectionProtocol.SERIAL)
    assert panel.current_protocol() == ConnectionProtocol.SERIAL
    assert panel.get_input_text() == "9F 00 00 00"


def test_serial_shows_rts_dtr_only(qtbot):
    panel = ManualControlPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.set_protocol(ConnectionProtocol.SERIAL)

    assert not panel.manual_control_widget.rts_chk.isHidden()
    assert not panel.manual_control_widget.dtr_chk.isHidden()
    assert panel._keep_cs_chk.isHidden()
    assert panel._repeated_start_chk.isHidden()


def test_spi_shows_keep_cs_only(qtbot):
    panel = ManualControlPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.set_protocol(TransactionProtocol.SPI.value)
    panel._keep_cs_chk.setChecked(True)

    assert panel.manual_control_widget.rts_chk.isHidden()
    assert panel.manual_control_widget.dtr_chk.isHidden()
    assert not panel._keep_cs_chk.isHidden()
    assert panel._repeated_start_chk.isHidden()
    assert panel.is_keep_cs_enabled() is True


def test_i2c_shows_repeated_start_only(qtbot):
    panel = ManualControlPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.set_protocol(TransactionProtocol.I2C.value)
    panel._repeated_start_chk.setChecked(False)

    assert panel.manual_control_widget.rts_chk.isHidden()
    assert panel.manual_control_widget.dtr_chk.isHidden()
    assert panel._keep_cs_chk.isHidden()
    assert not panel._repeated_start_chk.isHidden()
    assert panel.is_repeated_start_enabled() is False
