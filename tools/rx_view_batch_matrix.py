"""RxLogView flush-size matrix benchmark.

DataTrafficHandler는 UI_REFRESH_INTERVAL_MS마다 누적 RX를 한 번에 QSmartListView로 넘깁니다.
따라서 4KB chunk를 back-to-back으로 호출하는 stress 결과만으로 새 BatchRenderer 필요성을
판단하면 실제 upstream aggregation 효과를 과소평가할 수 있습니다.

이 도구는 같은 총 byte를 4KB/16KB/64KB 단위로 전달하고 매 append 후 event loop를
service하여, update 횟수 감소 자체가 View 처리량에 주는 효과를 비교합니다.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.rx_view_benchmark import MIB, bench_view_ascii_with_events  # noqa: E402

DEFAULT_TOTAL_BYTES = 2 * MIB
DEFAULT_REPEAT = 3
DEFAULT_CHUNK_SIZES = (4 * 1024, 16 * 1024, 64 * 1024)


def run_matrix(
    total_bytes: int = DEFAULT_TOTAL_BYTES,
    repeat: int = DEFAULT_REPEAT,
    chunk_sizes: tuple[int, ...] = DEFAULT_CHUNK_SIZES,
) -> dict[str, object]:
    if total_bytes < 1:
        raise ValueError("total_bytes must be >= 1")
    if repeat < 1:
        raise ValueError("repeat must be >= 1")
    if not chunk_sizes or any(size < 1 for size in chunk_sizes):
        raise ValueError("chunk_sizes must contain positive values")

    results: dict[str, object] = {}
    for chunk_size in chunk_sizes:
        samples = [
            bench_view_ascii_with_events(
                total_bytes=total_bytes,
                chunk_size=chunk_size,
                event_batch=1,
            )
            for _ in range(repeat)
        ]
        mb_s = statistics.median(sample.metrics["input_mb_s"] for sample in samples)
        elapsed_ms = statistics.median(sample.metrics["elapsed_ms"] for sample in samples)
        rows = statistics.median(sample.metrics["rows"] for sample in samples)
        update_count = max(1, total_bytes // chunk_size)

        results[str(chunk_size)] = {
            "chunk_kib": chunk_size / 1024.0,
            "update_count": update_count,
            "input_mb_s": mb_s,
            "elapsed_ms": elapsed_ms,
            "rows": rows,
        }

    smallest = min(chunk_sizes)
    largest = max(chunk_sizes)
    small_rate = results[str(smallest)]["input_mb_s"]
    large_rate = results[str(largest)]["input_mb_s"]

    return {
        "metadata": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "repeat": repeat,
            "total_bytes": total_bytes,
        },
        "results": results,
        "derived": {
            "largest_vs_smallest_throughput_ratio": (
                large_rate / small_rate if small_rate else float("inf")
            ),
            "update_count_reduction_ratio": (
                results[str(smallest)]["update_count"]
                / results[str(largest)]["update_count"]
            ),
        },
    }


def print_matrix(result: dict[str, object]) -> None:
    metadata = result["metadata"]
    print(
        f"Python {metadata['python']} / {metadata['platform']} / "
        f"repeat={metadata['repeat']} / total={metadata['total_bytes'] / MIB:.1f} MiB"
    )
    print("\nchunk(KiB)  updates    MB/s    elapsed(ms)    rows")
    print("---------------------------------------------------")
    for entry in result["results"].values():
        print(
            f"{entry['chunk_kib']:>10.0f}  "
            f"{entry['update_count']:>7}  "
            f"{entry['input_mb_s']:>7.3f}  "
            f"{entry['elapsed_ms']:>11.3f}  "
            f"{entry['rows']:>7.0f}"
        )

    print("\n[derived]")
    for key, value in result["derived"].items():
        print(f"  {key:<38} {value:>8.3f} x")


def main() -> None:
    parser = argparse.ArgumentParser(description="SerialTool RxLogView flush-size matrix")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--total-mib", type=float, default=DEFAULT_TOTAL_BYTES / MIB)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    result = run_matrix(total_bytes=max(1, int(args.total_mib * MIB)), repeat=args.repeat)
    print_matrix(result)

    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON saved: {output}")


if __name__ == "__main__":
    main()
