"""
UI 가이드(.agent/rules/ui_guide.md) 기계적 강제 테스트 모듈 (S-031)

## WHY
* UI 가이드가 문서로만 있으면 어긴 코드가 조용히 늘어난다. 원자료(doc/ui-guidelines.md)의
  핵심 설계인 "테스트가 기계적으로 강제한다"를 SerialTool 구조에 맞춰 재현한다.

## WHAT
* `setStyleSheet()` 인자 안 색 리터럴 금지 검사 (색은 QSS 테마 전용).
* `setStyleSheet()` 인자 안 인라인 `font-size` 금지 검사 (크기 위계는 QSS 클래스 전용).
* `view/`·`presenter/` 문자열 리터럴(주석·docstring 제외)의 한글 하드코딩 금지 검사.
* `common.constants`의 LAYOUT_*/ICON_BUTTON_SIZE 상수 존재·값 검사(무단 삭제·변경 감지).

## HOW
* Qt를 실행하지 않는다 — `ast`/`tokenize`로 소스 텍스트만 정적 분석한다
  (전체 스캔 1초 미만 목표).
* 각 검사 상단의 허용 목록(ALLOWLIST, 파일 경로 → 사유)에 등재된 파일은 위반이어도
  실패시키지 않는다. 목표는 빈 목록 — 등재는 "수정이 큰 판단을 요구하는" 경우만.

pytest tests/test_ui_guidelines.py -v
"""
import io
import tokenize
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("view", "presenter")

# -----------------------------------------------------------------------------
# 허용 목록 (파일 경로 → 사유). 시작 시점 목표는 빈 dict.
# -----------------------------------------------------------------------------
COLOR_LITERAL_ALLOWLIST: Dict[str, str] = {}
FONT_SIZE_ALLOWLIST: Dict[str, str] = {}
KOREAN_LITERAL_ALLOWLIST: Dict[str, str] = {}


def _iter_source_files():
    """view/·presenter/ 아래 모든 .py 파일을 재귀 순회한다."""
    for sub_dir in SCAN_DIRS:
        base = PROJECT_ROOT / sub_dir
        for path in sorted(base.rglob("*.py")):
            yield path


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_style_sheet_args(source: str) -> List[Tuple[int, str]]:
    """
    소스 텍스트에서 `setStyleSheet(...)` 호출의 인자 텍스트와 시작 줄 번호를 추출한다.

    Logic:
        - "setStyleSheet(" 위치를 찾아 괄호 깊이를 세며 문자열 리터럴 내부의
          괄호에 흔들리지 않는 단순 상태 기계로 대응하는 ")"까지의 텍스트를 잘라낸다.
        - f-string/포맷 조합 등 복잡한 인자도 텍스트 그대로 검사 대상에 포함한다
          (정규식 매칭만 하므로 완전한 파싱은 필요 없음).

    Args:
        source (str): 파일 전체 텍스트.

    Returns:
        List[Tuple[int, str]]: (호출이 시작된 줄 번호, 괄호 안 인자 텍스트) 목록.
    """
    results: List[Tuple[int, str]] = []
    marker = "setStyleSheet("
    idx = 0
    while True:
        start = source.find(marker, idx)
        if start == -1:
            break
        arg_start = start + len(marker)
        depth = 1
        i = arg_start
        in_str = None
        while i < len(source) and depth > 0:
            ch = source[i]
            if in_str:
                if ch == "\\":
                    i += 1
                elif ch == in_str:
                    in_str = None
            else:
                if ch in ("'", '"'):
                    in_str = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            i += 1
        arg_text = source[arg_start:i - 1]
        line_no = source.count("\n", 0, start) + 1
        results.append((line_no, arg_text))
        idx = i
    return results


def test_no_color_literals_in_widget_code():
    """
    setStyleSheet() 인자 안에 색 리터럴(#hex, rgb(, color: <이름>)이 없어야 한다.

    Logic:
        - view/·presenter/ 전체를 스캔해 setStyleSheet 호출 인자만 검사한다.
        - 색은 3테마 QSS(resources/themes/*.qss)가 정한다 — 위젯 코드에 색 리터럴을
          직접 쓰면 다크/라이트 대비 계산이 깨져도 아무도 모르게 된다.
    """
    import re

    hex_re = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    rgb_re = re.compile(r"\brgb\s*\(")
    named_color_re = re.compile(r"\bcolor\s*:\s*[a-zA-Z]+")

    violations: List[str] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in COLOR_LITERAL_ALLOWLIST:
            continue
        source = path.read_text(encoding="utf-8")
        for line_no, arg_text in _extract_style_sheet_args(source):
            if hex_re.search(arg_text) or rgb_re.search(arg_text) or named_color_re.search(arg_text):
                violations.append(f"{rel}:{line_no}")

    assert not violations, (
        "setStyleSheet() 안에 색 리터럴 발견 (QSS 테마의 동적 속성 방식으로 이전할 것):\n"
        + "\n".join(violations)
    )


def test_no_inline_font_size():
    """
    setStyleSheet() 인자 안에 인라인 font-size가 없어야 한다.

    Logic:
        - 글자 크기 위계는 QSS 클래스(section-title, about-title 등)로만 정한다.
          페이지마다 인라인으로 크기를 지정하면 위계가 갈린다(ui_guide.md §3).
    """
    violations: List[str] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in FONT_SIZE_ALLOWLIST:
            continue
        source = path.read_text(encoding="utf-8")
        for line_no, arg_text in _extract_style_sheet_args(source):
            if "font-size" in arg_text:
                violations.append(f"{rel}:{line_no}")

    assert not violations, (
        "setStyleSheet() 안에 인라인 font-size 발견 (QSS 클래스로 이전할 것):\n"
        + "\n".join(violations)
    )


def _prev_significant(tokens, i):
    """i번째 토큰 이전의 COMMENT/NL을 건너뛴 첫 유의미 토큰을 반환한다."""
    j = i - 1
    while j >= 0:
        t = tokens[j]
        if t.type in (tokenize.COMMENT, tokenize.NL):
            j -= 1
            continue
        return t
    return None


def _next_significant(tokens, i):
    """i번째 토큰 이후의 COMMENT/NL을 건너뛴 첫 유의미 토큰을 반환한다."""
    j = i + 1
    while j < len(tokens):
        t = tokens[j]
        if t.type in (tokenize.COMMENT, tokenize.NL):
            j += 1
            continue
        return t
    return None


_DOCSTRING_PRECEDING_TYPES = (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING)


def _find_korean_string_tokens(path: Path) -> List[Tuple[int, str]]:
    """
    파일의 STRING(및 f-string 리터럴 부분) 토큰 중 한글이 포함된 것을 찾는다.
    주석(COMMENT 토큰)과 docstring(모듈/클래스/함수의 첫 statement로 홀로 선 문자열)은 제외한다.

    Logic:
        - tokenize 모듈로 토큰화 — COMMENT는 애초에 STRING과 다른 토큰 타입이라 자동 제외.
        - docstring은 "직전 유의미 토큰이 NEWLINE/INDENT/DEDENT/ENCODING이고 직후 유의미
          토큰이 NEWLINE"인 홀로 선 문자열 statement로 식별해 제외한다.
        - Python 3.12+는 f-string을 FSTRING_START/MIDDLE/END로 쪼개 토큰화하므로
          FSTRING_MIDDLE(리터럴 텍스트 부분)도 함께 검사한다(버전 호환을 위해 getattr).

    Args:
        path (Path): 검사할 .py 파일 경로.

    Returns:
        List[Tuple[int, str]]: (줄 번호, 위반 문자열 일부) 목록.
    """
    korean_re = __import__("re").compile(r"[가-힣]")
    source = path.read_text(encoding="utf-8")
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))

    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    violations: List[Tuple[int, str]] = []

    for i, tok in enumerate(tokens):
        if tok.type == tokenize.STRING:
            prev_sig = _prev_significant(tokens, i)
            next_sig = _next_significant(tokens, i)
            is_standalone = (
                (prev_sig is None or prev_sig.type in _DOCSTRING_PRECEDING_TYPES)
                and (next_sig is not None and next_sig.type == tokenize.NEWLINE)
            )
            if is_standalone:
                continue
            if korean_re.search(tok.string):
                violations.append((tok.start[0], tok.string[:60]))
        elif fstring_middle is not None and tok.type == fstring_middle:
            if korean_re.search(tok.string):
                violations.append((tok.start[0], tok.string[:60]))

    return violations


def test_no_hardcoded_korean_in_code():
    """
    view/·presenter/의 문자열 리터럴에 한글이 없어야 한다 (주석·docstring 제외).

    Logic:
        - 사용자에게 보이는 모든 문구는 language_manager.get_text(key) 경유여야 한다
          (ui_guide.md §5). 위젯 코드/Presenter 상태 메시지에 한글 리터럴이 남아있으면
          다국어 전환 시 그 부분만 한글로 고정된다.
        - tokenize STRING(+f-string 리터럴 부분) 토큰만 검사해 주석/docstring은 제외한다.
    """
    violations: List[str] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in KOREAN_LITERAL_ALLOWLIST:
            continue
        for line_no, snippet in _find_korean_string_tokens(path):
            violations.append(f"{rel}:{line_no}: {snippet!r}")

    assert not violations, (
        "view/presenter 문자열 리터럴에 한글 하드코딩 발견 (언어 키로 전환할 것):\n"
        + "\n".join(violations)
    )


def test_layout_constants_exist():
    """
    common.constants에 LAYOUT_* 8종 + ICON_BUTTON_SIZE가 존재하고 가이드 표의 값과 일치해야 한다.

    Logic:
        - ui_guide.md §2 표에 박제된 값과 상수 모듈을 대조해 무단 삭제·변경을 감지한다.
        - LAYOUT_SPACING_TITLE/LAYOUT_SPACING_GROUP은 S-035에서 신설(그룹 경계·제목 간격 정비).
    """
    from common import constants

    expected = {
        "LAYOUT_MARGIN_NONE": 0,
        "LAYOUT_MARGIN_DEFAULT": 5,
        "LAYOUT_MARGIN_DIALOG": 15,
        "LAYOUT_SPACING_TIGHT": 2,
        "LAYOUT_SPACING_DEFAULT": 5,
        "LAYOUT_SPACING_TITLE": 8,
        "LAYOUT_SPACING_GROUP": 10,
        "ICON_BUTTON_SIZE": 30,
    }

    missing = [name for name in expected if not hasattr(constants, name)]
    assert not missing, f"common.constants에 누락된 UI 레이아웃 상수: {missing}"

    mismatched = [
        f"{name} (기대={value}, 실제={getattr(constants, name)})"
        for name, value in expected.items()
        if getattr(constants, name) != value
    ]
    assert not mismatched, f"UI 가이드 표와 값이 다른 상수: {mismatched}"
