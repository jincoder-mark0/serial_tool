"""TransactionConnectionConfig / legacy PortConfig migration tests."""

import pytest

from common.dtos import PortConfig
from common.enums import ConnectionProtocol
from core.transport.transaction.config import (
    LegacyPortConfigAdapter,
    TransactionConnectionConfig,
)
from core.transport.transaction.dto import (
    AdapterIdentity,
    I2cConfig,
    SpiConfig,
    TransactionProtocol,
)
from core.transport.transaction.errors import ProtocolConfigurationError


def test_spi_connection_keeps_adapter_identity_separate_from_protocol_fields():
    config = TransactionConnectionConfig(
        name="fixture-spi",
        protocol=TransactionProtocol.SPI,
        adapter=AdapterIdentity("pyftdi", "FT9ABC12", "A"),
        spi=SpiConfig(frequency_hz=12_000_000, mode=2, chip_select=1),
    )

    assert config.adapter.backend_id == "pyftdi"
    assert config.adapter.stable_id == "FT9ABC12"
    assert config.adapter.channel_id == "A"
    assert config.spi.frequency_hz == 12_000_000
    assert config.i2c is None


def test_i2c_connection_rejects_mixed_protocol_config():
    with pytest.raises(ProtocolConfigurationError, match="must not include spi"):
        TransactionConnectionConfig(
            name="fixture-i2c",
            protocol=TransactionProtocol.I2C,
            adapter=AdapterIdentity("ch347", "CH347-001"),
            spi=SpiConfig(frequency_hz=1_000_000),
            i2c=I2cConfig(frequency_hz=100_000, address=0x50),
        )


def test_legacy_spi_migration_requires_explicit_adapter_identity():
    legacy = PortConfig(
        port="legacy-spi",
        protocol=ConnectionProtocol.SPI,
        speed=5_000_000,
        mode=3,
    )
    identity = AdapterIdentity("pyftdi", "FT2232-001", "B")

    migrated = LegacyPortConfigAdapter.to_spi_connection(
        legacy,
        identity,
        chip_select=2,
    )

    assert migrated.protocol is TransactionProtocol.SPI
    assert migrated.adapter == identity
    assert migrated.spi == SpiConfig(
        frequency_hz=5_000_000,
        mode=3,
        chip_select=2,
    )


def test_legacy_serial_config_is_not_silently_converted_to_spi():
    legacy = PortConfig(port="COM3", protocol=ConnectionProtocol.SERIAL)

    with pytest.raises(ProtocolConfigurationError, match="must use SPI"):
        LegacyPortConfigAdapter.to_spi_connection(
            legacy,
            AdapterIdentity("pyftdi", "FT2232-001", "A"),
        )
