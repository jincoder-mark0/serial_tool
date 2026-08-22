"""
FontManager 단위 테스트 모듈 (S-053)

`ThemeManager`(833줄, S-050 조사)에서 폰트 서브시스템을 분리한 `FontManager`가
독립적으로 올바르게 동작하는지 확인한다. `FontManager`는 나머지 관심사(아이콘,
QSS, 싱글톤 수명)에 의존하지 않는 가장 깨끗한 분리 후보였다 — 이 파일의 테스트는
QApplication 유무와 무관하게 성립하는 순수 로직(폰트 값 계산, DTO 왕복, QSS 생성
문자열)과, QApplication이 있을 때만 의미 있는 콜백 트리거 계약을 나눠서 검증한다.

## WHY
* 분해 전에는 폰트 하나를 테스트하려 해도 ThemeManager 전체(아이콘·QSS·싱글톤)가
  딸려왔다. `FontManager`가 진짜로 독립적인지(=ThemeManager를 역참조하지 않는지)를
  구조적으로 고정한다 - 이게 깨지면 S-050에서 없앤 순환 참조가 되살아난 것이다.
* 폰트 변경 시 테마 재적용이 필요하지만 `FontManager`는 `ThemeManager`를 모른다 -
  `on_font_applied` 콜백 계약(호출 조건: `apply_now=True`일 때만)을 고정한다.

pytest tests/test_font_manager.py -v
"""
import ast
import inspect
from pathlib import Path

from common.constants import ConfigKeys
from view.managers import font_manager as font_manager_module
from view.managers.font_manager import FontManager


# -----------------------------------------------------------------------------
# 1. 순환 참조 재도입 방지 (S-050에서 없앤 순환을 되살리지 않는다 - S-053 핵심 제약)
# -----------------------------------------------------------------------------

def test_font_manager_module_does_not_import_theme_manager():
    """
    `font_manager.py`는 어떤 형태로도 `theme_manager` 모듈을 import하면 안 된다.
    재적용은 생성자 콜백(`on_font_applied`)으로만 통지한다 - 콜백은 클로저이므로
    호출자가 누구인지 FontManager는 알 필요가 없다.
    """
    source = Path(inspect.getfile(font_manager_module)).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    assert not any("theme_manager" in m for m in imported_modules), (
        f"FontManager가 theme_manager를 import하면 순환 참조가 되살아난다: {imported_modules}"
    )


# -----------------------------------------------------------------------------
# 2. 기본값 / 순수 로직 (QApplication 불필요)
# -----------------------------------------------------------------------------

def test_default_fonts_are_non_empty_for_current_platform():
    """생성자가 플랫폼에 맞는 기본 가변폭/고정폭 폰트를 채워야 한다."""
    fm = FontManager()

    prop_family, prop_size = fm.get_proportional_font_info()
    fixed_family, fixed_size = fm.get_fixed_font_info()

    assert prop_family
    assert prop_size > 0
    assert fixed_family
    assert fixed_size > 0


def test_font_settings_dto_round_trip_and_restore_from_settings_dict():
    """get_font_settings()/restore_fonts_from_settings() 왕복 계약 (앱 재시작 시나리오)."""
    fm = FontManager()

    fm.set_proportional_font("RoundTripProp", 12, apply_now=False)
    fm.set_fixed_font("RoundTripFixed", 14, apply_now=False)

    cfg = fm.get_font_settings()
    assert cfg.prop_family == "RoundTripProp"
    assert cfg.prop_size == 12
    assert cfg.fixed_family == "RoundTripFixed"
    assert cfg.fixed_size == 14

    # 다른 값으로 흐트러뜨린 뒤 저장된 설정 딕셔너리로 복원
    fm.set_proportional_font("Scratch", 8, apply_now=False)
    fm.set_fixed_font("Scratch", 8, apply_now=False)

    fm.restore_fonts_from_settings({
        "ui": {
            ConfigKeys.PROP_FONT_FAMILY: "RoundTripProp",
            ConfigKeys.PROP_FONT_SIZE: 12,
            ConfigKeys.FIXED_FONT_FAMILY: "RoundTripFixed",
            ConfigKeys.FIXED_FONT_SIZE: 14,
        }
    })

    assert fm.get_proportional_font_info() == ("RoundTripProp", 12)
    assert fm.get_fixed_font_info() == ("RoundTripFixed", 14)


def test_restore_fonts_from_settings_ignores_missing_keys():
    """설정 딕셔너리에 폰트 키가 없으면 기존 값을 그대로 유지한다 (예외를 던지지 않음)."""
    fm = FontManager()
    orig_prop = fm.get_proportional_font_info()
    orig_fixed = fm.get_fixed_font_info()

    fm.restore_fonts_from_settings({"ui": {}})

    assert fm.get_proportional_font_info() == orig_prop
    assert fm.get_fixed_font_info() == orig_fixed


def test_generate_font_stylesheet_separates_proportional_and_fixed_targets():
    """
    전역(*) 규칙은 가변폭 폰트를, `.fixed-font`/QTextEdit 등 로그·데이터 뷰 규칙은
    고정폭 폰트를 써야 한다 (섞이면 로그 뷰가 가변폭 폰트로 렌더링되는 회귀).
    """
    fm = FontManager()
    fm.set_proportional_font("CharTestProportional", 11, apply_now=False)
    fm.set_fixed_font("CharTestFixed", 17, apply_now=False)

    qss = fm._generate_font_stylesheet()

    assert 'font-family: "CharTestProportional"' in qss
    assert "font-size: 11pt" in qss
    assert 'font-family: "CharTestFixed"' in qss
    assert "font-size: 17pt" in qss

    global_block = qss.split(".fixed-font")[0]
    assert "CharTestProportional" in global_block
    assert "CharTestFixed" not in global_block


# -----------------------------------------------------------------------------
# 3. 재적용 콜백 계약 (QApplication 필요 - set_proportional_font가 QApplication.instance()를 참조)
# -----------------------------------------------------------------------------

def test_set_proportional_font_apply_now_true_invokes_callback(qapp):
    """apply_now=True면 콜백이 정확히 1회 호출돼야 한다 (테마 재적용 트리거)."""
    calls = []
    fm = FontManager(on_font_applied=lambda: calls.append(1))

    fm.set_proportional_font("CallbackProp", 10, apply_now=True)

    assert len(calls) == 1


def test_set_proportional_font_apply_now_false_does_not_invoke_callback(qapp):
    """apply_now=False면 콜백이 호출되면 안 된다 (일괄 복원 시나리오에서 중복 재적용 방지)."""
    calls = []
    fm = FontManager(on_font_applied=lambda: calls.append(1))

    fm.set_proportional_font("NoCallbackProp", 10, apply_now=False)

    assert calls == []


def test_set_fixed_font_apply_now_true_invokes_callback(qapp):
    """apply_now=True면 콜백이 정확히 1회 호출돼야 한다 (테마 재적용 트리거)."""
    calls = []
    fm = FontManager(on_font_applied=lambda: calls.append(1))

    fm.set_fixed_font("CallbackFixed", 12, apply_now=True)

    assert len(calls) == 1


def test_set_fixed_font_apply_now_false_does_not_invoke_callback(qapp):
    """apply_now=False면 콜백이 호출되면 안 된다."""
    calls = []
    fm = FontManager(on_font_applied=lambda: calls.append(1))

    fm.set_fixed_font("NoCallbackFixed", 12, apply_now=False)

    assert calls == []


def test_no_callback_configured_does_not_raise(qapp):
    """`on_font_applied`를 주지 않아도(None) apply_now=True 경로가 예외 없이 동작해야 한다."""
    fm = FontManager()

    fm.set_proportional_font("NoCallbackConfigured", 10, apply_now=True)
    fm.set_fixed_font("NoCallbackConfigured", 10, apply_now=True)
