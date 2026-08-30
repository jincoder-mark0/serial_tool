"""Vendor-neutral transaction adapter contract regression tests."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.transport.transaction.contracts import AdapterHandle, AdapterProvider
from core.transport.transaction.dto import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterIdentity,
    I2cCapabilities,
    I2cConfig,
    SpiCapabilities,
    SpiConfig,
    TransactionProtocol,
)
from core.transport.transaction.errors import (
    BackendUnavailableError,
    ProtocolConfigurationError,
    UnsupportedCapabilityError,
)
from core.transport.transaction.registry import AdapterBackendRegistry


class _FakeHandle(AdapterHandle):
    def __init__(self, descriptor: AdapterDescriptor) -> None:
        self._descriptor = descriptor
        self.closed = False

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def open_spi(self, config):
        raise NotImplementedError

    def open_i2c(self, config):
        raise NotImplementedError

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakeProvider(AdapterProvider):
    _backend_id: str
    descriptors: list[AdapterDescriptor]
    available: bool = True

    @property
    def backend_id(self) -> str:
        return self._backend_id

    def is_available(self) -> bool:
        return self.available

    def enumerate(self):
        return list(self.descriptors)

    def open(self, identity: AdapterIdentity) -> AdapterHandle:
        for descriptor in self.descriptors:
            if descriptor.identity == identity:
                return _FakeHandle(descriptor)
        raise AssertionError("registry must resolve identity before provider.open")


def _ft2232_descriptor(channel: str) -> AdapterDescriptor:
    return AdapterDescriptor(
        identity=AdapterIdentity("pyftdi", "FT9ABC12", channel),
        device_family="FT2232H",
        display_name=f"FT2232H FT9ABC12 channel {channel}",
        capabilities=AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI, TransactionProtocol.I2C}),
            channel_count=2,
            concurrent_channels=True,
            spi=SpiCapabilities(
                modes=frozenset({0, 1, 2, 3}),
                min_frequency_hz=1_000,
                max_frequency_hz=30_000_000,
                full_duplex=True,
                chip_select_count=5,
                cs_hold=True,
            ),
            i2c=I2cCapabilities(
                min_frequency_hz=10_000,
                max_frequency_hz=1_000_000,
                seven_bit_address=True,
                repeated_start=True,
                clock_stretching=False,
            ),
        ),
    )


def _ch347_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        identity=AdapterIdentity("ch347", "CH347-001"),
        device_family="CH347",
        display_name="CH347-001",
        capabilities=AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI, TransactionProtocol.I2C}),
            spi=SpiCapabilities(
                modes=frozenset({0, 1, 2, 3}),
                min_frequency_hz=1_000,
                max_frequency_hz=60_000_000,
                chip_select_count=2,
            ),
            i2c=I2cCapabilities(
                min_frequency_hz=10_000,
                max_frequency_hz=1_000_000,
                seven_bit_address=True,
                repeated_start=True,
            ),
        ),
    )


def _mcp2210_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        identity=AdapterIdentity("mcp2210", "MCP-001"),
        device_family="MCP2210",
        display_name="MCP2210 MCP-001",
        capabilities=AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI}),
            spi=SpiCapabilities(
                modes=frozenset({0, 1, 2, 3}),
                min_frequency_hz=1_500,
                max_frequency_hz=12_000_000,
                chip_select_count=9,
            ),
        ),
    )


def test_registry_supports_ft2232h_channel_identity_without_vendor_special_case():
    provider = _FakeProvider("pyftdi", [_ft2232_descriptor("A"), _ft2232_descriptor("B")])
    registry = AdapterBackendRegistry([provider])

    descriptors = registry.enumerate()

    assert [item.identity.channel_id for item in descriptors] == ["A", "B"]
    assert registry.resolve(AdapterIdentity("pyftdi", "FT9ABC12", "B")) == descriptors[1]
    assert descriptors[0].capabilities.concurrent_channels is True


def test_registry_can_hold_ftdi_ch347_and_mcp2210_together():
    registry = AdapterBackendRegistry(
        [
            _FakeProvider("pyftdi", [_ft2232_descriptor("A")]),
            _FakeProvider("ch347", [_ch347_descriptor()]),
            _FakeProvider("mcp2210", [_mcp2210_descriptor()]),
        ]
    )

    assert registry.backend_ids() == ("ch347", "mcp2210", "pyftdi")
    assert {item.device_family for item in registry.enumerate()} == {
        "FT2232H",
        "CH347",
        "MCP2210",
    }


def test_mcp2210_spi_only_capability_rejects_i2c_without_chip_specific_branch():
    descriptor = _mcp2210_descriptor()

    AdapterBackendRegistry.validate_spi(
        descriptor,
        SpiConfig(frequency_hz=1_000_000, mode=3, chip_select=8),
    )

    with pytest.raises(UnsupportedCapabilityError, match="does not support I2C"):
        AdapterBackendRegistry.validate_i2c(
            descriptor,
            I2cConfig(frequency_hz=100_000, address=0x50),
        )


def test_capability_validation_rejects_backend_specific_limits():
    ft2232 = _ft2232_descriptor("A")

    with pytest.raises(ProtocolConfigurationError, match="outside adapter range"):
        AdapterBackendRegistry.validate_spi(
            ft2232,
            SpiConfig(frequency_hz=40_000_000),
        )

    with pytest.raises(UnsupportedCapabilityError, match="clock stretching"):
        AdapterBackendRegistry.validate_i2c(
            ft2232,
            I2cConfig(
                frequency_hz=100_000,
                address=0x50,
                clock_stretching=True,
            ),
        )


def test_unavailable_optional_provider_does_not_break_enumeration():
    registry = AdapterBackendRegistry(
        [
            _FakeProvider("pyftdi", [_ft2232_descriptor("A")]),
            _FakeProvider("ch347", [_ch347_descriptor()], available=False),
        ]
    )

    assert [item.device_family for item in registry.enumerate()] == ["FT2232H"]

    with pytest.raises(BackendUnavailableError, match="unavailable"):
        registry.provider_for("ch347")


def test_duplicate_backend_id_is_rejected():
    with pytest.raises(ValueError, match="duplicate adapter backend_id"):
        AdapterBackendRegistry(
            [
                _FakeProvider("pyftdi", []),
                _FakeProvider("pyftdi", []),
            ]
        )
