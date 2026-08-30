"""Runtime-path benchmark smoke/contract tests.

실제 성능 수치를 CI threshold로 고정하지 않습니다. 이 테스트는 benchmark scenario가
동작하고 byte-preservation/metadata contract를 지키는지만 검증합니다.
"""
from tools import runtime_benchmark


def test_rx_pipeline_benchmark_smoke():
    result = runtime_benchmark.bench_rx_pipeline(
        total_bytes=256 * 1024,
        chunk_size=1024,
    )

    assert result.metrics["ingest_mb_s"] > 0
    assert result.metrics["flush_ms"] >= 0
    assert result.metrics["view_batches"] == 1


def test_worker_loop_benchmark_smoke():
    result = runtime_benchmark.bench_worker_loop(
        rx_bytes=256 * 1024,
        tx_bytes=64 * 1024,
        chunk_size=1024,
        timeout_s=3.0,
    )

    assert result.metrics["rx_mb_s"] > 0
    assert result.metrics["tx_mb_s"] > 0
    assert result.metrics["elapsed_ms"] > 0
    assert result.metrics["rx_batches"] > 0
    assert result.metrics["stop_ms"] >= 0


def test_runtime_benchmark_result_schema(monkeypatch):
    """Aggregation/schema는 작은 workload로 검증해 CI에서 full benchmark를 반복하지 않는다."""
    monkeypatch.setattr(
        runtime_benchmark,
        "SCENARIOS",
        {
            "rx_pipeline": lambda: runtime_benchmark.bench_rx_pipeline(
                total_bytes=128 * 1024,
                chunk_size=1024,
            ),
            "worker_loop": lambda: runtime_benchmark.bench_worker_loop(
                rx_bytes=128 * 1024,
                tx_bytes=32 * 1024,
                chunk_size=1024,
                timeout_s=3.0,
            ),
        },
    )

    result = runtime_benchmark.run_all(repeat=1)

    assert result["schema_version"] == runtime_benchmark.BENCHMARK_SCHEMA_VERSION
    assert result["metadata"]["repeat"] == 1
    assert set(result["scenarios"]) == {"rx_pipeline", "worker_loop"}

    for scenario in result["scenarios"].values():
        assert scenario["metrics"]
        assert set(scenario["metrics"]) == set(scenario["units"])


def test_runtime_benchmark_rejects_zero_repeat():
    try:
        runtime_benchmark.run_all(repeat=0)
    except ValueError as exc:
        assert "repeat" in str(exc)
    else:
        raise AssertionError("repeat=0 must be rejected")
