"""CommandTransmissionService와 Presenter 경계 회귀 테스트."""
import inspect

from common.dtos import ManualCommand
from common.enums import TransmissionErrorCode
from model.command_transmission_service import CommandTransmissionService
from presenter.main_presenter import MainPresenter
from presenter.manual_control_presenter import ManualControlPresenter


class _FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class _FakeController:
    def __init__(self):
        self.open_ports = set()
        self.broadcast_available = False
        self.broadcast_result = True
        self.single_result = True
        self.single_calls = []
        self.broadcast_calls = []

    def has_active_broadcast_ports(self):
        return self.broadcast_available

    def send_broadcast_data(self, data):
        self.broadcast_calls.append(data)
        return self.broadcast_result

    def is_connection_open(self, port):
        return port in self.open_ports

    def send_data(self, port, data):
        self.single_calls.append((port, data))
        return self.single_result


def test_single_send_is_processed_and_sent_by_service():
    controller = _FakeController()
    controller.open_ports.add("COM1")
    settings = _FakeSettings()
    service = CommandTransmissionService(controller, settings)

    result = service.send(ManualCommand(command="AT"), active_port="COM1")

    assert result.success is True
    assert result.data == b"AT"
    assert controller.single_calls == [("COM1", b"AT")]


def test_invalid_hex_command_returns_classified_failure():
    service = CommandTransmissionService(_FakeController(), _FakeSettings())

    result = service.send(
        ManualCommand(command="GG", hex_mode=True),
        active_port="COM1",
    )

    assert result.success is False
    assert result.error_code is TransmissionErrorCode.INVALID_COMMAND


def test_broadcast_without_target_returns_classified_failure():
    controller = _FakeController()
    service = CommandTransmissionService(controller, _FakeSettings())

    result = service.send(
        ManualCommand(command="AT", broadcast_enabled=True),
    )

    assert result.success is False
    assert result.error_code is TransmissionErrorCode.NO_BROADCAST_TARGET
    assert controller.broadcast_calls == []


def test_presenters_do_not_own_command_processing_or_send_branching():
    manual_source = inspect.getsource(ManualControlPresenter)
    main_source = inspect.getsource(MainPresenter)

    assert "CommandProcessor" not in manual_source
    assert "CommandProcessor" not in main_source
    assert "send_broadcast_data(" not in manual_source
    assert "send_data(" not in manual_source
    assert "send_broadcast_data(" not in main_source
    assert "send_data(" not in main_source


def test_macro_worker_send_handler_does_not_read_view_state():
    source = inspect.getsource(MainPresenter.deliver_macro_command)

    assert "port_presenter" not in source
    assert "self.view" not in source
    assert "_macro_target_port" in source
    assert "command_transmission_service.send" in source


def test_manual_presenter_uses_shared_transmission_service():
    source = inspect.getsource(ManualControlPresenter._process_and_send)

    assert "transmission_service.send" in source
