"""ThemeManager / ColorManager instance ownership architecture contract.

## WHY
두 매니저는 `__new__` 기반 class singleton + module-level 전역 인스턴스였다.
`SettingsManager`(P2-C #6)·`DataLoggerManager`와 같은 형태이고, 같은 문제를 만들었다.

1. **주입한 ResourcePath가 적용되지 않았다.** import 시점에 이미 초기화가 끝나 있어
   `main.py`의 `ColorManager(resource_path)`는 `_initialized` 가드에 막혀
   `_resource_path`만 갈아끼우고 `config_path`는 재계산하지 않았다. 색 규칙은 언제나
   import 시점의 기본 경로에서 로드됐다.
2. **import만으로 파일 I/O가 일어났다.** 모듈을 읽는 것만으로 `color_rules.json`을
   읽었고, PyInstaller 분석 단계에서도 그 로그가 찍혔다.
3. **테스트가 상태를 공유했다.** `tests/conftest.py`의 autouse fixture가 매 테스트마다
   전역 상태를 snapshot/restore해야 했다(S-048). 이 파일은 그 fixture를 대체한다 —
   복원이 아니라 **애초에 공유하지 않는 것**이 격리다.

## WHAT
* class singleton 기제(`__new__` / `_instance`)가 없는가
* module-level 전역 인스턴스가 없는가
* production에서 직접 생성하는 곳이 composition root(`main.py`)뿐인가
* 두 번 만들면 실제로 **다른 인스턴스**인가 (격리의 실질)
* `ThemeManager`가 `ColorManager`를 직접 부르지 않는가 (전역이 전역을 부르던 구조)

## HOW
AST로 source를 읽는다 — import 부작용 없이 판정하기 위해서다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_ROOT = PROJECT_ROOT / "main.py"
MANAGERS = {
    "ThemeManager": PROJECT_ROOT / "view" / "managers" / "theme_manager.py",
    "ColorManager": PROJECT_ROOT / "view" / "managers" / "color_manager.py",
}
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "common",
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "model",
    PROJECT_ROOT / "presenter",
    PROJECT_ROOT / "view",
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_production_files():
    for root_file in (COMPOSITION_ROOT, PROJECT_ROOT / "application_bootstrap.py"):
        if root_file.exists():
            yield root_file
    for root in PRODUCTION_ROOTS:
        if root.exists():
            yield from root.rglob("*.py")


@pytest.mark.parametrize("class_name", sorted(MANAGERS))
def test_manager_has_no_class_singleton_machinery(class_name):
    """`__new__`/`_instance`로 인스턴스를 하나로 묶으면 주입이 무력화된다."""
    tree = _parse(MANAGERS[class_name])
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
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
        f"{class_name}에 class singleton 기제가 있다: {offenders}. "
        f"주입한 ResourcePath가 초기화 가드에 막혀 무시되는 결함이 여기서 나왔다."
    )


@pytest.mark.parametrize("class_name", sorted(MANAGERS))
def test_module_defines_no_global_instance(class_name):
    """모듈이 전역 인스턴스를 만들면 import만으로 파일 I/O가 일어난다."""
    tree = _parse(MANAGERS[class_name])

    offenders = [
        node.lineno
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == class_name
    ]

    assert not offenders, (
        f"{MANAGERS[class_name].name}:{offenders}에 module-level {class_name} 인스턴스가 있다. "
        f"import만으로 설정 파일을 읽게 되고, 소비자는 그 전역을 직접 import하게 된다."
    )


@pytest.mark.parametrize("class_name", sorted(MANAGERS))
def test_only_composition_root_constructs_the_manager(class_name):
    """production에서 직접 생성하는 곳이 늘어나면 소유자가 흐려진다."""
    offenders: list[str] = []

    for path in _iter_production_files():
        if path == COMPOSITION_ROOT:
            continue
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == class_name
            ):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert not offenders, (
        f"composition root 밖에서 {class_name}을 생성한다: {offenders}. "
        f"생성자 주입으로 전달하라."
    )


@pytest.mark.parametrize("class_name", sorted(MANAGERS))
def test_two_constructions_are_independent_instances(class_name, qapp):
    """
    격리의 실질은 복원이 아니라 **공유하지 않는 것**이다.

    과거에는 두 번 만들어도 같은 객체였고, 그래서 테스트마다 상태를 되돌리는
    autouse fixture가 필요했다(S-048).
    """
    import importlib

    module = importlib.import_module(
        f"view.managers.{'theme_manager' if class_name == 'ThemeManager' else 'color_manager'}"
    )
    factory = getattr(module, class_name)

    first, second = factory(), factory()

    assert first is not second, (
        f"{class_name}을 두 번 만들었는데 같은 객체다 — class singleton이 남아 있다."
    )


def test_theme_manager_does_not_call_color_manager():
    """
    전역이 전역을 부르던 구조를 되살리지 않는다.

    `ThemeManager.apply_theme()`가 전역 `color_manager`를 직접 불렀다. 어느 쪽도
    교체할 수 없게 만드는 결합이었고, `MainWindow.switch_theme`은 이미 두 매니저에
    각각 적용하고 있어 그 호출은 중복이기도 했다. 팔레트 전파는 두 매니저를 모두
    아는 쪽(composition root / MainWindow)이 한다.
    """
    tree = _parse(MANAGERS["ThemeManager"])

    # 주석·docstring은 이 결합의 **이유**를 설명하므로 텍스트 검색으로 판정하면 안 된다.
    # 실제 import와 코드 참조만 본다.
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "view.managers.color_manager":
            offenders.append(f"import at line {node.lineno}")
        if isinstance(node, ast.Name) and node.id == "color_manager":
            offenders.append(f"reference at line {node.lineno}")

    assert not offenders, (
        f"ThemeManager가 다시 ColorManager를 참조한다: {offenders} — 전파는 상위가 한다."
    )
