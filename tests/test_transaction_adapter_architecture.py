"""Transaction adapter layer architecture policy tests."""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSACTION_ROOT = PROJECT_ROOT / "core" / "transport" / "transaction"
VENDOR_IMPORT_PREFIXES = (
    "pyftdi",
    "usb",
    "hid",
    "ch347",
    "mcp2210",
)


def test_vendor_libraries_do_not_leak_into_transaction_contract_modules():
    """#11 contract 단계에서 vendor dependency를 Core contract로 고정하지 않는다."""
    violations: list[str] = []

    for path in TRANSACTION_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module_name = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(VENDOR_IMPORT_PREFIXES):
                        violations.append(f"{path.name}:{node.lineno}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name.startswith(VENDOR_IMPORT_PREFIXES):
                    violations.append(f"{path.name}:{node.lineno}:{module_name}")

    assert not violations, f"vendor imports leaked into transaction contracts: {violations}"
