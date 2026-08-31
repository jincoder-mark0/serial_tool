"""Adapter backend registry and capability validation."""
from __future__ import annotations

from typing import Dict, Iterable, List

from core.transport.transaction.contracts import AdapterHandle, AdapterProvider
from core.transport.transaction.dto import (
    AdapterDescriptor,
    AdapterIdentity,
    I2cConfig,
    SpiConfig,
    TransactionProtocol,
)
from core.transport.transaction.errors import (
    AdapterNotFoundError,
    BackendUnavailableError,
    ProtocolConfigurationError,
    UnsupportedCapabilityError,
)


class AdapterBackendRegistry:
    """Composition Root가 소유하는 optional transaction backend registry."""

    def __init__(self, providers: Iterable[AdapterProvider] = ()) -> None:
        self._providers: Dict[str, AdapterProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: AdapterProvider) -> None:
        backend_id = provider.backend_id.strip()
        if not backend_id:
            raise ValueError("provider backend_id must not be empty")
        if backend_id in self._providers:
            raise ValueError(f"duplicate adapter backend_id: {backend_id}")
        self._providers[backend_id] = provider

    def backend_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def enumerate(self) -> List[AdapterDescriptor]:
        """Available provider만 열거하며 missing optional backend는 전체 앱을 막지 않는다."""
        descriptors: List[AdapterDescriptor] = []
        for provider in self._providers.values():
            if provider.is_available():
                descriptors.extend(provider.enumerate())
        return descriptors

    def provider_for(self, backend_id: str) -> AdapterProvider:
        provider = self._providers.get(backend_id)
        if provider is None:
            raise BackendUnavailableError(f"adapter backend is not registered: {backend_id}")
        if not provider.is_available():
            raise BackendUnavailableError(f"adapter backend is unavailable: {backend_id}")
        return provider

    def resolve(self, identity: AdapterIdentity) -> AdapterDescriptor:
        provider = self.provider_for(identity.backend_id)
        for descriptor in provider.enumerate():
            if descriptor.identity == identity:
                return descriptor
        raise AdapterNotFoundError(
            f"adapter not found: {identity.backend_id}/{identity.stable_id}"
            + (f"/{identity.channel_id}" if identity.channel_id else "")
        )

    def open(self, identity: AdapterIdentity) -> AdapterHandle:
        self.resolve(identity)
        return self.provider_for(identity.backend_id).open(identity)

    @staticmethod
    def validate_spi(descriptor: AdapterDescriptor, config: SpiConfig) -> None:
        caps = descriptor.capabilities
        if not caps.supports(TransactionProtocol.SPI) or caps.spi is None:
            raise UnsupportedCapabilityError(
                f"{descriptor.display_name} does not support SPI"
            )
        spi = caps.spi
        if config.mode not in spi.modes:
            raise UnsupportedCapabilityError(
                f"SPI mode {config.mode} is not supported by {descriptor.display_name}"
            )
        if config.bit_order not in spi.bit_orders:
            raise UnsupportedCapabilityError(
                f"SPI bit order {config.bit_order} is not supported by "
                f"{descriptor.display_name}"
            )
        if not spi.min_frequency_hz <= config.frequency_hz <= spi.max_frequency_hz:
            raise ProtocolConfigurationError(
                f"SPI frequency {config.frequency_hz} Hz is outside adapter range "
                f"{spi.min_frequency_hz}..{spi.max_frequency_hz} Hz"
            )
        if config.chip_select >= spi.chip_select_count:
            raise ProtocolConfigurationError(
                f"SPI chip_select {config.chip_select} exceeds available range "
                f"0..{spi.chip_select_count - 1}"
            )
        if config.full_duplex and not spi.full_duplex:
            raise UnsupportedCapabilityError(
                f"{descriptor.display_name} does not support full-duplex SPI"
            )

    @staticmethod
    def validate_i2c(descriptor: AdapterDescriptor, config: I2cConfig) -> None:
        caps = descriptor.capabilities
        if not caps.supports(TransactionProtocol.I2C) or caps.i2c is None:
            raise UnsupportedCapabilityError(
                f"{descriptor.display_name} does not support I2C"
            )
        i2c = caps.i2c
        if not i2c.min_frequency_hz <= config.frequency_hz <= i2c.max_frequency_hz:
            raise ProtocolConfigurationError(
                f"I2C frequency {config.frequency_hz} Hz is outside adapter range "
                f"{i2c.min_frequency_hz}..{i2c.max_frequency_hz} Hz"
            )
        if config.address_bits == 7 and not i2c.seven_bit_address:
            raise UnsupportedCapabilityError("adapter does not support 7-bit I2C address")
        if config.address_bits == 10 and not i2c.ten_bit_address:
            raise UnsupportedCapabilityError("adapter does not support 10-bit I2C address")
        if config.clock_stretching and not i2c.clock_stretching:
            raise UnsupportedCapabilityError(
                f"{descriptor.display_name} does not support requested I2C clock stretching"
            )
