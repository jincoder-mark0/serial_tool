"""SerialTool runtime-path 성능 benchmark.

기존 ``tools/benchmark.py``가 Core/Model micro benchmark를 담당하는 반면,
이 모듈은 P2-B 성능 작업의 실제 변경 대상인 RX presentation pipeline과
``ConnectionWorker`` I/O loop를 같은 scenario로 반복 비교하기 위한 기준선을 제공합니다.

WHY
- RxLogView/BatchRenderer 판단을 RingBuffer 처리량으로 대신하지 않기 위함
- Serial worker loop 변경 전후의 RX/TX throughput, batch 수, stop latency를 동일한
  synthetic transport에서 비교하기 위함
- 실제 USB Serial 검증과 deterministic software benchmark의 역할을 분리하기 위함

이 benchmark의 수치는 제품 성능 보장이 아닙니다. 같은 머신/환경에서 변경 전후를
비교하는 regression/decision evidence로만 사용합니다.
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
from typing import Callable

from PyQt5.QtCore import QCoreApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.constants import DEFAULT_READ_CHUNK_SIZE  # noqa: E402
from common.dtos import LogDataBatch, PortDataEvent  # noqa: E402
from core.data_logger import DataLoggerManager  # noqa: E402
from core.transport.base_transport import BaseTransport  # noqa: E402
from model.connection_worker import ConnectionWorker  # noqa: E402
from model.traffic_monitor import TrafficMonitor  # noqa: E402
from presenter.data_handler import DataTrafficHandler  # noqa: E402

MIB = 1024 * 1024
DEFAULT_RX_PIPELINE_BYTES = 32 * MIB
DEFAULT_WORKER_RX_BYTES = 16 * MIB
DEFAULT_WORKER_TX_BYTES = 4 * MIB
DEFAULT_REPEAT = 5
WORKER_BENCH_TIMEOUT_S = 10.0
EVENT_POLL_INTERVAL_S = 0.001
BENCHMARK_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RuntimeBenchmarkResult:
    """단일 runtime scenario 결과."""

    metrics: dict[str, float]
    units: dict[str, str]


class _BenchmarkView:
    """DataTrafficHandler가 요구하는 최소 View facade."""

    def __init__(self) -> None:
        self.batch_count = 0
        self.total_bytes = 0

    def append_rx_data(self, batch: LogDataBatch) -> None:
        self.batch_count += 1
        self.total_bytes += len(batch.data)


class _SyntheticBurstTransport(BaseTransport):
    """ConnectionWorker loop 비교용 메모리 transport.

    실제 Serial driver latency를 흉내 내지 않습니다. 같은 input workload에서 worker의
    batching/queue/sleep 정책 변경이 만드는 상대 차이를 안정적으로 비교하는 목적입니다.

    RX payload는 immutable ``bytes``와 offset으로 소비합니다. ``bytearray`` 앞부분을
    반복 삭제하면 매 read마다 남은 버퍼를 이동하는 O(n) 비용이 benchmark 자체의
    병목이 되어 worker loop 결과를 왜곡하기 때문입니다.
    """

    def __init__(self, rx_payload: bytes) -> None:
        self._rx_payload = rx_payload
        self._rx_offset = 0
        self._open = False
        self._lock = Lock()
        self._written_bytes = 0

    def open(self) -> bool:
        with self._lock:
            self._open = True
        return True

    def close(self) -> None:
        with self._lock:
            self._open = False

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
            return data

    def write(self, data: bytes) -> None:
        with self._lock:
            if not self._open:
                raise RuntimeError("synthetic transport is closed")
            self._written_bytes += len(data)

    @property
    def in_waiting(self) -> int:
        with self._lock:
            if not self._open:
                return 0
            return len(self._rx_payload) - self._rx_offset

    @property
    def written_bytes(self) -> int:
        with self._lock:
            return self._written_bytes


def _ensure_qt_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def bench_rx_pipeline(
    total_bytes: int = DEFAULT_RX_PIPELINE_BYTES,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
) -> RuntimeBenchmarkResult:
    """DataTrafficHandler ingest + flush 비용을 측정합니다.

    Timer cadence 자체가 아니라 timer tick에서 수행되는 실제 buffer aggregation/DTO/View
    facade 호출 비용을 측정합니다. QSmartListView rendering은 다음 P2-B #4의 별도
    비교 대상으로 남겨 이 benchmark와 결합하지 않습니다.
    """
    _ensure_qt_app()
    view = _BenchmarkView()
    monitor = TrafficMonitor(DataLoggerManager())
    handler = DataTrafficHandler(view, monitor)
    handler._ui_refresh_timer.stop()

    chunk = bytes(chunk_size)
    chunk_count = max(1, total_bytes // chunk_size)
    actual_bytes = chunk_count * chunk_size
    event = PortDataEvent(port="BENCH", data=chunk)

    start = time.perf_counter()
    for _ in range(chunk_count):
        handler.on_fast_data_received(event)
    ingest_elapsed = time.perf_counter() - start

    flush_start = time.perf_counter()
    handler._flush_rx_buffer_to_ui()
    flush_elapsed = time.perf_counter() - flush_start
    handler.stop()

    if view.total_bytes != actual_bytes:
        raise RuntimeError(
            f"RX pipeline byte mismatch: expected={actual_bytes}, actual={view.total_bytes}"
        )

    return RuntimeBenchmarkResult(
        metrics={
            "ingest_mb_s": (actual_bytes / MIB) / ingest_elapsed,
            "flush_ms": flush_elapsed * 1000.0,
            "view_batches": float(view.batch_count),
        },
        units={
            "ingest_mb_s": "MB/s",
            "flush_ms": "ms",
            "view_batches": "count",
        },
    )


def bench_worker_loop(
    rx_bytes: int = DEFAULT_WORKER_RX_BYTES,
    tx_bytes: int = DEFAULT_WORKER_TX_BYTES,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
    timeout_s: float = WORKER_BENCH_TIMEOUT_S,
) -> RuntimeBenchmarkResult:
    """실제 ConnectionWorker QThread의 mixed RX/TX loop를 측정합니다."""
    app = _ensure_qt_app()
    rx_chunk_count = max(1, rx_bytes // chunk_size)
    tx_chunk_count = max(0, tx_bytes // chunk_size)
    actual_rx_bytes = rx_chunk_count * chunk_size
    actual_tx_bytes = tx_chunk_count * chunk_size

    transport = _SyntheticBurstTransport(bytes(actual_rx_bytes))
    worker = ConnectionWorker(transport, "BENCH")

    received_bytes = 0
    batch_count = 0
    state_lock = Lock()

    def on_data(data: bytes) -> None:
        nonlocal received_bytes, batch_count
        with state_lock:
            received_bytes += len(data)
            batch_count += 1

    worker.data_received.connect(on_data)

    tx_chunk = bytes(chunk_size)
    for _ in range(tx_chunk_count):
        if not worker.send_data(tx_chunk):
            raise RuntimeError("failed to queue synthetic TX data")

    start = time.perf_counter()
    worker.start()
    deadline = start + timeout_s

    try:
        while time.perf_counter() < deadline:
            app.processEvents()
            with state_lock:
                rx_done = received_bytes >= actual_rx_bytes
            tx_done = transport.written_bytes >= actual_tx_bytes
            if rx_done and tx_done:
                break
            time.sleep(EVENT_POLL_INTERVAL_S)
        else:
            raise TimeoutError(
                "ConnectionWorker benchmark timed out: "
                f"rx={received_bytes}/{actual_rx_bytes}, "
                f"tx={transport.written_bytes}/{actual_tx_bytes}"
            )

        elapsed = time.perf_counter() - start
        stop_start = time.perf_counter()
        worker.stop()
        stop_elapsed = time.perf_counter() - stop_start
        app.processEvents()
    finally:
        if worker.isRunning():
            worker.stop()

    with state_lock:
        final_rx_bytes = received_bytes
        final_batches = batch_count

    if final_rx_bytes != actual_rx_bytes:
        raise RuntimeError(
            f"worker RX byte mismatch: expected={actual_rx_bytes}, actual={final_rx_bytes}"
        )
    if transport.written_bytes != actual_tx_bytes:
        raise RuntimeError(
            "worker TX byte mismatch: "
            f"expected={actual_tx_bytes}, actual={transport.written_bytes}"
        )

    return RuntimeBenchmarkResult(
        metrics={
            "rx_mb_s": (actual_rx_bytes / MIB) / elapsed,
            "tx_mb_s": (actual_tx_bytes / MIB) / elapsed if actual_tx_bytes else 0.0,
            "elapsed_ms": elapsed * 1000.0,
            "rx_batches": float(final_batches),
            "stop_ms": stop_elapsed * 1000.0,
        },
        units={
            "rx_mb_s": "MB/s",
            "tx_mb_s": "MB/s",
            "elapsed_ms": "ms",
            "rx_batches": "count",
            "stop_ms": "ms",
        },
    )


SCENARIOS: dict[str, Callable[[], RuntimeBenchmarkResult]] = {
    "rx_pipeline": bench_rx_pipeline,
    "worker_loop": bench_worker_loop,
}


def run_all(repeat: int = DEFAULT_REPEAT) -> dict[str, object]:
    """각 scenario를 반복 실행하고 metric별 중앙값을 반환합니다."""
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    scenario_results: dict[str, object] = {}
    for name, runner in SCENARIOS.items():
        samples = [runner() for _ in range(repeat)]
        metric_names = samples[0].metrics.keys()
        medians = {
            metric: statistics.median(sample.metrics[metric] for sample in samples)
            for metric in metric_names
        }
        scenario_results[name] = {
            "metrics": medians,
            "units": samples[0].units,
        }

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "metadata": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "repeat": repeat,
        },
        "scenarios": scenario_results,
    }


def print_results(result: dict[str, object]) -> None:
    metadata = result["metadata"]
    print(
        f"Python {metadata['python']} / {metadata['platform']} / "
        f"repeat={metadata['repeat']}"
    )
    for scenario_name, scenario in result["scenarios"].items():
        print(f"\n[{scenario_name}]")
        for metric, value in scenario["metrics"].items():
            unit = scenario["units"][metric]
            print(f"  {metric:<18} {value:>12,.3f} {unit}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SerialTool runtime-path benchmark")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    result = run_all(repeat=args.repeat)
    print_results(result)
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON saved: {output}")


if __name__ == "__main__":
    main()
