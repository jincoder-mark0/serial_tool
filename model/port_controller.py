"""
포트 생명주기 및 설정 관리 클래스.
ConnectionWorker와 UI 사이의 브리지 역할을 수행합니다.
"""
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional

# 변경된 모듈 임포트
from model.connection_worker import ConnectionWorker
from model.transports import SerialTransport
from app_constants import DEFAULT_BAUDRATE

class PortController(QObject):
    # 외부(Presenter)와 통신하는 시그널 (이름 유지)
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    data_received = pyqtSignal(bytes)

    def __init__(self) -> None:
        super().__init__()
        self.worker: Optional[ConnectionWorker] = None
        self._port_name = ""
        self._baudrate = DEFAULT_BAUDRATE

    @property
    def is_open(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def open_port(self, port_name: str, baudrate: int, **kwargs) -> bool:
        """
        시리얼 포트를 엽니다.
        내부적으로 SerialTransport를 생성하여 Worker에 주입합니다.
        """
        if self.is_open:
            self.error_occurred.emit("Port is already open.")
            return False

        self._port_name = port_name
        self._baudrate = baudrate

        # 1. Transport 객체 생성 (여기서 프로토콜 결정 가능)
        # 예: if protocol == 'SPI': transport = SpiTransport(...)
        transport = SerialTransport(port_name, baudrate, config=kwargs)

        # 2. Worker에 Transport 주입 (의존성 주입)
        self.worker = ConnectionWorker(transport, port_name)

        # 3. 시그널 매핑 (Worker 이벤트 -> Controller 시그널)
        self.worker.connection_opened.connect(self.port_opened)
        self.worker.connection_closed.connect(self.port_closed)
        self.worker.error_occurred.connect(self.error_occurred)
        self.worker.data_received.connect(self.data_received)

        self.worker.start()
        return True

    def close_port(self) -> None:
        """
        워커를 정지시키고 리소스를 정리합니다.
        """
        if self.worker:
            self.worker.stop()
            self.worker = None

    def send_data(self, data: bytes) -> None:
        """
        워커로 데이터를 전송합니다.

        Args:
            data (bytes): 전송할 바이트 데이터.
        """
        if self.is_open and self.worker:
            self.worker.send_data(data)
        else:
            self.error_occurred.emit("Port is not open.")

    def set_dtr(self, state: bool) -> None:
        """
        DTR(Data Terminal Ready) 신호를 설정합니다.

        Args:
            state (bool): True면 활성화, False면 비활성화.
        """
        if self.is_open and self.worker:
            self.worker.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """
        RTS(Request To Send) 신호 설정

        Args:
            state (bool): True면 활성화, False면 비활성화.
        """
        if self.is_open and self.worker:
            self.worker.set_rts(state)
