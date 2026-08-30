"""
모달 대화상자가 호출 스택 위에서 열리지 않는지 검증 (S-082)

## WHY
설계 점검 중 이런 호출 사슬이 나왔다:

    close_connection()          ← self.workers를 아직 정리하는 중
     → connection_closed direct Qt signal
     → MainPresenter / Coordinator의 사용자 알림 요청
     → MainWindow.show_alert_message()
     → QMessageBox.warning()

즉 워커를 정리하는 함수의 스택 위에서 모달이 열렸다. 모달은 중첩 이벤트 루프를
돌리므로, 그동안 밀려 있던 이벤트들이 끼어들어 정리 중이던 객체가 발밑에서
파괴될 수 있다.

**주의**: 이 경로가 offscreen에서 8/8로 죽는 것을 관찰했지만, 원인은 재진입이
아니었다. QApplication + QWidget + QMessageBox만으로도 offscreen에서는 똑같이
access violation이 난다 — Qt offscreen 플랫폼의 한계이지 이 앱의 결함이 아니다.
네이티브에서는 0/5로 죽지 않았다. 그러니 이 테스트는 **크래시를 막는다고
주장하지 않는다.** 정리 도중 중첩 이벤트 루프를 돌리지 않는다는 성질만 지킨다.

## WHAT
* 알림 요청이 **호출 즉시** 모달을 열지 않는가 (스택이 풀린 뒤에 열리는가)
* 이벤트 루프가 한 번 돌면 실제로 열리는가 (미루기만 하고 잃어버리면 안 된다)

## HOW
진짜 모달을 띄우지 않는다 — offscreen에서 프로세스가 죽기 때문이다. `QMessageBox`
호출 자체를 스파이로 갈아 끼워 **언제 불리는지**만 본다.
"""
import pytest
from PyQt5.QtWidgets import QApplication

from view.main_window import MainWindow


@pytest.fixture
def window(qapp):
    """메인 윈도우 한 개 (표시하지 않는다)."""
    view = MainWindow()
    yield view
    view.close()
    view.deleteLater()
    QApplication.processEvents()


def test_alert_is_not_opened_inside_the_caller_stack(window, monkeypatch):
    """
    알림 요청이 곧바로 모달을 열면 안 된다.

    모달은 중첩 이벤트 루프를 돌린다. 정리 작업 도중에 열리면 그 작업이 끝나기
    전에 다른 이벤트가 끼어든다 — 이번에 찾은 사슬이 정확히 그랬다.
    """
    import view.main_window as module

    calls = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *args, **kwargs: calls.append(args))

    window.show_alert_message("제목", "내용")

    assert not calls, "호출 스택이 풀리기 전에 모달이 열렸다"


def test_alert_is_still_shown_after_the_event_loop_turns(window, monkeypatch):
    """
    미루기만 하고 잃어버리면 안 된다 — 사용자는 알림을 봐야 한다.

    이게 없으면 "모달을 아예 띄우지 않기"로도 위 테스트를 통과할 수 있다.
    """
    import view.main_window as module

    calls = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *args, **kwargs: calls.append(args))

    window.show_alert_message("제목", "내용")
    for _ in range(5):
        QApplication.processEvents()

    assert calls, "미뤄 둔 알림이 끝내 표시되지 않았다"
    assert calls[0][1] == "제목" and calls[0][2] == "내용", (
        f"제목/내용이 전달되지 않았다: {calls[0]}"
    )
