"""RxLogView benchmark smoke/contract tests.

CI에서는 성능 수치를 threshold로 고정하지 않습니다. scenario가 실제 Qt/View 경로에서
동작하고 결과 schema가 유지되는지만 검증합니다.
"""
from tools import rx_view_benchmark


def test_model_batch_insert_smoke():
    result = rx_view_benchmark.bench_model_batch_insert(
        total_lines=1_000,
        batch_size=128,
    )
    assert result.metrics["lines_s"] > 0
    assert result.metrics["elapsed_ms"] >= 0


def test_preformatted_and_ascii_view_smoke(qapp):
    preformatted = rx_view_benchmark.bench_view_preformatted_text(
        total_bytes=64 * 1024,
        chunk_size=1024,
    )
    ascii_result = rx_view_benchmark.bench_view_ascii_bytes(
        total_bytes=64 * 1024,
        chunk_size=1024,
    )

    assert preformatted.metrics["input_mb_s"] > 0
    assert ascii_result.metrics["input_mb_s"] > 0
    assert preformatted.metrics["rows"] > 0
    assert ascii_result.metrics["rows"] > 0


def test_event_loop_and_hex_view_smoke(qapp):
    event_result = rx_view_benchmark.bench_view_ascii_with_events(
        total_bytes=32 * 1024,
        chunk_size=1024,
        event_batch=4,
    )
    hex_result = rx_view_benchmark.bench_view_hex_bytes(
        total_bytes=16 * 1024,
        chunk_size=128,
    )

    assert event_result.metrics["input_mb_s"] > 0
    assert event_result.metrics["rows"] > 0
    assert hex_result.metrics["input_mb_s"] > 0
    assert hex_result.metrics["rows"] > 0


def test_run_all_schema_with_small_scenarios(monkeypatch, qapp):
    monkeypatch.setattr(
        rx_view_benchmark,
        "SCENARIOS",
        {
            "model_batch_insert": lambda: rx_view_benchmark.bench_model_batch_insert(256, 64),
            "model_single_insert_control": lambda: rx_view_benchmark.bench_model_single_insert(128),
            "view_preformatted_text": lambda: rx_view_benchmark.bench_view_preformatted_text(16 * 1024, 1024),
            "view_ascii_bytes": lambda: rx_view_benchmark.bench_view_ascii_bytes(16 * 1024, 1024),
            "view_ascii_with_events": lambda: rx_view_benchmark.bench_view_ascii_with_events(16 * 1024, 1024, 4),
            "view_hex_bytes": lambda: rx_view_benchmark.bench_view_hex_bytes(8 * 1024, 128),
        },
    )

    result = rx_view_benchmark.run_all(repeat=1)

    assert result["schema_version"] == rx_view_benchmark.BENCHMARK_SCHEMA_VERSION
    assert result["metadata"]["repeat"] == 1
    assert set(result["scenarios"]) == {
        "model_batch_insert",
        "model_single_insert_control",
        "view_preformatted_text",
        "view_ascii_bytes",
        "view_ascii_with_events",
        "view_hex_bytes",
    }
    assert set(result["derived"]) == {
        "batch_vs_single_ratio",
        "ascii_formatting_cost_ratio",
        "event_loop_cost_ratio",
    }
    assert all(value > 0 for value in result["derived"].values())


def test_run_all_rejects_zero_repeat():
    try:
        rx_view_benchmark.run_all(repeat=0)
    except ValueError as exc:
        assert "repeat" in str(exc)
    else:
        raise AssertionError("repeat=0 must be rejected")
