"""Integration tests for the current MVP component contracts."""

import time
from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import QCoreApplication

from application_bootstrap import ApplicationBootstrapper
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
    return window


@pytest.fixture
def integration_system(mock_main_window, mock_serial_port, mock_settings_manager):
    components = ApplicationBootstrapper(mock_main_window, mock_settings_manager).build()
    presenter = MainPresenter(
        mock_main_window,
        dependencies=components.main_presenter_dependencies,
    )
    yield presenter, components, mock_main_window, mock_serial_port

    components.status_coordinator.stop()
    components.data_handler.stop()
    components.packet_presenter.stop()
    components.file_transfer_manager.shutdown()
    components.macro_script_manager.stop()
    components.port_scan_manager.stop()
    components.connection_controller.close_connection()


def test_system_initialization_wires_facade_views(integration_system):
    presenter, components, window, _ = integration_system
    assert presenter.port_presenter is not None
    assert presenter.manual_control_presenter is not None
    assert presenter.macro_execution_coordinator is not None
    assert presenter.shutdown_coordinator is not None
    for hidden in (
        "event_router",
        "settings_manager",
        "data_handler",
        "status_coordinator",
        "file_transfer_manager",
        "macro_presenter",
        "packet_presenter",
    ):
        assert not hasattr(presenter, hidden)
    assert components.control_state_coordinator is not None
    assert components.settings_coordinator is not None
    window.manual_control_view.send_requested.connect.assert_called()


def test_connection_send_and_close_flow(integration_system, sample_port_config):
    presenter, _, _, mock_serial = integration_system
    controller = presenter.connection_controller
    assert controller.open_connection(sample_port_config) is True
    controller.send_data(sample_port_config.port, b"TEST_MSG")
    assert wait_until(lambda: mock_serial.write.called)
    mock_serial.write.assert_called_with(b"TEST_MSG")
    controller.close_connection(sample_port_config.port)
    assert sample_port_config.port not in controller.workers


def test_data_reception_fast_path_batches_for_view(integration_system):
    presenter, components, window, _ = integration_system
    event = PortDataEvent(port="COM1", data=b"HELLO_WORLD")
    presenter.connection_controller.data_received.emit(event)
    components.data_handler._flush_rx_buffer_to_ui()
    batch = window.append_rx_data.call_args[0][0]
    assert batch.port == "COM1"
    assert batch.data == b"HELLO_WORLD"


def test_packet_event_is_formatted_for_packet_view(integration_system):
    presenter, components, window, _ = integration_system
    event = PacketEvent(
        port="COM1",
        packet=Packet(data=b"\xaa\xbb", timestamp=0, metadata={"type": "TEST_PKT"}),
    )
    presenter.connection_controller.packet_received.emit(event)
    components.packet_presenter._flush_pending_packets()
    view_data = window.packet_view.append_packet.call_args[0][0]
    assert view_data.data_hex == "AA BB"
    assert view_data.packet_type == "TEST_PKT"
