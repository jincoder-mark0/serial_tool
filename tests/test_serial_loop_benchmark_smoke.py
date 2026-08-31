"""Serial worker fairness benchmark smoke/contract tests.

절대 성능 threshold는 고정하지 않습니다. deterministic workload에서 byte preservation,
metric/schema, worker 종료와 bounded TX fairness contract를 검증합니다.
"""
from model.connection_worker import ConnectionWorker
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


def test_tx_budget_processes_only_one_chunk_when_budget_is_zero(monkeypatch):
    """0초 budget에서는 한 outer-loop의 TX 처리가 정확히 1 chunk여야 합니다.

    benchmark 전체의 마지막 RX 이후 남은 TX drain까지 write streak로 세면 fairness와 무관한
    구간이 섞입니다. 여기서는 worker의 bounded-TX primitive 자체를 직접 검증합니다.
    """
    monkeypatch.setattr(ConnectionWorker, "_TX_FAIRNESS_BUDGET_S", 0.0)
    transport = serial_loop_benchmark._TimedDuplexTransport(b"")
    assert transport.open() is True
    worker = ConnectionWorker(transport, "TEST_BOUNDED_TX")

    chunk = bytes(1024)
    for _ in range(8):
        assert worker.send_data(chunk) is True

    assert worker.get_write_queue_size() == 8
    assert worker._process_tx_budget() is True
    assert worker.get_write_queue_size() == 7
    assert transport.written_bytes == len(chunk)
    transport.close()


def test_idle_polling_smoke():
    result = serial_loop_benchmark.bench_idle_polling(window_s=0.03)

    assert result.metrics["polls_s"] > 0
    assert result.metrics["poll_count"] > 0
    assert result.metrics["window_ms"] >= 20
    assert result.metrics["stop_ms"] >= 0


def test_serial_loop_run_all_schema(monkeypatch):
    monkeypatch.setattr(serial_loop_benchmark, "DEFAULT_REPEAT", 1)
    monkeypatch.setattr(serial_loop_benchmark, "DEFAULT_TX_CHUNKS", 8)

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
