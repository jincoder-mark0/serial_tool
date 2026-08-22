"""Tests for manual command presentation and routing."""

from unittest.mock import MagicMock, patch

import pytest

from common.constants import ConfigKeys
from common.dtos import ManualControlState
from presenter.manual_control_presenter import ManualControlPresenter
from view.panels.manual_control_panel import ManualControlPanel


@pytest.fixture
def mock_panel():
    # spec을 지정해 실제 ManualControlPanel에 없는 메서드 호출을 Mock이 삼키지 않게 한다.
    # spec 없는 MagicMock은 어떤 이름이든 받아주므로, Presenter가 존재하지 않는 View
    # 메서드를 불러도 테스트는 통과한다 — 실제로 그 틈으로 결함이 새어 나갔다:
    # set_enabled()가 패널에 없는데(실제 이름은 set_controls_enabled) 393개 테스트가
    # 모두 통과하는 동안 앱은 포트 탭을 바꿀 때마다 AttributeError로 죽고 있었다.
    panel = MagicMock(spec=ManualControlPanel)
    panel.get_input_text.return_value = ""
    panel.is_hex_mode.return_value = False
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = False
    panel.is_rts_enabled.return_value = False
    panel.is_dtr_enabled.return_value = False
    return panel


@pytest.fixture
def mock_echo_callback():
    return MagicMock()


@pytest.fixture
def mock_get_port_callback():
    callback = MagicMock(return_value="COM1")
    return callback


@pytest.fixture
def presenter(mock_panel, mock_echo_callback, mock_get_port_callback):
    controller = MagicMock()
    controller.is_connection_open.return_value = True
    controller.has_active_broadcast_ports.return_value = True
    return ManualControlPresenter(
        panel=mock_panel,
        connection_controller=controller,
        local_echo_callback=mock_echo_callback,
        get_active_port_callback=mock_get_port_callback,
    )


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


def test_empty_command_is_not_sent(presenter, mock_panel):
    configure_command(mock_panel, "")

    presenter.on_send_requested()

    presenter.connection_controller.send_data.assert_not_called()


def test_single_port_command_is_encoded_and_echoed(
    presenter,
    mock_panel,
    mock_echo_callback,
):
    configure_command(mock_panel, "TEST", local_echo=True)
    presenter.local_echo_enabled = True

    presenter.on_send_requested()

    presenter.connection_controller.send_data.assert_called_once_with("COM1", b"TEST")
    mock_echo_callback.assert_called_once_with(b"TEST")


def test_broadcast_command_uses_broadcast_route(presenter, mock_panel):
    configure_command(mock_panel, "BCAST", broadcast=True)

    presenter.on_send_requested()

    presenter.connection_controller.send_broadcast_data.assert_called_once_with(b"BCAST")
    presenter.connection_controller.send_data.assert_not_called()


def test_prefix_and_suffix_are_applied(presenter, mock_panel):
    configure_command(mock_panel, "DATA", prefix=True, suffix=True)

    with patch.object(presenter.settings_manager, "get") as get_setting:
        get_setting.side_effect = lambda key, default=None: {
            ConfigKeys.COMMAND_PREFIX: "<",
            ConfigKeys.COMMAND_SUFFIX: ">",
        }.get(key, default)
        presenter.on_send_requested()

    presenter.connection_controller.send_data.assert_called_once_with("COM1", b"<DATA>")


def test_hex_command_is_decoded(presenter, mock_panel):
    configure_command(mock_panel, "AA BB CC", hex_mode=True)

    presenter.on_send_requested()

    presenter.connection_controller.send_data.assert_called_once_with(
        "COM1",
        b"\xaa\xbb\xcc",
    )


def test_missing_active_port_prevents_send(
    presenter,
    mock_panel,
    mock_get_port_callback,
):
    configure_command(mock_panel, "TEST")
    mock_get_port_callback.return_value = None

    presenter.on_send_requested()

    presenter.connection_controller.send_data.assert_not_called()


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
    state = ManualControlState(input_text="Saved")

    presenter.apply_state(state)

    mock_panel.apply_state.assert_called_once_with(state)


def test_local_echo_setting_updates_panel(presenter, mock_panel):
    presenter.update_local_echo_setting(True)

    assert presenter.local_echo_enabled is True
    mock_panel.set_local_echo_checked.assert_called_once_with(True)


def test_set_enabled_calls_existing_panel_method(presenter, mock_panel):
    """
    `set_enabled()`가 패널에 **실제로 존재하는** 메서드를 호출하는지 고정한다.

    회귀 배경: 이 메서드가 `panel.set_enabled()`를 부르고 있었는데 패널의 실제 이름은
    `set_controls_enabled()`였다. 포트 탭을 바꿀 때마다 AttributeError로 앱이 죽었지만,
    패널 Mock에 spec이 없어 어떤 이름이든 통과하는 바람에 전체 테스트는 초록이었다.
    `mock_panel`이 `spec=ManualControlPanel`이므로, 없는 이름을 부르면 여기서 걸린다.
    """
    presenter.set_enabled(True)
    mock_panel.set_controls_enabled.assert_called_once_with(True)

    presenter.set_enabled(False)
    assert mock_panel.set_controls_enabled.call_args[0][0] is False
