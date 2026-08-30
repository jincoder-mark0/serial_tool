"""MacroExecutionCoordinator의 target/send/interruption orchestration 테스트."""
from unittest.mock import MagicMock

from common.dtos import ManualCommand, PortConnectionEvent
from model.command_transmission_service import TransmissionResult
from presenter.macro_execution_coordinator import MacroExecutionCoordinator


def _make_coordinator(local_echo_enabled: bool = True):
    runner = MagicMock()
    runner.isRunning.return_value = True
    controller = MagicMock()
    service = MagicMock()
    port_view = MagicMock()
    port_view.get_current_port_name.return_value = "COM1"
    settings = MagicMock()
    settings.get.return_value = local_echo_enabled
    coordinator = MacroExecutionCoordinator(
        runner,
        controller,
        service,
        port_view,
        settings,
    )
    return coordinator, runner, controller, service, port_view, settings


def test_macro_start_snapshots_current_port_once():
    coordinator, _, _, _, port_view, _ = _make_coordinator()
    coordinator._on_macro_started()
    assert coordinator.target_port == "COM1"
    port_view.get_current_port_name.assert_called_once()


def test_repeated_worker_send_uses_snapshot_without_view_lookup():
    coordinator, _, _, service, port_view, _ = _make_coordinator()
    coordinator._target_port = "COM1"
    service.send.return_value = TransmissionResult(True, data=b"OK")
    port_view.reset_mock()

    result = coordinator.deliver_repeated_command(ManualCommand(command="AT"))

    assert result.success is True
    assert service.send.call_args.kwargs["active_port"] == "COM1"
    port_view.get_current_port_name.assert_not_called()


def test_single_send_emits_local_echo_only_when_setting_enabled():
    coordinator, _, _, service, port_view, settings = _make_coordinator(True)
    service.send.return_value = TransmissionResult(True, data=b"AT")
    echoed = []
    coordinator.local_echo_requested.connect(echoed.append)

    coordinator.on_single_send_requested(ManualCommand(command="AT"))

    port_view.get_current_port_name.assert_called_once()
    assert service.send.call_args.kwargs["active_port"] == "COM1"
    settings.get.assert_called_once()
    assert echoed == [b"AT"]


def test_single_send_does_not_emit_local_echo_when_disabled():
    coordinator, _, _, service, _, _ = _make_coordinator(False)
    service.send.return_value = TransmissionResult(True, data=b"AT")
    echoed = []
    coordinator.local_echo_requested.connect(echoed.append)

    coordinator.on_single_send_requested(ManualCommand(command="AT"))

    assert echoed == []


def test_single_send_failure_stops_and_surfaces_reason():
    coordinator, runner, _, service, _, _ = _make_coordinator()
    service.send.return_value = TransmissionResult(False, message="send failed")
    reasons = []
    coordinator.execution_interrupted.connect(reasons.append)

    coordinator.on_single_send_requested(ManualCommand(command="AT"))

    runner.stop.assert_called_once()
    assert reasons == ["send failed"]


def test_target_port_close_stops_non_broadcast_macro():
    coordinator, runner, _, _, _, _ = _make_coordinator()
    coordinator._target_port = "COM1"
    runner.broadcast_enabled = False
    reasons = []
    coordinator.execution_interrupted.connect(reasons.append)

    coordinator.on_connection_closed(PortConnectionEvent(port="COM1", state="closed"))

    runner.stop.assert_called_once()
    assert "COM1" in reasons[0]


def test_other_port_close_does_not_stop_non_broadcast_macro():
    coordinator, runner, _, _, _, _ = _make_coordinator()
    coordinator._target_port = "COM1"
    runner.broadcast_enabled = False

    coordinator.on_connection_closed(PortConnectionEvent(port="COM2", state="closed"))

    runner.stop.assert_not_called()


def test_broadcast_macro_stops_when_no_broadcast_ports_remain():
    coordinator, runner, controller, _, _, _ = _make_coordinator()
    runner.broadcast_enabled = True
    controller.has_active_broadcast_ports.return_value = False
    reasons = []
    coordinator.execution_interrupted.connect(reasons.append)

    coordinator.on_connection_closed(PortConnectionEvent(port="COM2", state="closed"))

    runner.stop.assert_called_once()
    assert reasons == ["No active ports left. Macro stopped."]
