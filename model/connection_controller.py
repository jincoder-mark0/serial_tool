"""
연결 컨트롤러 모듈

개별 연결 세션의 생명주기와 데이터 흐름을 제어합니다.

## WHY
* 단일 연결에 대한 상태 관리 및 로직 캡슐화 필요
* 하드웨어(Worker)와 UI(Presenter) 사이의 중재자 역할
* 데이터 파싱 및 이벤트 전파의 중심점

## WHAT
* 연결 열기/닫기(Open/Close) 관리
* Worker 스레드 관리 및 Transport 주입
* 패킷 파싱(Parser) 연결 및 데이터 브로드캐스팅
* 파일 전송 엔진 등록 및 관리

## HOW
* BaseTransport 구현체를 생성하여 ConnectionWorker에 주입
* PyQt Signal 및 EventBus를 통한 비동기 이벤트 전파
"""
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from model.connection_worker import ConnectionWorker
from core.transport.serial_transport import SerialTransport
from model.packet_parser import ParserFactory, PacketParser
from common.enums import ParserType
from common.dtos import (
    PortConfig, PortDataEvent, PortErrorEvent,
    PacketEvent, PortConnectionEvent # [New]
)from common.constants import DEFAULT_BAUDRATE, EventTopics
from core.event_bus import event_bus
from core.logger import logger

if TYPE_CHECKING:
    from model.file_transfer_service import FileTransferService

class ConnectionController(QObject):
    """
    개별 연결 세션 관리 클래스

    하나의 물리적/논리적 연결에 대한 Worker, Parser, 설정을 총괄합니다.
    특정 탭의 활성 상태를 저장하지 않으며, 메서드 호출 시 대상 포트를 인자로 받습니다.
    """
    # 시그널 정의
    connection_opened = pyqtSignal(object)
    connection_closed = pyqtSignal(object)

    error_occurred = pyqtSignal(object)
    data_received = pyqtSignal(object)
    data_sent = pyqtSignal(object)
    packet_received = pyqtSignal(object)

    def __init__(self) -> None:
        """
        ConnectionController 초기화

        Logic:
            - Worker/Parser 저장소 초기화
            - Signal -> EventBus 자동 중계 연결
            - _active_connection_name 초기화
        """
        super().__init__()
        # 연결 이름(str) -> ConnectionWorker 매핑
        self.workers: dict[str, ConnectionWorker] = {}
        # 연결 이름(str) -> PacketParser 매핑
        self.parsers: dict[str, PacketParser] = {}
        # 연결 이름(str) -> Config(dict) 매핑
        self.connection_configs: dict[str, PortConfig] = {}

        # 진행 중인 파일 전송 엔진 추적 (Race Condition 방지)
        # 연결 이름(str) -> FileTransferService 매핑
        self._active_file_transfers: Dict[str, 'FileTransferService'] = {}

        # EventBus 인스턴스
        self.event_bus = event_bus

        # Signal -> EventBus 자동 연결
        self._connect_signals_to_eventbus()

    def _connect_signals_to_eventbus(self) -> None:
        """Signal -> EventBus (DTO 발행)"""
        self.connection_opened.connect(lambda e: self.event_bus.publish(EventTopics.PORT_OPENED, e))
        self.connection_closed.connect(lambda e: self.event_bus.publish(EventTopics.PORT_CLOSED, e))

        self.error_occurred.connect(lambda e: self.event_bus.publish(EventTopics.PORT_ERROR, e))
        self.data_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_RECEIVED, e))
        self.data_sent.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_SENT, e))
        self.packet_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_PACKET_RECEIVED, e))

    # -------------------------------------------------------------------------
    # File Transfer Lifecycle Management (Race Condition Prevention)
    # -------------------------------------------------------------------------
    def register_file_transfer(self, port_name: str, file_transfer_service: 'FileTransferService') -> None:
        """
        파일 전송 시작 시 엔진을 등록합니다.

        Args:
            port_name: 포트 이름
            file_transfer_service: 실행 중인 FileTransferService 인스턴스
        """
        self._active_file_transfers[port_name] = file_transfer_service
        logger.debug(f"File transfer registered for port {port_name}")

    def unregister_file_transfer(self, port_name: str) -> None:
        """
        파일 전송 종료 시 엔진 등록을 해제합니다.

        Args:
            port_name: 포트 이름
        """
        if port_name in self._active_file_transfers:
            del self._active_file_transfers[port_name]
            logger.debug(f"File transfer unregistered for port {port_name}")

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    @property
    def has_active_connection(self) -> bool:
        """
        하나라도 활성화된 연결이 있는지 확인
        """
        return len(self.workers) > 0

    def get_active_connections(self) -> List[str]:
        """
        현재 활성화된 모든 연결의 이름을 반환합니다.

        Returns:
            List[str]: 연결 이름 리스트
        """
        return list(self.workers.keys())

    def is_connection_open(self, name: str) -> bool:
        """
        특정 연결이 열려있는지 확인

        Args:
            name: 확인할 연결 이름

        Returns:
            bool: 연결이 열려있고 Worker가 실행 중이면 True
        """
        worker = self.workers.get(name)
        return worker is not None and worker.isRunning()

    def get_connection_config(self, name: str) -> Optional[PortConfig]:
        """
        특정 연결의 설정 정보를 반환

        Args:
            name: 확인할 연결 이름

        Returns:
            Optional[PortConfig]: 설정 정보
        """
        return self.connection_configs.get(name)

    def get_write_queue_size(self, name: str) -> int:
        """
        특정 연결의 전송 대기 큐 크기 반환

        Args:
            name: 확인할 연결 이름

        Returns:
            int: 대기 중인 청크 개수 (포트가 없으면 0)
        """
        worker = self.workers.get(name)
        if worker:
            return worker.get_write_queue_size()
        return 0

    def open_connection(self, config: PortConfig) -> bool:
        """
        새로운 연결을 엽니다.

        Logic:
            - 필수 설정 확인
            - 중복 연결 방지
            - BaseTransport 생성
            - ConnectionWorker 생성 및 의존성 주입
            - Parser 설정 및 생성
            - Worker 시작

        Args:
            config (PortConfig): 연결 설정 정보

        Returns:
            bool: 시작 성공 여부
        """
        name = config.port
        if not name:
            self._emit_error("", "Connection name(port) is required.")
            return False

        # 중복 열기 방지
        if self.is_connection_open(name):
            self._emit_error(name, "Connection is already open.")
            return False

        # DTO를 직접 SerialTransport에 전달
        transport = SerialTransport(config)

        # Worker에 Transport 주입
        worker = ConnectionWorker(transport, name)

        # Parser 생성 (기본 Raw)
        self.parsers[name] = ParserFactory.create_parser(ParserType.RAW)
        self.connection_configs[name] = config

        # Worker signals -> Controller signals (Wrap in DTO)
        worker.connection_opened.connect(
            lambda n=name: self.connection_opened.emit(PortConnectionEvent(port=n, state="opened"))
        )
        worker.connection_closed.connect(
            lambda n=name: self.connection_closed.emit(PortConnectionEvent(port=n, state="closed"))
        )

        # Wrap worker signals in DTOs
        worker.error_occurred.connect(lambda msg, n=name: self._emit_error(n, msg))
        worker.data_received.connect(lambda data, n=name: self._handle_data_received(n, data))

        self.workers[name] = worker
        worker.start()

        return True

    def _emit_error(self, port: str, message: str) -> None:
        """
        Helper to emit PortErrorEvent

        Args:
            port: 포트 이름
            message: 에러 메시지
        """
        self.error_occurred.emit(PortErrorEvent(port=port, message=message))

    def _handle_data_received(self, name: str, data: bytes) -> None:
        """
        데이터 수신 처리 핸들러

        Logic:
            - Raw 데이터 시그널 발행
            - Parser를 통해 패킷 파싱 후 패킷 시그널 발행

        Args:
            name: 데이터를 수신한 연결 이름
            data: 수신된 바이트 데이터
        """
        self.data_received.emit(PortDataEvent(port=name, data=data))

        parser = self.parsers.get(name)
        if parser:
            packets = parser.parse(data)
            for packet in packets:
                # Emit DTO
                self.packet_received.emit(PacketEvent(port=name, packet=packet))

    def on_worker_closed(self, name: str) -> None:
        """
        Worker 종료 시 리소스 정리 핸들러

        Args:
            name: 닫힌 연결 이름
        """
        if name in self.workers:
            del self.workers[name]
        if name in self.parsers:
            del self.parsers[name]
        if name in self.connection_configs:
            del self.connection_configs[name]

        self.connection_closed.emit(PortConnectionEvent(port=name, state="closed"))

    def close_connection(self, name: Optional[str] = None) -> None:
        """
        연결을 종료합니다.

        Logic:
            - 해당 포트에서 진행 중인 파일 전송이 있다면 강제 취소 요청
            - Worker 스레드 종료 및 리소스 해제

        Args:
            name: 종료할 연결 이름. None이면 모든 연결 종료.
        """
        if name:
            # 파일 전송이 진행 중이라면 즉시 중단 요청을 보냅니다.
            # QRunnable은 wait()가 없으므로 cancel 플래그를 세팅하여 엔진이
            # 다음 청크 전송 시도 전에 스스로 루프를 탈출하도록 합니다.
            if name in self._active_file_transfers:
                logger.warning(f"Closing port {name} while file transfer is active. Cancelling transfer...")
                transfer_engine = self._active_file_transfers[name]
                transfer_engine.cancel()
                # 엔진이 등록 해제할 때까지 기다릴 수도 있지만, UI 블로킹 우려로 비동기 취소 처리
                # 엔진은 send_data 실패 시 예외 처리로 종료되거나 cancel 플래그 확인 후 종료됨.

            worker = self.workers.get(name)
            if worker:
                worker.stop()
        else:
            # 모든 포트 닫기 (복사본으로 순회하여 안전하게 삭제)
            for name in list(self.workers.keys()):
                self.close_connection(name)

    def send_data(self, port_name: str, data: bytes) -> None:
        """
        특정 포트로 데이터를 전송합니다.

        Args:
            port_name (str): 대상 포트 이름 (필수)
            data (bytes): 전송할 데이터
        """
        if not port_name:
            self.error_occurred.emit("", "Cannot send data: Port name is not specified.")
            return

        if not self.is_connection_open(port_name):
            self.error_occurred.emit(port_name, "Cannot send data: Port is not open.")
            return

        self.send_data_to_connection(port_name, data)

    def send_broadcast_data(self, data: bytes) -> None:
        """
        broadcasting 활성 연결로 데이터 Broadcasting

        Logic:
            - 현재 broadcasting 활성화된 워커 리스트를 순회하며 데이터를 전송
            - Worker의 broadcast_enabled() 상태 확인

        Args:
            data: 전송할 바이트 데이터
        """
        if not self.workers:
            self.error_occurred.emit("", "No active connections.")
            return

        sent_any = False
        for name, worker in self.workers.items():
            if worker.isRunning() and worker.broadcast_enabled():
                self.send_data_to_connection(name, data)
                sent_any = True

        if not sent_any:
            # 브로드캐스팅 대상이 없으면 ?
            # TODO : 모르겠음. 일단 로그 남김
            logger.warning("No active connections for broadcasting.")

    def send_data_to_all(self, data: bytes) -> None:
        """
        모든 활성 연결로 데이터 Broadcasting

        Logic:
            - 현재 활성화된 워커 리스트를 순회하며 데이터를 전송
            - send_data_to 메서드를 호출하여 실제 전송 수행

        Args:
            data: 전송할 바이트 데이터
        """
        if not self.workers:
            self.error_occurred.emit("", "No active connections.")
            return

        for name, worker in self.workers.items():
            if worker.isRunning():
                self.send_data_to_connection(name, data)

    def send_data_to_connection(self, name: str, data: bytes) -> bool:
        """
        특정 연결로 데이터 전송

        Logic:
            - 이름으로 워커를 찾아 전송 큐에 넣음
            - 성공 시 data_sent 시그널 발행

        Args:
            name (str): 대상 연결 이름
            data (bytes): 전송할 데이터

        Returns:
            bool: 전송 성공 여부
        """
        worker = self.workers.get(name)
        if worker and worker.isRunning():
            worker.send_data(data)
            # Emit DTO
            self.data_sent.emit(PortDataEvent(port=name, data=data))
            return True
        return False

    def set_port_broadcast_state(self, port_name: str, state: bool) -> None:
        """
        특정 포트의 브로드캐스트 수신 허용 상태를 변경합니다.

        Args:
            port_name (str): 포트 이름
            state (bool): True=허용, False=거부
        """
        worker = self.workers.get(port_name)
        if worker:
            worker.set_broadcast(state)

    def set_dtr(self, state: bool) -> None:
        """
        모든 포트의 DTR(Data Terminal Ready) 신호 설정

        Args:
            state: True면 DTR ON, False면 DTR OFF
        """
        for worker in self.workers.values():
            worker.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """
        모든 포트의 RTS(Request To Send) 신호 설정

        Args:
            state: True면 RTS ON, False면 RTS OFF
        """
        for worker in self.workers.values():
            worker.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        """
        모든 포트의 broadcasting 설정 (일괄 설정용)

        Args:
            state: True면 broadcasting ON, False면 broadcasting OFF
        """
        for worker in self.workers.values():
            worker.set_broadcast(state)
