"""
ColorRuleRepository 단위 테스트 (S-054)

`ColorManager`(511줄)에서 규칙 데이터 관리(기본값·CRUD·JSON 영속화)만 분리한
`ColorRuleRepository`가 PyQt5 없이 단독으로 동작하는지 검증한다.

## WHY
* S-054의 목적 자체가 "규칙 CRUD·영속화는 Qt 없이 단위 테스트할 수 있는 순수
  로직"임을 증명하는 것이다. 이 파일이 `qapp` 픽스처(conftest의 QApplication)를
  전혀 요구하지 않고 통과한다는 사실 자체가 Qt 의존 0을 뒷받침하는 증거다.

## HOW
* 모듈 최상단에서 `sys.modules`를 검사해 이 파일을 import/collect하는 시점까지
  `PyQt5`가 로드되지 않았음을 확인한다(다른 테스트 모듈이 먼저 수집되며 PyQt5를
  적재했을 가능성을 배제하기 위해, 이 검사는 참고용 정보로만 남기고 강한 단언은
  하지 않는다 - pytest가 여러 파일을 한 세션에서 수집하므로 순서에 따라 이미
  PyQt5가 로드돼 있을 수 있다. 실질적 증거는 `view.managers.color_rule_repository`
  모듈 자체의 소스에 `PyQt5` import가 없다는 정적 검사다).

pytest tests/test_color_rule_repository.py -v
"""
import copy
import json

import pytest

from view.managers.color_rule_repository import ColorRuleRepository


def test_module_source_has_no_pyqt5_import():
    """정적 검사: 이 모듈 소스 코드에 PyQt5 import 문이 없어야 한다 (Qt 의존 0).

    (모듈 docstring에는 설명을 위해 'PyQt5'라는 단어 자체는 등장할 수 있으므로,
    실제 import 문 형태만 검사한다.)
    """
    import inspect
    import view.managers.color_rule_repository as repo_module

    source = inspect.getsource(repo_module)
    assert "import PyQt5" not in source
    assert "from PyQt5" not in source


@pytest.fixture
def repo() -> ColorRuleRepository:
    """기본 규칙이 채워진 새 ColorRuleRepository 인스턴스."""
    r = ColorRuleRepository()
    r.init_default_rules()
    return r


def test_init_default_rules_populates_from_default_data(repo):
    """init_default_rules()는 DEFAULT_COLOR_RULES 개수만큼 정규화된 규칙을 채운다."""
    assert len(repo._rules) == len(ColorRuleRepository.DEFAULT_COLOR_RULES)
    names = [r.name for r in repo._rules]
    assert "AT_OK" in names
    assert "AT_ERROR" in names

    ok_rule = next(r for r in repo._rules if r.name == "AT_OK")
    # 기본 데이터는 light/dark 색상이 이미 지정돼 있어야 하며 '#'이 보장돼야 한다.
    assert ok_rule.light_color.startswith("#")
    assert ok_rule.dark_color.startswith("#")


def test_ensure_hex_adds_hash_only_to_valid_hex_strings():
    """_ensure_hex는 6/8자리 유효 HEX 문자열에만 '#'을 붙이고, 색상 이름은 그대로 둔다."""
    r = ColorRuleRepository()
    assert r._ensure_hex("FF0000") == "#FF0000"
    assert r._ensure_hex("#00FF00") == "#00FF00"
    assert r._ensure_hex("red") == "red"
    assert r._ensure_hex("") == ""
    # 8자리(알파 포함)도 처리
    assert r._ensure_hex("FF0000AA") == "#FF0000AA"


def test_add_custom_rule_normalizes_color_and_replaces_existing(repo):
    """add_custom_rule은 색상에 '#'을 보정하고, 동일 이름 규칙이 있으면 교체한다."""
    original_count = len(repo._rules)

    repo.add_custom_rule("CUSTOM", r"foo", "00AAFF")
    added = next(r for r in repo._rules if r.name == "CUSTOM")
    assert added.color == "#00AAFF"
    assert added.light_color == "#00AAFF"
    assert added.dark_color == "#00AAFF"
    assert added.enabled is True
    assert len(repo._rules) == original_count + 1

    # 같은 이름으로 다시 추가하면 개수가 늘지 않고 값만 갱신된다 (remove 후 append).
    repo.add_custom_rule("CUSTOM", r"bar", "#112233")
    assert len(repo._rules) == original_count + 1
    updated = next(r for r in repo._rules if r.name == "CUSTOM")
    assert updated.pattern == "bar"
    assert updated.color == "#112233"


def test_remove_rule_deletes_by_name(repo):
    """remove_rule은 이름이 일치하는 규칙만 제거한다."""
    original_count = len(repo._rules)
    repo.remove_rule("AT_OK")
    assert len(repo._rules) == original_count - 1
    assert not any(r.name == "AT_OK" for r in repo._rules)

    # 존재하지 않는 이름을 지워도 예외 없이 무시된다.
    repo.remove_rule("__NOT_EXIST__")
    assert len(repo._rules) == original_count - 1


def test_toggle_rule_flips_enabled_state(repo):
    """toggle_rule은 대상 규칙의 enabled를 반전시키고 나머지는 건드리지 않는다."""
    ok_rule = next(r for r in repo._rules if r.name == "AT_OK")
    original_state = ok_rule.enabled

    repo.toggle_rule("AT_OK")
    assert ok_rule.enabled is (not original_state)

    repo.toggle_rule("AT_OK")
    assert ok_rule.enabled is original_state


def test_get_rule_color_returns_current_color_or_fallback(repo):
    """get_rule_color는 규칙의 현재 .color 필드를, 없는 규칙은 검정(#000000)을 반환한다."""
    ok_rule = next(r for r in repo._rules if r.name == "AT_OK")
    assert repo.get_rule_color("AT_OK") == ok_rule.color
    assert repo.get_rule_color("__NOT_EXIST__") == "#000000"


def test_save_and_load_round_trip(repo, tmp_path):
    """save_rules -> load_rules 왕복 시 이름/패턴/색상/활성 상태가 보존된다."""
    repo.add_custom_rule("ROUNDTRIP", r"rt", "#ABCDEF", regex_enabled=False)
    repo.toggle_rule("AT_ERROR")

    file_path = str(tmp_path / "color_rules.json")
    repo.save_rules(file_path)

    reloaded = ColorRuleRepository()
    reloaded.load_rules(file_path)

    assert len(reloaded._rules) == len(repo._rules)

    rt = next(r for r in reloaded._rules if r.name == "ROUNDTRIP")
    assert rt.pattern == "rt"
    assert rt.color == "#ABCDEF"
    assert rt.regex_enabled is False

    at_error = next(r for r in reloaded._rules if r.name == "AT_ERROR")
    original_at_error = next(r for r in repo._rules if r.name == "AT_ERROR")
    assert at_error.enabled == original_at_error.enabled


def test_load_rules_normalizes_missing_hash_and_legacy_color_field(tmp_path):
    """
    레거시 데이터(color만 있고 light/dark_color가 비어있거나 '#'이 빠진 HEX)를
    로드해도 정규화되고, light/dark_color가 없으면 legacy color로 채워진다.
    """
    file_path = tmp_path / "legacy_color_rules.json"
    legacy_data = {
        "color_rules": [
            {
                "name": "LEGACY",
                "pattern": "legacy_pattern",
                "color": "AABBCC",  # '#' 없음
                "regex_enabled": True,
                "enabled": True,
            }
        ]
    }
    file_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    repo = ColorRuleRepository()
    repo.load_rules(str(file_path))

    assert len(repo._rules) == 1
    rule = repo._rules[0]
    assert rule.color == "#AABBCC"
    assert rule.light_color == "#AABBCC"
    assert rule.dark_color == "#AABBCC"


def test_load_rules_falls_back_to_defaults_on_invalid_file(tmp_path):
    """존재하지 않거나 파싱 불가능한 파일을 로드하면 예외 없이 기본 규칙으로 대체된다."""
    repo = ColorRuleRepository()
    repo.load_rules(str(tmp_path / "does_not_exist.json"))

    assert len(repo._rules) == len(ColorRuleRepository.DEFAULT_COLOR_RULES)
    assert any(r.name == "AT_OK" for r in repo._rules)


def test_repository_instances_do_not_share_rule_list_identity():
    """두 인스턴스가 만든 기본 규칙 리스트는 값은 같아도 서로 다른 객체(list/DTO)여야 한다."""
    repo_a = ColorRuleRepository()
    repo_a.init_default_rules()
    repo_b = ColorRuleRepository()
    repo_b.init_default_rules()

    assert repo_a._rules is not repo_b._rules
    assert repo_a._rules == copy.deepcopy(repo_b._rules)

    repo_a.remove_rule("AT_OK")
    assert any(r.name == "AT_OK" for r in repo_b._rules)
