"""SPI/I2C transaction connection config와 legacy PortConfig migration boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from common.dtos import PortConfig
from common.enums import ConnectionProtocol
from core.transport.transaction.dto import (
    AdapterIdentity,
    I2cConfig,
    SpiConfig,
    TransactionProtocol,
)
from core.transport.transaction.errors import ProtocolConfigurationError


@dataclass(frozen=True)
class TransactionConnectionConfig:
    """Vendor-neutral SPI/I2C connection config.

    기존 ``PortConfig``와 달리 protocol-specific field를 한 DTO에 섞지 않습니다.
    Adapter selector 역시 protocol field와 분리해 backend/chip 추가 시 DTO가 비대해지는
    것을 막습니다.
    """

    name: str
    protocol: TransactionProtocol
    adapter: AdapterIdentity
    spi: Optional[SpiConfig] = None
    i2c: Optional[I2cConfig] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ProtocolConfigurationError("transaction connection name must not be empty")

        if self.protocol is TransactionProtocol.SPI:
            if self.spi is None or self.i2c is not None:
                raise ProtocolConfigurationError(
                    "SPI connection requires spi config and must not include i2c config"
                )
            return

        if self.protocol is TransactionProtocol.I2C:
            if self.i2c is None or self.spi is not None:
                raise ProtocolConfigurationError(
                    "I2C connection requires i2c config and must not include spi config"
                )
            return

        raise ProtocolConfigurationError(f"unsupported transaction protocol: {self.protocol}")


class LegacyPortConfigAdapter:
    """기존 ``PortConfig``에서 새 transaction config로 넘어가는 명시적 경계.

    WHY:
    기존 저장 데이터에는 adapter backend/stable identity/channel 정보가 없습니다.
    따라서 FTDI/CH347/MCP2210 identity를 추측해서 자동 이관하면 잘못된 hardware를
    열 위험이 있습니다. Legacy SPI의 speed/mode만 재사용하고 adapter identity는
    사용자가 새 UI에서 선택한 값을 반드시 주입받습니다.
    """

    @staticmethod
    def to_spi_connection(
        legacy: PortConfig,
        adapter: AdapterIdentity,
        *,
        chip_select: int = 0,
        name: Optional[str] = None,
    ) -> TransactionConnectionConfig:
        if legacy.protocol != ConnectionProtocol.SPI:
            raise ProtocolConfigurationError(
                "legacy PortConfig must use SPI protocol for SPI migration"
            )

        connection_name = (name or legacy.port or adapter.stable_id).strip()
        return TransactionConnectionConfig(
            name=connection_name,
            protocol=TransactionProtocol.SPI,
            adapter=adapter,
            spi=SpiConfig(
                frequency_hz=int(legacy.speed),
                mode=int(legacy.mode),
                chip_select=chip_select,
            ),
        )
