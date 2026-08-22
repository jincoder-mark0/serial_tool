"""
계층 의존 방향(CLAUDE.md) 기계적 강제 테스트 (S-056)

## WHY
* CLAUDE.md 절대 규칙: 의존 방향 `View -> Presenter -> Model -> Core <- Common`,
  역방향 import 금지. S-036 감사①에서는 이 불변식을 수작업으로 확인했다
  ("core/가 상위 계층을 import: 위반 0건"). 그런데 S-036 자체가 크래시 다이얼로그
  번역을 위해 `core/error_handler.py`에 `view.managers.language_manager` 지연
  import(try/except로 감싼 함수 내부 import)를 끌어들여 위반 1건을 만들었고,
  수작업 감사로는 이런 재발을 막지 못했다. S-056은 core/error_handler.py의 view
  의존을 콜백 주입 방식으로 제거하면서, 동시에 이 불변식을 기계적으로 고정한다.

## WHAT
* `common/`: core·model·presenter·view import 금지 (의존성 최하위).
* `core/`: model·presenter·view import 금지 (인프라는 공급자/화면을 모른다).
* `model/`: presenter·view import 금지 (Model은 View/위젯을 모른다).
* `view/`: model import 금지 (Passive View - Model 직접 접근 금지, Presenter가 중재).
  (presenter->view, presenter->model, view->core/common 은 허용된 정상 의존이라
  검사 대상이 아니다 - MVP에서 Presenter가 View/Model 양쪽을 중재하는 것은 정상이고,
  core/common은 인프라 유틸리티라 모든 상위 계층이 직접 사용 가능하다.)

## HOW
* `ast`로 각 레이어 디렉터리의 .py 파일을 파싱해, 함수/클래스 내부의 지연 import를
  포함한 모든 절대 import(레벨 0)의 최상위 패키지명만 추출한다(문자열 검색이 아니라
  AST 기반이라 "# from view import ..." 같은 주석은 오탐하지 않는다).
* 상대 import(`from . import x`, level > 0)는 같은 패키지 내부 참조이므로 제외한다.
"""
import ast
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 레이어별로 import하면 안 되는 상위/이복 레이어 집합.
# (허용되는 의존은 아예 검사하지 않는다 - 예: presenter->view, presenter->model,
#  view->core/common, model->core/common)
FORBIDDEN_IMPORTS: Dict[str, Set[str]] = {
    "common": {"core", "model", "presenter", "view"},
    "core": {"model", "presenter", "view"},
    "model": {"presenter", "view"},
    "view": {"model"},
}


def _iter_py_files(layer: str):
    """레이어 디렉터리 아래 모든 .py 파일을 재귀 순회한다."""
    base = PROJECT_ROOT / layer
    for path in sorted(base.rglob("*.py")):
        yield path


def _top_level_imports(path: Path) -> Set[str]:
    """
    파일 안의 절대 import(레벨 0, 함수/클래스 내부의 지연 import 포함)의
    최상위 패키지명 집합을 반환한다.

    Logic:
        - ast.walk로 전체 트리를 순회하므로 try/except로 감싼 지연 import,
          함수 내부 import도 모두 포착한다(S-056이 고친 위반이 바로 이런 형태였다).
        - `from . import x` 같은 상대 import(level > 0)는 같은 패키지 내부
          참조이므로 검사 대상에서 제외한다.

    Args:
        path (Path): 검사할 .py 파일 경로.

    Returns:
        Set[str]: import된 최상위 패키지명 집합 (예: {"core", "PyQt5"}).
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _find_violations(layer: str) -> List[str]:
    """layer 디렉터리 전체를 스캔해 FORBIDDEN_IMPORTS[layer]에 해당하는 import를 찾는다."""
    forbidden = FORBIDDEN_IMPORTS[layer]
    violations: List[str] = []
    for path in _iter_py_files(layer):
        hit = _top_level_imports(path) & forbidden
        if hit:
            violations.append(f"{_rel(path)}: imports {sorted(hit)}")
    return violations


def test_common_does_not_import_upper_layers():
    """common/은 의존성 최하위 - core/model/presenter/view 어느 것도 import하지 않는다."""
    violations = _find_violations("common")
    assert not violations, (
        "common/에서 상위 계층 import 발견 (의존성 최하위 위반):\n" + "\n".join(violations)
    )


def test_core_does_not_import_upper_layers():
    """
    core/는 공급자(구체 구현)와 화면을 모른다 - model/presenter/view를 import하지 않는다.

    S-056: core/error_handler.py가 `_show_error_dialog` 안에서
    `view.managers.language_manager`를 지연 import하던 위반(S-036이 도입, 감사①이
    수동 발견)을 이 테스트가 기계적으로 고정한다.
    """
    violations = _find_violations("core")
    assert not violations, (
        "core/에서 상위 계층(model/presenter/view) import 발견:\n" + "\n".join(violations)
    )


def test_model_does_not_import_presenter_or_view():
    """Model은 View/위젯을 모른다 - UI 갱신은 Presenter가 중재한다."""
    violations = _find_violations("model")
    assert not violations, (
        "model/에서 presenter/view import 발견:\n" + "\n".join(violations)
    )


def test_view_does_not_import_model():
    """View는 Model을 import하지 않는다 (Passive View - 시그널 emit + 인터페이스 메서드만)."""
    violations = _find_violations("view")
    assert not violations, (
        "view/에서 model import 발견 (Presenter를 거치지 않은 직접 접근):\n" + "\n".join(violations)
    )
