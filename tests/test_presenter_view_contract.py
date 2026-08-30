"""Presenter -> View facade 호출 계약 정적 검사."""
import ast
import pathlib

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PRESENTER_DIR = PROJECT_ROOT / "presenter"
VIEW_TYPE_NAMES = {
    "MainWindow",
    "MainLeftSection",
    "ManualControlPanel",
    "PacketPanel",
    "MacroPanel",
}


def _build_view_instances():
    from view.main_window import MainWindow
    from view.panels.macro_panel import MacroPanel
    from view.panels.manual_control_panel import ManualControlPanel
    from view.panels.packet_panel import PacketPanel
    from view.sections.main_left_section import MainLeftSection

    return {
        "MainWindow": MainWindow(),
        "MainLeftSection": MainLeftSection(),
        "ManualControlPanel": ManualControlPanel(),
        "PacketPanel": PacketPanel(),
        "MacroPanel": MacroPanel(),
    }


def _annotation_name(node) -> str:
    return node.id if isinstance(node, ast.Name) else ""


def _collect_view_attrs(tree: ast.Module) -> dict:
    """`self.attr = <View 주석 파라미터>`를 {attr: ViewClass}로 수집합니다."""
    result = {}
    for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        init = next(
            (
                node
                for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name == "__init__"
            ),
            None,
        )
        if init is None:
            continue

        view_params = {}
        for arg in list(init.args.args) + list(init.args.kwonlyargs):
            name = _annotation_name(arg.annotation) if arg.annotation else ""
            if name in VIEW_TYPE_NAMES:
                view_params[arg.arg] = name

        for node in ast.walk(init):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
                continue
            if node.value.id not in view_params:
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    result[target.attr] = view_params[node.value.id]
    return result


def _attribute_chain(node: ast.Attribute):
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name) and current.id == "self":
        return list(reversed(parts))
    return None


def _touches_view_attr(node: ast.Attribute, view_attrs: dict) -> bool:
    current = node
    while isinstance(current, (ast.Attribute, ast.Call)):
        current = current.func if isinstance(current, ast.Call) else current.value
        if (
            isinstance(current, ast.Attribute)
            and isinstance(current.value, ast.Name)
            and current.value.id == "self"
        ):
            return current.attr in view_attrs
    return False


@pytest.fixture(scope="module")
def view_instances(qapp):
    return _build_view_instances()


def test_presenters_only_call_methods_that_exist_on_the_view(view_instances):
    """추적 가능한 모든 Presenter -> View 접근이 실제 View 계약에 존재해야 합니다."""
    problems = []
    checked = 0
    skipped = 0
    tracked_files = set()

    for path in sorted(PRESENTER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        view_attrs = _collect_view_attrs(tree)
        if not view_attrs:
            continue
        tracked_files.add(path.name)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            chain = _attribute_chain(node)
            if chain is None:
                if _touches_view_attr(node, view_attrs):
                    skipped += 1
                continue
            if len(chain) < 2:
                continue

            root, rest = chain[0], chain[1:]
            if root not in view_attrs:
                continue
            checked += 1

            obj = view_instances[view_attrs[root]]
            walked = [f"self.{root}"]
            for name in rest:
                if not hasattr(obj, name):
                    problems.append(
                        f"{path.name}:{node.lineno}: {'.'.join(walked)}.{name} — "
                        f"{type(obj).__name__}에 '{name}'이(가) 없다"
                    )
                    break
                obj = getattr(obj, name)
                walked.append(name)

    assert not problems, (
        "Presenter가 View에 없는 속성/메서드를 호출한다:\n  "
        + "\n  ".join(sorted(set(problems)))
        + f"\n\n검사 {checked}건 / 반환 타입 미확정 접근 {skipped}건"
    )

    # 호출 개수는 리팩토링이 잘 될수록 감소할 수 있다. 대신 핵심 Presenter가 추적
    # 대상에서 사라지지 않았는지를 고정해 검사 로직 자체가 무력화되는 것을 막는다.
    expected_tracked = {
        "main_presenter.py",
        "port_presenter.py",
        "manual_control_presenter.py",
        "packet_presenter.py",
        "macro_presenter.py",
    }
    assert expected_tracked <= tracked_files
    assert checked > 0


def test_port_presenter_uses_left_section_facades_for_tab_collection():
    path = PRESENTER_DIR / "port_presenter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []
    forbidden_methods = {"get_port_tabs_count", "get_port_panel_at"}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _attribute_chain(node)
        if not chain or len(chain) < 2 or chain[0] != "left_section":
            continue
        if chain[1] == "port_tab_panel" or chain[1] in forbidden_methods:
            violations.append(f"{path.name}:{node.lineno}: self.{'.'.join(chain)}")

    assert not violations, (
        "PortPresenter가 MainLeftSection의 탭 내부 구조/인덱스 순회에 직접 의존한다:\n  "
        + "\n  ".join(violations)
    )


def test_port_presenter_does_not_cache_current_port_panel():
    path = PRESENTER_DIR / "port_presenter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain = _attribute_chain(node)
            if chain and chain[0] == "current_port_panel":
                violations.append(f"{path.name}:{node.lineno}: self.{'.'.join(chain)}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "update_current_port_panel":
                violations.append(f"{path.name}:{node.lineno}: def {node.name}()")

    assert not violations, (
        "PortPresenter가 현재 PortPanel View 참조를 상태로 캐시한다:\n  "
        + "\n  ".join(violations)
    )
