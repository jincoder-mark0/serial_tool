"""ShutdownCoordinator의 책임과 S-059 종료 순서를 검증합니다."""
from unittest.mock import MagicMock, patch

from common.constants import BACKGROUND_WORKER_STOP_TIMEOUT_MS
from core.data_logger import DataLoggerManager
from presenter.shutdown_coordinator import ShutdownCoordinator


def _make_coordinator():
    view = MagicMock()
    settings = MagicMock()
    controller = MagicMock()
    file_transfer = MagicMock()
    macro = MagicMock()
    macro_script = MagicMock()
    port_scan = MagicMock()
    manual = MagicMock()
    packet = MagicMock()
    data = MagicMock()
    close_system_log = MagicMock()
    status = MagicMock()
    data_logger_manager = MagicMock(spec=DataLoggerManager)
    # MagicMock의 기본 반환값은 truthy다. 드레인 대기 루프는 이 값이 False가 될
    # 때까지 도므로, 기본을 "남은 드레인 없음"으로 명시하지 않으면 테스트가 멈춘다.
    controller.has_pending_flush.return_value = False

    coordinator = ShutdownCoordinator(
        view=view,
        settings_manager=settings,
        connection_controller=controller,
        file_transfer_manager=file_transfer,
        macro_runner=macro,
        macro_script_manager=macro_script,
        port_scan_manager=port_scan,
        manual_control_presenter=manual,
        packet_presenter=packet,
        data_handler=data,
        close_system_log=close_system_log,
        status_coordinator=status,
        data_logger_manager=data_logger_manager,
    )
    return (
        coordinator,
        view,
        settings,
        controller,
        file_transfer,
        macro,
        macro_script,
        port_scan,
        manual,
        packet,
        data,
        close_system_log,
        status,
        data_logger_manager,
    )


def test_shutdown_stops_runtime_services_and_saves_state():
    (
        coordinator,
        view,
        settings,
        controller,
        file_transfer,
        macro,
        macro_script,
        port_scan,
        manual,
        packet,
        data,
        close_system_log,
        status,
        data_logger_manager,
    ) = _make_coordinator()
    macro.isRunning.return_value = True
    controller.has_active_connection = True
    window_state = view.get_window_state.return_value
    manual_state = manual.get_state.return_value

    with patch(
        "presenter.shutdown_coordinator.ShutdownStateCollector.collect_and_apply"
    ) as collect, patch(
        "presenter.shutdown_coordinator.QCoreApplication.processEvents"
    ):
        coordinator.shutdown()

    data_logger_manager.stop_all.assert_called_once()
    macro.stop.assert_called_once()
    # 상한은 stop()에 전달돼야 한다. 과거처럼 stop() 뒤에 wait(1000)을 두면
    # stop() 내부의 무한 대기가 먼저 끝나 상한이 아무 역할도 못 한다.
    assert macro.stop.call_args.kwargs.get("timeout_ms") == BACKGROUND_WORKER_STOP_TIMEOUT_MS
    file_transfer.shutdown.assert_called_once()
    macro_script.stop.assert_called_once()
    port_scan.stop.assert_called_once()
    data.stop.assert_called_once()
    packet.stop.assert_called_once()
    status.stop.assert_called_once()
    manual.stop_auto_tx.assert_called_once()
    close_system_log.assert_called_once()
    collect.assert_called_once_with(settings, window_state, manual_state)
    settings.save_settings.assert_called_once()
    controller.close_connection.assert_called_once_with()


def test_auto_tx_is_stopped_before_manual_state_is_collected():
    coordinator, _, _, controller, _, macro, _, _, manual, *_rest = _make_coordinator()
    macro.isRunning.return_value = False
    controller.has_active_connection = False
    order = []
    manual.stop_auto_tx.side_effect = lambda: order.append("stop_auto_tx")
    manual.get_state.side_effect = lambda: order.append("get_state") or MagicMock()

    with patch(
        "presenter.shutdown_coordinator.ShutdownStateCollector.collect_and_apply"
    ), patch(
        "presenter.shutdown_coordinator.QCoreApplication.processEvents"
    ):
        coordinator.shutdown()

    assert order.index("stop_auto_tx") < order.index("get_state")


def test_connection_closes_before_queued_events_and_data_logger_stop():
    (
        coordinator, _view, _settings, controller, _ft, macro, *_rest
    ) = _make_coordinator()
    data_logger_manager = _rest[-1]
    macro.isRunning.return_value = False
    controller.has_active_connection = True
    order = []
    controller.close_connection.side_effect = lambda: order.append("close_connection")
    data_logger_manager.stop_all.side_effect = lambda: order.append("logger_stop")

    with patch(
        "presenter.shutdown_coordinator.QCoreApplication.processEvents",
        side_effect=lambda: order.append("process_events"),
    ):
        coordinator.shutdown()

    assert order == ["close_connection", "process_events", "logger_stop"]


def test_macro_runner_stop_receives_the_shutdown_timeout():
    """
    종료 시 매크로 정지는 상한을 **stop()에 넘겨야** 실제로 적용된다.

    ## WHY
    과거 코드는 `stop()` 다음 줄에서 `wait(1000)`을 불렀다. 그런데 `stop()`은 내부에서
    이미 상한 없는 `wait()`을 하므로, 그 다음 `wait(1000)`은 항상 **이미 끝난 스레드**를
    기다렸다. 1초 상한이라는 의도가 코드에 적혀만 있고 아무 역할도 하지 못했다 —
    매크로 스레드가 늦게 끝나면 종료가 그만큼 무한정 늘어졌다.
    """
    coordinator, _view, _settings, _controller, _ft, macro, *_rest = _make_coordinator()
    macro.isRunning.return_value = True

    with patch("presenter.shutdown_coordinator.QCoreApplication"):
        coordinator.shutdown()

    macro.stop.assert_called_once()
    assert macro.stop.call_args.kwargs.get("timeout_ms") == BACKGROUND_WORKER_STOP_TIMEOUT_MS, (
        "상한이 stop()에 전달되지 않았다 — stop() 뒤에 wait(timeout)을 두면 "
        "stop() 내부의 무한 대기가 먼저 끝나 상한이 무의미해진다"
    )


def test_shutdown_continues_when_macro_runner_does_not_stop_in_time():
    """상한을 넘겨도 종료 시퀀스의 나머지는 계속 진행돼야 한다."""
    (
        coordinator, _view, settings, controller, _ft, macro, *_rest
    ) = _make_coordinator()
    macro.isRunning.return_value = True
    macro.stop.return_value = False

    with patch("presenter.shutdown_coordinator.QCoreApplication"):
        coordinator.shutdown()

    controller.close_connection.assert_called_once()
    settings.save_settings.assert_called_once()
