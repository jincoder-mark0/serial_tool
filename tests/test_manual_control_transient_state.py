"""ManualControlPresenter의 transient Auto Tx 복원/종료 정책을 검증합니다."""
from unittest.mock import MagicMock

from common.dtos import ManualControlState
from presenter.manual_control_presenter import ManualControlPresenter


def _presenter():
    panel = MagicMock()
    panel.is_local_echo_enabled.return_value = False
    port_view = MagicMock()
    controller = MagicMock()
    service = MagicMock()
    presenter = ManualControlPresenter(panel, port_view, controller, service)
    return presenter, panel


def test_apply_state_never_restores_auto_tx_as_running():
    presenter, panel = _presenter()
    saved = ManualControlState(
        input_text="AT",
        auto_tx_enabled=True,
        auto_tx_interval_ms=500,
    )

    presenter.apply_state(saved)

    restored = panel.apply_state.call_args.args[0]
    assert restored.auto_tx_enabled is False
    assert saved.auto_tx_enabled is True  # 입력 DTO는 변형하지 않습니다.
    assert presenter.auto_tx_scheduler.is_running is False


def test_stop_auto_tx_stops_scheduler_and_unchecks_ui():
    presenter, panel = _presenter()
    presenter.auto_tx_scheduler = MagicMock()

    presenter.stop_auto_tx()

    presenter.auto_tx_scheduler.stop.assert_called_once()
    panel.set_auto_tx_checked.assert_called_once_with(False)
