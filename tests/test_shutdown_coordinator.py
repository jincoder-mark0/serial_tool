"""ShutdownCoordinator의 책임과 S-059 종료 순서를 검증합니다."""
from unittest.mock import MagicMock, call, patch

from presenter.shutdown_coordinator import ShutdownCoordinator


def _make_coordinator():
    view = MagicMock()
    settings = MagicMock()
    controller = MagicMock()
    macro = MagicMock()
    port = MagicMock()
    manual = MagicMock()
    packet = MagicMock()
    data = MagicMock()
    close_system_log = MagicMock()
    timer = MagicMock()

    coordinator = ShutdownCoordinator(
        view=view,
        settings_manager=settings,
        connection_controller=controller,
        macro_runner=macro,
        port_presenter=port,
        manual_control_presenter=manual,
        packet_presenter=packet,
        data_handler=data,
        close_system_log=close_system_log,
        status_timer=timer,
    )
    return coordinator, view, settings, controller, macro, port, manual, packet, data, close_system_log, timer


def test_shutdown_stops_runtime_services_and_saves_state():
    (
        coordinator, view, settings, controller, macro, port,
        manual, packet, data, close_system_log, timer,
    ) = _make_coordinator()
    macro.isRunning.return_value = True
    controller.has_active_connection = True
    window_state = view.get_window_state.return_value
    manual_state = manual.get_state.return_value

    with patch(
        "presenter.shutdown_coordinator.ShutdownStateCollector.collect_and_apply"
    ) as collect, patch(
        "presenter.shutdown_coordinator.QCoreApplication.processEvents"
    ), patch(
        "presenter.shutdown_coordinator.data_logger_manager.stop_all"
    ):
        coordinator.shutdown()

    macro.stop.assert_called_once()
    macro.wait.assert_called_once_with(1000)
    port.stop_pending_scan.assert_called_once()
    data.stop.assert_called_once()
    packet.stop.assert_called_once()
    timer.stop.assert_called_once()
    close_system_log.assert_called_once()
    collect.assert_called_once_with(settings, window_state, manual_state)
    settings.save_settings.assert_called_once()
    controller.close_connection.assert_called_once_with()


def test_connection_closes_before_queued_events_and_data_logger_stop():
    coordinator, _, _, controller, macro, *_ = _make_coordinator()
    macro.isRunning.return_value = False
    controller.has_active_connection = True
    order = []
    controller.close_connection.side_effect = lambda: order.append("close_connection")

    with patch(
        "presenter.shutdown_coordinator.QCoreApplication.processEvents",
        side_effect=lambda: order.append("process_events"),
    ), patch(
        "presenter.shutdown_coordinator.data_logger_manager.stop_all",
        side_effect=lambda: order.append("logger_stop"),
    ):
        coordinator.shutdown()

    assert order == ["close_connection", "process_events", "logger_stop"]
