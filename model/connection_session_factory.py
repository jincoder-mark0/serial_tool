"""
연결 세션 팩토리.

PortConfig를 구체 Transport와 ConnectionWorker로 조립하는 책임을 ConnectionController에서
분리합니다. Controller는 생성 규칙을 모르고 생성된 worker의 생명주기와 registry만 관리합니다.
"""
from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from core.transport.loopback_transport import LoopbackTransport
from core.transport.serial_transport import SerialTransport
from model.connection_worker import ConnectionWorker


class ConnectionSessionFactory:
    """PortConfig에 맞는 Transport/ConnectionWorker 조립 규칙을 소유합니다."""

    def create_worker(self, config: PortConfig) -> ConnectionWorker:
        """포트 종류에 맞는 transport를 선택하고 worker를 생성합니다."""
        transport = (
            LoopbackTransport(config)
            if config.port == LOOPBACK_PORT_NAME
            else SerialTransport(config)
        )
        return ConnectionWorker(transport, config.port)
