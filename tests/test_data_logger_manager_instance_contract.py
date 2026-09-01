"""DataLoggerManager instance ownership architecture contract.

## WHY
`core/data_logger.py`는 module-level 전역 인스턴스(`data_logger_manager`)를 두고
Model/Presenter가 각자 import했다. 그러면 import하는 위치가 곧 hidden global
dependency가 된다 — 소유자가 없고, 교체할 수 없고, 같은 프로세스의 테스트들이
상태를 공유해 실행 순서에 의존한다. P2-C #6이 `SettingsManager`에서 없앤 것과
정확히 같은 형태다.

현재는 composition root가 한 번 생성해 `TrafficMonitor` / `LoggingCoordinator` /
`ShutdownCoordinator`에 주입한다.

## HOW
- `core/data_logger.py` AST에 module-level `DataLoggerManager()` 대입이 없어야 한다
- production source에서 direct constructor call은 composition root만 허용한다
- production source가 module-level 전역 이름을 import하지 않아야 한다
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_LOGGER_PATH = PROJECT_ROOT / "core" / "data_logger.py"
COMPOSITION_ROOT = PROJECT_ROOT / "application_bootstrap.py"
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "common",
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "model",
    PROJECT_ROOT / "presenter",
    PROJECT_ROOT / "view",
)
ROOT_PRODUCTION_FILES = (
    PROJECT_ROOT / "main.py",
    COMPOSITION_ROOT,
)


def _iter_production_python_files():
    for root_file in ROOT_PRODUCTION_FILES:
        if root_file.exists():
            yield root_file
    for root in PRODUCTION_ROOTS:
        if root.exists():
            yield from root.rglob("*.py")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_data_logger_module_defines_no_global_instance():
    """모듈이 전역 인스턴스를 만들어 두면 import만으로 숨은 의존이 생긴다."""
    tree = _parse(DATA_LOGGER_PATH)

    offenders = [
        node.lineno
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "DataLoggerManager"
    ]

    assert not offenders, (
        f"core/data_logger.py:{offenders}에 module-level DataLoggerManager 인스턴스가 있다. "
        f"생성은 composition root 한 곳에서만 한다."
    )


def test_only_composition_root_constructs_the_manager():
    """production에서 직접 생성하는 곳이 늘어나면 소유자가 다시 흐려진다."""
    offenders: list[str] = []

    for path in _iter_production_python_files():
        if path == COMPOSITION_ROOT:
            continue
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DataLoggerManager"
            ):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert not offenders, (
        f"composition root 밖에서 DataLoggerManager를 생성한다: {offenders}. "
        f"생성자 주입으로 전달하라."
    )


def test_production_does_not_import_a_module_level_instance():
    """`from core.data_logger import data_logger_manager` 형태의 재도입을 막는다."""
    offenders: list[str] = []

    for path in _iter_production_python_files():
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "core.data_logger":
                continue
            for imported in node.names:
                if imported.name == "data_logger_manager":
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                    )

    assert not offenders, (
        f"전역 인스턴스를 import한다: {offenders}. "
        f"클래스를 import하고 인스턴스는 주입받아라."
    )
