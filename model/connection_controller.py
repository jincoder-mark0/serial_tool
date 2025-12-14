"""
연결 컨트롤러 모듈

개별 연결 세션의 생명주기와 데이터 흐름을 제어합니다.

## WHY
* 단일 연결에 대한 상태 관리 및 로직 캡슐화 필요
* 하드웨어(Worker)와 UI(Presenter) 사이의 중재자 역할
* 데이터 파싱 및 이벤트 전파의 중심점
* 브로드캐스팅 및 유니캐스트 전송 로직의 중앙화

## WHAT
* 연결 열기/닫기(Open/Close) 관리
* Worker 스레드 관리 및 Transport 주입
* 패킷 파싱(Parser) 연결
* EventBus를 통한 상태 및 데이터 전파

## HOW
* DeviceTransport 구현체(Serial 등)를 생성하여 ConnectionWorker에 주입
* PyQt Signal을 사용하여 비동기 이벤트 처리
* EventBus로 데이터 브로드캐스팅
"""
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List

from model.connection_worker import ConnectionWorker
from model.serial_transport import SerialTransport
from model.packet_parser import ParserFactory, PacketParser
from common.enums import ParserType
from common.dtos import PortConfig # DTO 사용
from common.constants import DEFAULT_BAUDRATE
from core.event_bus import event_bus

class ConnectionController(QObject):
    """
    개별 연결 세션 관리 클래스

    하나의 물리적/논리적 연결에 대한 Worker, Parser, 설정을 총괄합니다.
    """
    # 시그널 정의
    connection_opened = pyqtSignal(str)
    connection_closed = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str)
    data_received = pyqtSignal(str, bytes)
    data_sent = pyqtSignal(str, bytes)
    packet_received = pyqtSignal(str, object)

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
        self.connection_configs: dict[str, PortConfig] = {} # Dict[str, dict] -> Dict[str, PortConfig]

        # 명시적인 활성 연결 상태 관리 변수 (사용자가 선택한 탭)
        self._active_connection_name: Optional[str] = None

        # EventBus 인스턴스
        self.event_bus = event_bus

        # Signal -> EventBus 자동 연결
        self._connect_signals_to_eventbus()

    def _connect_signals_to_eventbus(self) -> None:
        """PyQt Signal 발생 시 자동으로 EventBus 이벤트를 발행하도록 연결합니다."""
        self.connection_opened.connect(lambda n: self.event_bus.publish("port.opened", n))
        self.connection_closed.connect(lambda n: self.event_bus.publish("port.closed", n))
        self.error_occurred.connect(
            lambda n, m: self.event_bus.publish("port.error", {'port': n, 'message': m})
        )

        self.data_received.connect(
            lambda n, d: self.event_bus.publish("port.data_received", {'port': n, 'data': d})
        )

        self.data_sent.connect(
            lambda n, d: self.event_bus.publish("port.data_sent", {'port': n, 'data': d})
        )

        self.packet_received.connect(
            lambda n, pkt: self.event_bus.publish("port.packet_received", {'port': n, 'packet': pkt})
        )

    @property
    def has_active_connection(self) -> bool:
        """
        하나라도 활성화된 연결이 있는지 확인
        """
        return len(self.workers) > 0

    @property
    def current_connection_name(self) -> Optional[str]:
        """
        현재 **명시적으로 활성화된** 연결 이름을 반환합니다.

        Logic:
            - `set_active_connection`으로 설정된 이름을 반환
            - 설정된 이름이 없다면, 첫 번째 워커의 이름을 반환 (Fallback)

        Returns:
            Optional[str]: 활성 연결 이름.
        """
        if self._active_connection_name and self._active_connection_name in self.workers:
            return self._active_connection_name

        # Fallback: 명시적으로 설정된 이름이 없으면 첫 번째 워커 이름 반환
        if self.workers:
            return list(self.workers.keys())[0]

        return None

    def set_active_connection(self, name: str) -> None:
        """
        현재 활성 탭에 해당하는 연결을 명시적으로 설정합니다.

        Args:
            name (str): 활성 연결 이름 (보통 포트 이름).
        """
        self._active_connection_name = name

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
            - DeviceTransport 생성
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
            self.error_occurred.emit("", "Connection name(port) is required.")
            return False

        # 중복 열기 방지
        if self.is_connection_open(name):
            self.error_occurred.emit(name, "Connection is already open.")
            return False

        # SerialTransport 생성 (Config DTO 속성 사용)
        # 기존 SerialTransport가 dict를 받도록 되어 있다면 DTO -> dict 변환 필요할 수 있음
        # 여기서는 편의상 SerialTransport가 config dict를 받는다고 가정하고 변환
        transport_config = {
            "bytesize": config.bytesize,
            "parity": config.parity,
            "stopbits": config.stopbits,
            "flowctrl": config.flowctrl
        }

        # 추후 SerialTransport도 DTO를 받도록 리팩토링 권장
        transport = SerialTransport(name, config.baudrate, config=transport_config)

        # Worker에 Transport 주입
        worker = ConnectionWorker(transport, name)

        # Parser 생성 (기본 Raw)
        self.parsers[name] = ParserFactory.create_parser(ParserType.RAW)
        self.connection_configs[name] = config

        # 시그널 매핑
        worker.connection_opened.connect(lambda n=name: self.connection_opened.emit(n))
        worker.connection_closed.connect(self.on_worker_closed)
        worker.error_occurred.connect(lambda msg, n=name: self.error_occurred.emit(n, msg))
        worker.data_received.connect(lambda data, n=name: self._handle_data_received(n, data))

        self.workers[name] = worker
        worker.start()

        # 새 연결이 열리면 해당 연결을 활성 연결로 설정 (탭이 열릴 때)
        self.set_active_connection(name)

        return True

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
        self.data_received.emit(name, data)

        parser = self.parsers.get(name)
        if parser:
            packets = parser.parse(data)
            for packet in packets:
                self.packet_received.emit(name, packet)

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

        # 닫힌 연결이 활성 연결이었다면, 활성 연결 상태 초기화
        if self._active_connection_name == name:
            self._active_connection_name = None

        self.connection_closed.emit(name)

    def close_connection(self, name: Optional[str] = None) -> None:
        """
        연결을 종료합니다.

        Args:
            name: 종료할 연결 이름. None이면 모든 연결 종료.
        """
        if name:
            worker = self.workers.get(name)
            if worker:
                worker.stop()
        else:
            # 모든 포트 닫기 (복사본으로 순회하여 안전하게 삭제)
            for name in list(self.workers.keys()):
                self.close_connection(name)

    def send_data(self, data: bytes, is_broadcast: bool = False) -> None:
        if not self.workers:
            self.error_occurred.emit("", "No active connections.")
            return
        if is_broadcast:
            self.send_data_to_all(data)
        else:
            active_name = self.current_connection_name
            if active_name:
                self.send_data_to_connection(active_name, data)
            else:
                self.error_occurred.emit("", "Cannot send data: No active connection selected.")

    def send_data_to_broadcasting(self, data: bytes) -> None:
        """
        broadcasting 활성 연결로 데이터 Broadcasting

        Logic:
            - 현재 broadcasting 활성화된 워커 리스트를 순회하며 데이터를 전송
            - send_data_to 메서드를 호출하여 실제 전송 수행

        Args:
            data: 전송할 바이트 데이터
        """
        if not self.workers:
            self.error_occurred.emit("", "No active connections.")
            return

        for name, worker in self.workers.items():
            if worker.isRunning() and worker.is_broadcasting():
                # TODO : broadcasting 설정 확인 로직 추가 필요
                self.send_data_to_connection(name, data)

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
            self.data_sent.emit(name, data)
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

    def set_broadcast(self, state: bool) -> None:
        """
        모든 포트의 broadcasting 설정

        Args:
            state: True면 broadcasting ON, False면 broadcasting OFF
        """
        for worker in self.workers.values():
            worker.set_broadcast(state)