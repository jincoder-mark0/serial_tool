"""
연결 워커 모듈

BaseTransport 인터페이스를 사용하여 하드웨어 독립적인 I/O 처리를 수행합니다.

## WHY
* UI Thread 블로킹 방지 (별도 Thread에서 I/O 처리)
* 효율적인 데이터 처리 (Batch 처리, Queue 기반 전송)
* Thread-safe한 송수신 보장

## WHAT
* 별도 Thread에서 데이터 송수신 루프 실행
* Batch 처리로 Signal 발행 빈도 최적화
* Thread-safe Queue 기반 비동기 전송
* 연결 상태 모니터링 및 이벤트 발행

## HOW
* QThread 상속으로 별도 Thread 실행
* BaseTransport로 하드웨어 추상화
* QMutex로 Thread-safe 상태 관리
"""
import time
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QObject
from typing import Optional
from core.transport.base_transport import BaseTransport
from core.structures import ThreadSafeQueue
from common.constants import (
    DEFAULT_READ_CHUNK_SIZE,
    BATCH_SIZE_THRESHOLD,
    BATCH_TIMEOUT_MS
)

class ConnectionWorker(QThread):
    """
    BaseTransport 기반 데이터 송수신 Worker Thread

    별도 Thread에서 실행되어 UI 블로킹 없이 데이터를 처리합니다.
    """

    # Signal 정의
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    connection_opened = pyqtSignal(str)
    connection_closed = pyqtSignal(str)

    def __init__(self, transport: BaseTransport, connection_name: str, parent: Optional[QObject] = None) -> None:
        """
        ConnectionWorker 초기화

        Args:
            transport (BaseTransport): 하드웨어 전송 계층 구현체
            connection_name (str): 연결 식별 이름 (예: 'COM1')
            parent (Optional[QObject]): 부모 QObject (선택)
        """
        super().__init__(parent)
        self.transport = transport
        self.connection_name = connection_name

        self._is_running = False
        self.broadcast_enableding = False

        self._mutex = QMutex()
        self._write_queue = ThreadSafeQueue() # 비동기 전송용 Queue

    def run(self) -> None:
        """
        Thread 실행 루프

        Logic:
            - Transport 열기 및 연결 확인
            - 수신 데이터 Batch 처리 (크기/시간 기준)
            - 전송 Queue 처리 (비동기 Write)
            - CPU 부하 최소화 (Sleep 조절)
            - 에러 발생 시 안전한 종료 처리
        """
        try:
            # 1. Transport 열기
            if self.transport.open():
                with QMutexLocker(self._mutex):
                    self._is_running = True

                self.connection_opened.emit(self.connection_name)

                # Batch 처리용 버퍼 및 타이머
                batch_buffer = bytearray()
                last_emit_time = time.monotonic() * 1000 # ms 단위

                while self.is_running():
                    try:
                        # 2. 데이터 읽기 (Transport 추상화)
                        if self.transport.in_waiting > 0:
                            chunk = self.transport.read(DEFAULT_READ_CHUNK_SIZE)
                            if chunk:
                                batch_buffer.extend(chunk)

                        # 3. Batch 전송 로직
                        # 조건: 크기 임계값 초과 OR 시간 초과
                        # BATCH_SIZE_THRESHOLD가 상향 조정되어 고속 통신 시 시그널 빈도 감소
                        current_time = time.monotonic() * 1000
                        time_diff = current_time - last_emit_time

                        if len(batch_buffer) > 0:
                            if len(batch_buffer) >= BATCH_SIZE_THRESHOLD or time_diff >= BATCH_TIMEOUT_MS:
                                self.data_received.emit(bytes(batch_buffer))
                                batch_buffer.clear()
                                last_emit_time = current_time

                        # 4. TX Queue 처리 (비동기 전송)
                        while not self._write_queue.is_empty():
                            data = self._write_queue.dequeue()
                            if data:
                                self.transport.write(data)

                        # 5. CPU 부하 방지
                        # 데이터가 없으면 긴 sleep, 있으면 짧은 sleep
                        if len(batch_buffer) == 0 and self._write_queue.is_empty():
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
        """
        Thread 실행 상태 확인 (Thread-safe)

        Returns:
            bool: 실행 중이면 True
        """
        with QMutexLocker(self._mutex):
            return self._is_running

    def stop(self) -> None:
        """Thread 중지 요청 및 대기"""
        with QMutexLocker(self._mutex):
            self._is_running = False
        self.wait()

    def close_connection(self) -> None:
        """
        연결 종료 및 리소스 정리

        Logic:
            - Transport가 열려있으면 닫기
            - connection_closed Signal 발행
            - 에러 발생 시 error_occurred Signal 발행
        """
        if self.transport.is_open():
            try:
                self.transport.close()
                self.connection_closed.emit(self.connection_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")

    def send_data(self, data: bytes) -> bool:
        """
        데이터 전송 (Non-blocking)

        Logic:
            - Transport가 열려있는지 확인
            - 전송 큐에 데이터 추가

        Args:
            data (bytes): 전송할 바이트 데이터

        Returns:
            bool: Queue 추가 성공 여부
        """
        if self.transport.is_open():
            return self._write_queue.enqueue(data)
        return False

    def get_write_queue_size(self) -> int:
        """
        현재 전송 대기 중인 데이터 큐의 크기(청크 개수)를 반환합니다.
        파일 전송 시 Backpressure 제어에 사용됩니다.

        Returns:
            int: 큐 사이즈
        """
        return self._write_queue.qsize()

    # ---------------------------------------------------------
    # 하드웨어 제어 신호 위임
    # ---------------------------------------------------------
    def set_dtr(self, state: bool) -> None:
        """
        DTR(Data Terminal Ready) 신호 설정

        Args:
            state (bool): True=ON, False=OFF
        """
        self.transport.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """
        RTS(Request To Send) 신호 설정

        Args:
            state (bool): True=ON, False=OFF
        """
        self.transport.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        """
        broadcasting 설정

        Args:
            state: True면 broadcasting ON, False면 broadcasting OFF
        """
        self.broadcast_enableding = state
        self.transport.set_broadcast(state)

    def broadcast_enableding(self) -> bool:
        """
        현재 브로드캐스팅 수신 허용 여부 반환

        Returns:
            bool: 브로드캐스팅 허용 여부
        """
        return self.broadcast_enableding
