"""
테마별 로그 색 팔레트 회귀 테스트 (S-078)

## WHY
사용자 지시: "코드 내에 하드 코딩되어 있는 색상은 테마로 모두 이동해야 함."

옮기려고 훑다가 실제 결함이 나왔다. `ColorManager`가 `theme_name == 'light'`로
밝기를 판정해, **밝은 테마인 classic이 다크용 로그 색을 받고 있었다.** 흰 배경 위에
다크 배경용 색을 얹은 셈이라 11개 중 10개가 WCAG 4.5:1 미달이었다 — 기본 텍스트는
1.61:1로 거의 읽히지 않았다.

색이 코드에 박혀 있으면 이런 어긋남을 아무도 못 본다. 정본을
`resources/themes/palette.json`으로 옮기고, 각 테마의 로그 배경 위에서 대비를
지키는지 여기서 강제한다.

## WHAT
* 4테마 모두 팔레트 항목이 갖춰졌는가 (한 테마만 빠지면 그 테마가 폴백으로 떨어진다)
* 각 색이 **그 테마의 로그 배경** 위에서 4.5:1 이상인가
* 밝기 분류(`is_light`)가 배경 밝기와 모순되지 않는가
* 코드에 로그 색 리터럴이 되살아나지 않았는가

## HOW
대비 기준은 본문 텍스트에 적용되는 WCAG AA(4.5:1)를 쓴다. 로그는 읽으라고 있는
텍스트이므로 장식 기준(3:1)으로 낮추지 않는다.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "resources" / "themes" / "palette.json"
EXPECTED_THEMES = {"dark", "light", "classic", "dracula"}
REQUIRED_KEYS = {
    "timestamp", "info", "error", "warn", "prompt",
    "success", "rx", "tx", "system", "debug", "default",
}
MIN_CONTRAST = 4.5


def _palette():
    return json.loads(PALETTE_PATH.read_text(encoding="utf-8"))["themes"]


def _luminance(color: str) -> float:
    color = color.lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    adjusted = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_palette_covers_every_theme():
    """
    4테마 모두 팔레트 항목이 있어야 한다.

    빠진 테마는 조회 시 dark로 폴백한다 — 밝은 테마가 빠지면 흰 배경에 다크용 색이
    얹혀 읽을 수 없게 된다. classic이 실제로 그 상태였다.
    """
    themes = set(_palette())
    missing = EXPECTED_THEMES - themes
    assert not missing, f"팔레트에 없는 테마: {sorted(missing)}"


@pytest.mark.parametrize("theme", sorted(EXPECTED_THEMES))
def test_palette_has_all_required_colors(theme):
    """의미 이름이 하나라도 빠지면 조회 시 KeyError로 앱이 죽는다."""
    log = _palette()[theme]["log"]
    missing = REQUIRED_KEYS - set(log)
    assert not missing, f"{theme} 테마에 없는 색: {sorted(missing)}"


@pytest.mark.parametrize("theme", sorted(EXPECTED_THEMES))
def test_every_log_color_is_readable_on_its_own_background(theme):
    """
    각 색이 **그 테마의 로그 배경** 위에서 읽혀야 한다.

    "어두운 테마용 / 밝은 테마용" 두 벌만 두고 테마를 늘리면 이 조건이 조용히
    깨진다. 배경을 팔레트에 함께 적어 두고 같은 파일 안에서 검사한다.
    """
    entry = _palette()[theme]
    background = entry["background"]
    failures = {
        name: round(_contrast(color, background), 2)
        for name, color in entry["log"].items()
        if _contrast(color, background) < MIN_CONTRAST
    }
    assert not failures, (
        f"{theme} 테마의 로그 색이 배경({background}) 위에서 기준({MIN_CONTRAST}) 미달: "
        f"{failures}"
    )


@pytest.mark.parametrize("theme", sorted(EXPECTED_THEMES))
def test_is_light_matches_the_background(theme):
    """
    밝기 분류가 배경과 모순되면 안 된다.

    `is_light`는 규칙 색(light_color/dark_color) 선택에 쓰인다. 배경은 밝은데
    is_light가 False면 어두운 배경용 색이 선택되어 대비가 무너진다.
    """
    entry = _palette()[theme]
    background_is_light = _luminance(entry["background"]) > 0.5
    assert entry["is_light"] == background_is_light, (
        f"{theme}: is_light={entry['is_light']}인데 배경 {entry['background']}의 밝기는 "
        f"{'밝음' if background_is_light else '어두움'}이다."
    )


def test_log_colors_are_not_hardcoded_in_code_again():
    """
    로그 색이 코드로 되돌아오지 않아야 한다.

    팔레트 파일로 옮긴 의미가 사라지지 않도록, 색을 쓰는 모듈에 색 리터럴이
    다시 생기는 것을 막는다. 파일을 읽지 못할 때를 위한 최후 폴백은 예외로 둔다 —
    그것까지 없애면 팔레트 파일이 깨졌을 때 앱이 아예 뜨지 못한다.
    """
    watched = [
        ROOT / "common" / "constants.py",
        ROOT / "view" / "managers" / "color_manager.py",
    ]
    hex_re = re.compile(r"#[0-9a-fA-F]{6}\b")
    offenders = []
    for path in watched:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "예" in line:      # 주석·docstring 예시 제외
                continue
            if hex_re.search(line):
                offenders.append(f"{path.name}:{line_no}: {stripped[:70]}")

    assert not offenders, (
        "로그 색 리터럴이 코드에 다시 생겼다 (resources/themes/palette.json로 옮길 것):\n  "
        + "\n  ".join(offenders)
    )
