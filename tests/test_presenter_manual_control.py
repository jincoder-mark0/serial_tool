"""ManualControlPresenter의 View orchestration 책임을 검증합니다."""
from unittest.mock import MagicMock

import pytest

from common.dtos import ManualControlState
from common.enums import TransmissionErrorCode
from model.command_transmission_service import TransmissionResult
from presenter.manual_control_presenter import ManualControlPresenter
from view.panels.manual_control_panel import ManualControlPanel
from view.sections.main_left_section import MainLeftSection


@pytest.fixture
def mock_panel():
    panel = MagicMock(spec=ManualControlPanel)
    panel.get_input_text.return_value = ""
    panel.is_hex_mode.return_value = False
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = False
    panel.is_rts_enabled.return_value = False
    panel.is_dtr_enabled.return_value = False
    panel.is_auto_tx_enabled.return_value = False
    panel.get_auto_tx_interval_ms.return_value = 1000
    return panel


@pytest.fixture
def mock_port_view():
    view = MagicMock(spec=MainLeftSection)
    view.get_current_port_name.return_value = "COM1"
    return view


@pytest.fixture
def presenter(mock_panel, mock_port_view):
    controller = MagicMock()
    controller.has_active_connection = True
    transmission_service = MagicMock()
    transmission_service.send.return_value = TransmissionResult(
        success=True,
        data=b"TEST",
    )
    instance = ManualControlPresenter(
        panel=mock_panel,
        port_view=mock_port_view,
        connection_controller=controller,
        transmission_service=transmission_service,
    )
    return instance


def configure_command(
    panel,
    text,
    *,
    hex_mode=False,
    prefix=False,
    suffix=False,
    local_echo=False,
    broadcast=False,
):
    panel.get_input_text.return_value = text
    panel.is_hex_mode.return_value = hex_mode
    panel.is_prefix_enabled.return_value = prefix
    panel.is_suffix_enabled.return_value = suffix
    panel.is_local_echo_enabled.return_value = local_echo
    panel.is_broadcast_enabled.return_value = broadcast


def test_initialization_connects_view_signals(presenter, mock_panel):
    mock_panel.send_requested.connect.assert_called()
    mock_panel.dtr_changed.connect.assert_called()
    mock_panel.rts_changed.connect.assert_called()
    mock_panel.broadcast_changed.connect.assert_called()
    mock_panel.auto_tx_toggled.connect.assert_called()


def test_single_port_command_is_delegated_with_current_port(
    presenter,
    mock_panel,
    mock_port_view,
):
    configure_command(mock_panel, "TEST")

    presenter.on_send_requested()

    command = presenter.transmission_service.send.call_args.args[0]
    assert command.command == "TEST"
    assert command.broadcast_enabled is False
    presenter.transmission_service.send.assert_called_once_with(
        command,
        active_port="COM1",
    )
    mock_port_view.get_current_port_name.assert_called_once()


def test_broadcast_command_does_not_resolve_current_port(
    presenter,
    mock_panel,
    mock_port_view,
):
    configure_command(mock_panel, "BCAST", broadcast=True)

    presenter.on_send_requested()

    command = presenter.transmission_service.send.call_args.args[0]
    presenter.transmission_service.send.assert_called_once_with(
        command,
        active_port=None,
    )
    mock_port_view.get_current_port_name.assert_not_called()


def test_successful_send_requests_local_echo_via_signal(presenter, mock_panel):
    configure_command(mock_panel, "TEST", local_echo=True)
    presenter.local_echo_enabled = True
    presenter.transmission_service.send.return_value = TransmissionResult(
        success=True,
        data=b"HELLO",
    )
    echoed = []
    presenter.local_echo_requested.connect(echoed.append)

    presenter.on_send_requested()

    assert echoed == [b"HELLO"]


def test_failed_send_emits_user_error_without_echo(presenter, mock_panel):
    configure_command(mock_panel, "TEST")
    presenter.transmission_service.send.return_value = TransmissionResult(
        success=False,
        message="No port selected.",
        error_code=TransmissionErrorCode.NO_ACTIVE_PORT,
    )
    errors = []
    echoes = []
    presenter.send_error.connect(lambda *args: errors.append(args))
    presenter.local_echo_requested.connect(echoes.append)

    presenter.on_send_requested()

    assert len(errors) == 1
    assert errors[0][2] is True
    assert echoes == []


def test_missing_current_port_is_passed_as_none_to_service(
    presenter,
    mock_panel,
    mock_port_view,
):
    configure_command(mock_panel, "TEST")
    mock_port_view.get_current_port_name.return_value = ""

    presenter.on_send_requested()

    assert presenter.transmission_service.send.call_args.kwargs["active_port"] is None


def test_hardware_control_is_forwarded(presenter):
    presenter.on_dtr_changed(True)
    presenter.on_rts_changed(False)

    presenter.connection_controller.set_dtr.assert_called_once_with(True)
    presenter.connection_controller.set_rts.assert_called_once_with(False)


def test_state_is_collected_through_panel_facade(presenter, mock_panel):
    configure_command(mock_panel, "Saved", broadcast=True)
    mock_panel.is_rts_enabled.return_value = True

    state = presenter.get_state()

    assert state.input_text == "Saved"
    assert state.rts_enabled is True
    assert state.broadcast_enabled is True


def test_state_is_applied_through_panel_facade(presenter, mock_panel):
    state = ManualControlState(input_text="Saved", local_echo_enabled=True)

    presenter.apply_state(state)

    assert presenter.local_echo_enabled is True
    mock_panel.apply_state.assert_called_once_with(state)


def test_local_echo_setting_updates_panel(presenter, mock_panel):
    presenter.update_local_echo_setting(True)

    assert presenter.local_echo_enabled is True
    mock_panel.set_local_echo_checked.assert_called_once_with(True)


def test_set_enabled_calls_existing_panel_method(presenter, mock_panel):
    presenter.set_enabled(True)
    mock_panel.set_controls_enabled.assert_called_once_with(True)
