"""크래시 다이얼로그가 모달 위에 모달로 쌓이지 않는지 검증한다.

## WHY
`GlobalErrorHandler._show_error_dialog`는 `show_error_signal` 슬롯이고 내부에서
`QMessageBox.exec_()`로 **중첩 이벤트 루프**를 돈다. 그 루프가 큐에 밀려 있던 다음
오류를 처리하면 첫 다이얼로그 **안에서** 두 번째가 열렸다 (실측 중첩 깊이 2).

타이머 슬롯처럼 반복 실행되는 곳에서 예외가 나면 다이얼로그가 무한정 쌓이고,
하나를 닫으면 다음이 나와 앱을 닫을 수 없다. 스로틀도 중복 제거도 없었다.

이 프로젝트는 **같은 위험을 이미 알고 고쳤다** — S-082가
`MainWindow.show_error_message`를 `QTimer.singleShot(0, ...)`로 지연시켰고
`tests/test_modal_not_reentrant.py`가 그 성질을 지킨다. 크래시 경로만 빠져 있었다.

## 왜 S-082와 같은 방식(지연)을 쓰지 않는가
지연하면 **이벤트 루프가 돌기 전에 난 오류는 아무것도 보이지 않는다.** `main.py`는
`app.exec_()` 이전에 설정·리소스·부트스트랩을 모두 수행하므로, 거기서 죽으면
사용자가 가장 필요한 순간에 침묵하게 된다. 실측으로 확인한 뒤 이 경로는 동기 표시를
유지하고 재진입만 막기로 했다.

## WHAT
* 다이얼로그가 열려 있는 동안 온 오류는 새 다이얼로그를 열지 않는가
* 억눌린 건수가 로그로 남는가 (조용히 사라지면 안 된다)
* 다이얼로그가 닫힌 뒤에는 다시 열리는가 (영구 차단이 아니다)
* 표시 도중 예외가 나도 가드가 풀리는가 (한 번의 실패로 영구 침묵되면 안 된다)
* **동기 표시를 유지하는가** — 시작 중 크래시가 보이려면 지연하면 안 된다
"""
from __future__ import annotations

import sys
import threading

import pytest

import core.error_handler as error_handler_module
from common.dtos import ErrorContext
from core.error_handler import GlobalErrorHandler


@pytest.fixture
def restored_hooks():
    """`GlobalErrorHandler()` 생성은 프로세스 전역 훅을 덮으므로 반드시 복원한다."""
    original_sys_hook = sys.excepthook
    original_threading_hook = threading.excepthook
    original_singleton = error_handler_module.global_error_handler

    yield

    sys.excepthook = original_sys_hook
    threading.excepthook = original_threading_hook
    error_handler_module.global_error_handler = original_singleton


def _context(name: str = "ValueError") -> ErrorContext:
    return ErrorContext(
        error_type=name, message="boom", traceback="tb", timestamp=0.0
    )


def test_second_error_does_not_open_a_dialog_inside_the_first(qapp, restored_hooks):
    """
    모달이 열려 있는 동안 온 오류는 **중첩 모달을 만들지 않아야** 한다.

    수정 전 실측: 열린 다이얼로그 2개, 최대 중첩 깊이 2.
    """
    handler = GlobalErrorHandler()

    depth = {"current": 0, "max": 0}
    opened = []

    def fake_render(context: ErrorContext) -> None:
        depth["current"] += 1
        depth["max"] = max(depth["max"], depth["current"])
        opened.append(context.error_type)
        # 실제 exec_()가 하는 일: 중첩 이벤트 루프가 다음 오류를 처리한다.
        handler._show_error_dialog(_context("SecondError"))
        depth["current"] -= 1

    handler._render_error_dialog = fake_render
    handler._show_error_dialog(_context("FirstError"))

    assert depth["max"] == 1, (
        f"모달 위에 모달이 열렸다 (중첩 깊이 {depth['max']}). "
        f"열린 다이얼로그: {opened}"
    )
    assert opened == ["FirstError"], f"두 번째 다이얼로그가 열렸다: {opened}"


def test_suppressed_count_is_logged(qapp, restored_hooks, monkeypatch):
    """
    억눌린 오류는 **조용히 사라지면 안 된다.**

    개별 traceback은 `_process_exception`이 이미 CRITICAL로 남기지만, "다이얼로그가
    몇 건 억눌렸는지"는 따로 알려야 사용자가 로그를 볼 이유를 안다.
    """
    warnings: list[str] = []
    monkeypatch.setattr(
        error_handler_module.logger, "warning", lambda msg: warnings.append(str(msg))
    )

    handler = GlobalErrorHandler()

    def fake_render(context: ErrorContext) -> None:
        for _ in range(3):
            handler._show_error_dialog(_context("Repeat"))

    handler._render_error_dialog = fake_render
    handler._show_error_dialog(_context("First"))

    assert warnings, "억눌린 다이얼로그가 있는데 아무것도 알리지 않았다"
    assert "3 further error dialog(s) suppressed" in warnings[-1]


def test_dialog_can_open_again_after_the_previous_one_closes(qapp, restored_hooks):
    """영구 차단이 아니다 — 닫힌 뒤에는 다음 오류가 다시 표시돼야 한다."""
    handler = GlobalErrorHandler()
    opened: list[str] = []

    handler._render_error_dialog = lambda ctx: opened.append(ctx.error_type)

    handler._show_error_dialog(_context("First"))
    handler._show_error_dialog(_context("Second"))

    assert opened == ["First", "Second"], (
        f"이전 다이얼로그가 닫힌 뒤에도 열리지 않았다: {opened}"
    )


def test_guard_is_released_even_if_rendering_raises(qapp, restored_hooks):
    """
    표시 도중 예외가 나도 가드가 풀려야 한다.

    풀리지 않으면 한 번의 렌더 실패로 이후 모든 오류가 **영구히 침묵**한다 —
    막으려던 것보다 나쁜 상태다.
    """
    handler = GlobalErrorHandler()

    def exploding_render(context: ErrorContext) -> None:
        raise RuntimeError("dialog construction failed")

    handler._render_error_dialog = exploding_render

    with pytest.raises(RuntimeError):
        handler._show_error_dialog(_context("First"))

    assert handler._dialog_open is False, "렌더 실패 후 가드가 잠긴 채 남았다"

    opened: list[str] = []
    handler._render_error_dialog = lambda ctx: opened.append(ctx.error_type)
    handler._show_error_dialog(_context("Second"))

    assert opened == ["Second"], "렌더 실패 이후 다이얼로그가 영구 차단됐다"


def test_dialog_is_shown_synchronously(qapp, restored_hooks):
    """
    표시를 지연하지 않는다 — 지연하면 시작 중 크래시가 보이지 않는다.

    `main.py`는 `app.exec_()` 이전에 설정·리소스·부트스트랩을 수행한다. 그 구간에서
    죽으면 이벤트 루프가 없으므로 `QTimer.singleShot`으로 미룬 다이얼로그는 영영
    열리지 않는다(실측 확인). S-082가 `MainWindow.show_error_message`에서 지연을
    택한 것과 결론이 다른 이유다.
    """
    handler = GlobalErrorHandler()
    opened: list[str] = []

    handler._render_error_dialog = lambda ctx: opened.append(ctx.error_type)
    handler._show_error_dialog(_context("Startup"))

    # 이벤트 루프를 한 번도 돌리지 않았는데도 이미 표시돼 있어야 한다.
    assert opened == ["Startup"], (
        "다이얼로그가 지연됐다 — 이벤트 루프가 없는 시작 구간의 크래시는 "
        "이 경로에서 아무것도 보여주지 못한다."
    )
