"""
연결 워커 모듈

BaseTransport 인터페이스를 사용하여 하드웨어 독립적인 I/O 처리를 수행합니다.

## WHY
* UI Thread 블로킹 방지 (별도 Thread에서 I/O 처리)
* 효율적인 데이터 처리 (Batch 처리, Queue 기반 전송)
* Thread-safe한 송수신 보장
* TX backlog가 지속될 때도 RX 확인 기회를 보장해 Full-Duplex fairness 유지

## WHAT
* 별도 Thread에서 데이터 송수신 루프 실행
* Batch 처리로 Signal 발행 빈도 최적화
* Thread-safe Queue 기반 비동기 전송
* bounded TX time budget으로 RX starvation 방지
* 연결 상태 모니터링 및 이벤트 발행

## HOW
* QThread 상속으로 별도 Thread 실행
* BaseTransport로 하드웨어 추상화
* QMutex로 Thread-safe 상태 관리
* 각 I/O loop에서 RX를 먼저 확인한 뒤 TX는 제한된 시간 budget만 처리
"""
import time
from typing import Optional

from PyQt5.QtCore import QObject, QMutex, QMutexLocker, QThread, pyqtSignal

from common.constants import (
    BATCH_SIZE_THRESHOLD,
    BATCH_TIMEOUT_MS,
    DEFAULT_READ_CHUNK_SIZE,
    WORKER_BUSY_WAIT_US,
    WORKER_IDLE_WAIT_MS,
)
from core.structures import ThreadSafeQueue
from core.transport.base_transport import BaseTransport


class ConnectionWorker(QThread):
    """BaseTransport 기반 데이터 송수신 Worker Thread."""

    # 한 loop에서 TX가 CPU/I/O 경로를 독점할 수 있는 최대 시간.
    # 첫 chunk는 budget 초과 여부와 무관하게 항상 1개 처리하므로 저속/큰 write도 진행된다.
    # 이후에는 약 1 ms마다 RX polling 기회를 다시 확보한다.
    _TX_FAIRNESS_BUDGET_S = 0.001

    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    connection_opened = pyqtSignal(str)
    connection_closed = pyqtSignal(str)
    worker_terminated = pyqtSignal(str)

    def __init__(
        self,
        transport: BaseTransport,
        connection_name: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.transport = transport
        self.connection_name = connection_name

        self._is_running = False
        self._stop_requested = False
        self._broadcast_enabled = False
        self._write_in_progress = False
        self._write_error: Optional[str] = None

        self._mutex = QMutex()
        self._write_queue = ThreadSafeQueue()

    def run(self) -> None:
        """RX 우선 + bounded TX budget으로 non-blocking I/O loop를 실행합니다."""
        batch_buffer = bytearray()

        try:
            if self.transport.open():
                with QMutexLocker(self._mutex):
                    self._is_running = not self._stop_requested

                if self.is_running():
                    self.connection_opened.emit(self.connection_name)

                last_emit_time = time.monotonic() * 1000

                while self.is_running():
                    try:
                        had_io_activity = False

                        # 1. RX를 먼저 확인한다.
                        # WHY: TX backlog가 길어져도 매 outer-loop마다 수신 기회를 보장한다.
                        if self.transport.in_waiting > 0:
                            chunk = self.transport.read(DEFAULT_READ_CHUNK_SIZE)
                            if chunk:
                                batch_buffer.extend(chunk)
                                had_io_activity = True

                        # 2. RX Batch emit 조건 확인.
                        current_time = time.monotonic() * 1000
                        time_diff = current_time - last_emit_time
                        if batch_buffer and (
                            len(batch_buffer) >= BATCH_SIZE_THRESHOLD
                            or time_diff >= BATCH_TIMEOUT_MS
                        ):
                            self.data_received.emit(bytes(batch_buffer))
                            batch_buffer.clear()
                            last_emit_time = current_time

                        # 3. TX는 queue 전량 drain 대신 time budget만큼 처리한다.
                        # WHY: 느린 write 또는 큰 backlog가 같은 port의 RX polling을
                        # 장시간 막는 구조적 starvation을 제거한다.
                        if self._process_tx_budget():
                            had_io_activity = True

                        # 4. 실제 I/O가 있었으면 즉시 yield, 아니면 pending 상태에 맞춰 대기.
                        self._wait_for_next_iteration(
                            had_io_activity=had_io_activity,
                            has_buffered_rx=bool(batch_buffer),
                        )

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

            # 정상 loop에서는 fairness를 위해 bounded TX를 사용하지만 종료 시에는
            # 큐잉 성공한 데이터 보존이 더 중요하므로 기존처럼 남은 TX를 끝까지 drain한다.
            self._drain_write_queue_on_exit()
            self.close_connection()

    def _process_tx_budget(self) -> bool:
        """현재 outer-loop에서 TX를 제한된 시간만 처리합니다.

        첫 chunk는 반드시 처리합니다. 그 뒤 queue가 남아 있어도 elapsed time이
        ``_TX_FAIRNESS_BUDGET_S`` 이상이면 반환해 다음 RX polling 기회를 제공합니다.

        Returns:
            bool: 하나 이상의 TX chunk가 실제 write되었으면 True.
        """
        if self._write_queue.is_empty():
            return False

        started = time.perf_counter()
        wrote_any = False

        while not self._write_queue.is_empty():
            if self._write_next_queued_chunk():
                wrote_any = True

            if time.perf_counter() - started >= self._TX_FAIRNESS_BUDGET_S:
                break

        return wrote_any

    def _wait_for_next_iteration(
        self,
        *,
        had_io_activity: bool,
        has_buffered_rx: bool,
    ) -> None:
        """이번 loop의 activity/pending 상태에 맞는 scheduling primitive를 선택합니다."""
        if had_io_activity:
            self.yieldCurrentThread()
            return

        if has_buffered_rx or not self._write_queue.is_empty():
            self.usleep(WORKER_BUSY_WAIT_US)
            return

        self.msleep(WORKER_IDLE_WAIT_MS)

    def _drain_write_queue_on_exit(self) -> None:
        """종료 시 TX 큐에 남은 데이터를 마지막으로 내보냅니다."""
        remaining = self._write_queue.qsize()
        if remaining == 0:
            return

        if not self.transport.is_open():
            self._write_queue.clear()
            self.error_occurred.emit(
                "TX queue drain skipped on close: transport already closed, "
                f"{remaining} pending chunk(s) discarded"
            )
            return

        drained = 0
        try:
            while not self._write_queue.is_empty():
                if self._write_next_queued_chunk():
                    drained += 1
        except Exception as e:
            failed_and_left = self._write_queue.qsize() + 1
            self._write_queue.clear()
            self.error_occurred.emit(
                f"TX queue drain failed on close after {drained} chunk(s) sent, "
                f"{failed_and_left} chunk(s) discarded: {str(e)}"
            )

    def _write_next_queued_chunk(self) -> bool:
        """다음 TX chunk의 dequeue부터 transport.write 반환까지 in-flight로 표시합니다."""
        with QMutexLocker(self._mutex):
            self._write_in_progress = True
        try:
            data = self._write_queue.dequeue()
            if not data:
                return False
            self.transport.write(data)
            return True
        except Exception as exc:
            with QMutexLocker(self._mutex):
                self._write_error = str(exc)
            raise
        finally:
            with QMutexLocker(self._mutex):
                self._write_in_progress = False

    def is_running(self) -> bool:
        """Thread 실행 상태를 thread-safe하게 반환합니다."""
        with QMutexLocker(self._mutex):
            return self._is_running

    def request_stop(self) -> None:
        """종료를 요청하고 **즉시 반환**합니다 (대기 없음).

        WHY:
            큐에 남은 TX는 worker thread가 `run()`의 finally에서 끝까지 내보낸다.
            즉 드레인에 호출자의 thread는 필요하지 않다. 그런데 과거 `stop()`은
            무조건 `wait()`를 걸어, 포트를 닫는 UI thread가 드레인이 끝날 때까지
            멈췄다 — 저속 포트에 backlog가 쌓여 있으면 그만큼 창이 얼어붙는다.

            요청과 대기를 분리하면 **데이터는 그대로 다 내보내면서** UI는 기다리지
            않는다. 실제 종료는 `worker_terminated` signal로 알린다.
        """
        with QMutexLocker(self._mutex):
            self._stop_requested = True
            self._is_running = False

    def stop(self, timeout_ms: Optional[int] = None) -> bool:
        """종료를 요청하고 thread가 실제로 끝날 때까지 기다립니다.

        Args:
            timeout_ms: 대기 상한(ms). None이면 종료까지 무한 대기한다.

        Returns:
            bool: thread가 실제로 종료됐으면 True.
        """
        self.request_stop()
        if timeout_ms is None:
            self.wait()
            return True
        return self.wait(timeout_ms)

    def close_connection(self) -> None:
        """Transport를 닫고 lifecycle signal을 정리합니다."""
        if self.transport.is_open():
            try:
                self.transport.close()
                self.connection_closed.emit(self.connection_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")

        self.worker_terminated.emit(self.connection_name)

    def send_data(self, data: bytes) -> bool:
        """데이터를 non-blocking TX queue에 추가합니다."""
        with QMutexLocker(self._mutex):
            stop_requested = self._stop_requested
        if stop_requested:
            return False
        return self._write_queue.enqueue(data)

    def get_write_queue_size(self) -> int:
        """현재 전송 대기 중인 TX chunk 개수를 반환합니다."""
        return self._write_queue.qsize()

    def is_write_idle(self) -> bool:
        """대기 Queue와 실제 transport write가 모두 끝났는지 반환합니다."""
        with QMutexLocker(self._mutex):
            write_in_progress = self._write_in_progress
        return not write_in_progress and self._write_queue.is_empty()

    def get_write_error(self) -> Optional[str]:
        """현재 세션에서 발생한 terminal transport write 오류를 반환합니다."""
        with QMutexLocker(self._mutex):
            return self._write_error

    def set_dtr(self, state: bool) -> None:
        """DTR(Data Terminal Ready) 신호를 Transport에 위임합니다."""
        self.transport.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        """RTS(Request To Send) 신호를 Transport에 위임합니다."""
        self.transport.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        """Broadcast 대상 허용 상태를 설정합니다."""
        self._broadcast_enabled = state
        self.transport.set_broadcast(state)

    def broadcast_enabled(self) -> bool:
        """현재 broadcast 대상 허용 여부를 반환합니다."""
        return self._broadcast_enabled
