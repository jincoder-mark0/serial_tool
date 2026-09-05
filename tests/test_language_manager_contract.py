"""LanguageManager 소유·설정 계약 테스트.

## WHY
`LanguageManager`는 `ThemeManager`/`ColorManager`와 **다른 결론**에 도달했다.
그 둘은 생성자 주입으로 바꿨지만 이것은 전역 인스턴스를 유지한다.

근거는 두 가지다.

1. **그 둘을 정당화한 결함이 여기엔 없다.** `ColorManager`는 주입한 ResourcePath가
   `config_path`에 반영되지 않았고 import만으로 파일을 읽었다. `LanguageManager`는
   `configure()`가 실제로 다시 로드하고, `resource_path` 없이 만들면 읽지 않는다.
2. **"현재 언어"는 앱 전체에 하나뿐인 값이다.** 텍스트 조회는 452곳의 위젯 내부
   `retranslate_ui()`에서 일어나고 17곳이 `language_changed`를 구독한다. 주입으로
   바꾸면 위젯 트리 전체(약 25개 클래스)에 인자를 관통시켜야 하는데 고쳐지는 결함이
   없다. 이 프로젝트는 같은 성격의 값을 이미 전역으로 인정했다(S-050 `theme_state`).

## 무엇을 지키는가
전역을 유지하기로 한 대신 **그 전역이 실제로 하나인지**를 고정한다.

`__new__` singleton을 없앴으므로 이제 `LanguageManager(resource_path)`를 부르면
**진짜로 다른 객체**가 만들어진다. 그 객체를 설정해도 위젯들이 구독한 전역은 그대로라,
언어를 바꿔도 화면이 갱신되지 않는다 — 예외도 로그도 없이 UI만 안 바뀐다.
과거 `__new__`가 가려주던 실수가 이제는 진짜 버그가 되므로 여기서 막는다.

## HOW
AST로 production source를 읽는다.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = PROJECT_ROOT / "view" / "managers" / "language_manager.py"
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "common",
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "model",
    PROJECT_ROOT / "presenter",
    PROJECT_ROOT / "view",
)
ROOT_FILES = (PROJECT_ROOT / "main.py", PROJECT_ROOT / "application_bootstrap.py")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_production_files():
    for path in ROOT_FILES:
        if path.exists():
            yield path
    for root in PRODUCTION_ROOTS:
        if root.exists():
            yield from root.rglob("*.py")


def test_class_singleton_machinery_is_gone():
    """
    `__new__` singleton은 "생성처럼 보이는 설정"을 만든다.

    `main.py`의 `LanguageManager(resource_path)`가 새 객체를 만드는 것처럼 보이면서
    실제로는 전역을 설정하고 있었다. 읽는 사람이 속는다.
    """
    tree = _parse(MANAGER_PATH)
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LanguageManager"
    )

    offenders = []
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__new__":
            offenders.append("__new__")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("_instance", "_initialized"):
                    offenders.append(target.id)

    assert not offenders, (
        f"LanguageManager에 class singleton 기제가 있다: {offenders}. "
        f"설정은 `configure()`로 드러나게 한다."
    )


def test_production_never_constructs_a_second_instance():
    """
    새 인스턴스를 만들면 **조용히** 고장난다.

    위젯 452곳이 모듈 전역을 직접 조회하고 17곳이 그 전역의 `language_changed`를
    구독한다. 다른 인스턴스를 설정하면 예외도 로그도 없이 UI만 갱신되지 않는다.
    """
    offenders: list[str] = []

    for path in _iter_production_files():
        if path == MANAGER_PATH:
            continue  # 모듈 자신이 전역 하나를 만든다
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "LanguageManager"
            ):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert not offenders, (
        f"production이 별도 LanguageManager를 생성한다: {offenders}. "
        f"전역을 `language_manager.configure(resource_path)`로 설정하라 — "
        f"다른 객체를 설정하면 언어를 바꿔도 화면이 갱신되지 않는다."
    )


def test_module_defines_exactly_one_global_instance():
    """전역이 둘이면 어느 것을 구독했는지에 따라 갱신 여부가 갈린다."""
    tree = _parse(MANAGER_PATH)

    globals_created = [
        node.lineno
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "LanguageManager"
    ]

    assert len(globals_created) == 1, (
        f"모듈이 전역 인스턴스를 {len(globals_created)}개 만든다 (line {globals_created}). "
        f"정확히 하나여야 한다."
    )


def test_configure_actually_reloads_resources(tmp_path):
    """
    `configure()`가 실제로 다시 로드해야 한다.

    이 동작이 `ColorManager`와의 차이다 — 거기서는 재설정이 경로만 갈아끼우고
    실제 로드를 하지 않아 주입이 무력화됐다. 여기서 같은 결함이 생기면
    "전역을 유지해도 된다"는 판단의 근거가 무너진다.
    """
    import json

    from core.resource_path import ResourcePath
    from view.managers.language_manager import LanguageManager

    languages = ResourcePath(tmp_path).languages_dir
    languages.mkdir(parents=True, exist_ok=True)
    (languages / "en.json").write_text(
        json.dumps({"_meta_lang_name": "English", "probe_key": "PROBE"}),
        encoding="utf-8",
    )

    manager = LanguageManager()
    assert manager.resources == {}, "경로 없이 만들었는데 파일을 읽었다"

    manager.configure(ResourcePath(tmp_path))

    assert manager.get_text("probe_key") == "PROBE", (
        "configure()가 언어 파일을 로드하지 않았다 — 설정이 무력화된다."
    )


def test_import_alone_does_not_read_language_files():
    """
    import만으로 파일을 읽으면 안 된다.

    `ColorManager`가 그랬고, PyInstaller 빌드 분석 단계에서까지 파일을 읽었다.
    전역을 유지하는 대신 이 성질은 지켜야 한다.
    """
    from view.managers.language_manager import LanguageManager

    bare = LanguageManager()

    assert bare.resources == {}, (
        "ResourcePath 없이 만든 인스턴스가 언어 파일을 읽었다 — "
        "import만으로 파일 I/O가 일어나게 된다."
    )
