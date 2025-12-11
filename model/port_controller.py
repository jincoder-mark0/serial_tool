"""
포트 생명주기 및 설정 관리 클래스.
ConnectionWorker와 UI 사이의 브리지 역할을 수행합니다.
"""
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional

# 변경된 모듈 임포트
from model.connection_worker import ConnectionWorker
from model.transports import SerialTransport
from model.packet_parser import ParserFactory, IPacketParser, Packet
from constants import DEFAULT_BAUDRATE

class PortController(QObject):
    # 외부(Presenter)와 통신하는 시그널
    # 다중 포트 지원을 위해 port_name 인자 추가
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str) # port_name, error_msg
    data_received = pyqtSignal(str, bytes) # port_name, data
    data_sent = pyqtSignal(str, bytes) # port_name, data
    packet_received = pyqtSignal(str, object) # port_name, Packet object

    def __init__(self) -> None:
        super().__init__()
        # 포트 이름(str) -> ConnectionWorker 매핑
        self.workers: dict[str, ConnectionWorker] = {}
        # 포트 이름(str) -> IPacketParser 매핑
        self.parsers: dict[str, IPacketParser] = {}

    @property
    def is_open(self) -> bool:
        """하나라도 열린 포트가 있으면 True 반환"""
        return len(self.workers) > 0

    @property
    def current_port_name(self) -> str:
        """
        현재 열려있는 포트 이름 중 하나를 반환합니다.
        다중 포트 환경에서는 대표 포트 이름 또는 마지막으로 열린 포트 이름을 반환할 수 있습니다.
        """
        if self.workers:
            return list(self.workers.keys())[-1]
        return ""

    def is_port_open(self, port_name: str) -> bool:
        """특정 포트가 열려있는지 확인합니다."""
        worker = self.workers.get(port_name)
        return worker is not None and worker.isRunning()

    def open_port(self, config: dict) -> bool:
        """
        시리얼 포트를 엽니다.
        내부적으로 SerialTransport를 생성하여 Worker에 주입합니다.

        Args:
            config (dict): 포트 설정 딕셔너리.
        """
        port_name = config.get('port')
        if not port_name:
            self.error_occurred.emit("", "Port name is required.")
            return False

        if self.is_port_open(port_name):
            self.error_occurred.emit(port_name, "Port is already open.")
            return False

        baudrate = config.get('baudrate', DEFAULT_BAUDRATE)

        # 1. Transport 객체 생성
        transport = SerialTransport(port_name, baudrate, config=config)

        # 2. Worker에 Transport 주입
        worker = ConnectionWorker(transport, port_name)

        # 3. Parser 생성
        parser_type = config.get('parser_type', 'Raw')
        parser_kwargs = {}
        if parser_type == 'Delimiter':
            parser_kwargs['delimiter'] = config.get('parser_delimiter', b'\n')
        elif parser_type == 'FixedLength':
            parser_kwargs['length'] = config.get('parser_length', 10)
            
        self.parsers[port_name] = ParserFactory.create_parser(parser_type, **parser_kwargs)

        # 4. 시그널 매핑 (Worker 이벤트 -> Controller 시그널)
        worker.connection_opened.connect(self.port_opened)
        worker.connection_closed.connect(self.on_worker_closed)
        
        worker.error_occurred.connect(lambda msg, p=port_name: self.error_occurred.emit(p, msg))
        
        # 데이터 수신 핸들러 연결 (Raw 데이터 및 패킷 파싱 처리)
        worker.data_received.connect(lambda data, p=port_name: self._handle_data_received(p, data))

        self.workers[port_name] = worker
        worker.start()
        return True

    def _handle_data_received(self, port_name: str, data: bytes) -> None:
        """데이터 수신 처리: Raw 시그널 발행 및 패킷 파싱"""
        # 1. Raw 데이터 시그널 발행
        self.data_received.emit(port_name, data)
        
        # 2. 패킷 파싱 및 패킷 시그널 발행
        parser = self.parsers.get(port_name)
        if parser:
            packets = parser.parse(data)
            for packet in packets:
                self.packet_received.emit(port_name, packet)

    def on_worker_closed(self, port_name: str) -> None:
        """Worker가 닫혔을 때 호출되는 내부 핸들러"""
        if port_name in self.workers:
            del self.workers[port_name]
        if port_name in self.parsers:
            del self.parsers[port_name]
        self.port_closed.emit(port_name)

    def close_port(self, port_name: Optional[str] = None) -> None:
        """
        포트를 닫습니다.
        
        Args:
            port_name: 닫을 포트 이름. None이면 모든 포트를 닫습니다.
        """
        if port_name:
            worker = self.workers.get(port_name)
            if worker:
                worker.stop()
                # on_worker_closed는 worker 시그널에 의해 호출됨
        else:
            # 모든 포트 닫기 (복사본으로 순회)
            for name in list(self.workers.keys()):
                self.close_port(name)

    def send_data(self, data: bytes) -> None:
        """
        모든 열린 포트로 데이터를 전송합니다 (Broadcasting).

        Args:
            data (bytes): 전송할 바이트 데이터.
        """
        if not self.workers:
            self.error_occurred.emit("", "No ports are open.")
            return

        for port_name, worker in self.workers.items():
            if worker.isRunning():
                worker.send_data(data)
                self.data_sent.emit(port_name, data)

    def set_dtr(self, state: bool) -> None:
        """모든 포트의 DTR 설정"""
        for worker in self.workers.values():
            worker.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """모든 포트의 RTS 설정"""
        for worker in self.workers.values():
            worker.set_rts(state)
