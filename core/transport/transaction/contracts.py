"""Abstract contracts for vendor-neutral transaction adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.dto import (
    AdapterDescriptor,
    AdapterIdentity,
    I2cConfig,
    I2cTransactionRequest,
    I2cTransactionResult,
    SpiConfig,
    SpiTransactionRequest,
    SpiTransactionResult,
)


class SpiController(ABC):
    """Opened SPI protocol controller bound to one adapter/channel."""

    @abstractmethod
    def transact(
        self,
        request: SpiTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> SpiTransactionResult:
        """Execute one SPI transaction with common timeout/cancellation policy."""

    @abstractmethod
    def close(self) -> None:
        """Release protocol-specific resources."""


class I2cController(ABC):
    """Opened I2C protocol controller bound to one adapter/channel."""

    @abstractmethod
    def transact(
        self,
        request: I2cTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> I2cTransactionResult:
        """Execute one I2C transaction with common timeout/cancellation policy."""

    @abstractmethod
    def close(self) -> None:
        """Release protocol-specific resources."""


class AdapterHandle(ABC):
    """Lifecycle owner for one physical adapter/channel selection."""

    @property
    @abstractmethod
    def descriptor(self) -> AdapterDescriptor:
        """Resolved descriptor for this opened adapter handle."""

    @abstractmethod
    def open_spi(self, config: SpiConfig) -> SpiController:
        """Open SPI protocol controller for this handle."""

    @abstractmethod
    def open_i2c(self, config: I2cConfig) -> I2cController:
        """Open I2C protocol controller for this handle."""

    @abstractmethod
    def close(self) -> None:
        """Release physical adapter/channel resources."""


class AdapterProvider(ABC):
    """Discovery/factory boundary implemented by each optional backend."""

    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Stable backend identifier, e.g. pyftdi/ch347/mcp2210."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether optional package/DLL/driver prerequisites are available."""

    @abstractmethod
    def enumerate(self) -> Sequence[AdapterDescriptor]:
        """Discover adapters without leaking vendor-native objects."""

    @abstractmethod
    def open(self, identity: AdapterIdentity) -> AdapterHandle:
        """Open the requested stable adapter/channel identity."""
