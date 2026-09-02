"""MacroRunner 시작 API 계약 테스트.

## WHY
`MacroRunner`는 `QThread`를 상속하면서 `start()`를 **완전히 다른 시그니처**로
override하고 있었다.

    QThread.start(priority=InheritPriority)
    MacroRunner.start(loop_count=1, interval_ms=0, broadcast_enabled=False, stop_on_error=True)

이 객체를 QThread로 취급하는 호출자가 `runner.start(QThread.HighPriority)`를 쓰면
priority enum이 `loop_count`로 조용히 들어가 엉뚱한 반복 횟수가 된다. 예외도
경고도 없이 매크로가 의도와 다른 횟수로 돈다.

base class와 계약이 다르면 이름도 달라야 한다 — `start_macro()`로 분리했다.

## WHAT
* `start()`를 다시 override하지 않는가 (상속된 것을 그대로 쓰는가)
* `start_macro()`가 정상 경로로 동작하는가
* 상속된 `start()`로 직접 시작해도 안전한 no-op인가 —
  이름만 바꾸고 이 경로를 방치하면 위험이 사라진 게 아니라 옮겨간 것이다
"""
import pytest
from PyQt5.QtCore import QThread

from common.dtos import MacroEntry, MacroSendResult
from model.macro_runner import MacroRunner


@pytest.fixture
def runner(qapp):
    instance = MacroRunner()
    yield instance
    if instance.isRunning():
        instance.stop()
    instance.wait(1000)


def test_start_is_not_overridden_with_a_different_signature():
    """`start`는 QThread의 것을 그대로 상속해야 한다.

    sip 바인딩은 클래스마다 별개의 descriptor를 돌려주므로 `is` 비교가 성립하지
    않는다. 실제로 물어야 할 것은 "서브클래스가 직접 정의했는가"이므로 MRO에서
    QThread 위쪽에 `start` 정의가 있는지 본다.
    """
    overriding = [
        klass.__name__
        for klass in MacroRunner.__mro__
        if klass is not QThread and "start" in klass.__dict__
    ]

    assert not overriding, (
        f"{overriding}가 QThread.start()를 다시 override했다. "
        "base class와 다른 계약이면 start_macro() 같은 별도 이름을 써야 한다 — "
        "QThread로 취급하는 호출자가 priority를 넘기면 loop_count로 잘못 해석된다."
    )


def test_start_macro_runs_the_loaded_macro(runner, qtbot):
    """정상 경로: start_macro()는 macro_started를 내보내고 실제로 실행한다."""
    runner.set_send_handler(lambda _cmd: MacroSendResult(True))
    runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])

    started = []
    runner.macro_started.connect(lambda: started.append(True))

    runner.start_macro(loop_count=0)
    qtbot.waitUntil(runner.isRunning, timeout=1000)

    assert started, "start_macro()가 macro_started를 내보내지 않았다"


def test_inherited_start_is_a_safe_noop(runner, qtbot):
    """
    상속된 `start()`로 직접 시작해도 매크로가 돌지 않고 유령 신호도 없어야 한다.

    `run()`이 실행 조건 없이 그대로 진행하면 설정되지 않은 상태로 루프에 들어가고,
    거기서 `macro_finished`를 내보내면 **macro_started 없이 완료 신호만 오는**
    유령 이벤트가 된다. 소비자는 돌지도 않은 매크로가 끝났다고 판단한다.
    """
    runner.set_send_handler(lambda _cmd: MacroSendResult(True))
    runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])

    started, finished = [], []
    runner.macro_started.connect(lambda: started.append(True))
    runner.macro_finished.connect(lambda: finished.append(True))

    runner.start()                      # QThread.start() — 매크로 설정 없이 시작
    assert runner.wait(2000), "thread가 종료되지 않았다"
    qtbot.wait(50)

    assert not started, "설정 없이 시작했는데 macro_started가 나왔다"
    assert not finished, (
        "macro_started 없이 macro_finished만 나왔다 — "
        "소비자는 돌지도 않은 매크로가 끝났다고 판단한다"
    )


def test_start_macro_after_inherited_start_still_works(runner, qtbot):
    """잘못된 시작이 이후 정상 시작을 막지 않아야 한다."""
    runner.set_send_handler(lambda _cmd: MacroSendResult(True))
    runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])

    runner.start()
    assert runner.wait(2000)

    runner.start_macro(loop_count=0)
    qtbot.waitUntil(runner.isRunning, timeout=1000)

    assert runner.isRunning()
