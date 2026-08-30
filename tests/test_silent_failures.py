"""
조용한 실패 회귀 테스트.

수동/Auto Tx 전송 실패가 사용자 알림 signal로 표면화되는지와 MacroRunner의
종료 signal이 정상/수동 종료 모두 정확히 한 번 발생하는지 검증합니다.
현재 runtime topology는 EventBus가 아니라 direct Qt signal을 사용합니다.
"""
from unittest.mock import MagicMock

from common.dtos import MacroEntry, MacroSendResult, ManualCommand
from model.command_transmission_service import CommandTransmissionService
from model.macro_runner import MacroRunner
from presenter.manual_control_presenter import ManualControlPresenter


def _make_presenter(
    controller: MagicMock,
    *,
    hex_mode: bool = False,
    broadcast: bool = False,
    text: str = "ZZ",
) -> tuple[ManualControlPresenter, MagicMock]:
    """현재 ManualControlPresenter/TransmissionService 경계로 테스트 조립체를 만듭니다."""
    panel = MagicMock()
    panel.get_input_text.return_value = text
    panel.is_hex_mode.return_value = hex_mode
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = broadcast
    panel.is_rts_enabled.return_value = False
    panel.is_dtr_enabled.return_value = False
    panel.get_auto_tx_interval_ms.return_value = 1000

    port_view = MagicMock()
    port_view.get_current_port_name.return_value = "COM1"

    settings = MagicMock()
    settings.get.return_value = None
    transmission_service = CommandTransmissionService(controller, settings)

    presenter = ManualControlPresenter(
        panel=panel,
        port_view=port_view,
        connection_controller=controller,
        transmission_service=transmission_service,
    )
    return presenter, panel


class TestManualSendFailureSurfacing:
    def test_invalid_hex_input_emits_send_error(self, qapp):
        controller = MagicMock()
        presenter, _ = _make_presenter(controller, hex_mode=True, text="ZZ")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        presenter.on_send_requested()

        controller.send_data.assert_not_called()
        error_spy.assert_called_once()
        title, message, show_dialog = error_spy.call_args[0]
        assert title
        assert message
        assert show_dialog is True

    def test_disconnected_port_emits_send_error(self, qapp):
        controller = MagicMock()
        controller.is_connection_open.return_value = False
        presenter, _ = _make_presenter(controller, text="TEST")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        presenter.on_send_requested()

        controller.send_data.assert_not_called()
        error_spy.assert_called_once()
        _title, message, show_dialog = error_spy.call_args[0]
        assert message
        assert show_dialog is True

    def test_broadcast_no_active_ports_emits_send_error(self, qapp):
        controller = MagicMock()
        controller.has_active_broadcast_ports.return_value = False
        presenter, _ = _make_presenter(controller, broadcast=True, text="TEST")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        presenter.on_send_requested()

        controller.send_broadcast_data.assert_not_called()
        error_spy.assert_called_once()
        _title, message, show_dialog = error_spy.call_args[0]
        assert message
        assert show_dialog is True

    def test_valid_send_does_not_emit_send_error(self, qapp):
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.send_data.return_value = True
        presenter, _ = _make_presenter(controller, text="OK")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        presenter.on_send_requested()

        controller.send_data.assert_called_once_with("COM1", b"OK")
        error_spy.assert_not_called()


class TestAutoTxFailureDoesNotFlood:
    def test_repeated_auto_tx_failure_notifies_once_without_dialog(self, qapp):
        controller = MagicMock()
        controller.is_connection_open.return_value = False
        presenter, _ = _make_presenter(controller, text="AT")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        command = ManualCommand(command="AT")
        presenter._on_auto_tx_send_requested(command)
        presenter._on_auto_tx_send_requested(command)
        presenter._on_auto_tx_send_requested(command)

        error_spy.assert_called_once()
        _title, _message, show_dialog = error_spy.call_args[0]
        assert show_dialog is False

    def test_auto_tx_failure_notifies_again_after_recovering(self, qapp):
        controller = MagicMock()
        presenter, _ = _make_presenter(controller, text="AT")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)
        command = ManualCommand(command="AT")

        controller.is_connection_open.return_value = False
        presenter._on_auto_tx_send_requested(command)

        controller.is_connection_open.return_value = True
        controller.send_data.return_value = True
        presenter._on_auto_tx_send_requested(command)

        controller.is_connection_open.return_value = False
        presenter._on_auto_tx_send_requested(command)

        assert error_spy.call_count == 2


class TestMacroFinishedNotificationConsistency:
    def test_normal_completion_emits_macro_finished_signal_once(self, qapp, qtbot):
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=0)])
        runner.set_send_handler(lambda _cmd: MacroSendResult(True))

        finished_spy = MagicMock()
        runner.macro_finished.connect(finished_spy)

        with qtbot.waitSignal(runner.macro_finished, timeout=3000):
            runner.start(loop_count=1, interval_ms=0)

        qapp.processEvents()
        assert finished_spy.call_count == 1
        assert runner.last_run_succeeded is True

    def test_manual_stop_emits_macro_finished_signal_exactly_once(self, qapp, qtbot):
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])
        runner.set_send_handler(lambda _cmd: MacroSendResult(True))

        finished_spy = MagicMock()
        runner.macro_finished.connect(finished_spy)

        runner.start(loop_count=0, interval_ms=0)
        qtbot.wait(100)
        runner.stop()

        qtbot.waitUntil(lambda: finished_spy.call_count >= 1, timeout=1000)
        qapp.processEvents()
        assert finished_spy.call_count == 1
        assert not runner.isRunning()
        assert runner.last_run_succeeded is False

    def test_start_then_immediate_stop_does_not_deadlock(self, qapp, qtbot):
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])
        runner.set_send_handler(lambda _cmd: MacroSendResult(True))

        finished_spy = MagicMock()
        runner.macro_finished.connect(finished_spy)

        runner.start(loop_count=0, interval_ms=0)
        runner.stop()

        qtbot.waitUntil(lambda: finished_spy.call_count >= 1, timeout=1000)
        qapp.processEvents()
        assert finished_spy.call_count == 1
        assert not runner.isRunning()
        assert runner.last_run_succeeded is False

    def test_start_while_running_is_rejected_without_replacing_state(self, qapp, qtbot):
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])
        runner.set_send_handler(lambda _cmd: MacroSendResult(True))
        errors = []
        runner.error_occurred.connect(errors.append)

        runner.start(loop_count=0)
        qtbot.waitUntil(runner.isRunning, timeout=1000)
        runner.start(loop_count=2)

        assert errors
        assert "already running" in errors[-1].message
        runner.stop()
