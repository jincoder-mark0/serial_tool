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
    BATCH_TIMEOUT_MS,
    WORKER_IDLE_WAIT_MS,
    WORKER_BUSY_WAIT_US,
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
    worker_terminated = pyqtSignal(str)  # 스레드 종료 통지(성공/실패 무관, 레지스트리 정리용, S-040)

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
        self._stop_requested = False
        self._broadcast_enabled = False

        self._mutex = QMutex()
        self._write_queue = ThreadSafeQueue()  # 비동기 전송용 Queue

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
        batch_buffer = bytearray()

        try:
            # 1. Transport 열기
            if self.transport.open():
                with QMutexLocker(self._mutex):
                    self._is_running = not self._stop_requested

                if self.is_running():
                    self.connection_opened.emit(self.connection_name)

                # Batch 처리용 버퍼 및 타이머
                last_emit_time = time.monotonic() * 1000  # ms 단위

                while self.is_running():
                    try:
                        # 2. 데이터 읽기 (Transport 추상화)
                        if self.transport.in_waiting > 0:
                            chunk = self.transport.read(DEFAULT_READ_CHUNK_SIZE)
                            if chunk:
                                batch_buffer.extend(chunk)

                        # 3. Batch 전송 로직
                        # 조건: 크기 임계값 초과 OR 시간 초과
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

                        # 5. CPU 부하 방지 — 타이밍 정책은 common.constants가 정본이다.
                        if len(batch_buffer) == 0 and self._write_queue.is_empty():
                            self.msleep(WORKER_IDLE_WAIT_MS)
                        else:
                            self.usleep(WORKER_BUSY_WAIT_US)

                    except Exception as e:
                        self.error_occurred.emit(f"IO Error: {str(e)}")
                        break
            else:
                self.error_occurred.emit("Failed to open connection")

        except Exception as e:
            self.error_occurred.emit(f"Connection Error: {str(e)}")
        finally:
            if batch_buffer:
                self.data_received.emit(bytes(batch_buffer))
            # close() 이전에 TX 큐를 마지막으로 드레인 (S-039)
            self._drain_write_queue_on_exit()
            self.close_connection()

    def _drain_write_queue_on_exit(self) -> None:
        """
        종료(run() 루프 탈출) 시 TX 큐에 남은 데이터를 마지막으로 내보냅니다 (S-039).
        """
        remaining = self._write_queue.qsize()
        if remaining == 0:
            return

        if not self.transport.is_open():
            self._write_queue.clear()
            self.error_occurred.emit(
                f"TX queue drain skipped on close: transport already closed, "
                f"{remaining} pending chunk(s) discarded"
            )
            return

        drained = 0
        try:
            while not self._write_queue.is_empty():
                data = self._write_queue.dequeue()
                if data:
                    self.transport.write(data)
                    drained += 1
        except Exception as e:
            failed_and_left = self._write_queue.qsize() + 1
            self._write_queue.clear()
            self.error_occurred.emit(
                f"TX queue drain failed on close after {drained} chunk(s) sent, "
                f"{failed_and_left} chunk(s) discarded: {str(e)}"
            )

    def is_running(self) -> bool:
        """현재 Worker 실행 상태를 thread-safe하게 반환합니다."""
        with QMutexLocker(self._mutex):
            return self._is_running

    def stop(self) -> None:
        """Thread 중지 요청 및 대기."""
        with QMutexLocker(self._mutex):
            self._stop_requested = True
            self._is_running = False
        self.wait()

    def close_connection(self) -> None:
        """연결 종료 및 리소스 정리를 수행합니다."""
        if self.transport.is_open():
            try:
                self.transport.close()
                self.connection_closed.emit(self.connection_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")

        # 성공/실패와 무관하게 항상 발행 (레지스트리 정리 전용 신호, S-040/B-3)
        self.worker_terminated.emit(self.connection_name)

    def send_data(self, data: bytes) -> bool:
        """데이터를 비동기 TX Queue에 추가합니다."""
        with QMutexLocker(self._mutex):
            stop_requested = self._stop_requested
        if stop_requested:
            return False
        return self._write_queue.enqueue(data)

    def get_write_queue_size(self) -> int:
        """현재 전송 대기 중인 TX Queue 크기를 반환합니다."""
        return self._write_queue.qsize()

    # ---------------------------------------------------------
    # 하드웨어 제어 신호 위임
    # ---------------------------------------------------------
    def set_dtr(self, state: bool) -> None:
        """DTR(Data Terminal Ready) 신호를 설정합니다."""
        self.transport.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """RTS(Request To Send) 신호를 설정합니다."""
        self.transport.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        """broadcasting 설정을 변경합니다."""
        self._broadcast_enabled = state
        self.transport.set_broadcast(state)

    def broadcast_enabled(self) -> bool:
        """현재 브로드캐스팅 수신 허용 여부를 반환합니다."""
        return self._broadcast_enabled
