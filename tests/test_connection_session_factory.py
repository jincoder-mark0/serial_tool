"""ConnectionSessionFactory / ConnectionController 생성 책임 경계 테스트."""
import inspect
from unittest.mock import patch

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from model.connection_controller import ConnectionController
from model.connection_session_factory import ConnectionSessionFactory


def test_controller_does_not_import_or_construct_concrete_transports():
    source = inspect.getsource(ConnectionController)

    assert "LoopbackTransport" not in source
    assert "SerialTransport" not in source
    assert "ConnectionWorker(" not in source
    assert "session_factory.create_worker(config)" in source


def test_factory_builds_loopback_worker_for_reserved_port():
    factory = ConnectionSessionFactory()
    config = PortConfig(port=LOOPBACK_PORT_NAME)

    worker = factory.create_worker(config)

    assert worker.connection_name == LOOPBACK_PORT_NAME
    assert worker.transport.__class__.__name__ == "LoopbackTransport"


def test_factory_builds_serial_worker_for_regular_port():
    factory = ConnectionSessionFactory()
    config = PortConfig(port="COM9")

    with patch("model.connection_session_factory.SerialTransport") as transport_cls, patch(
        "model.connection_session_factory.ConnectionWorker"
    ) as worker_cls:
        transport = transport_cls.return_value
        worker = worker_cls.return_value
        result = factory.create_worker(config)

    transport_cls.assert_called_once_with(config)
    worker_cls.assert_called_once_with(transport, "COM9")
    assert result is worker


def test_controller_removes_parser_session_if_worker_factory_fails():
    parser_manager = __import__(
        "model.packet_parser_manager", fromlist=["PacketParserManager"]
    ).PacketParserManager()
    factory = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    factory.create_worker.side_effect = OSError("cannot create worker")
    controller = ConnectionController(parser_manager, factory)
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.open_connection(PortConfig(port="COM9")) is False

    assert not parser_manager.has_parser("COM9")
    assert len(errors) == 1
    assert "connection session" in errors[0].message.lower()
