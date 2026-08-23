"""
매크로 스텝 판정이 실제 전송 결과를 따르는지 검증 (S-080)

## WHY
설계 점검 중 실행해 보고 나온 결함이다. **포트를 하나도 열지 않고** 매크로를
돌렸더니 이렇게 보고됐다:

    스텝 시작 1 / 성공보고 1 / 실패보고 0
    매크로 에러 이벤트 0건
    실제 전송 0건

원인은 실행 루프가 `send_requested.emit()` — 반환값 없는 fire-and-forget 시그널 —
로 전송을 요청하고, 그 결과를 기다리지 않은 채 스텝을 성공으로 넘긴 데 있었다.
`ConnectionController.send_data()`도 `None`을 반환해 실패를 에러 이벤트로만 알렸다.

파장이 컸다. `stop_on_error`가 **전송 실패에 대해 무력**했다 — `expect` 패턴이 걸린
행에서만 실패할 수 있으니, expect 없는 매크로는 원리적으로 실패할 수 없었다.
케이블이 빠져도 UI는 초록 성공 표시를 계속 냈다.

## WHAT
* 전송이 실패하면 스텝이 **실패로** 보고되는가
* 그때 매크로 에러 이벤트가 발생하는가 (`stop_on_error`가 판단할 근거)
* `stop_on_error=True`면 실제로 멈추는가
* 전송 핸들러가 아예 없으면 성공으로 넘어가지 않는가
* 보내지 못한 명령에 대해 `expect` 응답을 기다리지 않는가

## HOW
실제 포트 없이 전송 핸들러를 갈아 끼워 검증한다 — 이 결함은 전송 계층이 아니라
**결과를 판정에 반영하는가**의 문제이므로, 핸들러가 무엇을 반환하든 러너가 그것을
따르는지만 보면 된다.
"""
import time

import pytest
from PyQt5.QtWidgets import QApplication

from common.dtos import MacroEntry, MacroSendResult
from model.macro_runner import MacroRunner


def _run(runner: MacroRunner, timeout_s: float = 3.0) -> None:
    """
    매크로 스레드가 뜨기를 기다린 뒤, 끝날 때까지(또는 시간 초과까지) 돌린다.

    `start()` 직후에는 아직 OS 스레드가 `run()`에 들어가지 않아 `isRunning()`이
    False일 수 있다 — 곧바로 종료 조건으로 읽으면 한 스텝도 돌리지 못한 채
    테스트가 통과해 버린다.
    """
    deadline = time.time() + timeout_s
    while not runner.isRunning() and time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)

    while runner.isRunning() and time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    runner.stop()

    # 스텝 시그널은 매크로 스레드에서 emit되어 메인 스레드 큐에 쌓인다.
    # `stop()`이 `wait()`로 메인 스레드를 붙잡는 동안 밀린 것까지 배달한 뒤에
    # 세어야 한다 — 비우지 않고 단정하면 "0건"으로 읽혀 거짓 실패가 난다.
    for _ in range(20):
        QApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def runner(qapp):
    """엔트리 2개를 실은 매크로 실행기와 계측기."""
    macro = MacroRunner()
    macro.load_macro([
        MacroEntry(enabled=True, command="AT+ONE", delay_ms=10),
        MacroEntry(enabled=True, command="AT+TWO", delay_ms=10),
    ])
    yield macro
    if macro.isRunning():
        macro.stop()
    QApplication.processEvents()


def _instrument(macro: MacroRunner) -> dict:
    """스텝 성공/실패와 에러 이벤트를 센다."""
    counts = {"ok": 0, "fail": 0, "errors": []}
    macro.step_completed.connect(
        lambda e: counts.__setitem__("ok" if e.success else "fail",
                                     counts["ok" if e.success else "fail"] + 1)
    )
    macro.error_occurred.connect(lambda e: counts["errors"].append(e.message))
    return counts


def test_failed_send_is_reported_as_a_failed_step(runner):
    """
    전송이 실패하면 스텝도 실패여야 한다.

    이것이 결함의 핵심이다 — 아무것도 보내지 못했는데 성공으로 보고됐다.
    """
    counts = _instrument(runner)
    runner.set_send_handler(lambda command: MacroSendResult(False, "Port is not open."))

    runner.start(loop_count=1, interval_ms=0, stop_on_error=False)
    _run(runner)

    assert counts["ok"] == 0, f"보내지 못했는데 성공으로 보고됐다 (성공 {counts['ok']}건)"
    assert counts["fail"] > 0, "실패가 하나도 보고되지 않았다"


def test_failed_send_raises_a_macro_error_event(runner):
    """
    실패한 전송은 매크로 에러 이벤트를 남겨야 한다.

    `stop_on_error`가 판단할 근거이자, 사용자가 로그에서 확인할 유일한 흔적이다.
    """
    counts = _instrument(runner)
    runner.set_send_handler(lambda command: MacroSendResult(False, "Port is not open."))

    runner.start(loop_count=1, interval_ms=0, stop_on_error=False)
    _run(runner)

    assert counts["errors"], "전송 실패인데 에러 이벤트가 없다"
    assert "Port is not open." in counts["errors"][0], (
        f"실패 사유가 전달되지 않았다: {counts['errors'][0]!r}"
    )


def test_stop_on_error_actually_stops_on_a_send_failure(runner):
    """
    `stop_on_error=True`면 전송 실패에서 멈춰야 한다.

    예전에는 이 설정이 전송 실패에 대해 무력했다 — expect가 걸린 행에서만
    실패할 수 있었으므로, expect 없는 매크로는 끝까지 다 돌았다.
    """
    counts = _instrument(runner)
    runner.set_send_handler(lambda command: MacroSendResult(False, "Send failed."))

    runner.start(loop_count=3, interval_ms=0, stop_on_error=True)   # 2행 x 3회 = 6스텝이 예정돼 있다
    _run(runner)

    attempted = counts["ok"] + counts["fail"]
    assert attempted == 1, (
        f"첫 실패에서 멈춰야 하는데 스텝 {attempted}개가 진행됐다 "
        f"(성공 {counts['ok']} / 실패 {counts['fail']})"
    )


def test_missing_send_handler_is_not_treated_as_success(runner):
    """
    핸들러가 등록되지 않았으면 성공이 아니다.

    "보내지 못했는데 성공"이 이 결함의 정체였다. 미주입 상태를 조용한 성공으로
    넘기면 같은 구멍이 다시 열린다.
    """
    counts = _instrument(runner)
    # 핸들러를 일부러 등록하지 않는다
    runner.start(loop_count=1, interval_ms=0, stop_on_error=False)
    _run(runner)

    assert counts["ok"] == 0, "전송 핸들러가 없는데 성공으로 보고됐다"
    assert counts["fail"] > 0, "실패가 보고되지 않았다"


def test_expect_is_not_awaited_when_the_send_failed(qapp):
    """
    보내지 못한 명령의 응답을 기다리지 않아야 한다.

    보내지도 않은 명령의 응답을 타임아웃까지 기다리면, 실패를 알아채는 시점이
    그만큼 늦어진다.
    """
    macro = MacroRunner()
    macro.load_macro([
        MacroEntry(enabled=True, command="AT", delay_ms=0,
                   expect="OK", timeout_ms=3000),
    ])
    macro.set_send_handler(lambda command: MacroSendResult(False, "Send failed."))

    started = time.time()
    macro.start(loop_count=1, interval_ms=0, stop_on_error=True)
    _run(macro, timeout_s=5.0)
    elapsed = time.time() - started

    assert elapsed < 1.5, (
        f"전송 실패인데 expect 타임아웃(3초)까지 기다렸다 ({elapsed:.2f}초 소요)"
    )
