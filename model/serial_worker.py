import serial
import time
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QObject
from typing import Optional

class SerialWorker(QThread):
    """
    시리얼 포트에서 데이터를 지속적으로 읽어오는 워커 스레드 클래스입니다.
    """
    # 시그널 정의
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)

    def __init__(self, port_name: str, baudrate: int, parent: Optional[QObject] = None) -> None:
        """
        SerialWorker를 초기화합니다.

        Args:
            port_name (str): 포트 이름.
            baudrate (int): 통신 속도.
            parent (Optional[QObject]): 부모 객체. 기본값은 None.
        """
        super().__init__(parent)
        self.port_name = port_name
        self.baudrate = baudrate
        self.serial_port: Optional[serial.Serial] = None
        self._is_running = False
        self._mutex = QMutex()

        # 설정 (Settings)
        self.data_bits = serial.EIGHTBITS
        self.stop_bits = serial.STOPBITS_ONE
        self.parity = serial.PARITY_NONE
        self.flow = False # RTS/CTS

    def run(self) -> None:
        """스레드 실행 루프입니다."""
        try:
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                datasize=self.data_bits,
                parity=self.parity,
                stopbits=self.stop_bits,
                timeout=0.1, # 비차단 읽기를 위한 짧은 타임아웃
                xonxoff=False,
                rtscts=self.flow,
                dsrdtr=False
            )

            if self.serial_port.is_open:
                self._is_running = True
                self.port_opened.emit(self.port_name)

                while self._is_running:
                    try:
                        if self.serial_port.in_waiting > 0:
                            data = self.serial_port.read(self.serial_port.in_waiting)
                            if data:
                                self.data_received.emit(data)
                        else:
                            # CPU 점유율 방지를 위한 짧은 대기
                            self.msleep(10)
                    except Exception as e:
                        self.error_occurred.emit(f"Read Error: {str(e)}")
                        break

        except serial.SerialException as e:
            self.error_occurred.emit(f"Open Error: {str(e)}")
        finally:
            self.close_port()

    def stop(self) -> None:
        """스레드 중지를 요청합니다."""
        with QMutexLocker(self._mutex):
            self._is_running = False
        self.wait() # 스레드 종료 대기

    def close_port(self) -> None:
        """포트를 닫습니다."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.port_closed.emit(self.port_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")
        self.serial_port = None

    def write_data(self, data: bytes) -> bool:
        """
        데이터를 전송합니다 (스레드 안전).

        Args:
            data (bytes): 전송할 데이터.

        Returns:
            bool: 성공 시 True, 실패 시 False.
        """
        with QMutexLocker(self._mutex):
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.write(data)
                    return True
                except Exception as e:
                    self.error_occurred.emit(f"Write Error: {str(e)}")
        return False

    def set_dtr(self, state: bool) -> None:
        """
        DTR 신호를 설정합니다.

        Args:
            state (bool): 상태 값.
        """
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.dtr = state

    def set_rts(self, state: bool) -> None:
        """
        RTS 신호를 설정합니다.

        Args:
            state (bool): 상태 값.
        """
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.rts = state
