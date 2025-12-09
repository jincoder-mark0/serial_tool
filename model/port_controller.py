from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional
from model.serial_worker import SerialWorker
from core.utils import ThreadSafeQueue

class PortController(QObject):
    """
    시리얼 포트의 생명주기를 관리하고 포트 설정을 처리하는 클래스입니다.
    Presenter와 SerialWorker 사이의 브리지 역할을 수행합니다.

    Signals:
        port_opened(str): 포트가 열렸을 때 발생 (포트 이름)
        port_closed(str): 포트가 닫혔을 때 발생 (포트 이름)
        error_occurred(str): 에러 발생 시 발생 (에러 메시지)
        data_received(bytes): 데이터 수신 시 발생 (수신 데이터)
    """
    # 시그널 정의
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    data_received = pyqtSignal(bytes)

    def __init__(self) -> None:
        """
        PortController를 초기화합니다.
        SerialWorker와 송신 큐를 초기화합니다.
        """
        super().__init__()
        self.worker: Optional[SerialWorker] = None
        self.tx_queue = ThreadSafeQueue()
        self._port_name = ""
        self._baudrate = 115200

    @property
    def is_open(self) -> bool:
        """
        포트가 열려있는지 확인합니다.

        Returns:
            bool: 포트가 열려있고 작동 중이면 True, 아니면 False.
        """
        return self.worker is not None and self.worker.isRunning()

    def open_port(self, port_name: str, baudrate: int) -> bool:
        """
        시리얼 포트를 엽니다.

        Args:
            port_name (str): 포트 이름 (예: 'COM3', '/dev/ttyUSB0').
            baudrate (int): 통신 속도 (예: 115200).

        Returns:
            bool: 성공 시 True, 실패 시 False.
        """
        if self.is_open:
            self.error_occurred.emit("Port is already open.")
            return False

        self._port_name = port_name
        self._baudrate = baudrate

        self.worker = SerialWorker(port_name, baudrate)

        # 시그널 연결
        self.worker.port_opened.connect(self.port_opened)
        self.worker.port_closed.connect(self.port_closed)
        self.worker.error_occurred.connect(self.error_occurred)
        self.worker.data_received.connect(self.data_received)

        self.worker.start()
        return True

    def close_port(self) -> None:
        """
        시리얼 포트를 닫습니다.
        SerialWorker를 정지시키고 리소스를 정리합니다.
        """
        if self.worker:
            self.worker.stop()
            self.worker = None

    def send_data(self, data: bytes) -> None:
        """
        시리얼 포트로 데이터를 전송합니다.

        Args:
            data (bytes): 전송할 바이트 데이터.
        """
        if self.is_open and self.worker:
            self.worker.write_data(data)
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
        RTS(Request To Send) 신호를 설정합니다.

        Args:
            state (bool): True면 활성화, False면 비활성화.
        """
        if self.is_open and self.worker:
            self.worker.set_rts(state)
