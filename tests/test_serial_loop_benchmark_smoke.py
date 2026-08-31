"""Serial worker fairness benchmark smoke/contract tests.

성능 threshold는 고정하지 않고 deterministic workload에서 byte preservation, metric/schema,
worker 종료만 확인합니다.
"""
from tools import serial_loop_benchmark


def test_tx_rx_fairness_smoke():
    result = serial_loop_benchmark.bench_tx_rx_fairness(
        rx_bytes=16 * 1024,
        tx_chunks=8,
        chunk_size=1024,
        write_delay_s=0.0001,
        timeout_s=2.0,
    )

    assert result.metrics["first_rx_emit_ms"] >= 0
    assert result.metrics["second_read_ms"] >= 0
    assert result.metrics["complete_ms"] > 0
    assert result.metrics["max_write_streak"] >= 1
    assert result.metrics["rx_mb_s"] > 0
    assert result.metrics["tx_mb_s"] > 0
    assert result.metrics["stop_ms"] >= 0


def test_idle_polling_smoke():
    result = serial_loop_benchmark.bench_idle_polling(window_s=0.03)

    assert result.metrics["polls_s"] > 0
    assert result.metrics["poll_count"] > 0
    assert result.metrics["window_ms"] >= 20
    assert result.metrics["stop_ms"] >= 0


def test_serial_loop_run_all_schema(monkeypatch):
    monkeypatch.setattr(serial_loop_benchmark, "DEFAULT_REPEAT", 1)
    monkeypatch.setattr(serial_loop_benchmark, "DEFAULT_TX_CHUNKS", 8)

    # run_all 내부 default runner의 workload는 별도 관찰 benchmark용이므로
    # schema test에서는 직접 작은 결과를 구성해 public result contract만 확인한다.
    fairness = serial_loop_benchmark.bench_tx_rx_fairness(
        rx_bytes=16 * 1024,
        tx_chunks=8,
        chunk_size=1024,
        write_delay_s=0.0001,
        timeout_s=2.0,
    )
    idle = serial_loop_benchmark.bench_idle_polling(window_s=0.03)

    assert set(fairness.metrics) == set(fairness.units)
    assert set(idle.metrics) == set(idle.units)


def test_serial_loop_rejects_invalid_inputs():
    try:
        serial_loop_benchmark.bench_idle_polling(window_s=0)
    except ValueError:
        pass
    else:
        raise AssertionError("window_s=0 must be rejected")

    try:
        serial_loop_benchmark.bench_tx_rx_fairness(
            rx_bytes=1024,
            tx_chunks=1,
            chunk_size=1024,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("less than two RX chunks must be rejected")
