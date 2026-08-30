"""Transaction adapter layer architecture policy tests."""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSACTION_ROOT = PROJECT_ROOT / "core" / "transport" / "transaction"
BACKEND_ROOT = TRANSACTION_ROOT / "backends"
PRODUCTION_ROOTS = (
    PROJECT_ROOT / "common",
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "model",
    PROJECT_ROOT / "presenter",
    PROJECT_ROOT / "view",
)
VENDOR_IMPORT_PREFIXES = (
    "pyftdi",
    "usb",
    "hid",
    "ch347",
    "mcp2210",
)


def _vendor_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(VENDOR_IMPORT_PREFIXES):
                    found.append(f"{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name.startswith(VENDOR_IMPORT_PREFIXES):
                found.append(f"{node.lineno}:{module_name}")
    return found


def test_vendor_libraries_are_allowed_only_inside_backend_implementations():
    """Vendor dependency는 `transaction/backends/` 밖으로 누출되지 않는다."""
    violations: list[str] = []

    for root in PRODUCTION_ROOTS:
        for path in root.rglob("*.py"):
            if path.is_relative_to(BACKEND_ROOT):
                continue
            for detail in _vendor_imports(path):
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT).as_posix()}:{detail}"
                )

    assert not violations, f"vendor imports leaked outside backend package: {violations}"


def test_pyftdi_backend_is_lazy_imported():
    """Backend module import만으로 PyFtdi가 필수 dependency가 되지 않게 고정한다."""
    path = BACKEND_ROOT / "pyftdi_backend.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    vendor_import_function_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            names = [node.module or ""]
        if not any(name.startswith("pyftdi") for name in names):
            continue

        parent_function = None
        for candidate in ast.walk(tree):
            if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(child is node for child in ast.walk(candidate)):
                    parent_function = candidate.name
                    break
        if parent_function:
            vendor_import_function_names.add(parent_function)
        else:
            vendor_import_function_names.add("<module>")

    assert vendor_import_function_names == {"_load_pyftdi_api"}
