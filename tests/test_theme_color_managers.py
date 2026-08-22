"""
ThemeManager / ColorManager 특성화(Characterization) 테스트 모듈 (S-050)

`ThemeManager`(833줄)와 `ColorManager`(511줄)는 합쳐서 1300줄이 넘는데 테스트가
0건이었다. 이 파일은 **분해(God object 분해) 전 단계의 안전망**이다 - 두 매니저의
"바람직한" 동작이 아니라 "현재 실제로 관찰되는" 동작을 그대로 고정한다. 이후
리팩터/분해 작업에서 이 파일이 깨지면 관찰 가능한 행동이 바뀐 것이다.

## WHY
* 감사(`doc/refactor_audit_20260822.md` C-7)가 God object 분해를 권고했지만,
  테스트 없이 쪼개면 그 변경이 옳은지 검증할 수단이 없다.
* 특히 폰트 계약이 깨지면 로그 뷰 폰트 설정이 UI에 반영되지 않는 회귀가
  재발한다 - 이 계약을 최우선으로 고정한다. **S-036 실측 교훈**: 이 계약을
  "동적 폰트 QSS 블록이 최종 스타일시트 문자열상 뒤에 온다"는 것만으로
  검증하면 안 된다 - Qt QSS는 순서보다 선택자 특이도(specificity)를 먼저
  본다. `common.qss`에 `QSmartListView.fixed-font`(type+class, 특이도 2)
  같은 하드코딩이 남아있으면 뒤에 붙는 동적 규칙(`.fixed-font`나 bare
  type, 특이도 1)이 있어도 하드코딩이 이겨 설정이 무시된다(실측: 설정을
  D2Coding 16pt로 바꿔도 위젯은 Consolas 9pt 그대로) - 이전 버전의 이
  테스트가 바로 이 실패를 "통과"시키고 있었다. 그래서 아래 폰트 계약
  테스트는 **문자열 위치가 아니라 실제 위젯의 `.font()`(적용된 QFont)**로
  검증한다. 참고: `QFontInfo`가 반환하는 실제 매칭 폰트는 시스템 폰트
  데이터베이스가 필요해 오프스크린 플랫폼(이 프로젝트 pytest 표준
  `QT_QPA_PLATFORM=offscreen`)에서는 폰트가 0개 등록되어 있어 가족명/
  크기가 전부 빈 값/-1로 나온다(실측 확인) - 그래서 자동화 테스트는
  `widget.font()`(스타일 엔진이 실제로 위젯에 배정한 QFont, 특이도/캐스케이드
  버그를 그대로 드러낸다)를 쓰고, `QFontInfo`를 통한 실제 렌더 폰트 확인은
  네이티브 Qt 플랫폼에서 수동 실측 스크립트로 한다(`tasks/S-036-*.md` 실측
  절차 참고).

## HOW
* `tests/conftest.py::reset_ui_manager_state`(S-048, autouse)가 `ThemeManager.
  _current_theme`/`ColorManager._rules`/`COLOR_*` 팔레트를 테스트 전후로
  스냅샷/복원하므로, 이 파일의 테스트는 상태를 바꾼 뒤 수동으로 원복하지 않아도
  다음 테스트를 오염시키지 않는다(`test_singleton_isolation.py`가 이 픽스처
  자체의 동작을 별도로 검증한다). 단, **폰트 설정(`_proportional_font`/
  `_fixed_font`)과 `_resource_path`는 그 픽스처가 다루지 않는 범위**라서
  해당 테스트는 자체적으로 try/finally로 원복한다.
* S-050에서 `ThemeManager._current_theme`을 `view.managers.theme_state` 모듈에
  위임하는 property로 바꿨다(순환 참조 해소) - 위 자동 복원 픽스처는 여전히
  `theme_manager._current_theme = ...` 형태로 직접 대입하므로 코드 변경 없이도
  계속 정상 동작한다(이 파일의 테스트 하나가 그 사실 자체를 명시적으로 확인한다).

pytest tests/test_theme_color_managers.py -v
"""
import pytest
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtGui import QTextCharFormat

from core.resource_path import ResourcePath
from common.constants import ConfigKeys
from view.managers.theme_manager import theme_manager
from view.managers.color_manager import color_manager
from view.managers import theme_state
from view.custom_qt.smart_list_view import QSmartListView


# 각 테마 QSS 파일의 `QWidget { background-color: ... }` 값 - 실제로 그 테마 파일이
# 로드됐는지(폴백이나 다른 테마 혼입이 아닌지) 구분하는 지문(fingerprint).
# resources/themes/{dark,light,dracula}_theme.qss 실측값 (변경 시 이 상수도 갱신).
_THEME_BG_FINGERPRINT = {
    "dark": "#2b2b2b",
    "light": "#f5f5f5",
    "dracula": "#282a36",
    "classic": "#d4d0c8",
}


# -----------------------------------------------------------------------------
# 1. apply_theme() - 테마 파일 로드 및 _current_theme 상태 계약
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("theme_name", ["dark", "light", "dracula", "classic"])
def test_apply_theme_loads_correct_qss_file_and_updates_current_theme(qapp, theme_name):
    """apply_theme() 후 QApplication 스타일시트에 해당 테마 파일 내용이 실제로 들어있어야 한다."""
    theme_manager.apply_theme(theme_name)

    assert theme_manager.get_current_theme() == theme_name

    stylesheet = qapp.styleSheet()
    assert stylesheet.strip() != ""
    assert _THEME_BG_FINGERPRINT[theme_name] in stylesheet, (
        f"'{theme_name}' 테마 파일이 실제로 로드되지 않았다 "
        "(폴백 스타일시트로 대체됐거나 다른 테마가 혼입됐을 수 있다)"
    )


@pytest.mark.parametrize(
    "theme_name,expect_dark",
    [("dark", True), ("light", False), ("dracula", True), ("classic", False)],
)
def test_is_dark_theme_classification(qapp, theme_name, expect_dark):
    """dark/dracula는 dark 계열, light/classic은 아니다 (is_dark_theme 팔레트 선택 계약,
    classic은 S-060에서 밝은 계열로 추가됨)."""
    theme_manager.apply_theme(theme_name)
    assert theme_manager.is_dark_theme() is expect_dark


def test_current_theme_property_delegates_to_shared_theme_state(qapp):
    """
    S-050: `_current_theme`은 이제 `theme_state` 모듈에 위임하는 property다.
    직접 대입(`theme_manager._current_theme = ...`)과 theme_state 조회가
    항상 같은 값을 봐야 한다 - 이래야 conftest의 스냅샷/복원 픽스처가
    theme_state를 몰라도 계속 올바르게 동작한다.
    """
    theme_manager._current_theme = "light"
    assert theme_state.get_current_theme() == "light"
    assert theme_manager._current_theme == "light"

    theme_manager._current_theme = "dark"
    assert theme_state.get_current_theme() == "dark"


# -----------------------------------------------------------------------------
# 2. get_icon() - 테마별 아이콘 디렉터리 라우팅 계약 (S-023)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("theme_name", ["dark", "light", "dracula"])
def test_get_icon_routes_to_current_theme_directory(qapp, monkeypatch, theme_name):
    """
    get_icon()이 현재 테마 접미사가 붙은 디렉터리(icons/{theme}/{name}_{theme}.svg)를
    첫 시도로 사용하고, 그 파일이 실제로 존재해 접미사 없는 폴백으로 빠지지 않는지 확인한다.
    """
    theme_manager.apply_theme(theme_name)

    calls = []
    original_get_icon_path = theme_manager._resource_path.get_icon_path

    def spy(icon_name, theme=None):
        calls.append((icon_name, theme))
        return original_get_icon_path(icon_name, theme)

    monkeypatch.setattr(theme_manager._resource_path, "get_icon_path", spy)

    icon = theme_manager.get_icon("add")

    assert not icon.isNull(), "실제 존재하는 아이콘인데 로드에 실패했다"
    assert calls[0] == ("add", theme_name), "첫 시도가 현재 테마 접미사 경로여야 한다"
    assert len(calls) == 1, (
        "폴백(접미사 없는 경로)으로 재시도했다는 것은 1차 라우팅이 실패했다는 뜻이다"
    )


def test_get_icon_unknown_name_returns_null_icon(qapp):
    """존재하지 않는 아이콘 이름은 조용히 QIcon()(null)을 반환한다 (예외를 던지지 않음)."""
    theme_manager.apply_theme("dark")
    icon = theme_manager.get_icon("__definitely_not_a_real_icon__")
    assert icon.isNull()


def test_get_icon_classic_theme_falls_back_to_light_icon_directory(qapp):
    """
    S-060: classic 전용 아이콘 디렉터리(resources/icons/classic/)가 아직 없으므로,
    get_icon()은 classic 접미사 시도가 실패하면 light 아이콘으로 폴백해야 한다
    (classic은 밝은 계열이라 light 아이콘이 배경과 어울린다 - 확정 설계 4번 (b)).
    classic 디렉터리가 나중에 생기면 그쪽이 먼저 시도된다(코드 순서상 우선).
    """
    theme_manager.apply_theme("classic")

    # 전제 확인: classic 아이콘 디렉터리는 아직 없다 (있다면 이 테스트의 전제가 깨진 것).
    assert not theme_manager._resource_path.get_icon_path("add", "classic").exists()
    assert theme_manager._resource_path.get_icon_path("add", "light").exists()

    icon = theme_manager.get_icon("add")
    assert not icon.isNull(), "classic 테마는 light 아이콘으로 폴백해 아이콘을 로드해야 한다"


# -----------------------------------------------------------------------------
# 3. 폰트 계약 - ThemeManager가 폰트의 유일한 원천이다 (S-036 이후, 회귀 시 로그 뷰
#    폰트가 다시 안 먹는다). autouse 픽스처가 폰트 상태를 다루지 않으므로 직접 복원한다.
# -----------------------------------------------------------------------------

def test_generate_font_stylesheet_separates_proportional_and_fixed_targets(qapp):
    """
    전역(*) 규칙은 가변폭 폰트를, `.fixed-font`/QTextEdit 등 로그·데이터 뷰 규칙은
    고정폭 폰트를 써야 한다 (섞이면 로그 뷰가 가변폭 폰트로 렌더링되는 회귀).
    """
    orig_prop = theme_manager.get_proportional_font_info()
    orig_fixed = theme_manager.get_fixed_font_info()
    try:
        theme_manager.set_proportional_font("CharTestProportional", 11, apply_now=False)
        theme_manager.set_fixed_font("CharTestFixed", 17, apply_now=False)

        qss = theme_manager._generate_font_stylesheet()

        assert 'font-family: "CharTestProportional"' in qss
        assert "font-size: 11pt" in qss
        assert 'font-family: "CharTestFixed"' in qss
        assert "font-size: 17pt" in qss

        # 전역(* 선택자) 블록에는 고정폭 패밀리가 섞여 들어가면 안 된다.
        global_block = qss.split(".fixed-font")[0]
        assert "CharTestProportional" in global_block
        assert "CharTestFixed" not in global_block
    finally:
        theme_manager.set_proportional_font(*orig_prop, apply_now=False)
        theme_manager.set_fixed_font(*orig_fixed, apply_now=False)


def test_set_proportional_font_propagates_to_live_application_stylesheet(qapp):
    """set_proportional_font(apply_now=True)가 실제 QApplication 스타일시트까지 갱신해야 한다."""
    theme_manager.apply_theme("dark")
    orig_prop = theme_manager.get_proportional_font_info()
    try:
        theme_manager.set_proportional_font("LiveProportionalFont", 13)
        stylesheet = qapp.styleSheet()
        assert 'font-family: "LiveProportionalFont"' in stylesheet
        assert "font-size: 13pt" in stylesheet
    finally:
        theme_manager.set_proportional_font(*orig_prop)


def test_set_fixed_font_propagates_to_live_application_stylesheet(qapp):
    """set_fixed_font(apply_now=True)가 실제 QApplication 스타일시트까지 갱신해야 한다."""
    theme_manager.apply_theme("dark")
    orig_fixed = theme_manager.get_fixed_font_info()
    try:
        theme_manager.set_fixed_font("LiveFixedFont", 15)
        stylesheet = qapp.styleSheet()
        assert 'font-family: "LiveFixedFont"' in stylesheet
        assert "font-size: 15pt" in stylesheet
    finally:
        theme_manager.set_fixed_font(*orig_fixed)


def test_fixed_font_setting_is_actually_applied_to_real_widget(qapp):
    """
    S-036 회귀 재현 테스트: 문자열(스타일시트 텍스트)이 아니라 **실제 위젯에 배정된
    QFont**로 검증한다. 이전 버전(`test_font_stylesheet_is_appended_after_theme_qss_
    for_cascade_priority`)은 "동적 QSS 블록이 문자열상 뒤에 있다"만 확인했는데, Qt
    QSS는 순서가 아니라 선택자 특이도로 승자를 가리므로 이 검증은 실제 반영 실패를
    잡지 못했다(실측: `common.qss`의 `QSmartListView.fixed-font` 등 type+class
    하드코딩이 특이도 2로, 동적 규칙의 `.fixed-font`/bare type 특이도 1을 항상 이겨
    D2Coding 16pt로 바꿔도 위젯은 Consolas 9pt로 남았다).

    `QFontInfo`(실제 매칭 폰트)는 오프스크린 플랫폼에서 폰트 데이터베이스가 비어
    있어 쓸 수 없으므로(실측: family=''/size=-1), 스타일 엔진이 위젯에 배정한
    `widget.font()`로 대신한다 - 캐스케이드/특이도 버그는 이 값에도 그대로 드러난다
    (수동 실측 시에는 `QFontInfo(widget.font())`로 실제 렌더 폰트까지 확인한다).
    """
    theme_manager.apply_theme("dark")
    orig_fixed = theme_manager.get_fixed_font_info()
    try:
        # QSmartListView(RX/시스템 로그) - 생성자가 setProperty("class", "fixed-font")
        list_view = QSmartListView()
        list_view.ensurePolished()

        # QLineEdit + class=fixed-font (manual_control.py command_txt 등과 동일 패턴)
        line_edit = QLineEdit()
        line_edit.setProperty("class", "fixed-font")
        line_edit.ensurePolished()

        theme_manager.set_fixed_font("D2Coding", 16)
        list_view.ensurePolished()
        line_edit.ensurePolished()

        assert list_view.font().family() == "D2Coding"
        assert list_view.font().pointSize() == 16
        assert line_edit.font().family() == "D2Coding"
        assert line_edit.font().pointSize() == 16
    finally:
        theme_manager.set_fixed_font(*orig_fixed)


def test_proportional_font_setting_is_appended_after_theme_qss_for_cascade_priority(qapp):
    """
    가변폭 폰트는 전역(`*`) 선택자만 쓰므로(경쟁하는 하드코딩이 없음) 문자열 순서
    검증으로도 충분하다 - 순서 자체가 카스케이드에 영향을 주는 유일한 경우(동일
    특이도)이기 때문. `common.qss`의 다른 규칙(테마 파일)보다 뒤에 붙어야 우선한다.
    """
    theme_manager.apply_theme("dark")
    orig_prop = theme_manager.get_proportional_font_info()
    try:
        theme_manager.set_proportional_font("OrderCheckFont", 12)
        stylesheet = qapp.styleSheet()

        theme_marker_pos = stylesheet.index(_THEME_BG_FINGERPRINT["dark"])
        font_marker_pos = stylesheet.index('font-family: "OrderCheckFont"')
        assert theme_marker_pos < font_marker_pos
    finally:
        theme_manager.set_proportional_font(*orig_prop)


def test_font_settings_dto_round_trip_and_restore_from_settings_dict(qapp):
    """get_font_settings()/restore_fonts_from_settings() 왕복 계약 (앱 재시작 시나리오)."""
    orig_prop = theme_manager.get_proportional_font_info()
    orig_fixed = theme_manager.get_fixed_font_info()
    try:
        theme_manager.set_proportional_font("RoundTripProp", 12, apply_now=False)
        theme_manager.set_fixed_font("RoundTripFixed", 14, apply_now=False)

        cfg = theme_manager.get_font_settings()
        assert cfg.prop_family == "RoundTripProp"
        assert cfg.prop_size == 12
        assert cfg.fixed_family == "RoundTripFixed"
        assert cfg.fixed_size == 14

        # 다른 값으로 흐트러뜨린 뒤 저장된 설정 딕셔너리로 복원
        theme_manager.set_proportional_font("Scratch", 8, apply_now=False)
        theme_manager.set_fixed_font("Scratch", 8, apply_now=False)

        theme_manager.restore_fonts_from_settings({
            "ui": {
                ConfigKeys.PROP_FONT_FAMILY: "RoundTripProp",
                ConfigKeys.PROP_FONT_SIZE: 12,
                ConfigKeys.FIXED_FONT_FAMILY: "RoundTripFixed",
                ConfigKeys.FIXED_FONT_SIZE: 14,
            }
        })

        assert theme_manager.get_proportional_font_info() == ("RoundTripProp", 12)
        assert theme_manager.get_fixed_font_info() == ("RoundTripFixed", 14)
    finally:
        theme_manager.set_proportional_font(*orig_prop, apply_now=False)
        theme_manager.set_fixed_font(*orig_fixed, apply_now=False)


# -----------------------------------------------------------------------------
# 4. 폴백 스타일시트 경로 - 실제로 도달 가능한가? (감사는 "죽은 경로에 가깝다"고 의심)
# -----------------------------------------------------------------------------

def test_fallback_stylesheet_is_reachable_when_theme_directory_missing(qapp, tmp_path):
    """
    `doc/refactor_audit_20260822.md`는 `_get_fallback_stylesheet()`를 죽은 경로에
    가깝다고 판단했다. 실측 결과: **도달은 가능하지만, 트리거하려면 알려지지 않은
    함정을 피해야 한다.**

    함정(이 테스트로 처음 발견): `ThemeManager.__init__`은 `self._theme_dir =
    self._resource_path.themes_dir`를 **생성 시점에 한 번만** 캐싱한다.
    `_get_theme_file_path()`의 미등록 테마 폴백 분기가 `self._resource_path`가 아니라
    이 캐시된 `self._theme_dir`를 직접 참조하므로, `theme_manager._resource_path`만
    바꾸면 (실제로 시도해 확인함) 여전히 원래(진짜) 테마 디렉터리에서 파일을 찾아내
    폴백이 트리거되지 않는다 - `_theme_dir`도 함께 바꿔야 한다. 즉 `_resource_path`를
    나중에 교체해도 `_theme_dir`/`_icon_dir`가 따라가지 않는 잠재 버그가 있다
    (분해 후보 정리에 기록 - 이 태스크의 수정 범위 밖).
    """
    empty_resource_path = ResourcePath(base_dir=tmp_path)
    assert not empty_resource_path.themes_dir.exists()

    original_resource_path = theme_manager._resource_path
    original_theme_dir = theme_manager._theme_dir
    original_theme = theme_manager.get_current_theme()
    try:
        theme_manager._resource_path = empty_resource_path
        theme_manager._theme_dir = empty_resource_path.themes_dir  # 위 함정 회피
        theme_manager.apply_theme("dark")

        stylesheet = qapp.styleSheet()
        # 폴백 템플릿 고유 규칙 (실제 dark_theme.qss에는 없는 표현)
        assert "QPushButton" in stylesheet
        # 실제 테마 파일의 지문은 없어야 한다 (파일이 아니라 폴백 템플릿이 쓰였다는 증거)
        assert _THEME_BG_FINGERPRINT["dark"] not in stylesheet
    finally:
        theme_manager._resource_path = original_resource_path
        theme_manager._theme_dir = original_theme_dir
        # 실제 파일 기반 스타일시트로 원복 (이후 다른 테스트가 오염된 폴백 스타일시트를
        # 물려받지 않도록 - QApplication은 세션 스코프라 stylesheet가 테스트 간에 남는다)
        theme_manager.apply_theme(original_theme)


# -----------------------------------------------------------------------------
# 5. ColorManager - 하이브리드 색상 매핑 계약
# -----------------------------------------------------------------------------

def test_apply_rules_color_follows_theme_state_directly(qapp):
    """
    apply_rules()는 (color_manager.apply_theme()가 호출됐는지와 무관하게) 호출 시점의
    `theme_state.is_dark_theme()` 값만으로 dark_color/light_color 중 하나를 골라야 한다
    - 이것이 S-050에서 순환 참조를 해소하며 남긴 실제 계약이다.
    """
    ok_rule = next(r for r in color_manager._rules if r.name == "AT_OK")
    assert ok_rule.dark_color and ok_rule.light_color
    assert ok_rule.dark_color != ok_rule.light_color

    theme_manager._current_theme = "dark"
    dark_result = color_manager.apply_rules("OK")
    assert ok_rule.dark_color in dark_result

    theme_manager._current_theme = "light"
    light_result = color_manager.apply_rules("OK")
    assert ok_rule.light_color in light_result

    assert dark_result != light_result


def test_color_manager_apply_theme_syncs_palette_and_rule_colors():
    """ColorManager.apply_theme()이 COLOR_* 팔레트와 개별 규칙 .color 필드를 동기화한다."""
    color_manager.apply_theme("light")
    assert color_manager.COLOR_RX == "#0000FF"
    ok_rule = next(r for r in color_manager._rules if r.name == "AT_OK")
    assert ok_rule.color == ok_rule.light_color

    color_manager.apply_theme("dark")
    assert color_manager.COLOR_RX == "#2196F3"
    assert ok_rule.color == ok_rule.dark_color


def test_rules_property_excludes_disabled_rules_and_yields_qt_format(qapp):
    """`rules` 프로퍼티는 비활성 규칙을 제외하고 (pattern, QTextCharFormat) 튜플만 반환한다."""
    all_names = [r.name for r in color_manager._rules]
    assert "AT_OK" in all_names

    color_manager.toggle_rule("AT_OK")
    try:
        patterns = [pattern for pattern, _ in color_manager.rules]
        assert r"\bOK\b" not in patterns

        for pattern, fmt in color_manager.rules:
            assert isinstance(pattern, str)
            assert isinstance(fmt, QTextCharFormat)
    finally:
        color_manager.toggle_rule("AT_OK")


def test_add_and_remove_custom_rule_round_trip():
    """add_custom_rule()/remove_rule() 왕복 계약 (사용자 정의 하이라이트 규칙)."""
    original_count = len(color_manager._rules)
    color_manager.add_custom_rule("CHAR_TEST_RULE", r"CHARTEST", "FF00FF")

    added = next(r for r in color_manager._rules if r.name == "CHAR_TEST_RULE")
    assert added.color == "#FF00FF", "색상 코드에 '#'이 자동으로 붙어야 한다 (_ensure_hex)"
    assert len(color_manager._rules) == original_count + 1

    color_manager.remove_rule("CHAR_TEST_RULE")
    assert len(color_manager._rules) == original_count
    assert not any(r.name == "CHAR_TEST_RULE" for r in color_manager._rules)
