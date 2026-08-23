"""
QSS 색 대비 회귀 테스트 (S-065)

## WHY
* S-063이 4테마 x accent/danger/warning x 4상태(normal/hover/pressed/disabled) 48칸의
  텍스트 대비를 계산해 18칸을 고쳤다. 그런데 그 계산은 스크래치패드 1회성 스크립트로
  이루어져 프로젝트에 남지 않았다. 지금은 전부 통과해도, 누군가 QSS 색을 한 줄만
  바꾸면 대비가 아무도 모르게 되돌아간다 - 이 결함이 애초에 3테마에 오래 방치된
  이유이기도 하다(`warning:disabled`가 1.22:1로 방치됐던 사례). 이 테스트가 그것을
  기계적으로 고정한다.

## WHAT
* resources/themes/*.qss(공용 규칙만 담은 common.qss 제외 4테마)에서 의미색 버튼
  (QPushButton[class="accent"/"danger"/"warning"])과 포트 상태 버튼/라벨
  (QPushButton[state="connected"/"disconnected"/"error"/"recording"],
  QLabel[state="connected"/"disconnected"])의 배경/글자색을 파싱해 WCAG 상대 휘도
  대비를 계산하고 기준(활성 상태 ≥4.5:1, `:disabled` ≥3.0:1 - S-063이 쓴 기준과 동일)을
  강제한다.

## HOW
* Qt를 띄우지 않는다 - 정규식으로 `selector { decl; ... }` 블록을 파싱하는 경량 QSS
  파서를 직접 구현한다(4개 QSS 파일 전체 스캔, 1초 미만 목표).
* `:hover`/`:pressed`/`:checked`처럼 자신의 규칙에서 `color`(또는 `background-color`)를
  다시 선언하지 않는 상태는 그 셀렉터의 기본(상태 없는) 규칙 값을 물려받는다 -
  QSS의 실제 캐스케이딩 동작을 그대로 재현해야 "통과해선 안 될 조합이 통과"하거나
  "멀쩡한 조합이 실패"하는 오탐을 막는다(예: `QPushButton[class="danger"]:pressed`는
  `color`를 재선언하지 않고 기본 규칙의 흰 글씨를 물려받는다).
* `QLabel[state=...]`는 스스로 배경을 갖지 않는다 - 상태바(`QStatusBar`)의 영구 위젯으로
  추가되는 자식 라벨이라(`view/sections/main_status_bar.py`의 `port_status_lbl`),
  같은 테마 파일의 `QStatusBar` 배경색과 짝지어 계산한다.

pytest tests/test_qss_contrast.py -v
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = PROJECT_ROOT / "resources" / "themes"
THEME_FILES = ["light_theme.qss", "dark_theme.qss", "classic_theme.qss", "dracula_theme.qss"]

ACTIVE_MIN_RATIO = 4.5
DISABLED_MIN_RATIO = 3.0

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _parse_qss(path: Path) -> Dict[str, Dict[str, str]]:
    """QSS 파일을 `{셀렉터: {속성: 값}}` 딕셔너리로 파싱한다.

    Logic:
        - 주석(`/* ... */`)을 먼저 제거해 셀렉터/선언 추출에 섞이지 않게 한다.
        - `selector1, selector2 { decl; ... }`처럼 콤마로 묶인 셀렉터 목록은
          각 셀렉터에 동일한 선언을 개별 등록한다(`hint-text` 그룹 등 실제 존재하는
          패턴 - 이 테스트의 대상 셀렉터는 아니지만 파서가 깨지지 않아야 한다).

    Args:
        path (Path): 파싱할 QSS 파일 경로.

    Returns:
        Dict[str, Dict[str, str]]: 셀렉터 문자열 → {속성명: 값} 매핑.
    """
    text = _COMMENT_RE.sub("", path.read_text(encoding="utf-8"))
    rules: Dict[str, Dict[str, str]] = {}
    for sel_text, body in _RULE_RE.findall(text):
        decls: Dict[str, str] = {}
        for part in body.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            prop, _, value = part.partition(":")
            decls[prop.strip()] = value.strip()
        if not decls:
            continue
        normalized = " ".join(sel_text.split())
        for sel in normalized.split(","):
            sel = sel.strip()
            if sel:
                rules.setdefault(sel, {}).update(decls)
    return rules


def _luminance(hex_color: str) -> float:
    """WCAG 상대 휘도(relative luminance)를 계산한다."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast_ratio(color_a: str, color_b: str) -> float:
    """두 색의 WCAG 대비비(1.0~21.0)를 계산한다."""
    la, lb = sorted([_luminance(color_a), _luminance(color_b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _resolve_bg_color(
    rules: Dict[str, Dict[str, str]], base_selector: str, pseudo: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    pseudo 상태 셀렉터의 배경/글자색을 상속 규칙까지 반영해 계산한다.

    Logic:
        - pseudo 자신의 규칙에 `background-color`/`color`가 없으면 base(상태 없는)
          규칙의 값을 물려받는다. `:pressed`/`:hover`가 `color`를 재선언하지 않는
          실제 QSS 캐스케이딩과 동일한 동작.

    Args:
        rules (Dict[str, Dict[str, str]]): `_parse_qss()` 결과.
        base_selector (str): 상태 없는 기본 셀렉터(예: `QPushButton[class="accent"]`).
        pseudo (str): `""`(기본) 또는 `:hover`/`:pressed`/`:disabled`/`:checked` 등.

    Returns:
        Tuple[Optional[str], Optional[str]]: (배경색, 글자색). 파싱 실패 시 None 포함.
    """
    selector = f"{base_selector}{pseudo}" if pseudo else base_selector
    own = rules.get(selector, {})
    base = rules.get(base_selector, {})
    bg = own.get("background-color", base.get("background-color"))
    color = own.get("color", base.get("color"))
    return bg, color


# -----------------------------------------------------------------------------
# 검사 대상 정의 — (base_selector, [(pseudo, 임계값), ...])
# -----------------------------------------------------------------------------
BUTTON_CLASS_FAMILIES: List[Tuple[str, List[Tuple[str, float]]]] = [
    (
        f'QPushButton[class="{cls}"]',
        [
            ("", ACTIVE_MIN_RATIO),
            (":hover", ACTIVE_MIN_RATIO),
            (":pressed", ACTIVE_MIN_RATIO),
            (":disabled", DISABLED_MIN_RATIO),
        ],
    )
    for cls in ("accent", "danger", "warning")
]

# 포트 연결/해제/에러 버튼: 3테마 모두 disabled/pressed 규칙이 없어(항상 활성 상태로만
# 쓰임) normal/hover만 검사한다 - QSS에 없는 셀렉터를 검사 대상에 넣지 않는다.
BUTTON_STATE_FAMILIES: List[Tuple[str, List[Tuple[str, float]]]] = [
    (
        f'QPushButton[state="{state}"]',
        [
            ("", ACTIVE_MIN_RATIO),
            (":hover", ACTIVE_MIN_RATIO),
        ],
    )
    for state in ("connected", "disconnected", "error")
]

# 녹화(REC) 상태 버튼: `:checked`로만 존재(S-022).
RECORDING_FAMILY: Tuple[str, List[Tuple[str, float]]] = (
    'QPushButton[state="recording"]',
    [(":checked", ACTIVE_MIN_RATIO)],
)

# 의미색이 붙지 않은 **평범한** 위젯의 비활성 상태 (S-079).
# S-063은 accent/danger/warning만 훑어서, 정작 화면에 가장 많이 보이는 민짜 버튼·
# 입력창·콤보·탭의 비활성 색이 검사 밖에 있었다. 실측하니 dark 2.44 / light 2.29로
# 둘 다 기준 미달이었다 — 매크로 표의 "전송" 버튼이 실행 중에 거의 안 보였다.
PLAIN_DISABLED_FAMILIES: List[Tuple[str, List[Tuple[str, float]]]] = [
    (selector, [(":disabled", DISABLED_MIN_RATIO)])
    for selector in ("QPushButton", "QComboBox", "QLineEdit", "QTabBar::tab")
]

# 상태바 포트 상태 점(●/○) 라벨: 배경이 없으므로 QStatusBar 배경과 짝짓는다.
LABEL_STATE_SELECTORS: List[Tuple[str, float]] = [
    ('QLabel[state="connected"]', ACTIVE_MIN_RATIO),
    ('QLabel[state="disconnected"]', ACTIVE_MIN_RATIO),
]


def _iter_theme_files():
    for name in THEME_FILES:
        yield name, THEMES_DIR / name


def _check_families(families: List[Tuple[str, List[Tuple[str, float]]]]) -> List[str]:
    """families에 정의된 모든 (테마 x 셀렉터 x 상태) 조합의 대비를 검사해 위반 목록을 반환한다."""
    failures: List[str] = []
    for theme_name, path in _iter_theme_files():
        rules = _parse_qss(path)
        for base_selector, pseudo_specs in families:
            for pseudo, min_ratio in pseudo_specs:
                bg, color = _resolve_bg_color(rules, base_selector, pseudo)
                if not bg or not color or not _HEX_RE.match(bg) or not _HEX_RE.match(color):
                    failures.append(
                        f"{theme_name} {base_selector}{pseudo}: 색 파싱 실패 (bg={bg}, color={color})"
                    )
                    continue
                ratio = _contrast_ratio(bg, color)
                if ratio < min_ratio:
                    failures.append(
                        f"{theme_name} {base_selector}{pseudo}: {color} on {bg} = {ratio:.2f} "
                        f"(기준 {min_ratio}, 상태={pseudo or 'normal'})"
                    )
    return failures


def test_plain_widget_disabled_contrast():
    """
    의미색이 없는 평범한 위젯의 비활성 글자도 읽을 수 있어야 한다 (S-079 고정).

    Logic:
        - 4테마 x 4셀렉터(버튼/콤보/입력/탭)의 `:disabled` 조합을 검사한다.
        - 기준은 의미색 버튼과 같은 3.0:1 — 비활성이라고 안 보여도 되는 것은 아니다.
          "지금은 못 누른다"와 "무엇을 못 누르는지 모르겠다"는 다르다.
    """
    failures = _check_families(PLAIN_DISABLED_FAMILIES)
    assert not failures, (
        "평범한 위젯의 비활성 대비 미달 - 테마/셀렉터/상태/실측값:\n"
        + "\n".join(failures)
    )


def test_semantic_button_class_contrast():
    """
    accent/danger/warning 버튼의 배경/글자 대비가 상태별 기준을 만족해야 한다(S-063 고정).

    Logic:
        - 4테마 x 3클래스 x 4상태(normal/hover/pressed/disabled) = 48개 조합 전수 검사.
    """
    failures = _check_families(BUTTON_CLASS_FAMILIES)
    assert not failures, (
        "QSS 의미색 버튼(accent/danger/warning) 대비 미달 - 테마/셀렉터/상태/실측값:\n"
        + "\n".join(failures)
    )


def test_port_state_button_contrast():
    """
    포트 상태 버튼(state=connected/disconnected/error/recording)의 대비가 기준을 만족해야 한다(S-065).

    Logic:
        - S-063 수행자가 범위 밖으로 보고한 항목 - 의미색 버튼과 같은 원색을 재사용해
          동일한 대비 문제를 가질 가능성이 있어 별도로 고정한다.
    """
    failures = _check_families(BUTTON_STATE_FAMILIES + [RECORDING_FAMILY])
    assert not failures, (
        "QSS 포트 상태 버튼(state=connected/disconnected/error/recording) 대비 미달 - "
        "테마/셀렉터/상태/실측값:\n" + "\n".join(failures)
    )


def test_port_status_label_contrast():
    """
    상태바 포트 상태 라벨(QLabel[state=...])의 대비가 QStatusBar 배경 기준으로 충족해야 한다.

    Logic:
        - QLabel은 배경을 스스로 선언하지 않으므로 실제로 얹히는 QStatusBar 배경과
          짝지어야 한다(view/sections/main_status_bar.py의 port_status_lbl 배치 확인됨).
    """
    failures: List[str] = []
    for theme_name, path in _iter_theme_files():
        rules = _parse_qss(path)
        status_bar_bg = rules.get("QStatusBar", {}).get("background-color")
        for selector, min_ratio in LABEL_STATE_SELECTORS:
            color = rules.get(selector, {}).get("color")
            if not status_bar_bg or not color or not _HEX_RE.match(status_bar_bg) or not _HEX_RE.match(color):
                failures.append(
                    f"{theme_name} {selector}: 색 파싱 실패 (bg={status_bar_bg}, color={color})"
                )
                continue
            ratio = _contrast_ratio(status_bar_bg, color)
            if ratio < min_ratio:
                failures.append(
                    f"{theme_name} {selector}: {color} on QStatusBar {status_bar_bg} = {ratio:.2f} "
                    f"(기준 {min_ratio})"
                )
    assert not failures, (
        "QSS 포트 상태 라벨(QLabel[state=...]) 대비 미달 - 테마/셀렉터/실측값:\n"
        + "\n".join(failures)
    )
