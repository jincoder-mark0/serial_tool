"""
포트 탭 기본 이름 구분 테스트 (S-079)

## WHY
남은 화면을 훑다가 나온 결함이다. 탭을 넷 열고 캡처했더니 넷 다
**"포트:LOOPBACK"** 으로 똑같았다 — 어느 탭이 어느 것인지 알 수 없었다.

탭 제목은 `"{custom_name}:{포트명}"` 인데, 모든 탭이 기본 이름 "포트"로 시작하고
포트 콤보가 목록의 첫 항목을 자동 선택하므로 양쪽이 모두 같아진 것이다. 즉
멀티포트 도구인데 정작 탭으로 포트를 구분할 수 없었다.

## WHAT
* 새 탭을 여러 개 열면 제목이 서로 달라지는가
* 번호가 1부터 빈틈없이 붙는가 (전역 카운터를 쓰면 "포트 1, 포트 3"처럼 튄다)
* 탭을 닫아 비게 된 번호를 다시 쓰는가
* 사용자가 지정한 이름을 덮어쓰지 않는가

## HOW
포트 콤보가 무엇을 고르든 결과가 같아야 하므로, 제목 문자열 전체가 아니라
**기본 이름(custom_name)의 유일성**을 본다.
"""
import pytest
from PyQt5.QtWidgets import QApplication

from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel
from view.panels.port_tab_panel import PortTabPanel


@pytest.fixture
def tab_panel(qapp):
    """포트 탭 컨테이너 한 개 (테스트마다 새로 만든다)."""
    panel = PortTabPanel()
    yield panel
    panel.deleteLater()
    QApplication.processEvents()


def _names(panel: PortTabPanel) -> list:
    """현재 열려 있는 포트 탭들의 기본 이름 목록."""
    return [
        panel.widget(i).get_custom_name()
        for i in range(panel.count())
        if isinstance(panel.widget(i), PortPanel)
    ]


def test_new_tabs_get_distinct_names(tab_panel):
    """탭을 여러 개 열면 이름이 서로 달라야 한다 — 이게 깨져서 넷 다 같았다."""
    before = len(_names(tab_panel))              # 컨테이너가 만드는 최초 탭
    for _ in range(3):
        tab_panel.add_new_port_tab()

    names = _names(tab_panel)
    assert len(names) == before + 3, f"탭 수가 맞지 않는다: {names}"
    assert len(set(names)) == len(names), f"이름이 겹친다: {names}"


def test_numbering_starts_at_one_without_gaps(tab_panel):
    """
    번호는 1부터 빈틈없이 붙어야 한다.

    전역 카운터로 매기면 창을 다시 열거나 버려진 인스턴스가 생겼을 때
    "포트 1, 포트 3, 포트 4"처럼 건너뛴다 (실제로 그렇게 나왔다).
    """
    while len(_names(tab_panel)) < 3:
        tab_panel.add_new_port_tab()

    base = language_manager.get_text("port_tab_default_name")
    assert _names(tab_panel) == [f"{base} {n}" for n in (1, 2, 3)]


def test_closed_number_is_reused(tab_panel):
    """
    비워진 번호를 다시 쓴다.

    열고 닫기를 반복하는 동안 번호만 커지면 "포트 47"처럼 되어 이름의 뜻이
    사라진다. 남아 있는 탭과 겹치지만 않으면 작은 번호를 먼저 쓴다.
    """
    while len(_names(tab_panel)) < 3:
        tab_panel.add_new_port_tab()
    base = language_manager.get_text("port_tab_default_name")

    tab_panel.widget(1).deleteLater()
    tab_panel.removeTab(1)                       # "포트 2" 제거
    QApplication.processEvents()
    tab_panel.add_new_port_tab()

    names = _names(tab_panel)
    assert f"{base} 2" in names, f"비워진 번호를 다시 쓰지 않았다: {names}"
    assert len(set(names)) == len(names), f"이름이 겹친다: {names}"


def test_user_named_tab_is_not_renumbered(tab_panel):
    """사용자가 붙인 이름은 새 탭을 열어도 그대로 남아야 한다."""
    while len(_names(tab_panel)) < 1:
        tab_panel.add_new_port_tab()
    tab_panel.widget(0).set_custom_name("센서")

    tab_panel.add_new_port_tab()

    names = _names(tab_panel)
    assert "센서" in names, f"사용자 이름이 사라졌다: {names}"
    assert len(set(names)) == len(names), f"이름이 겹친다: {names}"
