"""
우측 패널 토글 왕복 회귀 테스트 (S-074)

## WHY
사용자 보고: "라이트 패널 활성화/비활성화에 따라 컴포넌트 크기들이 미묘하게 변해."

실측으로 확인했다. 숨겼다 다시 켜면 창과 좌측 패널이 원래 크기로 돌아오지 않았다.

    시작   창 1400  좌측 989  우측 395
    숨김   창 1055  좌측 1045 우측 0      <- 좌측이 56px 넓어짐
    표시   창 1456  좌측 1045 우측 395    <- 창이 56px 커진 채로 돌아옴

**뿌리는 줄어드는 양과 늘어나는 양이 다른 것**이다. 숨길 때는 창을
`좌측폭 + 마진`으로 줄이려 하지만 **창 최소 폭에 막혀 클램프**되어 의도한 만큼
줄지 못한다. 그런데 켤 때는 `현재 폭 + 우측 폭 + 핸들`로 막힘없이 다 늘어난다.
차액이 매번 쌓인다.

## WHAT
숨김 → 표시 왕복이 **항등**인지 확인한다: 창 폭, 좌측 폭, 우측 폭이 모두 원래대로.

## HOW
`offscreen`에서도 지오메트리 계산은 정상 동작한다(폰트 렌더와 달리). 다만 실제
픽셀값은 환경에 따라 다를 수 있으므로 **절대값이 아니라 "돌아왔는가"만** 본다.
"""
import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture
def window(qapp):
    """실제 MainWindow (토글은 창 지오메트리를 다루므로 Mock으로 대신할 수 없다)."""
    from view.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.resize(1500, 800)
    win.right_section.setVisible(True)
    for _ in range(6):
        QApplication.processEvents()
    yield win
    win.close()
    QApplication.processEvents()


def _snapshot(win):
    """현재 창·좌측·우측 폭을 찍는다."""
    for _ in range(6):
        QApplication.processEvents()
    return (
        win.width(),
        win.left_section.width(),
        win.right_section.width() if win.right_section.isVisible() else 0,
    )


def test_hide_then_show_restores_original_geometry(window):
    """
    숨겼다 켜면 창·좌측·우측 폭이 모두 원래대로 돌아와야 한다.

    돌아오지 않으면 토글할 때마다 창이 조금씩 커지고 패널 비율이 어긋난다.
    """
    before = _snapshot(window)

    window.toggle_right_section(False)
    hidden = _snapshot(window)
    assert hidden[2] == 0, "숨겼는데 우측 패널이 폭을 갖고 있다"

    window.toggle_right_section(True)
    after = _snapshot(window)

    assert after == before, (
        f"토글 왕복이 항등이 아니다.\n"
        f"  이전: 창={before[0]} 좌측={before[1]} 우측={before[2]}\n"
        f"  이후: 창={after[0]} 좌측={after[1]} 우측={after[2]}\n"
        f"숨길 때의 창 폭·좌측 폭을 저장해 켤 때 복원하는지 확인하라 — "
        f"'현재 폭 + 우측 폭'으로 계산하면 숨길 때 최소 폭에 막힌 만큼이 매번 쌓인다."
    )


def test_repeated_toggles_do_not_drift(window):
    """
    여러 번 반복해도 누적 오차가 없어야 한다.

    1회 왕복만 보면 오차가 작아 놓치기 쉽지만, 반복하면 눈에 띄게 커진다.
    """
    before = _snapshot(window)

    for _ in range(3):
        window.toggle_right_section(False)
        window.toggle_right_section(True)

    after = _snapshot(window)
    assert after == before, (
        f"토글 3회 반복 후 크기가 달라졌다: {before} -> {after} (누적 오차)"
    )


def test_maximized_toggle_only_changes_visibility(window):
    """
    최대화 상태에서는 창 크기를 건드리지 않고 표시 여부만 바꿔야 한다.

    최대화된 창을 resize하면 최대화가 풀려 사용자가 의도하지 않은 크기가 된다.
    """
    window.showMaximized()
    for _ in range(6):
        QApplication.processEvents()
    if not window.isMaximized():
        pytest.skip("이 환경에서는 최대화가 적용되지 않는다 (offscreen 등)")

    width_before = window.width()
    window.toggle_right_section(False)
    QApplication.processEvents()

    assert window.right_section.isVisible() is False
    assert window.width() == width_before, "최대화 상태에서 창 폭이 바뀌었다"
