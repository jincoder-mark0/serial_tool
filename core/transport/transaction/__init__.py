"""Vendor-neutral SPI/I2C transaction transport contracts.

실제 PyFtdi/CH347/MCP2210 backend는 이 package의 contract를 구현하며,
상위 계층은 vendor library를 직접 import하지 않습니다.
"""

from core.transport.transaction.config import (
    LegacyPortConfigAdapter,
    TransactionConnectionConfig,
)
from core.transport.transaction.contracts import (
    AdapterHandle,
    AdapterProvider,
    I2cController,
    SpiController,
)
from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.dto import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterIdentity,
    I2cCapabilities,
    I2cConfig,
    I2cTransactionRequest,
    I2cTransactionResult,
    SpiCapabilities,
    SpiConfig,
    SpiTransactionRequest,
    SpiTransactionResult,
    TransactionProtocol,
)
from core.transport.transaction.registry import AdapterBackendRegistry

__all__ = [
    "AdapterBackendRegistry",
    "AdapterCapabilities",
    "AdapterDescriptor",
    "AdapterHandle",
    "AdapterIdentity",
    "AdapterProvider",
    "CancellationToken",
    "I2cCapabilities",
    "I2cConfig",
    "I2cController",
    "I2cTransactionRequest",
    "I2cTransactionResult",
    "LegacyPortConfigAdapter",
    "SpiCapabilities",
    "SpiConfig",
    "SpiController",
    "SpiTransactionRequest",
    "SpiTransactionResult",
    "TransactionConnectionConfig",
    "TransactionOptions",
    "TransactionProtocol",
]
