"""종료 시 TX 드레인 대기가 창을 굳히지 않는지 검증한다.

## WHY
종료 경로는 유실을 막기 위해 드레인 완료를 **반드시** 기다려야 한다. 프로세스가
사라지면 아직 내보내지 못한 큐가 함께 사라지므로, 기다리지 않는 것이 곧 유실이다.

그런데 `QThread.wait()`로 기다리면 이벤트 루프가 멈춰 창이 흰 사각형으로 굳는다.
사용자에게는 앱이 죽은 것과 구분되지 않고, 큐가 클수록 오래 굳는다.

남은 양을 보여주며 기다리면 "멈춘 것"이 아니라 "내보내는 중"임이 보인다.

## WHAT
* 드레인이 끝날 때까지 기다리는가 (유실 방지 — 이게 1순위다)
* 기다리는 동안 이벤트를 흘려 창이 계속 그려지는가
* **사용자 입력은 배제하는가** — 입력까지 흘리면 종료 도중 다시 연결하거나
  매크로를 돌리는 재진입이 생긴다. 이미 정리한 자원을 다시 쓰게 되는 상태다
* 남은 바이트를 사용자에게 보여주는가
* 드레인할 게 없으면 불필요하게 돌지 않는가
"""
from unittest.mock import MagicMock, patch

from common.constants import SHUTDOWN_FLUSH_POLL_MS
from core.data_logger import DataLoggerManager
from presenter.shutdown_coordinator import ShutdownCoordinator


def _make_coordinator(controller):
    return ShutdownCoordinator(
        view=MagicMock(),
        settings_manager=MagicMock(),
        connection_controller=controller,
        file_transfer_manager=MagicMock(),
        macro_runner=MagicMock(),
        macro_script_manager=MagicMock(),
        port_scan_manager=MagicMock(),
        manual_control_presenter=MagicMock(),
        packet_presenter=MagicMock(),
        data_handler=MagicMock(),
        close_system_log=MagicMock(),
        status_coordinator=MagicMock(),
        data_logger_manager=MagicMock(spec=DataLoggerManager),
    )


def _controller_with_pending(rounds: int) -> MagicMock:
    """`rounds`번 폴링한 뒤 드레인이 끝나는 controller."""
    controller = MagicMock()
    controller.has_active_connection = True
    remaining = {"rounds": rounds}

    def _has_pending():
        return remaining["rounds"] > 0

    def _wait(timeout_ms=None):
        remaining["rounds"] -= 1
        return remaining["rounds"] <= 0

    controller.has_pending_flush.side_effect = _has_pending
    controller.wait_for_pending_flush.side_effect = _wait
    controller.pending_flush_bytes.side_effect = lambda: remaining["rounds"] * 1000
    return controller


def test_shutdown_waits_until_the_flush_completes():
    """1순위는 유실 방지다 — 드레인이 끝나기 전에 종료 시퀀스를 진행하면 안 된다."""
    controller = _controller_with_pending(rounds=3)
    coordinator = _make_coordinator(controller)

    with patch("presenter.shutdown_coordinator.QCoreApplication"):
        coordinator.shutdown()

    assert controller.has_pending_flush() is False, "드레인이 끝나지 않았는데 종료가 진행됐다"
    assert controller.wait_for_pending_flush.call_count >= 3


def test_wait_pumps_events_so_the_window_keeps_repainting():
    """
    기다리는 동안 이벤트를 흘리지 않으면 창이 흰 사각형으로 굳는다.

    사용자에게는 앱이 죽은 것과 구분되지 않는다.
    """
    controller = _controller_with_pending(rounds=3)
    coordinator = _make_coordinator(controller)

    with patch("presenter.shutdown_coordinator.QCoreApplication") as qapp:
        coordinator.shutdown()

    assert qapp.processEvents.call_count >= 3, (
        "드레인을 기다리는 동안 이벤트를 흘리지 않았다 — 창이 굳는다"
    )


def test_wait_excludes_user_input_to_prevent_reentrancy():
    """
    이벤트를 흘리되 **사용자 입력은 버려야** 한다.

    입력까지 흘리면 종료 도중 사용자가 다시 연결하거나 매크로를 돌릴 수 있다 —
    이미 정리한 자원을 다시 쓰게 되는 재진입이다.
    """
    from PyQt5.QtCore import QEventLoop

    controller = _controller_with_pending(rounds=2)
    coordinator = _make_coordinator(controller)

    with patch("presenter.shutdown_coordinator.QCoreApplication") as qapp:
        coordinator.shutdown()

    flush_calls = [
        call for call in qapp.processEvents.call_args_list if call.args
    ]
    assert flush_calls, "processEvents가 인자 없이 호출됐다 — 사용자 입력이 흘러든다"
    for call in flush_calls:
        assert call.args[0] == QEventLoop.ExcludeUserInputEvents, (
            f"사용자 입력을 배제하지 않았다: {call.args[0]}"
        )


def test_remaining_bytes_are_shown_while_waiting():
    """
    얼마나 남았는지 보여야 '멈춘 것'이 아니라 '내보내는 중'으로 읽힌다.

    언어 리소스 로딩 여부에 의존하지 않도록 템플릿을 주입해 **포맷 경로**를 본다.
    """
    controller = _controller_with_pending(rounds=2)
    coordinator = _make_coordinator(controller)
    view = coordinator._view

    with patch("presenter.shutdown_coordinator.QCoreApplication"), patch(
        "presenter.shutdown_coordinator.language_manager.get_text",
        return_value="flushing {0} bytes",
    ):
        coordinator.shutdown()

    messages = [call.args[0] for call in view.show_status_message.call_args_list]
    assert messages, "드레인을 기다리는 동안 아무것도 표시하지 않았다"
    assert any("2000" in message for message in messages), (
        f"남은 바이트가 메시지에 반영되지 않았다: {messages}"
    )


def test_flushing_message_key_carries_a_byte_placeholder():
    """
    메시지 키에 자리표시자가 없으면 남은 양이 화면에 나타나지 않는다.

    코드는 `.format(bytes)`를 부르지만, 템플릿에 `{0}`이 없으면 조용히 무시된다 —
    표시는 되는데 정보는 없는 상태다.
    """
    import json
    from pathlib import Path

    languages = Path(__file__).resolve().parents[1] / "resources" / "languages"
    for path in (languages / "en.json", languages / "ko.json"):
        catalog = json.loads(path.read_text(encoding="utf-8"))
        template = catalog["main_status_msg_flushing"]
        assert "{0}" in template, (
            f"{path.name}의 main_status_msg_flushing에 {{0}}이 없다: {template!r}"
        )


def test_no_polling_when_there_is_nothing_to_flush():
    """드레인할 게 없으면 폴링 루프에 들어가지 않아야 한다."""
    controller = MagicMock()
    controller.has_active_connection = True
    controller.has_pending_flush.return_value = False
    coordinator = _make_coordinator(controller)

    with patch("presenter.shutdown_coordinator.QCoreApplication"):
        coordinator.shutdown()

    controller.wait_for_pending_flush.assert_not_called()


def test_poll_interval_is_bounded_so_progress_updates_are_visible():
    """폴링 주기가 너무 길면 표시가 갱신되지 않아 굳은 것처럼 보인다."""
    assert 0 < SHUTDOWN_FLUSH_POLL_MS <= 200
