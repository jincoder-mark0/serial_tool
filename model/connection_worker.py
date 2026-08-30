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
        self._write_in_progress = False
        self._write_error: Optional[str] = None

        self._mutex = QMutex()
        self._write_queue = ThreadSafeQueue()  # 비동기 전송용 Queue

    def run(self) -> None:
        """
        Thread 실행 루프

        Logic:
            - Transport 열기 및 연결 확인
            - 수신 데이터 Batch 처리 (크기/시간 기준)
            - 전송 Queue 처리 (비동기 Write)
            - 실제 I/O activity 기준 Sleep/Yield 조절
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
                        # 이번 iteration에서 실제 RX/TX가 수행됐는지 추적한다.
                        # WHY: batch emit 직후 buffer가 비더라도 transport에는 다음 RX가
                        # 이미 대기할 수 있다. 기존 코드는 buffer/queue만 보고 1ms idle
                        # sleep에 들어가 sustained RX 처리량을 불필요하게 제한했다.
                        had_io_activity = False

                        # 2. 데이터 읽기 (Transport 추상화)
                        if self.transport.in_waiting > 0:
                            chunk = self.transport.read(DEFAULT_READ_CHUNK_SIZE)
                            if chunk:
                                batch_buffer.extend(chunk)
                                had_io_activity = True

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
                        # 기존 전량 drain semantics는 유지한다. TX backlog가 RX fairness를
                        # 실제로 해치는 증거가 확인되면 quota는 별도 후보로 분리한다.
                        while not self._write_queue.is_empty():
                            if self._write_next_queued_chunk():
                                had_io_activity = True

                        # 5. CPU 부하 / scheduler stall 균형
                        # 실제 I/O가 있었던 iteration에는 sub-ms sleep을 강제하지 않고
                        # thread yield로 다음 ready thread에 실행 기회를 준다. 새 I/O가
                        # 없으면서 buffered data만 남은 경우에는 기존 busy wait를 유지해
                        # batch timeout 대기 중 무의미한 spin을 피한다.
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
            # close() 이전에 TX 큐를 마지막으로 드레인 (S-039)
            # while 루프는 최상단에서만 is_running()을 확인하므로, msleep(1) 중에
            # stop()이 플래그를 내리면 큐 처리 블록을 한 번도 통과하지 못한 채
            # 여기로 올 수 있다 — 여기서 마저 내보내지 않으면 큐잉 성공(True) 응답을
            # 받은 데이터가 조용히 유실된다.
            self._drain_write_queue_on_exit()
            self.close_connection()

    def _wait_for_next_iteration(
        self,
        *,
        had_io_activity: bool,
        has_buffered_rx: bool,
    ) -> None:
        """이번 loop의 activity/pending 상태에 맞는 scheduling primitive를 선택합니다.

        WHY:
        Windows에서는 ``QThread.usleep(100)`` 같은 sub-millisecond sleep이 scheduler
        granularity 영향으로 약 1 ms급 stall처럼 동작할 수 있습니다. sustained RX에서
        매 read마다 이를 강제하면 worker 처리량이 Serial hardware가 아니라 scheduler
        tick에 의해 제한될 수 있습니다.

        HOW:
        - 이번 iteration에 RX/TX가 실제 수행됨 -> sleep 대신 thread yield
        - 새 I/O는 없지만 emit 전 RX batch 또는 TX queue가 남음 -> 기존 busy wait
        - activity/pending 모두 없음 -> 기존 idle wait

        ``WORKER_IDLE_WAIT_MS`` / ``WORKER_BUSY_WAIT_US`` 값 자체는 그대로 유지하고,
        active I/O path의 scheduling primitive만 변경합니다. 따라서 batch threshold,
        TX drain, shutdown/data-preservation semantics는 건드리지 않습니다.
        """
        if had_io_activity:
            self.yieldCurrentThread()
            return

        if has_buffered_rx or not self._write_queue.is_empty():
            self.usleep(WORKER_BUSY_WAIT_US)
            return

        self.msleep(WORKER_IDLE_WAIT_MS)

    def _drain_write_queue_on_exit(self) -> None:
        """
        종료(run() 루프 탈출) 시 TX 큐에 남은 데이터를 마지막으로 내보냅니다 (S-039).

        Logic:
            - 큐가 비어있으면 아무 것도 하지 않는다.
            - transport가 열려있지 않으면 드레인이 불가능하다 — 남은 항목을
              조용히 버리지 않고 개수를 error_occurred로 표면화한 뒤 큐를 비운다.
            - transport가 열려있으면 큐가 빌 때까지 write()를 반복한다.
            - write() 중 예외(예: write_timeout에 의한 SerialTimeoutException)가
              발생하면 무한 재시도하지 않고, 이미 내보낸 개수/남은 개수와 함께
              error_occurred로 보고한 뒤 큐를 비운다.
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
                if self._write_next_queued_chunk():
                    drained += 1
        except Exception as e:
            # write()가 실패한 청크는 이미 dequeue되어 큐에서 빠진 뒤이므로
            # qsize()에 잡히지 않는다 — 누락 없이 세려면 +1(그 청크 자신)을 더한다.
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
            self._stop_requested = True
            self._is_running = False
        self.wait()

    def close_connection(self) -> None:
        """
        연결 종료 및 리소스 정리

        Logic:
            - Transport가 열려있으면 닫고 connection_closed Signal 발행 (정상 연결 종료를
              의미 — 이 시그널의 의미를 흐리지 않기 위해 실제로 열렸던 경우에만 발행)
            - 에러 발생 시 error_occurred Signal 발행
            - transport가 한 번도 열리지 못한 경우(open() 실패, B-3)에도
              worker_terminated는 항상 발행한다 — 그래야 Controller가 레지스트리
              (workers/parsers/connection_configs)에서 죽은 Worker를 즉시 제거할 수
              있다. 이 경로에서는 connection_closed를 발행하지 않는다: open 실패는
              이미 run()에서 error_occurred로 통지되었으므로, 연결된 적도 없는
              포트에 대해 "Port closed"라는 오인 메시지가 중복 표시되는 것을 막는다.
        """
        if self.transport.is_open():
            try:
                self.transport.close()
                self.connection_closed.emit(self.connection_name)
            except Exception as e:
                self.error_occurred.emit(f"Close Error: {str(e)}")

        # 성공/실패와 무관하게 항상 발행 (레지스트리 정리 전용 신호, S-040/B-3)
        self.worker_terminated.emit(self.connection_name)

    def send_data(self, data: bytes) -> bool:
        """
        데이터 전송 (Non-blocking)

        Logic:
            - 워커 종료 요청 여부만 확인 (transport.is_open()이 아님 — S-037)
              QThread.start() 직후 controller.is_connection_open()은 즉시 True가
              되지만, 실제 OS 스레드가 run()에 진입해 transport.open()을 마치기까지는
              지연이 있다. 그 틈에 들어온 send를 transport.is_open()으로 막으면
              큐잉이 조용히 실패해 데이터가 유실된다. run() 루프는 open 성공 후
              TX 큐를 전량 드레인하므로, 열리기 전에 큐잉해도 순서가 보존된다.
              open이 실패하면 큐는 드레인되지 않고 버려지지만, 이 경우 이미 별도로
              "Failed to open connection" error_occurred가 발행되므로 상태 정보 누락은 아니다.
            - 전송 큐에 데이터 추가

        Args:
            data (bytes): 전송할 바이트 데이터

        Returns:
            bool: Queue 추가 성공 여부
        """
        with QMutexLocker(self._mutex):
            stop_requested = self._stop_requested
        if stop_requested:
            return False
        return self._write_queue.enqueue(data)

    def get_write_queue_size(self) -> int:
        """
        현재 전송 대기 중인 데이터 큐의 크기(청크 개수)를 반환합니다.
        파일 전송 시 Backpressure(역압) 제어에 사용됩니다.

        Returns:
            int: 큐 사이즈
        """
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
        self._broadcast_enabled = state
        self.transport.set_broadcast(state)

    def broadcast_enabled(self) -> bool:
        """
        현재 브로드캐스팅 수신 허용 여부 반환

        Returns:
            bool: 브로드캐스팅 허용 여부
        """
        return self._broadcast_enabled
