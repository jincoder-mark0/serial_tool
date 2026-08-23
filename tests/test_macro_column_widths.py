"""
매크로 표 컬럼 폭 배분 테스트 (S-079)

## WHY
남은 화면을 훑다가 나온 결함이다. 우측 패널을 최소 폭으로 두고 재 보니
**가장 중요한 "명령" 열이 가장 좁았다** — 뷰포트 586px 중 114px뿐인데 내용이
요구하는 폭은 375px였다. 긴 명령(`AT+VERY+LONG+COMMAND...`)은 잘리고 HEX 문자열은
두 줄로 접혔다.

원인은 헤더 잘림을 막으려던 S-032의 수정이었다. `setMinimumSectionSize()`는
**전 열에 공통으로** 걸리는 값이라, "가장 넓은 헤더"(지연(ms), 78px)를 최소로 잡자
정작 헤더 글자가 하나도 없는 체크박스 열까지 78px가 됐다. 고정 열 4개가 312px를
가져가고 남은 것이 명령 열 몫이었다.

전역 최소값은 좁은 열만 부풀리고 넓은 열에는 아무것도 더해 주지 않았다 — 잃기만 한
장치였다. 헤더 잘림은 ResizeToContents가 이미 열마다 막고 있었다.

## WHAT
* 최소 섹션 폭이 **체크박스 규모**인가 (헤더 글자 규모로 되돌아가지 않았는가)
* 체크박스가 보일 만큼은 되는가 (반대 방향으로 지나치지 않았는가)
* ResizeToContents가 열마다 헤더 텍스트를 반영하는가
  (이번 변경이 딛고 선 전제 — 깨지면 전역 최소값이 실은 필요했다는 뜻이다)
* 명령 열만 Stretch인가 (남는 폭이 명령 열로 가는 구조)

## HOW
실제 열 픽셀 폭은 재지 않는다. pytest 하네스(offscreen, 테마 QSS 미적용)에서는
델리게이트 크기 힌트가 실행 화면과 크게 달라(접두사 열이 361px로 나온다) 픽셀 비교가
거짓 통과·거짓 실패를 모두 낸다. 대신 **폭을 정하는 기전**을 본다.

실행 화면 실측(네이티브, 우측 패널 최소 폭)은 다음과 같았다:
    수정 전  명령 114px / 나머지 합 472px, 긴 명령 잘림
    수정 후  명령 232px(ko) · 227px(en), 헤더 잘림 0건, 가로 스크롤 없음
"""
import json
import pathlib

import pytest
from PyQt5.QtWidgets import QApplication, QHeaderView, QStyle

from view.managers.language_manager import language_manager
from view.widgets.macro_list import MacroColumns, MacroListWidget

# 헤더 라벨이 있는 열 (선택 열은 라벨이 없다)
LABEL_KEYS = {
    MacroColumns.PREFIX: "macro_list_col_prefix",
    MacroColumns.COMMAND: "macro_list_col_command",
    MacroColumns.SUFFIX: "macro_list_col_suffix",
    MacroColumns.HEX_MODE: "macro_list_col_hex",
    MacroColumns.DELAY: "macro_list_col_delay",
    MacroColumns.SEND_BTN: "macro_list_col_send",
}


LANGUAGE_DIR = pathlib.Path(__file__).resolve().parents[1] / "resources" / "languages"


@pytest.fixture
def macro_widget(qapp):
    """
    실제 언어 리소스를 얹은 매크로 목록 위젯 한 개.

    하네스의 language_manager는 리소스가 비어 있어 get_text가 키 이름을 그대로
    돌려준다 — 그 상태로 헤더 폭을 재면 실제 라벨이 아니라 키 문자열을 재게 된다.
    """
    for path in LANGUAGE_DIR.glob("*.json"):
        language_manager.resources[path.stem] = json.loads(
            path.read_text(encoding="utf-8")
        )
    language_manager.set_language("en")

    widget = MacroListWidget()
    yield widget
    widget.deleteLater()
    QApplication.processEvents()


def _widest_header_width(header) -> int:
    """모든 언어의 헤더 라벨 중 가장 넓은 텍스트 폭 — 예전 최소값의 근거였다."""
    metrics = header.fontMetrics()
    return max(
        metrics.horizontalAdvance(
            language_manager.get_text(key, language_code=lang)
        )
        for key in LABEL_KEYS.values()
        for lang in language_manager.get_supported_languages()
    )


def test_minimum_section_size_is_checkbox_scale_not_header_scale(macro_widget):
    """
    최소 섹션 폭이 **헤더 글자 규모로 되돌아가면 안 된다.**

    이것이 이번 결함의 정확한 지점이다. 전역 최소값을 "가장 넓은 헤더"로 잡으면
    라벨이 없는 열까지 그만큼 부풀어, 유일한 Stretch 열인 명령 열이 굶는다.
    """
    header = macro_widget.macro_table.horizontalHeader()
    widest_header = _widest_header_width(header)

    assert header.minimumSectionSize() < widest_header, (
        f"최소 섹션 폭({header.minimumSectionSize()}px)이 가장 넓은 헤더 텍스트"
        f"({widest_header}px) 수준이다 — 전역 헤더 기준 최소값이 되살아났다."
    )


def test_minimum_section_size_still_fits_a_checkbox(macro_widget):
    """
    반대 방향으로 지나치면 안 된다 — 선택 열의 체크박스는 보여야 한다.

    최소값을 0에 가깝게 두면 좁은 창에서 체크박스가 잘려 클릭할 수 없게 된다.
    """
    header = macro_widget.macro_table.horizontalHeader()
    indicator = header.style().pixelMetric(QStyle.PM_IndicatorWidth, None, header)

    assert header.minimumSectionSize() >= indicator, (
        f"최소 섹션 폭({header.minimumSectionSize()}px)이 체크박스 표시기"
        f"({indicator}px)보다 좁다."
    )


@pytest.mark.parametrize("language", ["en", "ko"])
def test_resize_to_contents_accounts_for_header_text(macro_widget, language):
    """
    ResizeToContents가 열마다 헤더 텍스트를 반영해야 한다.

    이번 변경은 "전역 최소값 없이도 헤더는 안 잘린다"는 전제 위에 서 있다.
    Qt의 계산이 바뀌어 이 전제가 깨지면 여기서 먼저 알려야 한다 —
    그때는 전역 최소값이 실은 필요했다는 뜻이므로 열별 대책을 다시 세워야 한다.
    """
    previous = language_manager.get_current_language()
    language_manager.set_language(language)
    try:
        header = macro_widget.macro_table.horizontalHeader()
        metrics = header.fontMetrics()
        model = macro_widget.macro_table.model()

        too_narrow = {}
        for column in LABEL_KEYS:
            label = model.headerData(column, 1) or ""      # 1 = Qt.Horizontal
            needed = metrics.horizontalAdvance(label)
            if header.sectionSizeHint(column) < needed:
                too_narrow[label] = (header.sectionSizeHint(column), needed)

        assert not too_narrow, (
            f"[{language}] 헤더 텍스트가 열 크기 힌트에 반영되지 않았다 "
            f"(힌트, 필요): {too_narrow}"
        )
    finally:
        language_manager.set_language(previous)


def test_command_is_the_only_stretching_column(macro_widget):
    """
    남는 폭은 명령 열로 가야 한다.

    다른 열이 함께 Stretch면 여분이 나뉘어, 정작 긴 문자열을 담는 명령 열이
    다시 좁아진다.
    """
    header = macro_widget.macro_table.horizontalHeader()
    stretching = [
        int(column)
        for column in range(macro_widget.macro_table.model().columnCount())
        if header.sectionResizeMode(column) == QHeaderView.Stretch
    ]

    assert stretching == [int(MacroColumns.COMMAND)], (
        f"Stretch 열이 명령 열 하나가 아니다: {stretching}"
    )


def test_command_cell_tooltip_shows_the_full_text(macro_widget):
    """
    잘린 명령을 마우스만 올려도 읽을 수 있어야 한다.

    명령 열은 좁은 우측 패널에서 긴 명령을 elide한다. 폭을 넓혀도 한계는 남으므로,
    전문을 읽을 길이 "셀을 편집 상태로 만들기"뿐이면 안 된다. 표 전체에 걸린
    고정 안내 툴팁은 무엇이 잘렸는지 알려 주지 않는다.
    """
    long_command = "AT+VERY+LONG+COMMAND+THAT+OVERFLOWS=1234567890"
    macro_widget.add_dummy_row(long_command, False, True, "2500")
    QApplication.processEvents()

    model = macro_widget.macro_table.model()
    row = model.rowCount() - 1
    item = model.item(row, MacroColumns.COMMAND)

    assert item.toolTip() == long_command, (
        f"명령 셀 툴팁이 전문과 다르다: {item.toolTip()!r} != {long_command!r}"
    )


def test_command_cell_tooltip_follows_edits(macro_widget):
    """
    명령을 고치면 툴팁도 따라가야 한다.

    행을 만들 때만 붙이면, 사용자가 명령을 바꾼 뒤에는 툴팁이 옛 문자열을 보여
    준다 — 없는 것보다 나쁘다.
    """
    macro_widget.add_dummy_row("AT", False, True, "100")
    QApplication.processEvents()

    model = macro_widget.macro_table.model()
    row = model.rowCount() - 1
    edited = "AT+CGSN=EDITED+AFTER+CREATION+0123456789"
    model.item(row, MacroColumns.COMMAND).setText(edited)
    QApplication.processEvents()

    tooltip = model.item(row, MacroColumns.COMMAND).toolTip()
    assert tooltip == edited, f"편집 후 툴팁이 갱신되지 않았다: {tooltip!r}"
