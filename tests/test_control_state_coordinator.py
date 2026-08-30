"""ControlStateCoordinator의 연결/탭/broadcast 활성화 정책 테스트."""
from unittest.mock import MagicMock

from presenter.control_state_coordinator import ControlStateCoordinator


def _make_coordinator(*, current_connected=False, any_connection=False):
    port_view = MagicMock()
    port_view.is_current_port_connected.return_value = current_connected
    controller = MagicMock()
    controller.has_active_connection = any_connection
    manual = MagicMock()
    macro = MagicMock()
    manual.is_broadcast_enabled.return_value = False
    macro.is_broadcast_enabled.return_value = False

    coordinator = ControlStateCoordinator(
        port_view,
        controller,
        manual,
        macro,
    )
    manual.reset_mock()
    macro.reset_mock()
    return coordinator, port_view, controller, manual, macro


def test_connected_current_tab_enables_both_controls():
    coordinator, _, _, manual, macro = _make_coordinator(current_connected=True)

    coordinator.refresh()

    manual.set_enabled.assert_called_once_with(True)
    macro.set_enabled.assert_called_once_with(True)


def test_disconnected_without_broadcast_disables_both_controls():
    coordinator, _, _, manual, macro = _make_coordinator(
        current_connected=False,
        any_connection=True,
    )

    coordinator.refresh()

    manual.set_enabled.assert_called_once_with(False)
    macro.set_enabled.assert_called_once_with(False)


def test_manual_broadcast_uses_any_active_connection_independently():
    coordinator, _, controller, manual, macro = _make_coordinator(
        current_connected=False,
        any_connection=True,
    )
    manual.is_broadcast_enabled.return_value = True
    macro.is_broadcast_enabled.return_value = False

    coordinator.refresh()

    manual.set_enabled.assert_called_once_with(True)
    macro.set_enabled.assert_called_once_with(False)
    assert controller.has_active_connection is True


def test_macro_broadcast_uses_any_active_connection_independently():
    coordinator, _, _, manual, macro = _make_coordinator(
        current_connected=False,
        any_connection=True,
    )
    manual.is_broadcast_enabled.return_value = False
    macro.is_broadcast_enabled.return_value = True

    coordinator.refresh()

    manual.set_enabled.assert_called_once_with(False)
    macro.set_enabled.assert_called_once_with(True)


def test_broadcast_does_not_enable_when_no_connection_exists():
    coordinator, _, _, manual, macro = _make_coordinator(
        current_connected=False,
        any_connection=False,
    )
    manual.is_broadcast_enabled.return_value = True
    macro.is_broadcast_enabled.return_value = True

    coordinator.refresh()

    manual.set_enabled.assert_called_once_with(False)
    macro.set_enabled.assert_called_once_with(False)


def test_coordinator_subscribes_to_all_state_change_sources():
    port_view = MagicMock()
    controller = MagicMock()
    manual = MagicMock()
    macro = MagicMock()

    ControlStateCoordinator(port_view, controller, manual, macro)

    port_view.current_tab_changed.connect.assert_called_once()
    controller.connection_opened.connect.assert_called_once()
    controller.connection_closed.connect.assert_called_once()
    manual.broadcast_changed.connect.assert_called_once()
    macro.broadcast_changed.connect.assert_called_once()
