"""
연결 컨트롤러 모듈

개별 연결 세션의 생명주기와 데이터 흐름을 제어합니다.

## WHY
* 단일 연결에 대한 상태 관리 및 로직 캡슐화 필요
* 하드웨어(Worker)와 UI(Presenter) 사이의 중재자 역할
* 데이터 파싱 및 이벤트 전파의 중심점
* 파일 전송 등 장기 작업 시의 연결 유지 관리

## WHAT
* 연결 열기/닫기(Open/Close) 관리 및 DTO 기반 이벤트 발행
* Worker 스레드 관리 및 Transport 주입
* 패킷 파싱(Parser) 연결 및 데이터 브로드캐스팅
* 파일 전송 엔진 등록 및 안전한 종료 처리

## HOW
* BaseTransport 구현체를 생성하여 ConnectionWorker에 주입
* PyQt Signal 및 EventBus를 통한 비동기 이벤트 전파 (DTO 사용)
* Dictionary를 사용하여 다중 포트 Worker 관리
"""
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from PyQt5.QtCore import QObject, pyqtSignal

from model.connection_worker import ConnectionWorker
from core.transport.serial_transport import SerialTransport
from core.transport.loopback_transport import LoopbackTransport
from model.packet_parser import ParserFactory, PacketParser
from common.enums import ParserType, ConnectionProtocol
from common.dtos import (
    PortConfig,
    PortDataEvent,
    PortErrorEvent,
    PacketEvent,
    PortConnectionEvent
)
from common.constants import EventTopics, LOOPBACK_PORT_NAME
from core.event_bus import event_bus
from core.logger import logger

if TYPE_CHECKING:
    from model.file_transfer_service import FileTransferService


class ConnectionController(QObject):
    """
    개별 연결 세션 관리 클래스

    하나의 물리적/논리적 연결에 대한 Worker, Parser, 설정을 총괄합니다.
    ConnectionWorker(Thread)를 생성하고 관리하며, 데이터 송수신 이벤트를 중계합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    connection_opened = pyqtSignal(object)  # PortConnectionEvent
    connection_closed = pyqtSignal(object)  # PortConnectionEvent

    error_occurred = pyqtSignal(object)     # PortErrorEvent
    data_received = pyqtSignal(object)      # PortDataEvent
    data_sent = pyqtSignal(object)          # PortDataEvent
    packet_received = pyqtSignal(object)    # PacketEvent

    def __init__(self) -> None:
        """
        ConnectionController 초기화

        Logic:
            - Worker/Parser/Config 저장소 초기화
            - 파일 전송 레지스트리 초기화
            - Signal -> EventBus 자동 중계 연결
        """
        super().__init__()
        # 연결 이름(str) -> ConnectionWorker 매핑
        self.workers: Dict[str, ConnectionWorker] = {}
        # 연결 이름(str) -> PacketParser 매핑
        self.parsers: Dict[str, PacketParser] = {}
        # 연결 이름(str) -> Config(PortConfig) 매핑
        self.connection_configs: Dict[str, PortConfig] = {}

        # 진행 중인 파일 전송 엔진 추적 (Race Condition 방지)
        # 연결 이름(str) -> FileTransferService 매핑
        self._active_file_transfers: Dict[str, 'FileTransferService'] = {}

        # EventBus 인스턴스
        self.event_bus = event_bus

        # Signal -> EventBus 자동 연결
        self._connect_signals_to_eventbus()

    def _connect_signals_to_eventbus(self) -> None:
        """
        Signal 발생 시 EventBus로 DTO를 발행하도록 연결합니다.

        Logic:
            - 각 시그널을 lambda를 통해 EventBus.publish로 연결
            - DTO가 이미 시그널에 담겨 있으므로 그대로 전달
        """
        self.connection_opened.connect(lambda e: self.event_bus.publish(EventTopics.PORT_OPENED, e))
        self.connection_closed.connect(lambda e: self.event_bus.publish(EventTopics.PORT_CLOSED, e))

        self.error_occurred.connect(lambda e: self.event_bus.publish(EventTopics.PORT_ERROR, e))
        self.data_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_RECEIVED, e))
        self.data_sent.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_SENT, e))
        self.packet_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_PACKET_RECEIVED, e))

    # -------------------------------------------------------------------------
    # File Transfer Management
    # -------------------------------------------------------------------------
    def register_file_transfer(self, port_name: str, file_transfer_service: 'FileTransferService') -> None:
        """
        활성 파일 전송 서비스를 등록합니다. (포트 강제 종료 시 안전 처리를 위함)

        Args:
            port_name (str): 대상 포트 이름.
            file_transfer_service (FileTransferService): 전송 서비스 인스턴스.
        """
        self._active_file_transfers[port_name] = file_transfer_service
        logger.debug(f"File transfer registered for port {port_name}")

    def unregister_file_transfer(self, port_name: str) -> None:
        """
        파일 전송 서비스 등록을 해제합니다. (전송 완료/취소 시 호출)

        Args:
            port_name (str): 대상 포트 이름.
        """
        if port_name in self._active_file_transfers:
            del self._active_file_transfers[port_name]
            logger.debug(f"File transfer unregistered for port {port_name}")

    # -------------------------------------------------------------------------
    # State Queries
    # -------------------------------------------------------------------------
    @property
    def has_active_connection(self) -> bool:
        """
        하나라도 활성화된 연결이 있는지 확인합니다.

        Returns:
            bool: 활성 연결이 있으면 True.
        """
        return len(self.workers) > 0

    def has_active_broadcast_ports(self) -> bool:
        """
        브로드캐스트 가능한 활성 포트가 하나라도 있는지 확인합니다.
        (매크로/수동 전송 시 Gatekeeper 역할)

        Returns:
            bool: 전송 가능한 포트가 있으면 True.
        """
        for worker in self.workers.values():
            if worker.isRunning() and worker.broadcast_enabled():
                return True
        return False

    def get_active_connections(self) -> List[str]:
        """
        현재 활성화된 모든 연결의 이름을 반환합니다.

        Returns:
            List[str]: 연결 이름 리스트.
        """
        return list(self.workers.keys())

    def is_connection_open(self, name: str) -> bool:
        """
        특정 연결이 열려있는지 확인합니다.

        Args:
            name (str): 확인할 연결 이름.

        Returns:
            bool: 연결이 열려있고 Worker가 실행 중이면 True.
        """
        worker = self.workers.get(name)
        return worker is not None and worker.isRunning()

    def get_connection_config(self, name: str) -> Optional[PortConfig]:
        """
        특정 연결의 설정 정보를 반환합니다.

        Args:
            name (str): 확인할 연결 이름.

        Returns:
            Optional[PortConfig]: 설정 정보 DTO. 없으면 None.
        """
        return self.connection_configs.get(name)

    def get_write_queue_size(self, name: str) -> int:
        """
        특정 연결의 전송 대기 큐 크기를 반환합니다.
        파일 전송 시 Backpressure(역압) 제어에 사용됩니다.

        Args:
            name (str): 확인할 연결 이름.

        Returns:
            int: 대기 중인 청크 개수. 포트가 없으면 0.
        """
        worker = self.workers.get(name)
        if worker:
            return worker.get_write_queue_size()
        return 0

    # -------------------------------------------------------------------------
    # Connection Management (Open/Close)
    # -------------------------------------------------------------------------
    def open_connection(self, config: PortConfig) -> bool:
        """
        새로운 포트 연결을 엽니다.

        Logic:
            1. 포트 이름 유효성 및 중복 연결 확인
            2. Transport(SerialTransport) 생성 (Config 주입)
            3. Worker(ConnectionWorker) 생성 및 Transport 주입
            4. Parser(PacketParser) 생성 및 등록
            5. Worker 시그널을 Controller 시그널(DTO)로 변환하여 연결
            6. Worker 스레드 시작

        Args:
            config (PortConfig): 연결 설정 정보 DTO.

        Returns:
            bool: 시작 성공 여부.
        """
        name = config.port
        if not name:
            self._emit_error("", "Connection name(port) is required.")
            return False

        # 중복 열기 방지
        if self.is_connection_open(name):
            self._emit_error(name, "Connection is already open.")
            return False

        # 미구현 프로토콜 명시적 거부 (S-041 B-2) — 조용히 Serial로 연결 시도하지 않는다.
        if config.protocol not in ConnectionProtocol.SUPPORTED:
            self._emit_error(
                name,
                f"Protocol '{config.protocol}' is not implemented yet. Connection not attempted."
            )
            return False

        # DTO를 직접 Transport에 전달 (provider 분기는 이 한 곳뿐 — S-033)
        if config.port == LOOPBACK_PORT_NAME:
            transport = LoopbackTransport(config)
        else:
            transport = SerialTransport(config)

        # Worker에 Transport 주입
        worker = ConnectionWorker(transport, name)

        # Parser 생성 (설정값 반영 — S-041 B-1). 잘못된 파라미터(빈 delimiter,
        # 0 이하 length)는 ParserFactory가 ValueError로 거부하므로 조용히
        # 삼키지 않고 _emit_error로 사용자에게 표면화한다.
        parser_type = ParserType.from_preference_index(config.parser_type)
        try:
            parser_kwargs = self._build_parser_kwargs(parser_type, config)
            self.parsers[name] = ParserFactory.create_parser(parser_type, **parser_kwargs)
        except ValueError as exc:
            self._emit_error(name, f"Invalid packet parser configuration: {exc}")
            return False

        self.connection_configs[name] = config

        # Worker signals -> Controller signals (Wrap in DTO)
        # 문자열 대신 PortConnectionEvent DTO 발행
        worker.connection_opened.connect(
            lambda n=name: self.connection_opened.emit(PortConnectionEvent(port=n, state="opened"))
        )
        worker.connection_closed.connect(self.on_worker_closed)
        worker.worker_terminated.connect(self.on_worker_terminated)

        # 데이터 및 에러 핸들러 연결
        worker.error_occurred.connect(lambda msg, n=name: self._emit_error(n, msg))
        worker.data_received.connect(lambda data, n=name: self._handle_data_received(n, data))

        # Worker 관리 및 시작
        self.workers[name] = worker
        worker.start()

        return True

    def close_connection(self, name: Optional[str] = None) -> None:
        """
        포트 연결을 닫습니다. (단일 또는 전체)

        Logic:
            - 이름이 주어지면 해당 포트만 종료
            - 파일 전송 중이라면 전송 취소 요청
            - Worker 정지 요청 (stop)

        Args:
            name (Optional[str]): 닫을 포트 이름. None이면 전체 닫기.
        """
        if name:
            # 1. 파일 전송 중인지 확인하고 취소
            if name in self._active_file_transfers:
                logger.warning(f"Closing port {name} while file transfer is active. Cancelling transfer...")
                transfer_engine = self._active_file_transfers[name]
                transfer_engine.cancel()
                # 엔진은 cancel 플래그 확인 후 루프 탈출 -> unregister 호출됨

            # 2. Worker 정지
            worker = self.workers.get(name)
            if worker:
                worker.stop()
                self.on_worker_closed(name)
        else:
            # 전체 닫기 (재귀 호출)
            for port_name in list(self.workers.keys()):
                self.close_connection(port_name)

    def _cleanup_worker_registry(self, name: str) -> bool:
        """
        Worker/Parser/Config 관리 Dictionary에서 name에 해당하는 항목을 제거합니다.

        두 종료 경로(정상 종료 `on_worker_closed`, 비정상 종료 `on_worker_terminated`)가
        공유하는 정리 로직이다. 이미 제거된 이름에 대해 다시 호출해도 안전하다(멱등).

        Args:
            name (str): 정리할 연결 이름.

        Returns:
            bool: 실제로 workers에서 제거했으면 True (중복 호출 시 False).
        """
        was_registered = name in self.workers
        if was_registered:
            del self.workers[name]
        if name in self.parsers:
            del self.parsers[name]
        if name in self.connection_configs:
            del self.connection_configs[name]
        return was_registered

    def on_worker_closed(self, name: str) -> None:
        """
        Worker가 정상적으로(실제 연결되었다가) 종료되었을 때 호출되는 콜백.
        `ConnectionWorker.connection_closed`(transport가 열렸던 경우에만 발행)에 연결된다.

        Logic:
            - 관리 Dictionary에서 해당 리소스 제거
            - 닫힘 시그널 발행 (연결이 실제로 있었던 경우에만)

        Args:
            name (str): 종료된 포트 이름.
        """
        if self._cleanup_worker_registry(name):
            self.connection_closed.emit(PortConnectionEvent(port=name, state="closed"))

    def on_worker_terminated(self, name: str) -> None:
        """
        Worker 스레드가 어떤 사유로든(정상/비정상) 종료되었을 때 호출되는 콜백.
        `ConnectionWorker.worker_terminated`(성공/실패 무관 항상 발행)에 연결된다 (S-040/B-3).

        Logic:
            - 관리 Dictionary에서 해당 리소스 제거만 수행한다.
            - connection_closed는 발행하지 않는다: open 실패 경로는 이미
              error_occurred로 실패가 통지되었으므로, 연결된 적 없는 포트에 대해
              "Port closed"로 오인되는 메시지가 중복 표시되지 않도록 한다.
            - 정상 종료 시에는 on_worker_closed가 먼저 호출되어 레지스트리가 이미
              비어있으므로(멱등) 이 호출은 아무 효과가 없다.

        Args:
            name (str): 종료된 포트 이름.
        """
        self._cleanup_worker_registry(name)

    @staticmethod
    def _build_parser_kwargs(parser_type: str, config: PortConfig) -> Dict[str, Any]:
        """
        파서 타입에 따라 ParserFactory에 전달할 kwargs를 구성합니다.

        Args:
            parser_type (str): ParserType 문자열 상수.
            config (PortConfig): 파서 설정이 실려 있는 연결 설정 DTO.

        Returns:
            Dict[str, Any]: ParserFactory.create_parser에 전달할 kwargs.
        """
        if parser_type == ParserType.DELIMITER:
            return {"delimiter": ConnectionController._decode_delimiter(config.packet_delimiter)}
        if parser_type == ParserType.FIXED_LENGTH:
            return {"length": config.packet_length}
        return {}

    @staticmethod
    def _decode_delimiter(raw: str) -> bytes:
        """
        Preferences에 저장된 이스케이프 문자열 구분자를 실제 바이트로 변환합니다.

        예: "\\r\\n" (백슬래시-r-백슬래시-n 4글자) -> b'\\r\\n' (CR LF 2바이트).

        Args:
            raw (str): 설정에 저장된 구분자 문자열.

        Returns:
            bytes: 디코딩된 구분자 바이트열. 빈 문자열이면 b""
                (DelimiterParser가 이를 거부하도록 그대로 전달한다).
        """
        if not raw:
            return b""
        try:
            return raw.encode("utf-8").decode("unicode_escape").encode("latin-1")
        except (UnicodeDecodeError, UnicodeEncodeError):
            # 디코딩 불가능한 값은 원본을 그대로 바이트로 취급 (최선의 노력)
            return raw.encode("utf-8")

    def _emit_error(self, port: str, message: str) -> None:
        """
        에러 발생 시 PortErrorEvent DTO를 발행합니다.

        Args:
            port (str): 포트 이름.
            message (str): 에러 메시지.
        """
        self.error_occurred.emit(PortErrorEvent(port=port, message=message))

    # -------------------------------------------------------------------------
    # Data Handling (Send/Receive)
    # -------------------------------------------------------------------------
    def _handle_data_received(self, name: str, data: bytes) -> None:
        """
        데이터 수신 처리 핸들러입니다.

        Logic:
            1. Raw 데이터에 대해 PortDataEvent 발행 (로그 및 UI 표시용)
            2. 등록된 Parser를 통해 데이터 파싱
            3. 파싱된 패킷마다 PacketEvent 발행

        Args:
            name (str): 데이터를 수신한 연결 이름.
            data (bytes): 수신된 바이트 데이터.
        """
        # Raw 데이터 이벤트 발행
        self.data_received.emit(PortDataEvent(port=name, data=data))

        # 패킷 파싱 및 이벤트 발행
        parser = self.parsers.get(name)
        if parser:
            packets = parser.parse(data)
            for packet in packets:
                self.packet_received.emit(PacketEvent(port=name, packet=packet))

    def send_data(self, port_name: str, data: bytes) -> None:
        """
        특정 포트로 데이터 전송.

        Args:
            port_name (str): 대상 포트 이름.
            data (bytes): 전송할 데이터.
        """
        if not port_name:
            self._emit_error("", "Cannot send data: Port name is not specified.")
            return

        if not self.is_connection_open(port_name):
            self._emit_error(port_name, "Cannot send data: Port is not open.")
            return

        self.send_data_to_connection(port_name, data)

    def send_broadcast_data(self, data: bytes) -> None:
        """
        브로드캐스트 활성화된 모든 포트로 데이터 전송.

        Logic:
            - 딕셔너리 변경 대비 리스트 복사본을 순회
            - 각 Worker의 broadcast_enabled 상태 확인 후 전송

        Args:
            data (bytes): 전송할 데이터.
        """
        if not self.workers:
            self._emit_error("", "No active connections.")
            return

        sent_any = False
        # Runtime Error 방지: list(items())로 복사하여 순회
        for name, worker in list(self.workers.items()):
            # Worker가 실행 중이고 브로드캐스트가 허용된 경우만 전송
            if worker.isRunning() and worker.broadcast_enabled():
                self.send_data_to_connection(name, data)
                sent_any = True

        if not sent_any:
            logger.warning("No active connections enabled for broadcasting.")

    def send_data_to_all(self, data: bytes) -> None:
        """
        모든 활성 포트로 데이터 전송 (강제 브로드캐스트).

        Args:
            data (bytes): 전송할 데이터.
        """
        if not self.workers:
            self._emit_error("", "No active connections.")
            return

        for name, worker in list(self.workers.items()):
            if worker.isRunning():
                self.send_data_to_connection(name, data)

    def send_data_to_connection(self, name: str, data: bytes) -> bool:
        """
        실제 Worker에게 데이터 전송을 요청하는 내부 메서드.

        Logic:
            - Worker 존재 및 실행 여부 확인
            - Worker의 비동기 전송 큐에 데이터 추가
            - 성공 시 PortDataEvent(Sent) DTO 발행

        Args:
            name (str): 포트 이름.
            data (bytes): 데이터.

        Returns:
            bool: 전송 요청 성공 여부.
        """
        worker = self.workers.get(name)
        if worker and worker.isRunning():
            if worker.send_data(data):
                # 송신 데이터 이벤트 발행
                self.data_sent.emit(PortDataEvent(port=name, data=data))
                return True
        return False

    # -------------------------------------------------------------------------
    # Control Signals
    # -------------------------------------------------------------------------
    def set_port_broadcast_state(self, port_name: str, state: bool) -> None:
        """
        특정 포트의 브로드캐스트 수신 허용 상태 변경.

        Args:
            port_name (str): 포트 이름.
            state (bool): True=허용, False=거부.
        """
        worker = self.workers.get(port_name)
        if worker:
            worker.set_broadcast(state)

    def set_dtr(self, state: bool) -> None:
        """
        모든 활성 포트의 DTR(Data Terminal Ready) 신호 설정.

        Args:
            state (bool): True=ON, False=OFF.
        """
        for worker in self.workers.values():
            worker.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """
        모든 활성 포트의 RTS(Request To Send) 신호 설정.

        Args:
            state (bool): True=ON, False=OFF.
        """
        for worker in self.workers.values():
            worker.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        """
        모든 활성 포트의 브로드캐스트 설정 일괄 변경.

        Args:
            state (bool): True=ON, False=OFF.
        """
        for worker in self.workers.values():
            worker.set_broadcast(state)
