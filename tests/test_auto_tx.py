"""
AutoTxScheduler 및 현재 ManualControlPresenter 배선 테스트.

스케줄러의 반복 규칙과 Presenter가 CommandTransmissionService/port View facade를
사용하는지 검증합니다.
"""
from unittest.mock import MagicMock

from common.constants import MIN_AUTO_TX_INTERVAL_MS
from common.dtos import ManualCommand
from model.auto_tx import AutoTxScheduler
from model.command_transmission_service import CommandTransmissionService
from presenter.manual_control_presenter import ManualControlPresenter
from view.panels.manual_control_panel import ManualControlPanel


class TestAutoTxScheduler:
    def test_start_emits_immediately(self, qapp):
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        scheduler.start(command, interval_ms=5000, max_runs=0)

        send_spy.assert_called_once_with(command)
        assert scheduler.is_running
        scheduler.stop()

    def test_max_runs_reached_stops_and_emits_finished(self, qapp, qtbot):
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        with qtbot.waitSignal(scheduler.finished, timeout=2000):
            scheduler.start(
                command,
                interval_ms=MIN_AUTO_TX_INTERVAL_MS,
                max_runs=2,
            )

        assert send_spy.call_count == 2
        assert not scheduler.is_running

    def test_stop_prevents_further_emission(self, qapp, qtbot):
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        scheduler.start(command, interval_ms=MIN_AUTO_TX_INTERVAL_MS, max_runs=0)
        scheduler.stop()
        qtbot.wait(200)

        assert send_spy.call_count == 1
        assert not scheduler.is_running

    def test_interval_is_clamped_to_minimum(self, qapp):
        scheduler = AutoTxScheduler()
        command = ManualCommand(command="AT")

        scheduler.start(command, interval_ms=1, max_runs=0)

        assert scheduler._timer.interval() == MIN_AUTO_TX_INTERVAL_MS
        scheduler.stop()

    def test_restart_replaces_previous_command(self, qapp):
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command1 = ManualCommand(command="AT1")
        command2 = ManualCommand(command="AT2")

        scheduler.start(command1, interval_ms=5000, max_runs=0)
        scheduler.start(command2, interval_ms=5000, max_runs=0)

        assert send_spy.call_count == 2
        assert send_spy.call_args[0][0] is command2
        assert scheduler.is_running
        scheduler.stop()


def _make_mock_panel(text: str = "AT", interval_ms: int = 200) -> MagicMock:
    panel = MagicMock(spec=ManualControlPanel)
    panel.get_input_text.return_value = text
    panel.is_hex_mode.return_value = False
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = False
    panel.is_rts_enabled.return_value = False
    panel.is_dtr_enabled.return_value = False
    panel.get_auto_tx_interval_ms.return_value = interval_ms
    return panel


def _make_presenter(panel, controller):
    port_view = MagicMock()
    port_view.get_current_port_name.return_value = "COM1"
    settings = MagicMock()
    settings.get.return_value = None
    service = CommandTransmissionService(controller, settings)
    return ManualControlPresenter(
        panel=panel,
        port_view=port_view,
        connection_controller=controller,
        transmission_service=service,
    )


class TestManualControlPresenterAutoTxWiring:
    def test_toggle_on_starts_scheduler_and_sends_via_shared_service(self, qapp):
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.send_data.return_value = True
        controller.has_active_connection = True
        presenter = _make_presenter(panel, controller)

        presenter.on_auto_tx_toggled(True)

        assert presenter.auto_tx_scheduler.is_running
        controller.send_data.assert_called_once_with("COM1", b"AT")

        presenter.on_auto_tx_toggled(False)
        assert not presenter.auto_tx_scheduler.is_running

    def test_toggle_on_with_invalid_panel_state_reverts_checkbox(self, qapp):
        panel = MagicMock(spec=ManualControlPanel)
        panel.get_input_text.side_effect = AttributeError("boom")
        controller = MagicMock()
        presenter = _make_presenter(panel, controller)

        presenter.on_auto_tx_toggled(True)

        assert not presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_called_once_with(False)

    def test_connection_closed_stops_auto_tx_when_no_active_ports(self, qapp):
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.send_data.return_value = True
        controller.has_active_connection = True
        presenter = _make_presenter(panel, controller)
        presenter.on_auto_tx_toggled(True)
        assert presenter.auto_tx_scheduler.is_running

        controller.has_active_connection = False
        presenter._on_connection_closed()

        assert not presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_called_once_with(False)

    def test_connection_closed_keeps_running_when_other_ports_active(self, qapp):
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.send_data.return_value = True
        controller.has_active_connection = True
        presenter = _make_presenter(panel, controller)
        presenter.on_auto_tx_toggled(True)

        presenter._on_connection_closed()

        assert presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_not_called()
        presenter.on_auto_tx_toggled(False)
