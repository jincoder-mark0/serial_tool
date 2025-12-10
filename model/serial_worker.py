"""
시리얼 통신 워커 모듈입니다.

실제 시리얼 포트 입출력을 담당하며, 별도의 스레드에서 동작합니다.
배치 처리를 통해 고속 데이터 수신 시 UI 성능 저하를 방지합니다.
"""

import time
import serial
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QObject
from typing import Optional

from core.constants import (
    DEFAULT_READ_CHUNK_SIZE,
    BATCH_SIZE_THRESHOLD,
    BATCH_TIMEOUT_MS
)

class SerialWorker(QThread):
    """
    시리얼 포트 I/O를 처리하는 워커 스레드입니다.
    Non-blocking 읽기 및 배치 전송을 지원합니다.
    """

    # 시그널 정의
    data_received = pyqtSignal(bytes)  # 수신 데이터 (배치 처리됨)
    error_occurred = pyqtSignal(str)   # 에러 메시지
    port_opened = pyqtSignal(str)      # 포트 열림 알림
    port_closed = pyqtSignal(str)      # 포트 닫힘 알림

    def __init__(self, port_name: str, baudrate: int, parent: Optional[QObject] = None) -> None:
        """
        SerialWorker를 초기화합니다.

        Args:
            port_name (str): 포트 이름 (예: 'COM1').
            baudrate (int): 통신 속도.
            parent (Optional[QObject]): 부모 객체.
        """
        super().__init__(parent)
        self.port_name = port_name
        self.baudrate = baudrate
        self.serial_port: Optional[serial.Serial] = None

        # 스레드 제어 변수 (Mutex로 보호)
        self._is_running = False
        self._mutex = QMutex()

        # 설정 (기본값)
        self.bytesize = serial.EIGHTBITS
        self.stopbits = serial.STOPBITS_ONE
        self.parity = serial.PARITY_NONE
        self.flowctrl = False # RTS/CTS

    def run(self) -> None:
        """
        스레드 실행 루프입니다.
        데이터를 읽고 배치 조건(크기 또는 시간)을 만족하면 시그널을 보냅니다.
        """
        try:
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=0,  # Non-blocking Read
                xonxoff=False,
                rtscts=self.flowctrl,
                dsrdtr=False
            )

            if self.serial_port.is_open:
                with QMutexLocker(self._mutex):
                    self._is_running = True

                self.port_opened.emit(self.port_name)

                # 배치 처리를 위한 버퍼 및 타이머 변수
                batch_buffer = bytearray()
                last_emit_time = time.time() * 1000  # ms 단위

                while self.is_running():
                    try:
                        # 1. 데이터 읽기 (Non-blocking)
                        if self.serial_port.in_waiting > 0:
                            # 큐에 있는 데이터를 덩어리로 읽음
                            chunk = self.serial_port.read(min(self.serial_port.in_waiting, DEFAULT_READ_CHUNK_SIZE))
                            if chunk:
                                batch_buffer.extend(chunk)

                        current_time = time.time() * 1000
                        time_diff = current_time - last_emit_time

                        # 2. 배치 전송 조건 확인
                        # 조건 A: 버퍼가 임계값 이상 쌓였을 때
                        # 조건 B: 데이터가 있고, 일정 시간이 지났을 때 (Timeout)
                        if len(batch_buffer) > 0:
                            if len(batch_buffer) >= BATCH_SIZE_THRESHOLD or time_diff >= BATCH_TIMEOUT_MS:
                                self.data_received.emit(bytes(batch_buffer))
                                batch_buffer.clear()
                                last_emit_time = current_time

                        # CPU 점유율 방지를 위한 짧은 대기
                        # 데이터가 없을 때는 조금 더 길게 대기 가능
                        if len(batch_buffer) == 0:
                            self.msleep(1)
                        else:
                            self.usleep(100) # 데이터가 들어오는 중이면 짧게 대기

                    except Exception as e:
                        self.error_occurred.emit(f"Read Error: {str(e)}")
                        break

        except serial.SerialException as e:
            self.error_occurred.emit(f"Open Error: {str(e)}")
        finally:
            self.close_port()

    def is_running(self) -> bool:
        """
        스레드 실행 상태를 반환합니다 (Thread-safe).

        Returns:
            bool: 실행 중이면 True.
        """
        with QMutexLocker(self._mutex):
            return self._is_running

    def stop(self) -> None:
        """스레드 중지를 요청합니다."""
        with QMutexLocker(self._mutex):
            self._is_running = False
        self.wait() # 스레드 종료 대기

    def close_port(self) -> None:
        """포트를 닫고 리소스를 정리합니다."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.port_closed.emit(self.port_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")
        self.serial_port = None

    def send_data(self, data: bytes) -> bool:
        """
        데이터를 전송합니다 (스레드 안전).

        Args:
            data (bytes): 전송할 데이터.

        Returns:
            bool: 성공 시 True, 실패 시 False.
        """
        # Serial 객체 자체는 내부적으로 락이 있을 수 있으나,
        # 안전을 위해 포트 상태 확인과 쓰기를 묶어서 처리
        # (주의: write는 블로킹될 수 있으므로 뮤텍스 범위 주의)

        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data)
                return True
            except Exception as e:
                self.error_occurred.emit(f"Write Error: {str(e)}")
        return False

    def set_dtr(self, state: bool) -> None:
        """DTR 신호를 설정합니다."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.dtr = state

    def set_rts(self, state: bool) -> None:
        """RTS 신호를 설정합니다."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.rts = state
