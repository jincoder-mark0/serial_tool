"""PortPresenter의 명시적 context 전달과 비침범 signal 연결 계약."""
import ast
import inspect
from pathlib import Path

from presenter.port_presenter import PortPresenter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT_PRESENTER = PROJECT_ROOT / "presenter" / "port_presenter.py"


def _load_tree() -> ast.Module:
    return ast.parse(
        PORT_PRESENTER.read_text(encoding="utf-8"),
        filename=str(PORT_PRESENTER),
    )


def test_port_presenter_does_not_use_qobject_sender():
    tree = _load_tree()
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "sender"
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
        ):
            violations.append(node.lineno)

    assert not violations


def test_handle_close_request_requires_explicit_config_argument():
    tree = _load_tree()
    presenter = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PortPresenter"
    )
    method = next(
        node for node in presenter.body
        if isinstance(node, ast.FunctionDef) and node.name == "handle_close_request"
    )

    assert [arg.arg for arg in method.args.args] == ["self", "config"]


def test_tab_signal_wiring_does_not_disconnect_other_subscribers():
    source = inspect.getsource(PortPresenter._connect_tab_signals)

    assert ".disconnect(" not in source
    assert "panel in self._connected_panels" in source
    assert "self._connected_panels.add(panel)" in source
