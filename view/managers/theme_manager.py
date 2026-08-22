"""
테마 관리자 모듈

애플리케이션의 전체적인 룩앤필(Look & Feel)을 관리하는 싱글톤 클래스입니다.
Dark/Light 모드 전환, 외부 QSS 파일 로드 및 경로 치환, 동적 색상/폰트 적용을 담당합니다.

## WHY
* 운영체제 설정이나 사용자 선호에 따른 시각적 테마 제공 필요
* 위젯별 색상 하드코딩 방지 및 중앙 집중식 스타일 관리 (유지보수성 향상)
* 런타임 폰트 변경 및 외부 스타일시트 파일 지원을 통한 확장성 확보
* 플랫폼별 최적화된 기본 폰트 제공 및 PyInstaller 배포 시 리소스 경로 문제 해결

## WHAT
* 테마 상태(`theme_state`) 보유 및 `apply_theme` 오케스트레이션
  (QPalette 적용 -> QSS 조립 -> ColorManager 동기화)
* 폰트(`FontManager`)·리소스 로딩(`ThemeResourceLoader`) 위임, 외부에는 기존
  공개 메서드를 그대로 유지

## HOW
* Singleton 패턴으로 전역 접근 허용
* S-053에서 `FontManager`(폰트 서브시스템)와 `ThemeResourceLoader`(아이콘/테마
  파일/QSS 폴백)를 분리했다. `ThemeManager`는 이제 이 둘을 조합하는 얇은
  오케스트레이터다 — 공개 API(이름·시그니처)는 분해 전과 동일하게 유지되므로
  앱 전역의 호출 코드는 변경이 필요 없다.
  `FontManager`는 재적용 콜백만 받고 `ThemeManager`를 역참조하지 않는다
  (S-050에서 없앤 순환 참조를 되살리지 않기 위함).
* SettingsManager와 연동하여 폰트 설정 저장 및 복원
* ColorManager 업데이트를 통해 구문 강조 색상 동기화
"""
from typing import Any, Dict, Optional, Tuple

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QObject

from core.logger import logger
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager

from common.enums import ThemeType
from common.dtos import FontConfig
from view.managers import theme_state
from view.managers.font_manager import FontManager
from view.managers.theme_resource_loader import ThemeResourceLoader
# ColorManager는 theme_state만 참조하고 ThemeManager를 참조하지 않으므로(S-050),
# 최상단에서 바로 import해도 순환 참조가 생기지 않는다.
from view.managers.color_manager import color_manager


class ThemeManager(QObject):
    """
    애플리케이션 테마(색상, 스타일, 아이콘, 폰트)를 관리하는 관리자 클래스 (Singleton).

    S-053에서 폰트(`FontManager`)와 리소스 로딩(`ThemeResourceLoader`)을 분리해
    자신은 상태 보유·오케스트레이션만 담당하는 얇은 클래스가 되었다. 공개 API는
    분해 이전과 동일하다.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Singleton 인스턴스 보장 및 초기화 플래그 설정
        """
        if not cls._instance:
            # QObject 상속 시 super().__new__에는 인자를 전달하지 않는 것이 안전함
            cls._instance = super(ThemeManager, cls).__new__(cls)
            # 인스턴스 생성 직후 플래그 초기화
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """
        ThemeManager 초기화

        Logic:
            - 플래그 체크로 중복 초기화 방지
            - super().__init__() 호출 (QObject 필수)
            - 리소스 로더/폰트 관리자 구성

        Args:
            resource_path: ResourcePath 인스턴스. None이면 내부에서 생성.
        """
        # ResourcePath 설정 (주입받거나 없으면 생성)
        if resource_path is None:
            resource_path = ResourcePath()

        # 싱글톤 중복 초기화 방지
        if hasattr(self, '_initialized') and self._initialized:
            # 이미 초기화되었더라도, 새로운 resource_path가 들어오면 업데이트
            if resource_path is not None:
                self._resource_path = resource_path
            return

        # QObject 초기화 (가장 먼저 호출해야 함)
        super().__init__()

        self._settings = SettingsManager()  # 설정 매니저 인스턴스

        # 기본값 초기화 (실제 저장은 theme_state 모듈 - _current_theme property 참고)
        self._current_theme = ThemeType.DARK.value
        self._app: Optional[QApplication] = None

        # 리소스 로더 구성 (아이콘/테마 파일/QSS 폴백/팔레트)
        self._resource_loader = ThemeResourceLoader(resource_path)

        # 폰트 관리자 구성. 폰트 변경 시 테마 재적용이 필요하지만, FontManager가
        # ThemeManager를 역참조하면 순환 참조가 되살아나므로(S-050) 콜백만 넘긴다.
        self._font_manager = FontManager(on_font_applied=self._reapply_current_theme)

        # 초기화 완료 플래그 설정
        self._initialized = True

    def _reapply_current_theme(self) -> None:
        """현재 테마를 재적용한다 (FontManager의 재적용 콜백 대상)."""
        self.apply_theme(self._current_theme)

    # -------------------------------------------------------------------------
    # Shared Theme State (순환 참조 해소용 - S-050)
    # -------------------------------------------------------------------------
    @property
    def _current_theme(self) -> str:
        """
        현재 테마 이름. 실제 저장 위치는 `theme_state` 모듈이다.

        ColorManager와 값이 어긋날 수 없도록(캐시 동기화 문제 방지) 값 자체를
        `theme_state`에 위임한다. 기존 코드(및 테스트)가 `self._current_theme`을
        일반 속성처럼 읽고 쓰는 코드를 그대로 쓸 수 있도록 property로 감쌌다.
        """
        return theme_state.get_current_theme()

    @_current_theme.setter
    def _current_theme(self, value: str) -> None:
        theme_state.set_current_theme(value)

    # -------------------------------------------------------------------------
    # Resource Path 호환 프로퍼티 (S-053: ThemeResourceLoader로 실제 상태 이전)
    # -------------------------------------------------------------------------
    @property
    def _resource_path(self) -> ResourcePath:
        """리소스 경로. 실제 상태는 `ThemeResourceLoader`가 보유한다."""
        return self._resource_loader.resource_path

    @_resource_path.setter
    def _resource_path(self, value: ResourcePath) -> None:
        self._resource_loader.resource_path = value

    @property
    def _icon_dir(self):
        """
        아이콘 디렉터리 경로 (하위 호환용 읽기 전용 뷰).

        `ThemeResourceLoader.icons_dir`을 그때그때 반영한다 - `_resource_path`를
        교체하면 별도 동기화 없이 다음 접근부터 새 경로를 본다(S-050 캐싱 함정 수정).
        """
        return self._resource_loader.icons_dir

    @_icon_dir.setter
    def _icon_dir(self, value) -> None:
        # S-053 이전에는 생성 시점 캐시였던 필드다. 이제 진짜 출처는
        # `_resource_path`이므로 직접 대입은 무시한다 - `_resource_path`를 바꾸면
        # `_icon_dir` 조회값도 자동으로 따라간다. 과거 코드(및 테스트)가
        # `theme_manager._icon_dir = ...` 형태로 대입해도 예외 없이 동작하도록
        # 세터만 남겨둔다.
        pass

    @property
    def _theme_dir(self):
        """
        테마 디렉터리 경로 (하위 호환용 읽기 전용 뷰).

        `ThemeResourceLoader.themes_dir`을 그때그때 반영한다 - `_resource_path`를
        교체하면 별도 동기화 없이 다음 접근부터 새 경로를 본다(S-050 캐싱 함정 수정,
        S-053에서 실제로 고침).
        """
        return self._resource_loader.themes_dir

    @_theme_dir.setter
    def _theme_dir(self, value) -> None:
        # `_icon_dir` 세터와 동일한 이유로 무시한다 - 진짜 출처는 `_resource_path`.
        pass

    # -------------------------------------------------------------------------
    # Resource Access (Icon, Theme File) - ThemeResourceLoader로 위임
    # -------------------------------------------------------------------------
    def get_icon(self, icon_name: str) -> QIcon:
        """
        아이콘 이름(파일명)을 받아 현재 테마에 맞는 QIcon 객체를 반환합니다.

        Args:
            icon_name (str): 아이콘 파일명 (예: 'add', 'settings.png').

        Returns:
            QIcon: 로드된 아이콘 객체.
        """
        return self._resource_loader.get_icon(icon_name, self._current_theme)

    def get_available_themes(self):
        """
        사용 가능한 테마 목록 반환 (파일 스캔 방식).

        Returns:
            List[str]: 테마 이름 리스트 (예: ['Dark', 'Light', 'Dracula']).
        """
        return self._resource_loader.get_available_themes()

    def is_dark_theme(self) -> bool:
        """
        현재 테마가 어두운 배경을 사용하는지 확인합니다.

        Returns:
            bool: 어두운 테마면 True, 밝은 테마면 False.
        """
        current = self._current_theme.lower()
        return current in [ThemeType.DARK.value, ThemeType.DRACULA.value]

    def load_theme_file_content(self, theme_name: str) -> str:
        """
        지정된 테마 파일 및 공통 파일을 로드하고 경로를 치환하여 QSS 문자열을 반환합니다.

        Args:
            theme_name (str): 테마 이름.

        Returns:
            str: 처리된 QSS 문자열.
        """
        return self._resource_loader.load_theme_file_content(theme_name)

    # -------------------------------------------------------------------------
    # Font Management - FontManager로 위임
    # -------------------------------------------------------------------------
    def set_proportional_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """UI 전반에 사용될 가변폭 폰트(Proportional Font)를 설정합니다."""
        self._font_manager.set_proportional_font(family, size, apply_now)

    def get_proportional_font(self) -> QFont:
        """현재 설정된 가변폭 폰트 객체를 반환합니다."""
        return self._font_manager.get_proportional_font()

    def get_proportional_font_info(self) -> Tuple[str, int]:
        """현재 설정된 가변폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)"""
        return self._font_manager.get_proportional_font_info()

    def set_fixed_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """로그 및 데이터 뷰에 사용될 고정폭 폰트(Fixed Font)를 설정합니다."""
        self._font_manager.set_fixed_font(family, size, apply_now)

    def get_fixed_font(self) -> QFont:
        """현재 설정된 고정폭 폰트 객체를 반환합니다."""
        return self._font_manager.get_fixed_font()

    def get_fixed_font_info(self) -> Tuple[str, int]:
        """현재 설정된 고정폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)"""
        return self._font_manager.get_fixed_font_info()

    def get_font_settings(self) -> FontConfig:
        """현재 폰트 설정 전체를 DTO로 반환합니다."""
        return self._font_manager.get_font_settings()

    def restore_fonts_from_settings(self, settings: Dict[str, Any]) -> None:
        """
        설정 딕셔너리로부터 폰트 설정을 복원합니다.
        (앱 초기화 시 SettingsManager로부터 데이터를 주입받을 때 사용)
        """
        self._font_manager.restore_fonts_from_settings(settings)

    def _generate_font_stylesheet(self) -> str:
        """현재 폰트 설정을 기반으로 CSS 폰트 규칙을 생성합니다."""
        return self._font_manager._generate_font_stylesheet()

    # -------------------------------------------------------------------------
    # Theme Application
    # -------------------------------------------------------------------------
    def apply_theme(self, theme_name: str = "dark") -> None:
        """
        지정된 테마를 애플리케이션 전체에 적용합니다.

        Logic:
            1. 테마 이름 유효성 확인
            2. QPalette 적용 (네이티브 위젯 색상)
            3. QSS 파일 로드 및 생성 (파일 -> Fallback)
            4. 폰트 스타일시트 병합 및 적용
            5. ColorManager 업데이트

        Args:
            theme_name (str): 적용할 테마 이름.
        """
        app = QApplication.instance()
        if not app:
            logger.warning("QApplication instance not found. Theme might not apply immediately.")
            return

        theme_name = theme_name.lower()

        # 파일 경로 확인 (유효성 검사)
        file_path = self._resource_loader.get_theme_file_path(theme_name)
        if not file_path and theme_name not in ["dark", "light"]:
            logger.warning(f"Unknown theme '{theme_name}'. Falling back to 'dark'.")
            theme_name = "dark"

        previous_theme = self._current_theme
        self._current_theme = theme_name
        self._app = app  # App 인스턴스 저장

        # Fallback용 색상 팔레트 선택
        is_dark = self.is_dark_theme()
        colors = self._resource_loader.get_theme_colors(is_dark)

        # 1. QPalette 적용
        palette = self._resource_loader.create_palette(colors)
        app.setPalette(palette)

        # 2. Stylesheet 로드
        # 파일에서 로드 시도 (common.qss 포함)
        stylesheet = self._resource_loader.load_theme_file_content(theme_name)

        # 파일 로드 실패 또는 내용 없음 -> Fallback 생성
        if not stylesheet.strip():
            stylesheet = self._resource_loader.get_fallback_stylesheet(colors, theme_name)

        # 3. 폰트 스타일 병합
        font_qss = self._font_manager._generate_font_stylesheet()
        full_stylesheet = stylesheet + "\n" + font_qss

        app.setStyleSheet(full_stylesheet)

        # 5. ColorManager 업데이트 (로그 강조 색상 팔레트 동기화)
        # NOTE: main_window.switch_theme()에서도 별도로 color_manager.apply_theme()를
        # 호출하므로 동일 theme_name으로 중복 호출될 수 있음. ColorManager.apply_theme은
        # theme_name과 규칙의 light_color/dark_color(불변)만으로 상태를 재계산하고
        # 시그널을 발행하지 않아 idempotent함 (2026-08-22 확인) - 중복 호출해도 안전.
        color_manager.apply_theme(theme_name)

        # 로그 출력 제어
        if previous_theme != theme_name:
            logger.info(f"Theme changed to '{theme_name}'.")
        else:
            logger.debug(f"Theme '{theme_name}' refreshed (style/font update).")

    def get_current_theme(self) -> str:
        """현재 적용된 테마 이름을 반환합니다."""
        return self._current_theme


# 전역 싱글톤 인스턴스 생성
theme_manager = ThemeManager()
