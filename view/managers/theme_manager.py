"""
테마 관리자 모듈

애플리케이션의 전체적인 Look & Feel을 관리합니다.
Dark/Light 모드 전환, 외부 QSS 파일 로드 및 경로 치환, 동적 색상/폰트 적용을 담당합니다.

## WHY
* 운영체제 설정이나 사용자 선호에 따른 시각적 테마 제공
* 위젯별 색상 하드코딩 방지 및 중앙 집중식 스타일 관리
* 런타임 폰트 변경 및 외부 stylesheet 지원
* ThemeManager가 SettingsManager를 직접 생성하지 않고 외부에서 전달된 설정 데이터만 사용

## WHAT
* 테마 상태(`theme_state`) 보유 및 `apply_theme` orchestration
* 폰트(`FontManager`)와 리소스 로딩(`ThemeResourceLoader`) 위임
* 기존 공개 API 유지

## HOW
* composition root가 한 번 생성해 주입한다 (class singleton / module 전역 없음)
* 설정 복원은 `restore_fonts_from_settings()`로 전달받은 plain dict 사용
* FontManager는 재적용 callback만 받아 ThemeManager 역참조를 피함
* ColorManager를 직접 호출하지 않는다 — 팔레트 전파는 두 매니저를 모두 아는 쪽이 한다.
  현재 테마 조회는 shared `theme_state`(리프 모듈)를 통한다
"""

from typing import Any, Dict, Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication

from common.dtos import FontConfig
from common.enums import ThemeType
from core.logger import logger
from core.resource_path import ResourcePath
from view.managers import theme_state
from view.managers.font_manager import FontManager
from view.managers.theme_resource_loader import ThemeResourceLoader


class ThemeManager(QObject):
    """애플리케이션 테마/폰트/resource orchestration을 담당한다.

    WHY instance:
        과거에는 `__new__` 기반 class singleton + module-level 전역 인스턴스였다.
        `main.py`가 ResourcePath를 넘겨도 `_initialized` 가드가 early-return해
        `ThemeResourceLoader`는 import 시점의 기본 경로로 만들어진 것을 계속 썼다.

        지금은 composition root가 한 번 생성해 주입한다 (P2-C #6의 SettingsManager와
        같은 결정).
    """

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """ThemeManager를 초기화한다.

        Args:
            resource_path: ResourcePath instance. None이면 기본 경로 생성
                (SettingsManager와 동일한 관례).
        """
        super().__init__()

        if resource_path is None:
            resource_path = ResourcePath()

        # `_resource_path`는 `_resource_loader`에 위임하는 property이므로 여기서
        # 직접 대입하지 않는다 — loader가 먼저 있어야 한다.

        # SettingsManager를 내부에서 생성하지 않는다.
        # 저장된 폰트 설정은 lifecycle/bootstrap 경로가 plain dict로 전달한다.
        self._current_theme = ThemeType.DARK.value
        self._app: Optional[QApplication] = None

        self._resource_loader = ThemeResourceLoader(resource_path)
        self._font_manager = FontManager(on_font_applied=self._reapply_current_theme)

    def _reapply_current_theme(self) -> None:
        """FontManager 변경 후 현재 테마를 재적용한다."""
        self.apply_theme(self._current_theme)

    # -------------------------------------------------------------------------
    # Shared Theme State
    # -------------------------------------------------------------------------
    @property
    def _current_theme(self) -> str:
        """현재 테마 이름을 shared theme_state에서 읽는다."""
        return theme_state.get_current_theme()

    @_current_theme.setter
    def _current_theme(self, value: str) -> None:
        theme_state.set_current_theme(value)

    # -------------------------------------------------------------------------
    # Resource Path 호환 property
    # -------------------------------------------------------------------------
    @property
    def _resource_path(self) -> ResourcePath:
        """ThemeResourceLoader가 보유한 resource path를 반환한다."""
        return self._resource_loader.resource_path

    @_resource_path.setter
    def _resource_path(self, value: ResourcePath) -> None:
        self._resource_loader.resource_path = value

    @property
    def _icon_dir(self):
        """현재 resource path 기준 icon directory를 반환한다."""
        return self._resource_loader.icons_dir

    @_icon_dir.setter
    def _icon_dir(self, value) -> None:
        # 과거 직접 대입 API 호환. 실제 source of truth는 resource_path다.
        pass

    @property
    def _theme_dir(self):
        """현재 resource path 기준 theme directory를 반환한다."""
        return self._resource_loader.themes_dir

    @_theme_dir.setter
    def _theme_dir(self, value) -> None:
        # 과거 직접 대입 API 호환. 실제 source of truth는 resource_path다.
        pass

    # -------------------------------------------------------------------------
    # Resource Access
    # -------------------------------------------------------------------------
    def get_icon(self, icon_name: str) -> QIcon:
        """현재 테마에 맞는 icon을 반환한다."""
        return self._resource_loader.get_icon(icon_name, self._current_theme)

    def get_available_themes(self):
        """사용 가능한 theme name 목록을 반환한다."""
        return self._resource_loader.get_available_themes()

    def is_dark_theme(self) -> bool:
        """현재 theme가 dark 계열인지 반환한다."""
        current = self._current_theme.lower()
        return current in [ThemeType.DARK.value, ThemeType.DRACULA.value]

    def load_theme_file_content(self, theme_name: str) -> str:
        """지정 theme의 QSS content를 반환한다."""
        return self._resource_loader.load_theme_file_content(theme_name)

    # -------------------------------------------------------------------------
    # Font Management
    # -------------------------------------------------------------------------
    def set_proportional_font(
        self,
        family: str,
        size: int,
        apply_now: bool = True,
    ) -> None:
        """UI 전반의 proportional font를 설정한다."""
        self._font_manager.set_proportional_font(family, size, apply_now)

    def get_proportional_font(self) -> QFont:
        """현재 proportional font를 반환한다."""
        return self._font_manager.get_proportional_font()

    def get_proportional_font_info(self) -> Tuple[str, int]:
        """현재 proportional font의 family/size를 반환한다."""
        return self._font_manager.get_proportional_font_info()

    def set_fixed_font(
        self,
        family: str,
        size: int,
        apply_now: bool = True,
    ) -> None:
        """로그/데이터 View의 fixed font를 설정한다."""
        self._font_manager.set_fixed_font(family, size, apply_now)

    def get_fixed_font(self) -> QFont:
        """현재 fixed font를 반환한다."""
        return self._font_manager.get_fixed_font()

    def get_fixed_font_info(self) -> Tuple[str, int]:
        """현재 fixed font의 family/size를 반환한다."""
        return self._font_manager.get_fixed_font_info()

    def get_font_settings(self) -> FontConfig:
        """현재 font 설정을 DTO로 반환한다."""
        return self._font_manager.get_font_settings()

    def restore_fonts_from_settings(self, settings: Dict[str, Any]) -> None:
        """외부에서 주입된 settings dict로 font 설정을 복원한다."""
        self._font_manager.restore_fonts_from_settings(settings)

    def _generate_font_stylesheet(self) -> str:
        """현재 font 설정 기반 CSS rule을 생성한다."""
        return self._font_manager._generate_font_stylesheet()

    # -------------------------------------------------------------------------
    # Theme Application
    # -------------------------------------------------------------------------
    def apply_theme(self, theme_name: str = "dark") -> None:
        """지정된 theme를 QApplication 전체에 적용한다."""
        app = QApplication.instance()
        if not app:
            logger.warning(
                "QApplication instance not found. Theme might not apply immediately."
            )
            return

        theme_name = theme_name.lower()

        file_path = self._resource_loader.get_theme_file_path(theme_name)
        if not file_path and theme_name not in ["dark", "light"]:
            logger.warning(f"Unknown theme '{theme_name}'. Falling back to 'dark'.")
            theme_name = "dark"

        previous_theme = self._current_theme
        self._current_theme = theme_name
        self._app = app

        is_dark = self.is_dark_theme()
        colors = self._resource_loader.get_theme_colors(is_dark)

        palette = self._resource_loader.create_palette(colors)
        app.setPalette(palette)

        stylesheet = self._resource_loader.load_theme_file_content(theme_name)
        if not stylesheet.strip():
            stylesheet = self._resource_loader.get_fallback_stylesheet(
                colors,
                theme_name,
            )

        font_qss = self._font_manager._generate_font_stylesheet()
        app.setStyleSheet(stylesheet + "\n" + font_qss)

        # ColorManager는 여기서 부르지 않는다.
        # WHY: 과거에는 전역 `color_manager`를 직접 호출했다 — 전역이 전역을 부르는
        #      구조라 어느 쪽도 교체할 수 없었다. 팔레트 전파는 두 매니저를 모두
        #      아는 쪽(composition root와 MainWindow.switch_theme)이 한다.
        #      `MainWindow.switch_theme`은 이미 두 매니저에 각각 적용하고 있었다.

        if previous_theme != theme_name:
            logger.info(f"Theme changed to '{theme_name}'.")
        else:
            logger.debug(f"Theme '{theme_name}' refreshed (style/font update).")

    def get_current_theme(self) -> str:
        """현재 적용된 theme 이름을 반환한다."""
        return self._current_theme
