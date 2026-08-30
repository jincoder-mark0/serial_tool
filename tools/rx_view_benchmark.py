"""RxLogView / QSmartListView 성능 benchmark.

P2-B #4의 목적은 `BatchRenderer`를 먼저 구현하는 것이 아니라 현재 RX View 경로에서
실제 병목이 어디인지 분리해서 측정하는 것입니다.

측정 계층
---------
1. LogModel batch insert
2. LogModel single-row insert (대조군; production 후보 아님)
3. QSmartListView.append() - 이미 문자열로 준비된 text
4. QSmartListView.append_bytes() - ASCII decode/formatting 포함
5. QSmartListView.append_bytes() + QApplication.processEvents() - event-loop/paint 포함
6. HEX append_bytes() - byte -> HEX expansion 비용 확인

WHY
---
현재 `LogModel.add_logs()`는 이미 beginInsertRows/endInsertRows 한 번으로 여러 row를
추가합니다. 따라서 별도 BatchRenderer가 의미 있으려면 model insert가 아니라
formatting/autoscroll/delegate paint/repaint 등 다른 구간이 병목이라는 증거가 필요합니다.

이 benchmark 수치는 제품 성능 보장이 아닙니다. 같은 머신/환경에서 current/candidate를
비교하는 decision evidence로만 사용합니다. GitHub-hosted runner의 수치를 threshold로
사용하지 않습니다.
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
from typing import Callable

from PyQt5.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from view.custom_qt.smart_list_view import LogModel, QSmartListView  # noqa: E402

MIB = 1024 * 1024
BENCHMARK_SCHEMA_VERSION = 1
DEFAULT_REPEAT = 5
DEFAULT_MODEL_LINES = 50_000
DEFAULT_MODEL_BATCH_SIZE = 256
DEFAULT_VIEW_BYTES = 2 * MIB
DEFAULT_VIEW_CHUNK_SIZE = 4096
DEFAULT_HEX_BYTES = 512 * 1024
DEFAULT_HEX_CHUNK_SIZE = 256
DEFAULT_MAX_LINES = 250_000
DEFAULT_EVENT_BATCH = 8

# QApplication은 Python wrapper의 strong reference가 사라지면 QApplication.instance()
# 자체가 먼저 파괴될 수 있습니다. pytest에서는 qapp fixture가 이 역할을 하지만 CLI에서는
# benchmark 모듈이 직접 lifetime을 소유해야 QWidget 생성 전 fatal 종료를 피할 수 있습니다.
_BENCHMARK_APP: QApplication | None = None


@dataclass(frozen=True)
class ViewBenchmarkResult:
    """단일 View benchmark scenario 결과."""

    metrics: dict[str, float]
    units: dict[str, str]


def _ensure_application() -> QApplication:
    """QWidget benchmark에 필요한 QApplication을 생성/보존하여 반환합니다."""
    global _BENCHMARK_APP

    app = QApplication.instance()
    if app is None:
        _BENCHMARK_APP = QApplication([])
        app = _BENCHMARK_APP
    elif isinstance(app, QApplication):
        _BENCHMARK_APP = app

    if not isinstance(app, QApplication):
        raise RuntimeError("QApplication is required for RxLogView benchmark")
    return app


def _build_ascii_chunk(chunk_size: int) -> bytes:
    """newline이 충분히 포함된 deterministic ASCII payload를 생성합니다."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    line = b"RX 0123456789ABCDEF payload benchmark line\n"
    repeat = (chunk_size + len(line) - 1) // len(line)
    return (line * repeat)[:chunk_size]


def _line_payload(index: int) -> str:
    return f"RX {index:08d} 0123456789ABCDEF payload benchmark line"


def bench_model_batch_insert(
    total_lines: int = DEFAULT_MODEL_LINES,
    batch_size: int = DEFAULT_MODEL_BATCH_SIZE,
) -> ViewBenchmarkResult:
    """현재 production 방식과 같은 batch add_logs 처리량을 측정합니다."""
    if total_lines < 1 or batch_size < 1:
        raise ValueError("total_lines and batch_size must be >= 1")

    model = LogModel(max_lines=max(DEFAULT_MAX_LINES, total_lines + batch_size))
    inserted = 0
    start = time.perf_counter()
    while inserted < total_lines:
        count = min(batch_size, total_lines - inserted)
        lines = [_line_payload(inserted + i) for i in range(count)]
        model.add_logs(lines)
        inserted += count
    elapsed = time.perf_counter() - start

    if model.rowCount() != total_lines:
        raise RuntimeError(
            f"model batch row mismatch: expected={total_lines}, actual={model.rowCount()}"
        )

    return ViewBenchmarkResult(
        metrics={
            "lines_s": total_lines / elapsed,
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"lines_s": "lines/s", "elapsed_ms": "ms"},
    )


def bench_model_single_insert(total_lines: int = 5_000) -> ViewBenchmarkResult:
    """single-row insertion 대조군입니다. production 변경 후보가 아닙니다."""
    if total_lines < 1:
        raise ValueError("total_lines must be >= 1")

    model = LogModel(max_lines=max(DEFAULT_MAX_LINES, total_lines + 1))
    start = time.perf_counter()
    for index in range(total_lines):
        model.add_logs([_line_payload(index)])
    elapsed = time.perf_counter() - start

    if model.rowCount() != total_lines:
        raise RuntimeError(
            f"model single row mismatch: expected={total_lines}, actual={model.rowCount()}"
        )

    return ViewBenchmarkResult(
        metrics={
            "lines_s": total_lines / elapsed,
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"lines_s": "lines/s", "elapsed_ms": "ms"},
    )


def _new_benchmark_view() -> QSmartListView:
    _ensure_application()
    view = QSmartListView()
    view.set_max_lines(DEFAULT_MAX_LINES)
    view.resize(1000, 600)
    return view


def bench_view_preformatted_text(
    total_bytes: int = DEFAULT_VIEW_BYTES,
    chunk_size: int = DEFAULT_VIEW_CHUNK_SIZE,
) -> ViewBenchmarkResult:
    """decode/HEX 변환 이전의 QSmartListView.append() 비용을 측정합니다."""
    if total_bytes < 1 or chunk_size < 1:
        raise ValueError("total_bytes and chunk_size must be >= 1")

    view = _new_benchmark_view()
    payload = _build_ascii_chunk(chunk_size).decode("ascii", errors="replace")
    chunk_count = max(1, total_bytes // chunk_size)
    actual_bytes = chunk_count * chunk_size

    try:
        start = time.perf_counter()
        for _ in range(chunk_count):
            view.append(payload)
        elapsed = time.perf_counter() - start
        rows = view.log_model.rowCount()
    finally:
        view.close()

    return ViewBenchmarkResult(
        metrics={
            "input_mb_s": (actual_bytes / MIB) / elapsed,
            "rows": float(rows),
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"input_mb_s": "MB/s", "rows": "count", "elapsed_ms": "ms"},
    )


def bench_view_ascii_bytes(
    total_bytes: int = DEFAULT_VIEW_BYTES,
    chunk_size: int = DEFAULT_VIEW_CHUNK_SIZE,
) -> ViewBenchmarkResult:
    """ASCII append_bytes의 decode + formatting + model insert 비용을 측정합니다."""
    if total_bytes < 1 or chunk_size < 1:
        raise ValueError("total_bytes and chunk_size must be >= 1")

    view = _new_benchmark_view()
    payload = _build_ascii_chunk(chunk_size)
    chunk_count = max(1, total_bytes // chunk_size)
    actual_bytes = chunk_count * chunk_size

    try:
        start = time.perf_counter()
        for _ in range(chunk_count):
            view.append_bytes(payload)
        elapsed = time.perf_counter() - start
        rows = view.log_model.rowCount()
    finally:
        view.close()

    return ViewBenchmarkResult(
        metrics={
            "input_mb_s": (actual_bytes / MIB) / elapsed,
            "rows": float(rows),
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"input_mb_s": "MB/s", "rows": "count", "elapsed_ms": "ms"},
    )


def bench_view_ascii_with_events(
    total_bytes: int = DEFAULT_VIEW_BYTES,
    chunk_size: int = DEFAULT_VIEW_CHUNK_SIZE,
    event_batch: int = DEFAULT_EVENT_BATCH,
) -> ViewBenchmarkResult:
    """event-loop/paint servicing을 포함한 ASCII append 경로를 측정합니다."""
    if total_bytes < 1 or chunk_size < 1 or event_batch < 1:
        raise ValueError("total_bytes, chunk_size and event_batch must be >= 1")

    app = _ensure_application()
    view = _new_benchmark_view()
    payload = _build_ascii_chunk(chunk_size)
    chunk_count = max(1, total_bytes // chunk_size)
    actual_bytes = chunk_count * chunk_size

    view.show()
    app.processEvents()
    try:
        start = time.perf_counter()
        for index in range(chunk_count):
            view.append_bytes(payload)
            if (index + 1) % event_batch == 0:
                app.processEvents()
        app.processEvents()
        elapsed = time.perf_counter() - start
        rows = view.log_model.rowCount()
    finally:
        view.close()
        app.processEvents()

    return ViewBenchmarkResult(
        metrics={
            "input_mb_s": (actual_bytes / MIB) / elapsed,
            "rows": float(rows),
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"input_mb_s": "MB/s", "rows": "count", "elapsed_ms": "ms"},
    )


def bench_view_hex_bytes(
    total_bytes: int = DEFAULT_HEX_BYTES,
    chunk_size: int = DEFAULT_HEX_CHUNK_SIZE,
) -> ViewBenchmarkResult:
    """HEX 변환(각 byte -> 'XX ')이 포함된 append_bytes 비용을 측정합니다."""
    if total_bytes < 1 or chunk_size < 1:
        raise ValueError("total_bytes and chunk_size must be >= 1")

    view = _new_benchmark_view()
    view.set_hex_mode_enabled(True)
    payload = bytes((index % 256 for index in range(chunk_size)))
    chunk_count = max(1, total_bytes // chunk_size)
    actual_bytes = chunk_count * chunk_size

    try:
        start = time.perf_counter()
        for _ in range(chunk_count):
            view.append_bytes(payload)
        elapsed = time.perf_counter() - start
        rows = view.log_model.rowCount()
    finally:
        view.close()

    return ViewBenchmarkResult(
        metrics={
            "input_mb_s": (actual_bytes / MIB) / elapsed,
            "rows": float(rows),
            "elapsed_ms": elapsed * 1000.0,
        },
        units={"input_mb_s": "MB/s", "rows": "count", "elapsed_ms": "ms"},
    )


SCENARIOS: dict[str, Callable[[], ViewBenchmarkResult]] = {
    "model_batch_insert": bench_model_batch_insert,
    "model_single_insert_control": bench_model_single_insert,
    "view_preformatted_text": bench_view_preformatted_text,
    "view_ascii_bytes": bench_view_ascii_bytes,
    "view_ascii_with_events": bench_view_ascii_with_events,
    "view_hex_bytes": bench_view_hex_bytes,
}


def run_all(repeat: int = DEFAULT_REPEAT) -> dict[str, object]:
    """모든 scenario를 반복 실행하고 metric별 중앙값을 반환합니다."""
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    scenarios: dict[str, object] = {}
    for name, runner in SCENARIOS.items():
        samples = [runner() for _ in range(repeat)]
        metric_names = samples[0].metrics.keys()
        medians = {
            metric: statistics.median(sample.metrics[metric] for sample in samples)
            for metric in metric_names
        }
        scenarios[name] = {"metrics": medians, "units": samples[0].units}

    batch_rate = scenarios["model_batch_insert"]["metrics"]["lines_s"]
    single_rate = scenarios["model_single_insert_control"]["metrics"]["lines_s"]
    preformatted_rate = scenarios["view_preformatted_text"]["metrics"]["input_mb_s"]
    ascii_rate = scenarios["view_ascii_bytes"]["metrics"]["input_mb_s"]
    event_rate = scenarios["view_ascii_with_events"]["metrics"]["input_mb_s"]

    derived = {
        "batch_vs_single_ratio": batch_rate / single_rate if single_rate else float("inf"),
        "ascii_formatting_cost_ratio": preformatted_rate / ascii_rate if ascii_rate else float("inf"),
        "event_loop_cost_ratio": ascii_rate / event_rate if event_rate else float("inf"),
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
        "scenarios": scenarios,
        "derived": derived,
    }


def print_results(result: dict[str, object]) -> None:
    metadata = result["metadata"]
    print(
        f"Python {metadata['python']} / {metadata['platform']} / "
        f"repeat={metadata['repeat']}"
    )
    for name, scenario in result["scenarios"].items():
        print(f"\n[{name}]")
        for metric, value in scenario["metrics"].items():
            print(f"  {metric:<18} {value:>12,.3f} {scenario['units'][metric]}")

    print("\n[derived]")
    for metric, value in result["derived"].items():
        print(f"  {metric:<28} {value:>10,.3f} x")


def main() -> None:
    parser = argparse.ArgumentParser(description="SerialTool RxLogView benchmark")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    # CLI 실행에서도 QApplication lifetime을 benchmark 전체 동안 명시적으로 유지합니다.
    app = _ensure_application()
    result = run_all(repeat=args.repeat)
    print_results(result)
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON saved: {output}")
    _ = app


if __name__ == "__main__":
    main()
