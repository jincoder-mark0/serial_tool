"""Integration tests for the current MVP component contracts."""

import time
from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import QCoreApplication

from common.dtos import PacketEvent, PortDataEvent
from model.packet_parser import Packet
from presenter.main_presenter import MainPresenter


def wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def mock_main_window(qapp):
    window = MagicMock()
    window.port_view = MagicMock()
    window.macro_view = MagicMock()
    window.manual_control_view = MagicMock()
    window.packet_view = MagicMock()
    window.get_port_tabs_count.return_value = 0
    return window


@pytest.fixture
def integration_system(mock_main_window, mock_serial_port, mock_settings_manager):
    presenter = MainPresenter(
        mock_main_window,
        settings_manager=mock_settings_manager,
    )
    yield presenter, mock_main_window, mock_serial_port

    presenter.data_handler.stop()
    presenter.packet_presenter.stop()
    if presenter.status_timer:
        presenter.status_timer.stop()
    presenter.connection_controller.close_connection()


def test_system_initialization_wires_facade_views(integration_system):
    presenter, window, _ = integration_system

    assert presenter.port_presenter is not None
    assert presenter.macro_presenter is not None
    assert presenter.manual_control_presenter is not None
    assert presenter.packet_presenter is not None
    assert not hasattr(presenter, "event_router")
    window.connect_port_tab_changed.assert_called_once()
    window.manual_control_view.send_requested.connect.assert_called()


def test_connection_send_and_close_flow(
    integration_system,
    sample_port_config,
):
    presenter, _, mock_serial = integration_system
    controller = presenter.connection_controller

    assert controller.open_connection(sample_port_config) is True
    controller.send_data(sample_port_config.port, b"TEST_MSG")

    assert wait_until(lambda: mock_serial.write.called)
    mock_serial.write.assert_called_with(b"TEST_MSG")

    controller.close_connection(sample_port_config.port)
    assert sample_port_config.port not in controller.workers


def test_data_reception_fast_path_batches_for_view(integration_system):
    presenter, window, _ = integration_system
    event = PortDataEvent(port="COM1", data=b"HELLO_WORLD")

    presenter.connection_controller.data_received.emit(event)
    presenter.data_handler._flush_rx_buffer_to_ui()

    batch = window.append_rx_data.call_args[0][0]
    assert batch.port == "COM1"
    assert batch.data == b"HELLO_WORLD"


def test_packet_event_is_formatted_for_packet_view(integration_system):
    presenter, window, _ = integration_system
    event = PacketEvent(
        port="COM1",
        packet=Packet(
            data=b"\xaa\xbb",
            timestamp=0,
            metadata={"type": "TEST_PKT"},
        ),
    )

    presenter.connection_controller.packet_received.emit(event)
    presenter.packet_presenter._flush_pending_packets()

    view_data = window.packet_view.append_packet.call_args[0][0]
    assert view_data.data_hex == "AA BB"
    assert view_data.packet_type == "TEST_PKT"
