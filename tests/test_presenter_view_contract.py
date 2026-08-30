"""
Presenter → View 호출 계약 정적 검사 (S-070)

## WHY
Presenter 테스트는 View를 `MagicMock()`으로 대신하는데, `spec`이 없으면 **존재하지
않는 메서드를 불러도 조용히 통과**한다. 실제로 그 틈으로 결함이 새어 나갔다 —
`ManualControlPresenter.set_enabled()`가 패널에 없는 `panel.set_enabled()`를 부르고
있었고(실제 이름은 `set_controls_enabled`), 393개 테스트가 전부 초록인 동안 앱은
포트 탭을 바꿀 때마다 AttributeError로 죽었다(S-067).

Mock에 `spec`을 붙이면 **테스트가 실제로 지나가는 경로**는 막을 수 있다. 그런데
Presenter의 View 호출은 대부분 테스트가 닿지 않는다. 그래서 이 파일은 **소스를
정적으로 훑어** 모든 호출을 확인한다.

## WHAT
각 `presenter/*.py`에서 `__init__` 파라미터 중 View 타입으로 주석된 것을 찾고,
`self.<이름> = <파라미터>` 대입을 추적한 뒤, 모듈 전체에서 그 속성으로 시작하는
접근 체인(`self.panel.foo`, `self.view.left_section.bar`)이 **실제 View 객체에
존재하는지** 확인한다.

또한 `PortPresenter`는 `MainLeftSection`의 공개 facade까지만 사용하고,
`left_section.port_tab_panel`처럼 하위 위젯 구현으로 직접 내려가거나 탭 개수와
인덱스를 직접 순회하지 않는 것을 별도 계약으로 고정한다.

## HOW
클래스만 봐서는 부족하다 — `left_section` 같은 속성은 `__init__`에서 만들어져
클래스에는 없다. 그래서 실제 인스턴스를 하나 만들어 체인을 `getattr`로 따라간다.

메서드 호출 결과에 이어지는 접근(`self.view.get_panel_at(0).foo`)은 반환 타입을
알 수 없어 검사하지 않는다 — 검사할 수 없는 것을 통과로 위장하지 않기 위해,
건너뛴 개수를 테스트가 함께 보고한다.
"""
import ast
import pathlib

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PRESENTER_DIR = PROJECT_ROOT / "presenter"

# View 타입 주석 -> 실제 인스턴스를 만드는 팩토리.
# 생성 비용이 있는 것은 테스트 1회만 만들어 재사용한다.
VIEW_FACTORIES = {}


def _build_view_instances():
    """검사에 쓸 실제 View 인스턴스를 만든다 (Qt 위젯이므로 QApplication 필요)."""
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
    """타입 주석 노드에서 이름만 뽑는다 (Optional[X] 같은 것은 무시)."""
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _collect_view_attrs(tree: ast.Module) -> dict:
    """
    `self.<속성> = <View 타입 파라미터>` 대입을 찾아 {속성: View 클래스명}을 만든다.
    """
    result = {}
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        init = next(
            (n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"),
            None,
        )
        if init is None:
            continue

        # View 타입으로 주석된 파라미터 이름 수집
        view_params = {}
        for arg in list(init.args.args) + list(init.args.kwonlyargs):
            name = _annotation_name(arg.annotation) if arg.annotation else ""
            if name in VIEW_FACTORIES:
                view_params[arg.arg] = name

        if not view_params:
            continue

        # self.X = <그 파라미터> 대입 추적
        for node in ast.walk(init):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
                continue
            src = node.value.id
            if src not in view_params:
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    result[target.attr] = view_params[src]
    return result


def _attribute_chain(node: ast.Attribute):
    """
    `self.a.b.c` 형태의 접근을 ["a", "b", "c"]로 편다.

    중간에 메서드 호출이 끼면(`self.a.f().b`) 반환 타입을 알 수 없으므로 None.
    """
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name) and cur.id == "self":
        return list(reversed(parts))
    return None


def _touches_view_attr(node: ast.Attribute, view_attrs: dict) -> bool:
    """접근 체인의 뿌리가 View 속성인지 (건너뛴 건수 집계용)."""
    cur = node
    while isinstance(cur, (ast.Attribute, ast.Call)):
        cur = cur.func if isinstance(cur, ast.Call) else cur.value
        if (
            isinstance(cur, ast.Attribute)
            and isinstance(cur.value, ast.Name)
            and cur.value.id == "self"
        ):
            return cur.attr in view_attrs
    return False


@pytest.fixture(scope="module")
def view_instances(qapp):
    """실제 View 인스턴스 (모듈 단위로 한 번만 생성)."""
    VIEW_FACTORIES.update({k: None for k in
                           ("MainWindow", "MainLeftSection", "ManualControlPanel",
                            "PacketPanel", "MacroPanel")})
    return _build_view_instances()


def test_presenters_only_call_methods_that_exist_on_the_view(view_instances):
    """
    Presenter가 부르는 View 속성·메서드가 실제로 존재해야 한다.

    존재하지 않으면 실행 시 AttributeError로 죽는다. Mock이 삼켜 테스트가 통과하는
    부류라, 소스를 직접 훑어 확인한다.
    """
    problems = []
    skipped = 0
    checked = 0

    for path in sorted(PRESENTER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        view_attrs = _collect_view_attrs(tree)
        if not view_attrs:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            chain = _attribute_chain(node)
            if chain is None:
                # 중간에 메서드 호출이 껴 반환 타입을 알 수 없는 접근.
                # 검사하지 못한 것을 통과로 위장하지 않도록 개수를 센다.
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
            else:
                continue

    assert not problems, (
        "Presenter가 View에 없는 속성·메서드를 부른다 (실행 시 AttributeError):\n  "
        + "\n  ".join(sorted(set(problems)))
        + f"\n\n(검사 {checked}건 / 반환 타입을 알 수 없어 건너뛴 접근 {skipped}건)"
    )

    # 검사가 조용히 무의미해지지 않도록 최소 규모를 고정한다. Presenter가 View를
    # 부르는 지점이 이보다 크게 줄었다면 추적 로직(타입 주석 -> self 속성 대입)이
    # 깨진 것이지, 코드가 갑자기 깔끔해진 것이 아니다.
    assert checked >= 100, (
        f"검사한 View 접근이 {checked}건뿐이다 — 추적 로직이 깨졌을 수 있다. "
        f"Presenter의 View 파라미터 타입 주석과 `self.X = param` 대입 형태를 확인하라."
    )


def test_port_presenter_uses_left_section_facades_for_tab_collection():
    """
    PortPresenter는 MainLeftSection의 공개 facade까지만 사용해야 한다.

    금지하는 접근:
      * `left_section.port_tab_panel`: 하위 위젯 구현 직접 접근
      * `get_port_tabs_count()` + `get_port_panel_at()`: 탭 개수/인덱스 구조 직접 순회

    개별 PortPanel 객체의 시그널 계약은 Presenter가 담당할 수 있지만, 패널 컬렉션의
    저장 구조와 탐색 방식은 MainLeftSection이 소유해야 한다.
    """
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
        "PortPresenter가 MainLeftSection의 탭 내부 구조/순회 방식에 직접 의존한다. "
        "MainLeftSection facade/signal을 사용해야 한다:\n  "
        + "\n  ".join(violations)
    )


def test_port_presenter_does_not_cache_current_port_panel():
    """
    현재 탭의 View 객체를 Presenter 상태로 보관하지 않는다.

    현재 패널은 탭 전환/닫기 때 수명이 바뀌므로, Presenter가 `current_port_panel`
    같은 멤버를 캐시하고 변경 시그널로 동기화하면 stale QWidget 참조와 별도 상태
    동기화 책임이 생긴다. 필요한 순간에 MainLeftSection facade로 조회해야 한다.
    """
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
        "PortPresenter가 현재 PortPanel View 참조를 상태로 캐시한다. "
        "사용 시 MainLeftSection.get_current_port_panel()로 즉시 조회해야 한다:\n  "
        + "\n  ".join(violations)
    )
