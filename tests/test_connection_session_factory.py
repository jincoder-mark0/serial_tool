"""ConnectionSessionFactory / ConnectionController 생성 책임 경계 테스트."""
import inspect
from unittest.mock import MagicMock, patch

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from model.connection_controller import ConnectionController
from model.connection_session_factory import ConnectionSessionFactory
from model.packet_parser_manager import PacketParserManager


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
    parser_manager = PacketParserManager()
    factory = MagicMock()
    factory.create_worker.side_effect = OSError("cannot create worker")
    controller = ConnectionController(parser_manager, factory)
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.open_connection(PortConfig(port="COM9")) is False

    assert not parser_manager.has_parser("COM9")
    assert len(errors) == 1
    assert "connection session" in errors[0].message.lower()


def test_connection_closing_is_emitted_before_worker_stop():
    """`connection_closing`은 worker에 종료를 요청하기 **전에** 나가야 한다.

    FileTransferManager 등 소비자가 이 신호를 받아 자기 세션을 먼저 취소한다 —
    순서가 뒤집히면 취소하기도 전에 드레인이 시작된다.
    """
    controller = ConnectionController()
    worker = MagicMock()
    order = []
    controller.workers["COM1"] = worker
    controller.connection_configs["COM1"] = PortConfig(port="COM1")
    controller.connection_closing.connect(lambda port: order.append(f"closing:{port}"))
    worker.request_stop.side_effect = lambda: order.append("worker.request_stop")

    controller.close_connection("COM1")

    assert order[:2] == ["closing:COM1", "worker.request_stop"]
    assert "COM1" not in controller.workers
