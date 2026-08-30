"""ConnectionWorker activity-aware wait policy regression tests.

WHY
- RX/TX activity가 실제 발생한 loop에서 Windows scheduler granularity에 묶이는
  sub-millisecond sleep을 강제하면 sustained throughput이 크게 제한될 수 있습니다.
- 새 I/O는 없지만 emit 전 RX buffer/TX queue가 남은 경우에는 기존 busy wait를 유지해
  무의미한 spin을 피합니다.
- 절대 성능값은 benchmark에서 비교하고, 여기서는 policy 분기만 고정합니다.
"""
from core.transport.base_transport import BaseTransport
from model.connection_worker import ConnectionWorker
from common.constants import WORKER_BUSY_WAIT_US, WORKER_IDLE_WAIT_MS


class _NullTransport(BaseTransport):
    def open(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def is_open(self) -> bool:
        return True

    def read(self, size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        return None

    @property
    def in_waiting(self) -> int:
        return 0


class _WaitProbeWorker(ConnectionWorker):
    def __init__(self) -> None:
        super().__init__(_NullTransport(), "WAIT_PROBE")
        self.wait_calls: list[tuple[str, int]] = []

    def msleep(self, msecs: int) -> None:
        self.wait_calls.append(("idle", msecs))

    def usleep(self, usecs: int) -> None:
        self.wait_calls.append(("busy", usecs))

    def yieldCurrentThread(self) -> None:
        self.wait_calls.append(("yield", 0))


def test_idle_wait_only_when_no_activity_or_pending_data():
    worker = _WaitProbeWorker()

    worker._wait_for_next_iteration(
        had_io_activity=False,
        has_buffered_rx=False,
    )

    assert worker.wait_calls == [("idle", WORKER_IDLE_WAIT_MS)]


def test_rx_activity_yields_after_batch_buffer_was_flushed():
    worker = _WaitProbeWorker()

    worker._wait_for_next_iteration(
        had_io_activity=True,
        has_buffered_rx=False,
    )

    assert worker.wait_calls == [("yield", 0)]


def test_buffered_rx_keeps_busy_wait_without_new_activity():
    worker = _WaitProbeWorker()

    worker._wait_for_next_iteration(
        had_io_activity=False,
        has_buffered_rx=True,
    )

    assert worker.wait_calls == [("busy", WORKER_BUSY_WAIT_US)]


def test_pending_tx_keeps_busy_wait_without_new_rx_activity():
    worker = _WaitProbeWorker()
    assert worker.send_data(b"pending") is True

    worker._wait_for_next_iteration(
        had_io_activity=False,
        has_buffered_rx=False,
    )

    assert worker.wait_calls == [("busy", WORKER_BUSY_WAIT_US)]
