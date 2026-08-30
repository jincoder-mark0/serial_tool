"""
PortPresenter의 Qt sender() 의존 재도입 방지 테스트.

## WHY
* disconnect_requested는 인자가 없는 Qt signal이라 과거에는 handle_close_request()가
  QObject.sender()를 호출해 어떤 PortPanel에서 온 요청인지 런타임에 추론했다.
* sender()는 signal 호출 문맥에 숨은 상태라 직접 슬롯 호출, 테스트, 배선 변경에 취약하다.
* 현재는 signal 연결 시 PortPanel을 명시적으로 캡처하고 PortConfig를 슬롯 인자로 전달한다.

## WHAT
* presenter/port_presenter.py에서 self.sender() 호출을 금지한다.
* handle_close_request()가 PortConfig 인자를 명시적으로 받는지 확인한다.
"""
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT_PRESENTER = PROJECT_ROOT / "presenter" / "port_presenter.py"


def _load_tree() -> ast.Module:
    return ast.parse(PORT_PRESENTER.read_text(encoding="utf-8"), filename=str(PORT_PRESENTER))


def test_port_presenter_does_not_use_qobject_sender():
    """PortPresenter는 QObject.sender()로 요청 출처를 추론하지 않는다."""
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

    assert not violations, (
        "PortPresenter에서 self.sender() 호출이 발견됐다. "
        "signal 연결 시 필요한 컨텍스트를 명시적으로 전달해야 한다: "
        + ", ".join(map(str, violations))
    )


def test_handle_close_request_requires_explicit_config_argument():
    """연결 해제 슬롯은 닫을 대상을 PortConfig 인자로 명시적으로 받아야 한다."""
    tree = _load_tree()
    presenter = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PortPresenter"
    )
    method = next(
        node for node in presenter.body
        if isinstance(node, ast.FunctionDef) and node.name == "handle_close_request"
    )

    arg_names = [arg.arg for arg in method.args.args]
    assert arg_names == ["self", "config"], (
        "handle_close_request()는 (self, config) 계약을 유지해야 한다. "
        f"현재 인자: {arg_names}"
    )
