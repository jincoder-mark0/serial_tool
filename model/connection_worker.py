"""
통신 I/O 워커 모듈입니다.
ITransport 인터페이스를 사용하여 하드웨어 독립적으로 동작합니다.
"""

import time
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QObject
from typing import Optional
from core.interfaces import ITransport
from core.constants import (
    DEFAULT_READ_CHUNK_SIZE,
    BATCH_SIZE_THRESHOLD,
    BATCH_TIMEOUT_MS
)

class ConnectionWorker(QThread):
    """
    ITransport 구현체를 사용하여 데이터를 송수신하는 워커 스레드입니다.
    """

    # 시그널 정의 (범용적인 이름 사용)
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    connection_opened = pyqtSignal(str)
    connection_closed = pyqtSignal(str)

    def __init__(self, transport: ITransport, connection_name: str, parent: Optional[QObject] = None) -> None:
        """
        Args:
            transport: 실제 통신을 담당할 객체 (SerialTransport 등)
            connection_name: 식별 이름 (예: 'COM1')
        """
        super().__init__(parent)
        self.transport = transport
        self.connection_name = connection_name

        self._is_running = False
        self._mutex = QMutex()

    def run(self) -> None:
        """스레드 실행 루프"""
        try:
            # 1. Transport 열기
            if self.transport.open():
                with QMutexLocker(self._mutex):
                    self._is_running = True

                self.connection_opened.emit(self.connection_name)

                # 배치 처리를 위한 버퍼
                batch_buffer = bytearray()
                last_emit_time = time.time() * 1000

                while self.is_running():
                    try:
                        # 2. 데이터 읽기 (Transport 추상화 사용)
                        if self.transport.in_waiting > 0:
                            chunk = self.transport.read(DEFAULT_READ_CHUNK_SIZE)
                            if chunk:
                                batch_buffer.extend(chunk)

                        # 3. 배치 전송 로직
                        current_time = time.time() * 1000
                        time_diff = current_time - last_emit_time

                        if len(batch_buffer) > 0:
                            if len(batch_buffer) >= BATCH_SIZE_THRESHOLD or time_diff >= BATCH_TIMEOUT_MS:
                                self.data_received.emit(bytes(batch_buffer))
                                batch_buffer.clear()
                                last_emit_time = current_time

                        # CPU 부하 방지
                        if len(batch_buffer) == 0:
                            self.msleep(1)
                        else:
                            self.usleep(100)

                    except Exception as e:
                        self.error_occurred.emit(f"IO Error: {str(e)}")
                        break
            else:
                self.error_occurred.emit("Failed to open connection")

        except Exception as e:
            self.error_occurred.emit(f"Connection Error: {str(e)}")
        finally:
            self.close_connection()

    def is_running(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._is_running

    def stop(self) -> None:
        with QMutexLocker(self._mutex):
            self._is_running = False
        self.wait()

    def close_connection(self) -> None:
        """연결을 닫습니다."""
        if self.transport.is_open():
            try:
                self.transport.close()
                self.connection_closed.emit(self.connection_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")

    def send_data(self, data: bytes) -> bool:
        """데이터를 전송합니다 (Thread-safe delegate)."""
        # 주의: write가 블로킹일 경우 별도 큐를 사용하는 것이 좋으나,
        # 현재 구조에서는 직접 호출합니다. (pyserial write는 보통 빠름)
        if self.transport.is_open():
            try:
                self.transport.write(data)
                return True
            except Exception as e:
                self.error_occurred.emit(f"Write Error: {str(e)}")
        return False

    # 하드웨어 제어 메서드 위임
    def set_dtr(self, state: bool) -> None:
        self.transport.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        self.transport.set_rts(state)
