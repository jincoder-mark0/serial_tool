"""
클래식 테마 사각 모서리 회귀 테스트 (S-073)

## WHY
사용자 보고: "클래식이면 둥근 느낌이 없어야 하는 거 아닌가."

맞는 지적이었다. 그런데 `border-radius`는 테마 파일이 아니라 **4테마가 공유하는
`common.qss`에 13곳** 있었다(테마 파일에는 0곳). 공유 파일이 모서리를 강제하니
클래식만 빠져나갈 수 없었다 — `S-036`에서 폰트가 같은 구조로 막혔던 것과 같은 부류다.

테마 QSS가 `common.qss` 뒤에 이어 붙으므로(`ThemeResourceLoader.load_theme_file_content`),
클래식에서 **같은 셀렉터로** 다시 선언하면 나중 것이 이긴다.

## WHAT
`common.qss`에서 `border-radius`를 지정하는 모든 셀렉터가, `classic_theme.qss`에
**동일한 셀렉터 문자열**로 `0`으로 덮여 있는지 확인한다.

## HOW — 왜 셀렉터 문자열이 같아야 하는가
Qt QSS는 순서보다 **선택자 특이도**를 먼저 본다(S-036 실측). `QSmartListView`에
`common.qss`가 `type+class`로 걸어둔 규칙은, 뒤에 오는 `class`만의 규칙으로는 이길 수
없었다. 그래서 이 테스트는 "클래식 어딘가에 border-radius: 0이 있다"가 아니라
**"같은 셀렉터로 덮었다"**를 확인한다.

`common.qss`에 규칙이 새로 추가되면 이 테스트가 먼저 실패해 클래식 갱신을 요구한다.
"""
import pathlib
import re

THEMES_DIR = pathlib.Path(__file__).resolve().parents[1] / "resources" / "themes"


def _rules_with_border_radius(path: pathlib.Path) -> dict:
    """
    QSS에서 `border-radius`를 지정한 규칙을 {셀렉터: 값}으로 뽑는다.

    쉼표로 묶인 셀렉터 목록(`A, B`)은 **개별 셀렉터로 펴서** 담는다. 파일마다
    묶는 방식이 다르기 때문이다 — `common.qss`는 스크롤바 핸들을 세로/가로로
    나눠 쓰고, 테마 파일들은 하나로 묶어 쓴다. 문자열 그대로 비교하면 같은 것을
    다르다고 판정한다.

    같은 셀렉터가 여러 번 나오면 **마지막 값**을 쓴다 — QSS에서 나중 선언이 이긴다.
    """
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    found = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        radius = re.search(r"border-radius:\s*([^;]+)", match.group(2))
        if not radius:
            continue
        for part in match.group(1).split(","):
            selector = " ".join(part.split())
            if selector:
                found[selector] = radius.group(1).strip()
    return found


def _is_zero(value: str) -> bool:
    """`0`, `0px`, `0 0 0 0` 등을 모두 0으로 본다."""
    return all(part.rstrip("px") in ("0", "") for part in value.split())


def test_classic_overrides_every_shared_border_radius():
    """`common.qss`가 둥글린 모든 셀렉터를 클래식이 같은 셀렉터로 0으로 덮어야 한다."""
    shared = _rules_with_border_radius(THEMES_DIR / "common.qss")
    classic = _rules_with_border_radius(THEMES_DIR / "classic_theme.qss")

    assert shared, "common.qss에서 border-radius 규칙을 찾지 못했다 — 파싱이 깨졌다"

    missing = [sel for sel in shared if sel not in classic]
    assert not missing, (
        "common.qss가 둥글리는데 classic_theme.qss가 덮지 않은 셀렉터:\n  "
        + "\n  ".join(missing)
        + "\n\nclassic_theme.qss에 **동일한 셀렉터 문자열**로 "
        "`border-radius: 0px;`를 추가하라. 셀렉터가 다르면 특이도 싸움이 되어 "
        "의도대로 이기지 못한다(S-036)."
    )

    not_zero = {sel: classic[sel] for sel in shared if not _is_zero(classic[sel])}
    assert not not_zero, (
        f"클래식이 덮긴 했으나 0이 아닌 셀렉터: {not_zero}"
    )


def test_other_themes_keep_rounded_corners():
    """
    나머지 3테마는 둥근 모서리를 유지해야 한다.

    클래식만 각지게 하는 것이 요청이었다. 공유 규칙을 건드려 전 테마를 각지게 만드는
    실수를 막는다.
    """
    shared = _rules_with_border_radius(THEMES_DIR / "common.qss")
    rounded = {sel for sel, val in shared.items() if not _is_zero(val)}
    assert rounded, "common.qss의 둥근 모서리 규칙이 사라졌다 — 전 테마가 각져 버린다"

    for theme in ("dark", "light", "dracula"):
        overrides = _rules_with_border_radius(THEMES_DIR / f"{theme}_theme.qss")
        squared = [sel for sel in rounded if sel in overrides and _is_zero(overrides[sel])]
        assert not squared, (
            f"{theme} 테마가 공유 둥근 모서리를 0으로 덮고 있다: {squared} — "
            f"각진 모서리는 클래식만이다."
        )
