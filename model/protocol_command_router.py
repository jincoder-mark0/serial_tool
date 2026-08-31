"""Protocol-independent command delivery router.

## WHY
* Manual/Auto Tx/Macro/Broadcast가 각각 Serial/SPI/I2C 분기를 복제하지 않도록 함
* ASCII/HEX + Prefix/Suffix payload 생성과 실제 bus delivery 책임을 분리
* View/QWidget를 worker thread에 전달하지 않고 immutable target snapshot만 사용

## HOW
* CommandTransmissionService.prepare()로 payload bytes를 한 번 생성
* Serial은 기존 ConnectionController queue/broadcast policy를 그대로 사용
* SPI/I2C는 TransactionManager session queue로 request를 전달
* enqueue 성공을 delivery 성공으로 반환하고 실제 bus 완료/실패는 TransactionManager signal이 담당
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from common.dtos import ManualCommand
from common.enums import ConnectionProtocol, TransmissionErrorCode
from core.transport.transaction.dto import (
    I2cTransactionRequest,
    SpiTransactionRequest,
    TransactionProtocol,
)
from model.command_transmission_service import CommandTransmissionService, TransmissionResult
from model.connection_controller import ConnectionController
from model.transaction_manager import TransactionManager


@dataclass(frozen=True)
class ProtocolCommandTarget:
    """UI와 분리된 전송 대상 snapshot."""

    name: str
    protocol: str


@dataclass(frozen=True)
class ProtocolCommandOptions:
    """Protocol별 Manual/Macro bus option."""

    keep_cs: bool = False
    repeated_start: bool = True


class ProtocolCommandRouter:
    """공통 payload를 현재 target의 transport semantics로 전달합니다."""

    def __init__(
        self,
        connection_controller: ConnectionController,
        transaction_manager: TransactionManager,
        transmission_service: CommandTransmissionService,
    ) -> None:
        self._connection_controller = connection_controller
        self._transaction_manager = transaction_manager
        self._transmission_service = transmission_service

    def send(
        self,
        command: ManualCommand,
        target: ProtocolCommandTarget,
        *,
        options: ProtocolCommandOptions | None = None,
    ) -> TransmissionResult:
        """단일 target으로 command를 전달합니다."""
        command = replace(command, broadcast_enabled=False)
        if target.protocol == ConnectionProtocol.SERIAL:
            return self._transmission_service.send(command, active_port=target.name)

        prepared = self._transmission_service.prepare(command)
        if not prepared.success or not prepared.data:
            return prepared

        return self._send_transaction_payload(
            target,
            prepared.data,
            options or ProtocolCommandOptions(),
        )

    def broadcast(
        self,
        command: ManualCommand,
        transaction_targets: Iterable[ProtocolCommandTarget],
        *,
        options: ProtocolCommandOptions | None = None,
    ) -> TransmissionResult:
        """Serial broadcast policy + 연결된 SPI/I2C targets에 동일 payload를 전달합니다."""
        prepared = self._transmission_service.prepare(command)
        if not prepared.success or not prepared.data:
            return prepared

        payload = prepared.data
        delivered = 0
        failures: list[str] = []

        # Serial은 기존 worker.broadcast_enabled() 정책을 그대로 존중합니다.
        if self._connection_controller.has_active_broadcast_ports():
            if self._connection_controller.send_broadcast_data(payload):
                delivered += 1
            else:
                failures.append("Serial broadcast")

        resolved_options = options or ProtocolCommandOptions()
        for target in transaction_targets:
            result = self._send_transaction_payload(target, payload, resolved_options)
            if result.success:
                delivered += 1
            else:
                failures.append(target.name)

        if delivered == 0:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.NO_BROADCAST_TARGET,
                message="No active Serial/SPI/I2C broadcast target.",
            )
        if failures:
            return TransmissionResult(
                success=False,
                data=payload,
                error_code=TransmissionErrorCode.BROADCAST_SEND_FAILED,
                message=f"Broadcast failed for: {', '.join(failures)}",
            )
        return TransmissionResult(success=True, data=payload)

    def _send_transaction_payload(
        self,
        target: ProtocolCommandTarget,
        payload: bytes,
        options: ProtocolCommandOptions,
    ) -> TransmissionResult:
        if target.protocol == TransactionProtocol.SPI.value:
            request = SpiTransactionRequest(
                tx_data=payload,
                rx_length=len(payload),
                keep_cs_asserted=options.keep_cs,
            )
        elif target.protocol == TransactionProtocol.I2C.value:
            request = I2cTransactionRequest(
                write_data=payload,
                read_length=0,
                repeated_start=options.repeated_start,
            )
        else:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.SEND_FAILED,
                message=f"Unsupported protocol: {target.protocol}",
            )

        request_id = self._transaction_manager.execute(target.name, request)
        if request_id is None:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.SEND_FAILED,
                message=f"Transaction session is not ready: {target.name}",
            )
        return TransmissionResult(success=True, data=payload)
