"""ConnectionWorker non-blocking I/O loop fairness benchmark.

P2-B #5에서 최적화 코드를 먼저 넣지 않고 현재 loop의 RX/TX fairness와 idle polling을
측정합니다. 실제 Serial driver를 대체하는 성능 보장이 아니라 동일한 deterministic
transport에서 변경 전후를 비교하기 위한 decision evidence입니다.

핵심 질문
---------
1. TX queue에 많은 chunk가 있을 때 RX read가 얼마나 오래 지연되는가?
2. 연속 write 사이에 RX read 기회가 있는가?
3. idle 상태에서 loop가 어느 정도 poll하는가?
4. stop latency와 byte preservation은 유지되는가?
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from PyQt5.QtCore import QCoreApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.constants import DEFAULT_READ_CHUNK_SIZE  # noqa: E402
from core.transport.base_transport import BaseTransport  # noqa: E402
from model.connection_worker import ConnectionWorker  # noqa: E402

MIB = 1024 * 1024
DEFAULT_REPEAT = 5
DEFAULT_RX_BYTES = 64 * 1024
DEFAULT_TX_CHUNKS = 256
DEFAULT_WRITE_DELAY_S = 0.0005
DEFAULT_IDLE_WINDOW_S = 0.25
BENCHMARK_TIMEOUT_S = 5.0
EVENT_POLL_S = 0.0005
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SerialLoopResult:
    metrics: dict[str, float]
    units: dict[str, str]


class _TimedDuplexTransport(BaseTransport):
    """read/write 순서와 timing을 기록하는 deterministic duplex transport."""

    def __init__(self, rx_payload: bytes, write_delay_s: float = 0.0) -> None:
        self._rx_payload = rx_payload
        self._rx_offset = 0
        self._write_delay_s = write_delay_s
        self._open = False
        self._lock = Lock()
        self._written_bytes = 0
        self._read_count = 0
        self._write_count = 0
        self._poll_count = 0
        self._events: list[tuple[str, float]] = []
        self._origin = 0.0

    def set_origin(self, origin: float) -> None:
        with self._lock:
            self._origin = origin

    def _record(self, name: str) -> None:
        now = time.perf_counter()
        self._events.append((name, now - self._origin if self._origin else 0.0))

    def open(self) -> bool:
        with self._lock:
            self._open = True
            self._record("open")
        return True

    def close(self) -> None:
        with self._lock:
            self._open = False
            self._record("close")

    def is_open(self) -> bool:
        with self._lock:
            return self._open

    def read(self, size: int) -> bytes:
        with self._lock:
            if not self._open or self._rx_offset >= len(self._rx_payload):
                return b""
            end = min(self._rx_offset + size, len(self._rx_payload))
            data = self._rx_payload[self._rx_offset:end]
            self._rx_offset = end
            self._read_count += 1
            self._record("read")
            return data

    def write(self, data: bytes) -> None:
        if self._write_delay_s:
            time.sleep(self._write_delay_s)
        with self._lock:
            if not self._open:
                raise RuntimeError("timed transport is closed")
            self._written_bytes += len(data)
            self._write_count += 1
            self._record("write")

    @property
    def in_waiting(self) -> int:
        with self._lock:
            self._poll_count += 1
            if not self._open:
                return 0
            return len(self._rx_payload) - self._rx_offset

    @property
    def written_bytes(self) -> int:
        with self._lock:
            return self._written_bytes

    @property
    def read_count(self) -> int:
        with self._lock:
            return self._read_count

    @property
    def poll_count(self) -> int:
        with self._lock:
            return self._poll_count

    def events_snapshot(self) -> list[tuple[str, float]]:
        with self._lock:
            return list(self._events)


def _ensure_qt_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _max_write_streak(events: list[tuple[str, float]]) -> int:
    current = 0
    maximum = 0
    for name, _ in events:
        if name == "write":
            current += 1
            maximum = max(maximum, current)
        elif name == "read":
            current = 0
    return maximum


def bench_tx_rx_fairness(
    rx_bytes: int = DEFAULT_RX_BYTES,
    tx_chunks: int = DEFAULT_TX_CHUNKS,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
    write_delay_s: float = DEFAULT_WRITE_DELAY_S,
    timeout_s: float = BENCHMARK_TIMEOUT_S,
) -> SerialLoopResult:
    """TX backlog 중 RX delivery/read fairness를 측정합니다."""
    if rx_bytes < chunk_size * 2:
        raise ValueError("rx_bytes must contain at least two read chunks")
    if tx_chunks < 1 or chunk_size < 1 or write_delay_s < 0:
        raise ValueError("tx_chunks/chunk_size must be positive and delay non-negative")

    app = _ensure_qt_app()
    actual_rx = max(2, rx_bytes // chunk_size) * chunk_size
    actual_tx = tx_chunks * chunk_size
    transport = _TimedDuplexTransport(bytes(actual_rx), write_delay_s)
    worker = ConnectionWorker(transport, "BENCH_FAIRNESS")

    rx_received = 0
    first_emit_s: float | None = None
    start = time.perf_counter()
    state_lock = Lock()

    def on_rx(data: bytes) -> None:
        nonlocal rx_received, first_emit_s
        now = time.perf_counter()
        with state_lock:
            rx_received += len(data)
            if first_emit_s is None:
                first_emit_s = now - start

    worker.data_received.connect(on_rx)

    tx_chunk = bytes(chunk_size)
    for _ in range(tx_chunks):
        if not worker.send_data(tx_chunk):
            raise RuntimeError("failed to queue TX chunk")

    transport.set_origin(start)
    worker.start()
    deadline = start + timeout_s

    try:
        while time.perf_counter() < deadline:
            app.processEvents()
            with state_lock:
                rx_done = rx_received >= actual_rx
            if rx_done and transport.written_bytes >= actual_tx:
                break
            time.sleep(EVENT_POLL_S)
        else:
            raise TimeoutError(
                f"fairness benchmark timed out: rx={rx_received}/{actual_rx}, "
                f"tx={transport.written_bytes}/{actual_tx}"
            )

        complete_s = time.perf_counter() - start
        stop_start = time.perf_counter()
        worker.stop()
        stop_s = time.perf_counter() - stop_start
        app.processEvents()
    finally:
        if worker.isRunning():
            worker.stop()

    with state_lock:
        final_rx = rx_received
        first_emit = first_emit_s

    events = transport.events_snapshot()
    read_times = [timestamp for name, timestamp in events if name == "read"]

    if final_rx != actual_rx:
        raise RuntimeError(f"RX mismatch: {final_rx}/{actual_rx}")
    if transport.written_bytes != actual_tx:
        raise RuntimeError(f"TX mismatch: {transport.written_bytes}/{actual_tx}")
    if first_emit is None or len(read_times) < 2:
        raise RuntimeError("RX delivery/read timestamps were not captured")

    return SerialLoopResult(
        metrics={
            "first_rx_emit_ms": first_emit * 1000.0,
            "second_read_ms": read_times[1] * 1000.0,
            "complete_ms": complete_s * 1000.0,
            "max_write_streak": float(_max_write_streak(events)),
            "rx_mb_s": (actual_rx / MIB) / complete_s,
            "tx_mb_s": (actual_tx / MIB) / complete_s,
            "stop_ms": stop_s * 1000.0,
        },
        units={
            "first_rx_emit_ms": "ms",
            "second_read_ms": "ms",
            "complete_ms": "ms",
            "max_write_streak": "chunks",
            "rx_mb_s": "MB/s",
            "tx_mb_s": "MB/s",
            "stop_ms": "ms",
        },
    )


def bench_idle_polling(window_s: float = DEFAULT_IDLE_WINDOW_S) -> SerialLoopResult:
    """RX/TX가 없는 worker의 poll cadence와 stop latency를 측정합니다."""
    if window_s <= 0:
        raise ValueError("window_s must be > 0")

    app = _ensure_qt_app()
    transport = _TimedDuplexTransport(b"")
    worker = ConnectionWorker(transport, "BENCH_IDLE")
    start = time.perf_counter()
    transport.set_origin(start)
    worker.start()

    deadline = start + window_s
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(EVENT_POLL_S)

    elapsed = time.perf_counter() - start
    poll_count = transport.poll_count
    stop_start = time.perf_counter()
    worker.stop()
    stop_s = time.perf_counter() - stop_start
    app.processEvents()

    return SerialLoopResult(
        metrics={
            "polls_s": poll_count / elapsed,
            "poll_count": float(poll_count),
            "window_ms": elapsed * 1000.0,
            "stop_ms": stop_s * 1000.0,
        },
        units={
            "polls_s": "polls/s",
            "poll_count": "count",
            "window_ms": "ms",
            "stop_ms": "ms",
        },
    )


def run_all(repeat: int = DEFAULT_REPEAT) -> dict[str, object]:
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    runners = {
        "tx_rx_fairness": bench_tx_rx_fairness,
        "idle_polling": bench_idle_polling,
    }
    scenarios: dict[str, object] = {}

    for name, runner in runners.items():
        samples = [runner() for _ in range(repeat)]
        metrics = {
            metric: statistics.median(sample.metrics[metric] for sample in samples)
            for metric in samples[0].metrics
        }
        scenarios[name] = {"metrics": metrics, "units": samples[0].units}

    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "repeat": repeat,
            "write_delay_ms": DEFAULT_WRITE_DELAY_S * 1000.0,
            "tx_chunks": DEFAULT_TX_CHUNKS,
        },
        "scenarios": scenarios,
    }


def print_results(result: dict[str, object]) -> None:
    metadata = result["metadata"]
    print(
        f"Python {metadata['python']} / {metadata['platform']} / repeat={metadata['repeat']} / "
        f"write_delay={metadata['write_delay_ms']:.3f} ms / tx_chunks={metadata['tx_chunks']}"
    )
    for name, scenario in result["scenarios"].items():
        print(f"\n[{name}]")
        for metric, value in scenario["metrics"].items():
            print(f"  {metric:<20} {value:>12,.3f} {scenario['units'][metric]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SerialTool ConnectionWorker loop benchmark")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    result = run_all(args.repeat)
    print_results(result)
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON saved: {output}")


if __name__ == "__main__":
    main()
