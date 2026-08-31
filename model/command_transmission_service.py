"""
명령 전송 애플리케이션 서비스

Manual/Macro Presenter가 중복으로 수행하던 명령 가공, Prefix/Suffix 적용,
단일/브로드캐스트 대상 검증, 실제 전송 결과 판정을 한 곳에 모읍니다.

## WHY
* Presenter마다 같은 전송 규칙을 복제하면 한 경로만 수정되어 동작이 달라질 수 있습니다.
* Presenter는 사용자 의도와 표시 정책을 담당하고, 전송 유스케이스는 UI와 분리되어야 합니다.
* 매크로 스레드에서도 호출되므로 QWidget/Qt UI 객체에 의존하지 않습니다.
* Serial/SPI/I2C Manual Control이 같은 입력 규칙을 사용해야 Protocol별 payload 해석 차이를 방지할 수 있습니다.

## HOW
* SettingsManager와 ConnectionController를 생성자 주입받습니다.
* prepare()는 ManualCommand를 실제 bytes로만 변환하며 transport에는 쓰지 않습니다.
* send()는 prepare() 결과를 단일 Serial 포트 또는 브로드캐스트로 전송합니다.
* 실패는 TransmissionErrorCode와 기술 메시지로 반환하고 UI 문구는 Presenter가 결정합니다.
"""
from dataclasses import dataclass
from typing import Optional

from common.constants import ConfigKeys
from common.dtos import ManualCommand
from common.enums import TransmissionErrorCode
from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from model.connection_controller import ConnectionController


@dataclass(frozen=True)
class TransmissionResult:
    """명령 전송 유스케이스의 UI 비의존 결과."""

    success: bool
    data: bytes = b""
    message: str = ""
    error_code: Optional[TransmissionErrorCode] = None


class CommandTransmissionService:
    """Manual/Macro 공용 명령 가공 및 Serial 전송 서비스."""

    def __init__(
        self,
        connection_controller: ConnectionController,
        settings_manager: SettingsManager,
    ) -> None:
        self._connection_controller = connection_controller
        self._settings_manager = settings_manager

    def prepare(self, command: ManualCommand) -> TransmissionResult:
        """ManualCommand를 transport-independent payload bytes로 변환합니다.

        Serial/SPI/I2C가 ASCII/HEX, Prefix/Suffix 규칙을 공유하기 위한 공통 경계입니다.
        이 메서드는 실제 I/O를 수행하지 않습니다.
        """
        return self._process_command(command)

    def send(
        self,
        command: ManualCommand,
        active_port: Optional[str] = None,
    ) -> TransmissionResult:
        """명령을 가공한 뒤 단일 Serial 포트 또는 브로드캐스트로 전송합니다."""
        processed = self.prepare(command)
        if not processed.success:
            return processed

        data = processed.data
        if not data:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.EMPTY_DATA,
                message="Command produced no data.",
            )

        if command.broadcast_enabled:
            return self._send_broadcast(data)
        return self._send_single(active_port, data)

    def _process_command(self, command: ManualCommand) -> TransmissionResult:
        prefix = (
            self._settings_manager.get(ConfigKeys.COMMAND_PREFIX)
            if command.prefix_enabled
            else None
        )
        suffix = (
            self._settings_manager.get(ConfigKeys.COMMAND_SUFFIX)
            if command.suffix_enabled
            else None
        )

        try:
            data = CommandProcessor.process_command(
                command.command,
                command.hex_mode,
                prefix=prefix,
                suffix=suffix,
            )
        except ValueError as exc:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.INVALID_COMMAND,
                message=f"Command processing error: {exc}",
            )

        return TransmissionResult(success=True, data=data)

    def _send_broadcast(self, data: bytes) -> TransmissionResult:
        if not self._connection_controller.has_active_broadcast_ports():
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.NO_BROADCAST_TARGET,
                message="No active ports available for broadcast.",
            )

        if not self._connection_controller.send_broadcast_data(data):
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.BROADCAST_SEND_FAILED,
                message="Broadcast send failed on one or more ports.",
            )

        return TransmissionResult(success=True, data=data)

    def _send_single(self, active_port: Optional[str], data: bytes) -> TransmissionResult:
        if not active_port:
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.NO_ACTIVE_PORT,
                message="No port selected.",
            )

        if not self._connection_controller.is_connection_open(active_port):
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.PORT_NOT_OPEN,
                message=f"Port '{active_port}' is disconnected.",
            )

        if not self._connection_controller.send_data(active_port, data):
            return TransmissionResult(
                success=False,
                error_code=TransmissionErrorCode.SEND_FAILED,
                message=f"Send failed on port '{active_port}'.",
            )

        return TransmissionResult(success=True, data=data)
