"""TrafficMonitor / DataTrafficHandler 책임 경계 테스트."""
import inspect
from unittest.mock import MagicMock, call, patch

from common.dtos import PortDataEvent
from model.traffic_monitor import TrafficMonitor
from presenter.data_handler import DataTrafficHandler


def test_data_handler_does_not_write_data_logger_directly():
    source = inspect.getsource(DataTrafficHandler)

    assert "data_logger_manager" not in source
    assert "traffic_monitor.record_received" in source
    assert "traffic_monitor.record_sent" in source


def test_monitor_counts_rx_tx_and_take_resets_interval():
    monitor = TrafficMonitor()

    with patch("model.traffic_monitor.data_logger_manager.is_logging", return_value=False):
        monitor.record_received(PortDataEvent(port="COM1", data=b"1234"))
        monitor.record_sent(PortDataEvent(port="COM1", data=b"12"))

    assert monitor.rx_bytes == 4
    assert monitor.tx_bytes == 2

    stats = monitor.take_statistics()

    assert stats.rx_bytes == 4
    assert stats.tx_bytes == 2
    assert monitor.rx_bytes == 0
    assert monitor.tx_bytes == 0


def test_monitor_writes_full_duplex_data_when_logging_active():
    monitor = TrafficMonitor()
    rx = PortDataEvent(port="COM7", data=b"RX")
    tx = PortDataEvent(port="COM7", data=b"TX")

    with patch(
        "model.traffic_monitor.data_logger_manager.is_logging",
        return_value=True,
    ), patch("model.traffic_monitor.data_logger_manager.write") as write:
        monitor.record_received(rx)
        monitor.record_sent(tx)

    assert write.call_args_list == [
        call("COM7", b"RX"),
        call("COM7", b"TX"),
    ]


def test_data_handler_only_buffers_rx_for_view(qapp):
    view = MagicMock()
    monitor = MagicMock(spec=TrafficMonitor)
    handler = DataTrafficHandler(view, monitor)
    event = PortDataEvent(port="COM1", data=b"ABC")
    try:
        handler.on_fast_data_received(event)
        view.append_rx_data.assert_not_called()

        handler._flush_rx_buffer_to_ui()

        monitor.record_received.assert_called_once_with(event)
        batch = view.append_rx_data.call_args.args[0]
        assert batch.port == "COM1"
        assert batch.data == b"ABC"
    finally:
        handler.stop()
