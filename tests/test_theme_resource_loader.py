"""
ThemeResourceLoader 단위 테스트 모듈 (S-053)

`ThemeManager`(833줄, S-050 조사)에서 아이콘/테마 파일 탐색/QSS 폴백/팔레트 생성을
분리한 `ThemeResourceLoader`가 독립적으로 올바르게 동작하는지, 그리고 S-050이
발견한 `_theme_dir` 캐싱 함정이 실제로 고쳐졌는지 확인한다.

## WHY
* S-050 특성화 테스트(`tests/test_theme_color_managers.py`)가 발견한 함정:
  옛 `ThemeManager.__init__`은 `self._theme_dir`를 생성 시점에 한 번만 캐싱해서,
  이후 `_resource_path`만 재주입하면 테마 경로 리다이렉트가 무효였다(`_theme_dir`도
  함께 바꿔야만 트리거됨). 이 파일의 첫 테스트가 그 함정이 실제로 해소됐음을
  `resource_path` 재주입 **한 번만으로** 증명한다 - 옛 함정이 있었다면 이 테스트가
  실패했을 것이다.

pytest tests/test_theme_resource_loader.py -v
"""
from core.resource_path import ResourcePath
from view.managers.theme_resource_loader import ThemeResourceLoader


# -----------------------------------------------------------------------------
# 1. `_theme_dir`/`_icon_dir` 캐싱 함정 해소 (S-053 핵심 수정 사항)
# -----------------------------------------------------------------------------

def test_themes_dir_and_icons_dir_follow_resource_path_reassignment_alone(tmp_path):
    """
    `resource_path`를 재주입하기만 해도(다른 필드를 손대지 않아도)
    `themes_dir`/`icons_dir`가 새 경로를 즉시 반영해야 한다 - S-050이 발견한
    캐싱 함정(`_theme_dir`가 생성 시점에 고정돼 `_resource_path`만 바꾸면 무효화됨)이
    ThemeResourceLoader에는 없어야 한다.
    """
    real_resource_path = ResourcePath()
    loader = ThemeResourceLoader(real_resource_path)

    assert loader.themes_dir == real_resource_path.themes_dir
    assert loader.icons_dir == real_resource_path.icons_dir

    empty_resource_path = ResourcePath(base_dir=tmp_path)
    assert not empty_resource_path.themes_dir.exists()

    # 캐싱 함정이 있었다면 아래 재주입 이후에도 loader.themes_dir가 여전히
    # 옛(real) 경로를 가리켰을 것이다 - 다른 필드는 일부러 건드리지 않는다.
    loader.resource_path = empty_resource_path

    assert loader.themes_dir == empty_resource_path.themes_dir
    assert loader.icons_dir == empty_resource_path.icons_dir


def test_get_theme_file_path_redirects_after_resource_path_swap_without_extra_step(tmp_path):
    """
    `resource_path` 재주입 한 번만으로 `get_theme_file_path()`가 새(빈) 디렉터리
    기준으로 동작해야 한다(= 존재하지 않는 테마 파일에 대해 None 반환).
    """
    loader = ThemeResourceLoader(ResourcePath())
    assert loader.get_theme_file_path("dark") is not None  # 실제 파일 존재

    loader.resource_path = ResourcePath(base_dir=tmp_path)

    assert loader.get_theme_file_path("dark") is None


def test_load_theme_file_content_is_empty_when_theme_directory_missing(tmp_path):
    """테마 디렉터리가 없으면(common.qss도 없음) 내용이 비어 있어야 한다 (폴백 트리거 조건)."""
    loader = ThemeResourceLoader(ResourcePath(base_dir=tmp_path))

    content = loader.load_theme_file_content("dark")

    assert content == ""


# -----------------------------------------------------------------------------
# 2. 아이콘 라우팅
# -----------------------------------------------------------------------------

def test_get_icon_unknown_name_returns_null_icon(qapp):
    loader = ThemeResourceLoader(ResourcePath())
    icon = loader.get_icon("__definitely_not_a_real_icon__", "dark")
    assert icon.isNull()


def test_get_icon_unregistered_theme_falls_back_to_dark_suffix(qapp, monkeypatch):
    """미확인 테마 이름은 dark 접미사로 폴백해야 한다 (ThemeManager와 동일 계약)."""
    loader = ThemeResourceLoader(ResourcePath())

    calls = []
    original_get_icon_path = loader.resource_path.get_icon_path

    def spy(icon_name, theme=None):
        calls.append((icon_name, theme))
        return original_get_icon_path(icon_name, theme)

    monkeypatch.setattr(loader.resource_path, "get_icon_path", spy)

    loader.get_icon("add", "some_unknown_theme")

    assert calls[0] == ("add", "dark")


# -----------------------------------------------------------------------------
# 3. 폴백 팔레트 / 스타일시트
# -----------------------------------------------------------------------------

def test_get_theme_colors_dark_and_light_are_distinct():
    loader = ThemeResourceLoader(ResourcePath())

    dark = loader.get_theme_colors(is_dark=True)
    light = loader.get_theme_colors(is_dark=False)

    assert dark != light
    assert dark["bg_base"] != light["bg_base"]


def test_get_fallback_stylesheet_uses_injected_colors():
    loader = ThemeResourceLoader(ResourcePath())
    colors = loader.get_theme_colors(is_dark=True)

    qss = loader.get_fallback_stylesheet(colors, "dark")

    assert colors["bg_alt"] in qss
    assert "QToolTip" in qss  # dark 전용 툴팁 규칙


def test_create_palette_uses_injected_colors(qapp):
    loader = ThemeResourceLoader(ResourcePath())
    colors = loader.get_theme_colors(is_dark=False)

    from PyQt5.QtGui import QPalette, QColor
    palette = loader.create_palette(colors)

    assert palette.color(QPalette.Base) == QColor(colors["bg_base"])
    assert palette.color(QPalette.WindowText) == QColor(colors["fg_primary"])
