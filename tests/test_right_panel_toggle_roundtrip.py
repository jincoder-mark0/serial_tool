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
from view.managers.color_manager import ColorManager
from view.managers.theme_manager import ThemeManager


@pytest.fixture
def window(qapp):
    """실제 MainWindow (토글은 창 지오메트리를 다루므로 Mock으로 대신할 수 없다)."""
    from view.main_window import MainWindow

    win = MainWindow(ThemeManager(), ColorManager())
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


def test_hiding_shrinks_the_window_instead_of_stretching_the_left_section(window):
    """
    패널을 숨기면 **창이 줄어야** 한다 — 좌측 섹션이 빈자리를 먹어서는 안 된다.

    ## WHY
    사용자 보고(2026-09-02): "창 크기가 변해야 하는데 창 크기가 유지되어 컴포넌트
    크기가 변한다."

    원인은 Qt의 지연된 레이아웃 무효화다. `right_section.setVisible(False)` 직후에는
    splitter와 상위 레이아웃이 아직 우측 섹션의 최소 폭을 품고 있어 창의 최소 폭이
    줄지 않은 상태이고, 그 시점의 `resize()`는 **옛 최소 폭에 클램프되어 무시**된다.
    그래서 창은 그대로인 채 좌측 섹션만 넓어졌다.

        숨김 전   창 3838  좌측 3244  우측 580
        숨김 후   창 3838  좌측 3828  우측 0     <- 창은 그대로, 좌측이 584px 확장

    ## WHAT
    기존 왕복 항등 테스트(`test_hide_then_show_restores_original_geometry`)는 이걸
    잡지 못했다. 숨길 때의 창 폭을 저장해 켤 때 되돌리므로, 숨김 단계에서 창이
    전혀 줄지 않아도 왕복은 항등이기 때문이다. 그래서 **숨김 단계 자체**를 본다.
    """
    before_window, before_left, before_right = _snapshot(window)
    assert before_right > 0, "우측 패널이 보이는 상태에서 시작해야 한다"

    window.toggle_right_section(False)
    hidden_window, hidden_left, _ = _snapshot(window)

    assert hidden_window < before_window, (
        f"패널을 숨겼는데 창 폭이 줄지 않았다 ({before_window} -> {hidden_window}). "
        f"setVisible(False) 직후에는 창의 최소 폭이 아직 우측 패널을 포함하므로 "
        f"resize()가 클램프된다 — 레이아웃 제약을 먼저 재계산해야 한다."
    )
    assert hidden_left == before_left, (
        f"창 대신 좌측 섹션이 늘어났다 ({before_left} -> {hidden_left}). "
        f"컴포넌트 크기는 그대로 두고 창이 줄어야 한다."
    )
