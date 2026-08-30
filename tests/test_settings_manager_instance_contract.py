"""SettingsManager instance ownership architecture contract.

WHY
- SettingsManager Singleton을 제거해도 production 각 모듈이 다시 ``SettingsManager()``를
  직접 생성하면 hidden global dependency가 다른 형태로 재발합니다.
- 설정 instance 생성 책임은 Composition Root 진입점인 ``main.py`` 하나에만 둡니다.
- test fixture가 과거 `_instance` attribute를 동적으로 붙여도 구현 source 판정이
  test order에 영향받지 않아야 합니다.

HOW
- ``core/settings_manager.py`` AST에서 Singleton field/``__new__`` 정의 금지
- production Python source에서 direct constructor call은 ``main.py``만 허용
- tests/conftest 포함 테스트 source에도 stale ``SettingsManager._instance`` /
  ``SettingsManager._initialized`` 접근을 허용하지 않음
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_MANAGER_PATH = PROJECT_ROOT / "core" / "settings_manager.py"
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "common",
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "model",
    PROJECT_ROOT / "presenter",
    PROJECT_ROOT / "view",
)
ROOT_PRODUCTION_FILES = (
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "application_bootstrap.py",
)


def _iter_production_python_files():
    for root_file in ROOT_PRODUCTION_FILES:
        if root_file.exists():
            yield root_file

    for root in PRODUCTION_ROOTS:
        if root.exists():
            yield from root.rglob("*.py")


def _settings_manager_constructor_lines(path: Path) -> list[int]:
    """해당 source에서 SettingsManager direct constructor call line을 반환한다."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = {"SettingsManager"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "core.settings_manager":
            for imported in node.names:
                if imported.name == "SettingsManager":
                    aliases.add(imported.asname or imported.name)

    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in aliases:
            lines.append(node.lineno)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "SettingsManager":
            lines.append(node.lineno)
    return sorted(lines)


def test_settings_manager_source_has_no_singleton_mechanism():
    """구현 source가 Singleton state/constructor override를 다시 갖지 않게 고정한다."""
    tree = ast.parse(
        SETTINGS_MANAGER_PATH.read_text(encoding="utf-8"),
        filename=str(SETTINGS_MANAGER_PATH),
    )
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SettingsManager"
    )

    method_names = {
        node.name
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    class_fields = {
        target.id
        for node in class_node.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }

    assert "__new__" not in method_names
    assert "_instance" not in class_fields
    assert "_initialized" not in class_fields


def test_only_main_creates_settings_manager_in_production():
    """Production에서 SettingsManager 생성 책임은 main.py 하나만 갖는다."""
    violations: list[str] = []
    main_calls: list[int] = []

    for path in _iter_production_python_files():
        calls = _settings_manager_constructor_lines(path)
        if not calls:
            continue

        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative == "main.py":
            main_calls.extend(calls)
        else:
            violations.extend(f"{relative}:{line}" for line in calls)

    assert main_calls, "main.py must own SettingsManager construction"
    assert not violations, (
        "SettingsManager direct construction must stay in main.py; inject the existing "
        f"instance instead: {violations}"
    )


def test_tests_do_not_reset_removed_settings_singleton_state():
    """Test code도 제거된 Singleton field를 다시 만드는 stale reset을 사용하지 않는다."""
    stale_refs: list[str] = []
    tests_root = PROJECT_ROOT / "tests"

    for path in tests_root.rglob("*.py"):
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "SettingsManager._instance" in line or "SettingsManager._initialized" in line:
                stale_refs.append(
                    f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line_no}"
                )

    assert not stale_refs, (
        "Removed SettingsManager Singleton state must not be recreated by tests: "
        f"{stale_refs}"
    )
