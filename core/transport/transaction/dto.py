"""Vendor-neutral SPI/I2C adapter and transaction DTOs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Optional

from core.transport.transaction.errors import ProtocolConfigurationError


class TransactionProtocol(str, Enum):
    SPI = "SPI"
    I2C = "I2C"


@dataclass(frozen=True)
class AdapterIdentity:
    """Adapter selector.

    가능한 경우 serial number처럼 재연결 후에도 유지되는 stable identity를 사용합니다.
    ``AdapterDescriptor.identity_persistent``가 False이면 backend가 USB topology 등 임시
    locator를 fallback으로 사용했다는 뜻입니다.
    """

    backend_id: str
    stable_id: str
    channel_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.backend_id.strip():
            raise ValueError("backend_id must not be empty")
        if not self.stable_id.strip():
            raise ValueError("stable_id must not be empty")


@dataclass(frozen=True)
class SpiCapabilities:
    modes: FrozenSet[int] = field(default_factory=lambda: frozenset({0, 1, 2, 3}))
    bit_orders: FrozenSet[str] = field(default_factory=lambda: frozenset({"msb"}))
    min_frequency_hz: int = 1
    max_frequency_hz: int = 1
    full_duplex: bool = True
    chip_select_count: int = 1
    cs_hold: bool = False

    def __post_init__(self) -> None:
        if not self.modes or any(mode not in {0, 1, 2, 3} for mode in self.modes):
            raise ValueError("SPI modes must be a non-empty subset of {0,1,2,3}")
        if not self.bit_orders or not self.bit_orders.issubset({"msb", "lsb"}):
            raise ValueError("SPI bit_orders must be a non-empty subset of {'msb','lsb'}")
        if self.min_frequency_hz <= 0 or self.max_frequency_hz < self.min_frequency_hz:
            raise ValueError("invalid SPI frequency range")
        if self.chip_select_count <= 0:
            raise ValueError("chip_select_count must be positive")


@dataclass(frozen=True)
class I2cCapabilities:
    min_frequency_hz: int = 1
    max_frequency_hz: int = 1
    seven_bit_address: bool = True
    ten_bit_address: bool = False
    repeated_start: bool = True
    clock_stretching: bool = False

    def __post_init__(self) -> None:
        if self.min_frequency_hz <= 0 or self.max_frequency_hz < self.min_frequency_hz:
            raise ValueError("invalid I2C frequency range")


@dataclass(frozen=True)
class AdapterCapabilities:
    protocols: FrozenSet[TransactionProtocol]
    channel_count: int = 1
    concurrent_channels: bool = False
    spi: Optional[SpiCapabilities] = None
    i2c: Optional[I2cCapabilities] = None

    def __post_init__(self) -> None:
        if self.channel_count <= 0:
            raise ValueError("channel_count must be positive")
        if TransactionProtocol.SPI in self.protocols and self.spi is None:
            raise ValueError("SPI protocol requires SpiCapabilities")
        if TransactionProtocol.I2C in self.protocols and self.i2c is None:
            raise ValueError("I2C protocol requires I2cCapabilities")
        if TransactionProtocol.SPI not in self.protocols and self.spi is not None:
            raise ValueError("SpiCapabilities requires SPI protocol")
        if TransactionProtocol.I2C not in self.protocols and self.i2c is not None:
            raise ValueError("I2cCapabilities requires I2C protocol")

    def supports(self, protocol: TransactionProtocol) -> bool:
        return protocol in self.protocols


@dataclass(frozen=True)
class AdapterDescriptor:
    identity: AdapterIdentity
    device_family: str
    display_name: str
    capabilities: AdapterCapabilities
    identity_persistent: bool = True

    def __post_init__(self) -> None:
        if not self.device_family.strip():
            raise ValueError("device_family must not be empty")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")


@dataclass(frozen=True)
class SpiConfig:
    frequency_hz: int
    mode: int = 0
    chip_select: int = 0
    bit_order: str = "msb"
    full_duplex: bool = True

    def __post_init__(self) -> None:
        if self.frequency_hz <= 0:
            raise ProtocolConfigurationError("SPI frequency_hz must be positive")
        if self.mode not in {0, 1, 2, 3}:
            raise ProtocolConfigurationError("SPI mode must be 0..3")
        if self.chip_select < 0:
            raise ProtocolConfigurationError("SPI chip_select must be >= 0")
        if self.bit_order not in {"msb", "lsb"}:
            raise ProtocolConfigurationError("SPI bit_order must be 'msb' or 'lsb'")


@dataclass(frozen=True)
class I2cConfig:
    frequency_hz: int
    address: int
    address_bits: int = 7
    clock_stretching: bool = False

    def __post_init__(self) -> None:
        if self.frequency_hz <= 0:
            raise ProtocolConfigurationError("I2C frequency_hz must be positive")
        if self.address_bits not in {7, 10}:
            raise ProtocolConfigurationError("I2C address_bits must be 7 or 10")
        max_address = 0x7F if self.address_bits == 7 else 0x3FF
        if not 0 <= self.address <= max_address:
            raise ProtocolConfigurationError(
                f"I2C address must be within 0..0x{max_address:X}"
            )


@dataclass(frozen=True)
class SpiTransactionRequest:
    tx_data: bytes = b""
    rx_length: int = 0
    keep_cs_asserted: bool = False

    def __post_init__(self) -> None:
        if self.rx_length < 0:
            raise ProtocolConfigurationError("SPI rx_length must be >= 0")
        if not self.tx_data and self.rx_length == 0:
            raise ProtocolConfigurationError("SPI transaction must read or write data")


@dataclass(frozen=True)
class SpiTransactionResult:
    rx_data: bytes
    actual_frequency_hz: int


@dataclass(frozen=True)
class I2cTransactionRequest:
    write_data: bytes = b""
    read_length: int = 0
    repeated_start: bool = True

    def __post_init__(self) -> None:
        if self.read_length < 0:
            raise ProtocolConfigurationError("I2C read_length must be >= 0")
        if not self.write_data and self.read_length == 0:
            raise ProtocolConfigurationError("I2C transaction must read or write data")


@dataclass(frozen=True)
class I2cTransactionResult:
    read_data: bytes
    actual_frequency_hz: int
