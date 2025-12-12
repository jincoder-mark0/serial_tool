"""
포트 컨트롤러 모듈

시리얼 포트의 생명주기와 설정을 관리 컨트롤러

## WHY
* 다중 포트 동시 관리 지원
* ConnectionWorker와 UI 사이의 중재자 역할
* 포트별 독립적인 파서 및 설정 관리
* 이벤트 기반 통신으로 느슨한 결합 유지

## WHAT
* 포트 열기/닫기 생명주기 관리
* 데이터 송수신 및 브로드캐스팅
* 패킷 파싱 및 이벤트 발행
* DTR/RTS 제어 신호 관리
* 다중 포트 상태 추적

## HOW
* ConnectionWorker를 포트별로 생성하여 스레드 격리
* Dictionary로 포트별 Worker 및 Parser 매핑
* PyQt Signal/Slot으로 비동기 이벤트 처리
* EventBus로 전역 이벤트 발행
* SerialTransport를 Worker에 주입하여 의존성 역전
"""
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any

from model.connection_worker import ConnectionWorker
from model.serial_transport import SerialTransport
from model.packet_parser import ParserFactory, IPacketParser, ParserType
from constants import DEFAULT_BAUDRATE
from core.event_bus import event_bus

class PortController(QObject):
    """
    포트 생명주기 및 설정 관리 클래스

    다중 포트 동시 관리
    각 포트별로 독립적인 Worker와 Parser를 유지
    Signal 발생 시 자동으로 EventBus로 이벤트를 전파
    """

    # 외부(Presenter)와 통신하는 시그널
    # 다중 포트 지원을 위해 port_name 인자 추가
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str) # port_name, error_msg
    data_received = pyqtSignal(str, bytes) # port_name, data
    data_sent = pyqtSignal(str, bytes) # port_name, data
    packet_received = pyqtSignal(str, object) # port_name, Packet object

    def __init__(self) -> None:
        """
        PortController 초기화

        Logic:
            - Worker/Parser 저장소 초기화
            - Signal -> EventBus 자동 중계 연결
        """
        super().__init__()
        # 포트 이름(str) -> ConnectionWorker 매핑
        self.workers: dict[str, ConnectionWorker] = {}
        # 포트 이름(str) -> IPacketParser 매핑
        self.parsers: dict[str, IPacketParser] = {}
        # 포트 이름(str) -> Config(dict) 매핑 [New]
        self.port_configs: dict[str, dict] = {}

        # EventBus 인스턴스
        self.event_bus = event_bus

        # Signal -> EventBus 자동 연결
        self._connect_signals_to_eventbus()

    def _connect_signals_to_eventbus(self) -> None:
        """PyQt Signal 발생 시 자동으로 EventBus 이벤트를 발행하도록 연결합니다."""
        self.port_opened.connect(lambda p: self.event_bus.publish("port.opened", p))
        self.port_closed.connect(lambda p: self.event_bus.publish("port.closed", p))

        self.error_occurred.connect(
            lambda p, m: self.event_bus.publish("port.error", {'port': p, 'message': m})
        )

        self.data_received.connect(
            lambda p, d: self.event_bus.publish("port.data_received", {'port': p, 'data': d})
        )

        self.data_sent.connect(
            lambda p, d: self.event_bus.publish("port.data_sent", {'port': p, 'data': d})
        )

        self.packet_received.connect(
            lambda p, pkt: self.event_bus.publish("port.packet_received", {'port': p, 'packet': pkt})
        )

    @property
    def is_open(self) -> bool:
        """하나라도 열린 포트가 있으면 True 반환"""
        return len(self.workers) > 0

    @property
    def current_port_name(self) -> str:
        """
        현재 열려있는 포트 이름 중 하나를 반환

        다중 포트 환경에서는 마지막으로 열린 포트 이름을 반환합니다.

        Returns:
            str: 포트 이름 (열린 포트가 없으면 빈 문자열)
        """
        if self.workers:
            return list(self.workers.keys())[-1]
        return ""

    def is_port_open(self, port_name: str) -> bool:
        """
        특정 포트가 열려있는지 확인

        Args:
            port_name: 확인할 포트 이름

        Returns:
            bool: 포트가 열려있고 실행 중이면 True
        """
        worker = self.workers.get(port_name)
        return worker is not None and worker.isRunning()

    def get_port_config(self, port_name: str) -> Dict[str, Any]:
        """
        특정 포트의 설정 정보를 반환합니다.

        Args:
            port_name: 포트 이름

        Returns:
            dict: 설정 딕셔너리 (없으면 빈 딕셔너리)
        """
        return self.port_configs.get(port_name, {})

    def get_write_queue_size(self, port_name: str) -> int:
        """
        특정 포트의 전송 대기 큐 크기를 반환합니다.

        Returns:
            int: 대기 중인 청크 개수 (포트가 없으면 0)
        """
        worker = self.workers.get(port_name)
        if worker:
            return worker.get_write_queue_size()
        return 0

    def open_port(self, config: dict) -> bool:
        """
        시리얼 포트를 엽니다

        Logic:
            - 포트 이름 유효성 검사
            - 중복 열기 방지
            - SerialTransport 생성 및 설정
            - ConnectionWorker 생성 및 시그널 연결
            - Parser 생성 및 매핑
            - Worker 스레드 시작

        Args:
            config: 포트 설정 딕셔너리
                - port (str): 포트 이름 (필수)
                - baudrate (int): 보드레이트 (기본값: DEFAULT_BAUDRATE)
                - parser_type (ParserType): 파서 타입
                - parser_delimiter (bytes): 구분자 (DELIMITER 파서용)
                - parser_length (int): 패킷 길이 (FIXED_LENGTH 파서용)

        Returns:
            bool: 성공 여부
        """
        port_name = config.get('port')
        if not port_name:
            self.error_occurred.emit("", "Port name is required.")
            return False

        # 중복 열기 방지
        if self.is_port_open(port_name):
            self.error_occurred.emit(port_name, "Port is already open.")
            return False

        baudrate = config.get('baudrate', DEFAULT_BAUDRATE)

        # 1. Transport 객체 생성
        transport = SerialTransport(port_name, baudrate, config=config)

        # 2. Worker에 Transport 주입 (의존성 역전)
        worker = ConnectionWorker(transport, port_name)

        # 3. Parser 생성 (타입별 설정)
        parser_type = config.get('parser_type', ParserType.RAW)
        parser_kwargs = {}
        if parser_type == ParserType.DELIMITER:
            parser_kwargs['delimiter'] = config.get('parser_delimiter', b'\n')
        elif parser_type == ParserType.FIXED_LENGTH:
            parser_kwargs['length'] = config.get('parser_length', 10)

        self.parsers[port_name] = ParserFactory.create_parser(parser_type, **parser_kwargs)

        self.port_configs[port_name] = config

        # 4. 시그널 매핑 (Worker 이벤트 -> Controller 시그널)
        worker.connection_opened.connect(lambda p=port_name: self.port_opened.emit(p))
        worker.connection_closed.connect(self.on_worker_closed)

        worker.error_occurred.connect(lambda msg, p=port_name: self.error_occurred.emit(p, msg))

        # 데이터 수신 핸들러 연결 (Raw 데이터 및 패킷 파싱 처리)
        worker.data_received.connect(lambda data, p=port_name: self._handle_data_received(p, data))

        self.workers[port_name] = worker
        worker.start()
        return True

    def _handle_data_received(self, port_name: str, data: bytes) -> None:
        """
        데이터 수신 처리

        Logic:
            - Raw 데이터 시그널 발행 (Signal -> EventBus 자동 전파)
            - 해당 포트의 Parser로 패킷 파싱
            - 파싱된 각 패킷을 시그널로 발행

        Args:
            port_name: 데이터를 수신한 포트 이름
            data: 수신된 바이트 데이터
        """
        # 1. Raw 데이터 시그널 발행
        self.data_received.emit(port_name, data)

        # 2. 패킷 파싱 및 패킷 시그널 발행
        parser = self.parsers.get(port_name)
        if parser:
            packets = parser.parse(data)
            for packet in packets:
                self.packet_received.emit(port_name, packet)

    def on_worker_closed(self, port_name: str) -> None:
        """
        Worker가 닫혔을 때 호출되는 내부 핸들러

        Args:
            port_name: 닫힌 포트 이름
        """
        # 리소스 정리
        if port_name in self.workers:
            del self.workers[port_name]
        if port_name in self.parsers:
            del self.parsers[port_name]
        if port_name in self.port_configs:
            del self.port_configs[port_name]

        # 이벤트 발행
        self.port_closed.emit(port_name)

    def close_port(self, port_name: Optional[str] = None) -> None:
        """
        포트를 닫습니다

        Args:
            port_name: 닫을 포트 이름. None이면 모든 포트를 닫습니다
        """
        if port_name:
            worker = self.workers.get(port_name)
            if worker:
                worker.stop()
                # on_worker_closed는 worker 시그널에 의해 자동 호출됨
        else:
            # 모든 포트 닫기 (복사본으로 순회하여 안전하게 삭제)
            for name in list(self.workers.keys()):
                self.close_port(name)

    def send_data(self, data: bytes) -> None:
        """
        모든 열린 포트로 데이터를 전송합니다 (Broadcasting)

        Args:
            data: 전송할 바이트 데이터
        """
        if not self.workers:
            self.error_occurred.emit("", "No ports are open.")
            return

        for port_name, worker in self.workers.items():
            if worker.isRunning():
                worker.send_data(data)
                self.data_sent.emit(port_name, data)

    def send_data_to_port(self, port_name: str, data: bytes) -> bool:
        """
        특정 포트로 데이터를 전송합니다

        Args:
            port_name: 대상 포트 이름
            data: 전송할 데이터

        Returns:
            bool: 전송 성공 여부
        """
        worker = self.workers.get(port_name)
        if worker and worker.isRunning():
            worker.send_data(data)
            self.data_sent.emit(port_name, data)
            return True
        return False

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

    def set_local_echo(self, state: bool) -> None:
        """
        모든 포트의 Local Echo 신호 설정

        Args:
            state: True면 Local Echo ON, False면 Local Echo OFF
        """
        for worker in self.workers.values():
            worker.set_local_echo(state)
