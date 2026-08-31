"""Unified ConnectionSettingsWidget regression tests."""
from __future__ import annotations

from common.dtos import PortConfig, PortInfo
from common.enums import ConnectionProtocol
from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.dto import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterIdentity,
    I2cCapabilities,
    SpiCapabilities,
    TransactionProtocol,
)
from view.widgets.connection_settings import ConnectionSettingsWidget


def _ft2232_descriptor(channel: str) -> AdapterDescriptor:
    return AdapterDescriptor(
        identity=AdapterIdentity("pyftdi", "FT2232-SN", channel),
        device_family="FT2232H",
        display_name=f"FT2232H FT2232-SN [{channel}]",
        capabilities=AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI, TransactionProtocol.I2C}),
            channel_count=2,
            concurrent_channels=True,
            spi=SpiCapabilities(
                modes=frozenset({0, 2}),
                bit_orders=frozenset({"msb"}),
                min_frequency_hz=1_000,
                max_frequency_hz=30_000_000,
                full_duplex=True,
                chip_select_count=2,
            ),
            i2c=I2cCapabilities(
                min_frequency_hz=10_000,
                max_frequency_hz=400_000,
                seven_bit_address=True,
                ten_bit_address=False,
                repeated_start=True,
                clock_stretching=False,
            ),
        ),
    )


def test_serial_path_preserves_legacy_port_config(qtbot):
    widget = ConnectionSettingsWidget()
    qtbot.addWidget(widget)
    widget.set_port_list([PortInfo(device="COM3", description="fixture")])
    widget.protocol_combo.setCurrentText(ConnectionProtocol.SERIAL)
    widget.serial_controls_ui["baud_combo"].setCurrentText("115200")

    config = widget.get_current_config()

    assert isinstance(config, PortConfig)
    assert config.port == "COM3"
    assert config.protocol == ConnectionProtocol.SERIAL
    assert config.baudrate == 115200


def test_spi_path_uses_adapter_identity_and_capability_limited_controls(qtbot):
    widget = ConnectionSettingsWidget()
    qtbot.addWidget(widget)
    widget.protocol_combo.setCurrentText(TransactionProtocol.SPI.value)
    widget.set_adapter_descriptors(
        [_ft2232_descriptor("A"), _ft2232_descriptor("B")]
    )

    widget.channel_combo.setCurrentIndex(1)
    widget.spi_controls_ui["speed_combo"].setCurrentText("4000000")
    widget.spi_controls_ui["mode_combo"].setCurrentText("2")
    widget.spi_controls_ui["cs_combo"].setCurrentText("1")

    config = widget.get_current_config()

    assert isinstance(config, TransactionConnectionConfig)
    assert config.protocol is TransactionProtocol.SPI
    assert config.adapter == AdapterIdentity("pyftdi", "FT2232-SN", "B")
    assert config.spi.frequency_hz == 4_000_000
    assert config.spi.mode == 2
    assert config.spi.chip_select == 1
    assert config.spi.bit_order == "msb"
    assert [widget.spi_controls_ui["mode_combo"].itemText(i) for i in range(2)] == ["0", "2"]
    assert widget.spi_controls_ui["cs_combo"].count() == 2
    assert widget.spi_controls_ui["bit_order_combo"].count() == 1


def test_i2c_path_builds_transaction_config_from_same_port_panel(qtbot):
    widget = ConnectionSettingsWidget()
    qtbot.addWidget(widget)
    widget.protocol_combo.setCurrentText(TransactionProtocol.I2C.value)
    widget.set_adapter_descriptors([_ft2232_descriptor("A")])
    widget.i2c_controls_ui["speed_combo"].setCurrentText("400000")
    widget.i2c_controls_ui["address_edit"].setText("0x50")

    config = widget.get_current_config()

    assert isinstance(config, TransactionConnectionConfig)
    assert config.protocol is TransactionProtocol.I2C
    assert config.adapter == AdapterIdentity("pyftdi", "FT2232-SN", "A")
    assert config.i2c.frequency_hz == 400_000
    assert config.i2c.address == 0x50
    assert config.i2c.address_bits == 7
    assert widget.i2c_controls_ui["address_bits_combo"].count() == 1
    assert widget.i2c_controls_ui["stretch_chk"].isEnabled() is False


def test_saved_transaction_identity_is_restored_after_late_discovery(qtbot):
    widget = ConnectionSettingsWidget()
    qtbot.addWidget(widget)

    widget.apply_state(
        {
            "protocol": "SPI",
            "spi": {
                "speed": "12000000",
                "mode": "2",
                "chip_select": "1",
                "bit_order": "msb",
                "full_duplex": True,
            },
            "transaction_identity": {
                "backend_id": "pyftdi",
                "stable_id": "FT2232-SN",
                "channel_id": "B",
            },
        }
    )

    # No USB discovery result yet: identity is retained in persisted state/display contract.
    assert widget.get_connection_display_name() == "FT2232-SN[B]"
    assert widget.get_state()["transaction_identity"]["channel_id"] == "B"

    widget.set_adapter_descriptors(
        [_ft2232_descriptor("A"), _ft2232_descriptor("B")]
    )

    config = widget.get_current_config()
    assert config.adapter == AdapterIdentity("pyftdi", "FT2232-SN", "B")
    assert config.spi.frequency_hz == 12_000_000
    assert config.spi.mode == 2
    assert config.spi.chip_select == 1


def test_legacy_serial_state_schema_still_restores(qtbot):
    widget = ConnectionSettingsWidget()
    qtbot.addWidget(widget)

    widget.apply_state(
        {
            "protocol": "Serial",
            "port": "COM7",
            "serial": {
                "baudrate": "921600",
                "bytesize": "8",
                "parity": "N",
                "stopbits": "1.0",
                "flowctrl": "None",
            },
            "spi": {"speed": "1000000", "mode": "0"},
        }
    )

    config = widget.get_current_config()
    assert isinstance(config, PortConfig)
    assert config.port == "COM7"
    assert config.baudrate == 921600
