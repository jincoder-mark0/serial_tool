"""TX 큐 상한과 backpressure 계약 테스트.

## WHY
상한이 없으면 `send_data()`가 **항상** 성공을 돌려준다. 그래서 "큐잉 성공"이
"전송 성공"을 뜻하지 않았다 — 생산자는 포트가 감당하지 못하는 속도로 계속 쌓을 수
있었고, 실제로 못 보냈다는 사실은 한참 뒤에야(또는 전혀) 드러나지 않았다.
큐가 무한정 자라는 것도 같은 문제의 다른 얼굴이다.

`ThreadSafeQueue.enqueue()`는 가득 찼을 때 **가장 오래된 것을 버리지 않고 False를
돌려준다**. 조용히 버리면 그 순간 유실이지만, 거절하면 생산자가 즉시 알고 늦출 수
있다. 여기에 `TX_QUEUE_MAX_BYTES` 상한을 걸어 그 성질을 실제로 쓰게 했다.

## WHAT
* 상한에 닿으면 enqueue가 거절하고, 기존 데이터는 그대로 남는가 (버리지 않는가)
* 드레인으로 자리가 나면 다시 받는가
* 큐가 가득 찬 것과 포트가 닫힌 것을 호출자가 구분할 수 있는가
  — 구분하지 못하면 일시적 backpressure에 전송을 중단하게 된다
* 큐 가득참이 조용히 False로 끝나지 않고 표면화되는가
"""
import time
from threading import Event

from common.constants import TX_QUEUE_MAX_BYTES
from common.dtos import PortConfig
from core.structures import ThreadSafeQueue
from core.transport.base_transport import BaseTransport
from model.connection_controller import ConnectionController
from model.connection_worker import ConnectionWorker

PORT = "COM-BP"


class _NeverDrainsTransport(BaseTransport):
    """열려 있지만 write가 붙잡혀 끝나지 않는 transport (드레인 정지 상황)."""

    def __init__(self) -> None:
        self._open = False
        self.release = Event()

    def open(self) -> bool:
        self._open = True
        return True

    def close(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def read(self, size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        self.release.wait(5)

    @property
    def in_waiting(self) -> int:
        return 0


# --------------------------------------------------------------------------
# ThreadSafeQueue: 바이트 상한 자체의 계약
# --------------------------------------------------------------------------

def test_queue_rejects_instead_of_dropping_oldest_when_byte_limit_is_reached():
    """
    상한에 닿으면 **거절**해야 한다. 오래된 것을 버리면 그 순간이 곧 유실이다.
    """
    queue = ThreadSafeQueue(max_bytes=10)

    assert queue.enqueue(b"12345") is True
    assert queue.enqueue(b"67890") is True
    assert queue.total_bytes() == 10
    assert queue.is_full() is True

    assert queue.enqueue(b"X") is False, "상한을 넘겼는데 받아들였다"

    # 거절했을 뿐 기존 데이터는 그대로여야 한다.
    assert queue.qsize() == 2
    assert queue.dequeue() == b"12345"
    assert queue.dequeue() == b"67890"


def test_queue_accepts_again_after_draining_frees_space():
    """드레인으로 자리가 나면 다시 받아야 한다 — 영구 차단이 아니다."""
    queue = ThreadSafeQueue(max_bytes=8)

    assert queue.enqueue(b"AAAABBBB") is True
    assert queue.enqueue(b"C") is False

    assert queue.dequeue() == b"AAAABBBB"
    assert queue.total_bytes() == 0
    assert queue.enqueue(b"C") is True


def test_clear_resets_the_byte_accounting():
    """clear가 바이트 집계를 놓치면 큐가 비었는데도 가득 찬 것으로 보인다."""
    queue = ThreadSafeQueue(max_bytes=4)
    assert queue.enqueue(b"ABCD") is True

    queue.clear()

    assert queue.total_bytes() == 0
    assert queue.is_full() is False
    assert queue.enqueue(b"EFGH") is True


def test_unbounded_queue_keeps_previous_behaviour():
    """max_bytes를 주지 않으면 기존처럼 무제한이어야 한다 (기존 호출자 보호)."""
    queue = ThreadSafeQueue()
    for _ in range(1000):
        assert queue.enqueue(b"X" * 1024) is True
    assert queue.is_full() is False


# --------------------------------------------------------------------------
# ConnectionWorker / ConnectionController: 상한 적용과 표면화
# --------------------------------------------------------------------------

def test_worker_send_data_is_rejected_when_the_tx_cap_is_reached(qapp):
    """worker가 실제로 상한을 적용하는가 (thread는 돌리지 않는다)."""
    worker = ConnectionWorker(_NeverDrainsTransport(), PORT)

    chunk = b"X" * 4096
    # 상한이 없으면 이 루프가 끝나지 않는다. 회귀 시 hang이 아니라 **실패**로
    # 드러나도록 상한의 2배에서 끊는다.
    max_attempts = (TX_QUEUE_MAX_BYTES // len(chunk)) * 2
    accepted = 0
    while worker.send_data(chunk):
        accepted += 1
        assert accepted <= max_attempts, (
            f"{accepted}개를 받아들이고도 상한에 걸리지 않았다 — 큐가 무한정 자란다"
        )

    assert worker.is_write_queue_full() is True
    assert worker.get_write_queue_bytes() + len(chunk) > TX_QUEUE_MAX_BYTES
    assert worker.get_write_queue_bytes() <= TX_QUEUE_MAX_BYTES


def test_full_queue_is_surfaced_and_distinguishable_from_a_closed_port(qapp):
    """
    "큐가 가득 참"과 "포트가 닫힘"을 구분할 수 있어야 한다.

    구분하지 못하면 생산자는 일시적 backpressure를 전송 실패로 오인해 중단한다.
    그리고 가득 참이 조용히 False로만 끝나면 사용자는 명령이 사라진 이유를 모른다.
    """
    controller = ConnectionController()
    worker = ConnectionWorker(_NeverDrainsTransport(), PORT)
    controller.session_factory.create_worker = lambda _config: worker

    errors = []
    controller.error_occurred.connect(errors.append)

    try:
        assert controller.open_connection(PortConfig(port=PORT)) is True
        deadline = time.monotonic() + 2.0
        while not worker.is_running() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert worker.is_running(), "worker가 시작되지 않았다"

        # write가 붙잡혀 있으므로 큐는 비지 않는다 — 상한까지 채운다.
        chunk = b"X" * 4096
        max_attempts = (TX_QUEUE_MAX_BYTES // len(chunk)) * 2
        filled = 0
        while worker.send_data(chunk):
            filled += 1
            assert filled <= max_attempts, "상한이 걸리지 않았다 — 큐가 무한정 자란다"

        assert controller.is_write_queue_full(PORT) is True
        assert controller.is_connection_open(PORT) is True, (
            "포트는 열려 있다 — 닫힌 것과 구분되어야 한다"
        )

        assert controller.send_data(PORT, b"OVERFLOW") is False
        assert errors, "큐가 가득 차서 거절했는데 아무것도 알리지 않았다"
        assert "queue is full" in errors[-1].message.lower()
    finally:
        worker._write_queue.clear()
        transport = worker.transport
        transport.release.set()
        controller.close_all_and_wait(timeout_ms=3000)


def test_closed_port_is_not_reported_as_a_full_queue(qapp):
    """닫힌 포트는 큐 상한과 다른 이유로 실패해야 한다."""
    controller = ConnectionController()
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.send_data("NOT_OPEN", b"DATA") is False

    assert errors
    assert "not open" in errors[-1].message.lower()
    assert controller.is_write_queue_full("NOT_OPEN") is False
