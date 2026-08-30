"""main 대비 전체 diff 감사에서 발견된 runtime 회귀를 고정합니다."""

from unittest.mock import MagicMock, PropertyMock

import pytest
import serial

from common.dtos import PortConfig
from common.enums import ParserType
from core.transport.serial_transport import SerialTransport
from model.connection_controller import ConnectionController
from model.packet_parser_manager import PacketParserManager


def test_stale_worker_signal_does_not_remove_reconnected_session():
    parser_manager = PacketParserManager()
    controller = ConnectionController(packet_parser_manager=parser_manager)
    old_worker = MagicMock()
    new_worker = MagicMock()
    config = PortConfig(port="COM1")
    parser_manager.configure("COM1", config)
    controller.workers["COM1"] = new_worker
    controller.connection_configs["COM1"] = config

    controller.on_worker_terminated("COM1", old_worker)

    assert controller.workers["COM1"] is new_worker
    assert controller.connection_configs["COM1"] is config
    assert parser_manager.has_parser("COM1")


def test_current_worker_signal_still_cleans_session():
    parser_manager = PacketParserManager()
    controller = ConnectionController(packet_parser_manager=parser_manager)
    worker = MagicMock()
    config = PortConfig(port="COM1")
    parser_manager.configure("COM1", config)
    controller.workers["COM1"] = worker
    controller.connection_configs["COM1"] = config

    controller.on_worker_terminated("COM1", worker)

    assert "COM1" not in controller.workers
    assert "COM1" not in controller.connection_configs
    assert not parser_manager.has_parser("COM1")


def test_all_stale_worker_events_are_ignored_after_reconnect():
    parser_manager = PacketParserManager()
    controller = ConnectionController(packet_parser_manager=parser_manager)
    old_worker = MagicMock()
    new_worker = MagicMock()
    config = PortConfig(port="COM1")
    parser_manager.configure("COM1", config)
    controller.workers["COM1"] = old_worker
    controller.connection_configs["COM1"] = config
    assert controller._cleanup_worker_registry("COM1", old_worker) is True

    # 동일 port 재연결은 새 parser/session을 만들며 old final event보다 우선합니다.
    parser_manager.configure("COM1", config)
    controller.workers["COM1"] = new_worker
    controller.connection_configs["COM1"] = config
    opened = []
    errors = []
    received = []
    packets = []
    controller.connection_opened.connect(opened.append)
    controller.error_occurred.connect(errors.append)
    controller.data_received.connect(received.append)
    controller.packet_received.connect(packets.append)

    controller._on_worker_opened("COM1", old_worker)
    controller._on_worker_error("COM1", old_worker, "stale error")
    controller._on_worker_data_received("COM1", old_worker, b"stale data")

    assert opened == []
    assert errors == []
    assert received == []
    assert packets == []

    controller._on_worker_opened("COM1", new_worker)
    controller._on_worker_error("COM1", new_worker, "current error")
    controller._on_worker_data_received("COM1", new_worker, b"current data")

    assert opened[0].port == "COM1"
    assert errors[0].message == "current error"
    assert received[0].data == b"current data"
    assert packets[0].packet.data == b"current data"


def test_retiring_worker_final_data_is_kept_until_termination():
    controller = ConnectionController()
    worker = MagicMock()
    config = PortConfig(port="COM1")
    controller.packet_parser_manager.configure("COM1", config)
    controller.workers["COM1"] = worker
    controller.connection_configs["COM1"] = config
    received = []
    controller.data_received.connect(received.append)

    assert controller._cleanup_worker_registry("COM1", worker) is True
    controller._on_worker_data_received("COM1", worker, b"final data")

    assert received[0].data == b"final data"

    controller.on_worker_terminated("COM1", worker)
    controller._on_worker_data_received("COM1", worker, b"too late")
    assert len(received) == 1


def test_serial_transport_propagates_device_read_error():
    transport = SerialTransport(PortConfig(port="COM1"))
    serial_port = MagicMock()
    serial_port.is_open = True
    serial_port.read.side_effect = serial.SerialException("device disconnected")
    transport._serial = serial_port

    with pytest.raises(serial.SerialException, match="device disconnected"):
        transport.read(1)


def test_serial_transport_propagates_in_waiting_error():
    transport = SerialTransport(PortConfig(port="COM1"))
    serial_port = MagicMock()
    serial_port.is_open = True
    type(serial_port).in_waiting = PropertyMock(
        side_effect=serial.SerialException("device disconnected")
    )
    transport._serial = serial_port

    with pytest.raises(serial.SerialException, match="device disconnected"):
        _ = transport.in_waiting


@pytest.mark.parametrize("invalid_index", [None, "bad", object()])
def test_invalid_parser_preference_type_falls_back_to_raw(invalid_index):
    assert ParserType.from_preference_index(invalid_index) == ParserType.RAW
