"""
싱글톤 상태 격리 회귀 테스트 모듈 (S-048)

ThemeManager/ColorManager/LanguageManager는 모듈 전역에서 단 한 번 생성되는
싱글톤 인스턴스를 코드베이스 전체가 공유한다. 상태를 바꾸는 테스트가 상태를
복원하지 않으면, 같은 pytest 세션의 이후 테스트가 실행 순서에 따라 오염된
상태를 물려받는다(S-049에서 이 매니저들을 분해하기 전에 안전망이 필요한 이유).

## WHY
* `tests/conftest.py::reset_ui_manager_state`(autouse)가 실제로 오염을 막는지
  증명한다. 이 파일이 통과하면 "픽스처가 존재한다"가 아니라 "픽스처가 동작한다"를
  검증한 것이 된다.

## HOW
* 각 매니저마다 "상태를 바꾸는 더미 테스트 2개"를 순서대로 배치한다.
  1번 테스트가 상태를 임의의 다른 값으로 바꾸고 원래 값을 모듈 전역 변수에 기록,
  2번 테스트는 (조회 시점에) 그 값이 1번 테스트 실행 *이전* 값으로 복원되어
  있음을 확인한다. autouse 픽스처가 1번 테스트 종료 시 복원하지 않았다면 2번
  테스트에서 값이 여전히 1번 테스트가 남긴 값과 같아 실패한다.
* pytest-randomly 등 순서 랜덤화 플러그인이 설치되어 있지 않음을 전제로 한다
  (설치 시 이 파일 내 실행 순서 자체는 pytest가 같은 파일 안에서는 정의 순서를
  유지하므로 영향 없음).

pytest tests/test_singleton_isolation.py -v
"""
import copy

from view.managers.theme_manager import theme_manager
from view.managers.color_manager import color_manager
from view.managers.language_manager import language_manager


# -----------------------------------------------------------------------------
# ThemeManager._current_theme
# -----------------------------------------------------------------------------
_theme_baseline = None


def test_theme_manager_dummy_1_changes_theme():
    global _theme_baseline
    _theme_baseline = theme_manager._current_theme

    # 현재 값과 다른 값으로 강제 변경 (apply_theme의 QSS/QApplication 부수효과를
    # 피하기 위해 내부 상태만 직접 조작 - 여기서 확인하려는 것은 apply_theme
    # 로직이 아니라 픽스처의 상태 복원 여부다).
    theme_manager._current_theme = "light" if _theme_baseline != "light" else "dark"

    assert theme_manager._current_theme != _theme_baseline


def test_theme_manager_dummy_2_sees_reset_state():
    assert _theme_baseline is not None, "dummy_1이 먼저 실행되어야 한다"
    assert theme_manager._current_theme == _theme_baseline


# -----------------------------------------------------------------------------
# LanguageManager._current_language / .resources
# -----------------------------------------------------------------------------
_lang_current_baseline = None
_lang_resources_baseline = None


def test_language_manager_dummy_1_changes_language_and_resources():
    global _lang_current_baseline, _lang_resources_baseline
    _lang_current_baseline = language_manager._current_language
    _lang_resources_baseline = copy.deepcopy(language_manager.resources)

    # test_view_translations.py와 동일한 실사용 패턴: resources 통째 교체
    language_manager.resources = {"en": {"dummy_key": "Dummy"}}
    language_manager._current_language = "en" if _lang_current_baseline != "en" else "ko"

    assert language_manager.resources != _lang_resources_baseline


def test_language_manager_dummy_2_sees_reset_state():
    assert _lang_current_baseline is not None, "dummy_1이 먼저 실행되어야 한다"
    assert language_manager._current_language == _lang_current_baseline
    assert language_manager.resources == _lang_resources_baseline


# -----------------------------------------------------------------------------
# ColorManager._rules (리스트 재할당 + 기존 객체 제자리 mutation 둘 다 검증)
# -----------------------------------------------------------------------------
_color_rules_baseline = None


def test_color_manager_dummy_1_adds_rule_and_mutates_existing():
    global _color_rules_baseline
    _color_rules_baseline = copy.deepcopy(color_manager._rules)
    original_count = len(color_manager._rules)
    first_rule_name = color_manager._rules[0].name
    original_color = color_manager._rules[0].color

    # (1) 리스트 자체를 바꾸는 변경 (add_custom_rule)
    color_manager.add_custom_rule("DUMMY_RULE", r"dummy", "#123456")
    assert len(color_manager._rules) == original_count + 1

    # (2) 기존 객체를 제자리(in-place)로 바꾸는 변경 (apply_theme)
    other_theme = "light" if theme_manager.is_dark_theme() else "dark"
    color_manager.apply_theme(other_theme)
    assert color_manager._rules[0].color != original_color or \
        color_manager._rules[0].name != first_rule_name


def test_color_manager_dummy_2_sees_reset_state():
    assert _color_rules_baseline is not None, "dummy_1이 먼저 실행되어야 한다"
    assert color_manager._rules == _color_rules_baseline
    assert not any(r.name == "DUMMY_RULE" for r in color_manager._rules)
