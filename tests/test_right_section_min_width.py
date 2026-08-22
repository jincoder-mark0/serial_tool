"""
우측 섹션 최소 폭 회귀 테스트 (매크로 목록 가로 스크롤 방지)

## WHY
사용자 보고(2026-08-22): "라이트패널의 최소폭을 매크로패널의 좌우 스크롤이 생기지
않는 범위로 지정해야 한다." 조사 결과 `MainRightSection.minimumWidth()`가 **0**이라
스플리터가 우측 섹션을 0px까지 밀어붙일 수 있었다 — 패널이 "표시됨" 상태인데도 화면에서
사라지거나, 매크로 표가 가로로 잘린 채 스크롤로만 보였다.

## WHAT
* 최소 폭이 실제로 적용돼 있는지 (0이면 스플리터가 패널을 접어버린다)
* 매크로 표의 컬럼 리사이즈 구성이 그대로인지 — 요구 폭을 결정하는 것이 이 구성이다

## HOW — 왜 픽셀 임계값을 여기서 재지 않는가
상수 580px는 **네이티브 렌더에서 실측**한 값이다(4테마 x 2언어 전 조합: ko 566 /
en 575, 최댓값 575에 여유). 그런데 pytest 표준 환경인 `QT_QPA_PLATFORM=offscreen`은
시스템 폰트가 0개라 텍스트 폭이 실제와 다르게 계산된다(S-050 주석에 같은 제약이
기록돼 있다). 그 환경에서 임계값을 재면 네이티브보다 훨씬 작게 나오고, **너무 작은
상수도 통과시키는 무의미한 테스트**가 된다.

실제로 초기 구현이 그랬다 — 상수를 580에서 300으로 낮춰도 통과했다.

그래서 여기서는 픽셀 임계값을 재지 않고, **요구 폭을 결정하는 구조**(매크로 표의 컬럼
리사이즈 구성)가 바뀌지 않았는지를 고정한다. 이 구성이 달라지면 테스트가 실패하며,
그때가 네이티브에서 임계값을 다시 재야 한다는 신호다.

재측정 방법(네이티브에서 수동 실행): MainWindow + MainPresenter를 띄워 매크로가 로드된
상태로 만들고, 스플리터로 우측 섹션 폭을 1px씩 줄이며 매크로 표의
`horizontalScrollBar().maximum() > 0`이 되는 지점을 찾는다. 4테마 x 2언어 전 조합을
돌려 최댓값에 여유를 더한다.
"""
from PyQt5.QtWidgets import QTableView, QHeaderView

from common.constants import CONTROL_MIN_WIDTH_RIGHT_SECTION
from view.sections.main_right_section import MainRightSection

# 상수를 실측했을 당시의 매크로 표 컬럼 리사이즈 구성.
# ResizeToContents 컬럼은 내용보다 좁아지지 않아 요구 폭의 하한을 만든다.
EXPECTED_MACRO_RESIZE_MODES = [
    QHeaderView.ResizeToContents,
    QHeaderView.ResizeToContents,
    QHeaderView.Stretch,
    QHeaderView.ResizeToContents,
    QHeaderView.ResizeToContents,
    QHeaderView.ResizeToContents,
    QHeaderView.ResizeToContents,
]


def test_right_section_applies_minimum_width(qtbot):
    """상수가 실제 위젯에 적용돼 있어야 한다 (스플리터가 0까지 밀지 못하도록)."""
    section = MainRightSection()
    qtbot.addWidget(section)

    assert section.minimumWidth() == CONTROL_MIN_WIDTH_RIGHT_SECTION, (
        "우측 섹션에 최소 폭이 적용되지 않았다 — minimumWidth가 0이면 스플리터가 "
        "패널을 0px까지 접어버려 '표시됨'인데 보이지 않는 상태가 된다."
    )


def test_macro_table_column_layout_unchanged(qtbot):
    """
    매크로 표의 컬럼 리사이즈 구성이 상수 실측 당시와 같은지 고정한다.

    이 구성이 요구 폭을 정한다. 컬럼이 늘거나 Stretch/ResizeToContents가 바뀌면
    580px로는 부족해질 수 있으므로, 그때는 네이티브에서 다시 재고 상수를 갱신해야 한다.
    """
    section = MainRightSection()
    qtbot.addWidget(section)

    tables = section.findChildren(QTableView)
    assert tables, "우측 섹션에서 표를 찾지 못했다 — 구조가 바뀌었는지 확인할 것"

    macro_table = next(
        (t for t in tables
         if t.model() is not None and t.model().columnCount() == len(EXPECTED_MACRO_RESIZE_MODES)),
        None,
    )
    assert macro_table is not None, (
        f"컬럼 {len(EXPECTED_MACRO_RESIZE_MODES)}개짜리 매크로 표를 찾지 못했다. "
        f"컬럼 수가 바뀌었다면 CONTROL_MIN_WIDTH_RIGHT_SECTION을 네이티브에서 다시 재고 "
        f"이 테스트의 EXPECTED_MACRO_RESIZE_MODES도 갱신하라."
    )

    header = macro_table.horizontalHeader()
    actual = [header.sectionResizeMode(c) for c in range(macro_table.model().columnCount())]
    assert actual == EXPECTED_MACRO_RESIZE_MODES, (
        f"매크로 표 컬럼 리사이즈 구성이 바뀌었다 (기대 {EXPECTED_MACRO_RESIZE_MODES}, "
        f"실제 {actual}). 요구 폭이 달라졌을 수 있으니 네이티브 환경에서 "
        f"가로 스크롤 임계값을 다시 재고 CONTROL_MIN_WIDTH_RIGHT_SECTION을 갱신하라."
    )
