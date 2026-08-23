"""
테마 QSS 구조 통일성 + 컴포넌트 구분 회귀 테스트 (S-077)

## WHY
사용자 요청 둘을 함께 다룬다.

1. "버튼과 리스트 박스 같은 서로 다른 컴포넌트의 구분이 잘 안 되는 것 같다. 색이
   똑같아서 그런가?" — 맞는 짐작이었다. 버튼 배경과 입력/리스트 배경의 대비가
   1.32~1.73에 불과했고, **light·classic은 테두리 색까지 동일**해 단서가 없었다.
   게다가 `QComboBox`가 테마마다 편이 달랐다 — dark·dracula는 버튼 쪽 배경,
   light·classic은 입력 쪽 배경이라 "콤보는 누르는 것인가 입력하는 것인가"에
   테마마다 다른 답을 하고 있었다.

2. "모든 테마 파일이 통일성이 있어야 관리가 수월하다. 클래식은 모양 때문에 어쩔 수
   없지만 최대한 통일성이 있어야 한다." — S-073에서 클래식에만 override 블록 13줄을
   덧붙여 79규칙이던 구조가 92규칙으로 어긋나 있었다.

## WHAT
* 4테마의 **셀렉터 집합과 등장 순서가 동일**한가 (파일 간 대조가 쉬워야 한다)
* 버튼과 입력/리스트가 **테두리로 구분**되는가
* `QComboBox`가 4테마에서 **같은 편**(입력 계열)인가

## HOW
값이 아니라 **관계**를 고정한다. 팔레트는 테마마다 다르므로 절대 색을 박으면 테마를
손볼 때마다 테스트가 깨진다. "버튼 테두리와 입력 테두리가 서로 구분되는가" 같은
관계는 팔레트가 바뀌어도 유지되어야 하는 성질이다.
"""
import pathlib
import re

import pytest

THEMES_DIR = pathlib.Path(__file__).resolve().parents[1] / "resources" / "themes"
THEMES = ("dark", "light", "classic", "dracula")

# 버튼 테두리와 입력 테두리를 구분되게 만드는 최소 대비.
# 1.0은 "완전히 같은 색"이다 — light/classic이 실제로 그랬다.
MIN_BORDER_SEPARATION = 1.5


def _rules(theme: str):
    """테마 QSS를 [(셀렉터, 본문)] 순서대로 읽는다 (주석 제거)."""
    text = re.sub(
        r"/\*.*?\*/", "", (THEMES_DIR / f"{theme}_theme.qss").read_text(encoding="utf-8"), flags=re.S
    )
    return [
        (" ".join(m.group(1).split()), m.group(2))
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)
    ]


def _prop(theme: str, selector: str, prop: str):
    """지정 셀렉터의 속성값 (없으면 None). 같은 셀렉터가 여러 번이면 마지막 값."""
    value = None
    for sel, body in _rules(theme):
        if sel != selector:
            continue
        found = re.search(rf"{re.escape(prop)}:\s*([^;]+)", body)
        if found:
            value = found.group(1).strip()
    return value


def _luminance(color: str) -> float:
    color = color.lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    adjusted = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_all_themes_share_the_same_selector_set():
    """
    4테마가 같은 셀렉터를 갖춰야 한다.

    한 테마에만 규칙이 있으면 다른 테마에서 그 위젯이 공용 스타일로 떨어져
    "이 테마에서만 이상하다"가 된다. 파일 간 대조로 찾기도 어려워진다.
    """
    base = {sel for sel, _ in _rules("dark")}
    for theme in THEMES[1:]:
        current = {sel for sel, _ in _rules(theme)}
        only_here = current - base
        missing = base - current
        assert not (only_here or missing), (
            f"{theme} 테마의 셀렉터가 dark와 다르다.\n"
            f"  이 테마에만: {sorted(only_here)}\n"
            f"  빠진 것:     {sorted(missing)}"
        )


def test_all_themes_declare_rules_in_the_same_order():
    """
    규칙 등장 순서까지 같아야 한다.

    순서가 같아야 파일을 나란히 놓고 값만 비교할 수 있다. QSS는 같은 특이도에서
    나중 선언이 이기므로, 순서가 어긋나면 우선순위도 테마마다 달라진다.
    """
    base = [sel for sel, _ in _rules("dark")]
    for theme in THEMES[1:]:
        current = [sel for sel, _ in _rules(theme)]
        first_diff = next(
            (f"index {i}: dark={a} / {theme}={b}"
             for i, (a, b) in enumerate(zip(base, current)) if a != b),
            "길이 차이",
        )
        assert current == base, (
            f"{theme} 테마의 규칙 순서가 dark와 다르다 (첫 불일치: {first_diff})"
        )


@pytest.mark.parametrize("theme", THEMES)
def test_button_border_is_distinguishable_from_input_border(theme):
    """
    버튼 테두리가 입력/리스트 테두리와 구분되어야 한다.

    배경 대비만으로는 부족했다(1.32~1.73). light·classic은 테두리까지 같은 색이라
    (대비 1.00) 두 부류를 가를 단서가 아예 없었다.
    """
    button = _prop(theme, "QPushButton", "border-color")
    field = _prop(
        theme, "QLineEdit, QTextEdit, QPlainTextEdit, QSmartTextEdit, QSmartListView", "border-color"
    )
    assert button and field, f"{theme}: 버튼/입력 테두리 색을 찾지 못했다"

    separation = _contrast(button, field)
    assert separation >= MIN_BORDER_SEPARATION, (
        f"{theme}: 버튼 테두리({button})와 입력 테두리({field})의 대비가 "
        f"{separation:.2f}로 낮다 (기준 {MIN_BORDER_SEPARATION}). "
        f"두 컴포넌트를 눈으로 가를 단서가 없다."
    )


@pytest.mark.parametrize("theme", THEMES)
def test_combobox_sides_with_inputs_not_buttons(theme):
    """
    콤보박스는 4테마에서 **입력 계열**로 통일되어야 한다.

    값을 고르는 것이지 동작을 실행하는 것이 아니므로 입력에 가깝다. 예전에는
    dark·dracula가 버튼 배경, light·classic이 입력 배경을 써서 테마마다 답이
    달랐다 — 사용자가 "구분이 잘 안 된다"고 느낀 원인 중 하나다.
    """
    combo = _prop(theme, "QComboBox", "background-color")
    field = _prop(
        theme, "QLineEdit, QTextEdit, QPlainTextEdit, QSmartTextEdit, QSmartListView",
        "background-color",
    )
    button = _prop(theme, "QPushButton", "background-color")
    assert combo and field and button, f"{theme}: 배경색을 찾지 못했다"

    assert combo == field, (
        f"{theme}: 콤보 배경({combo})이 입력 배경({field})과 다르다 — "
        f"버튼 배경은 {button}. 콤보는 입력 계열로 통일한다."
    )
