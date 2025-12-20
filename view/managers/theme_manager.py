"""
테마 관리자 모듈

애플리케이션의 시각적 테마(QSS)와 폰트, 아이콘을 관리합니다.

## WHY
* 다크/라이트 모드 지원 및 일관된 디자인 언어 유지
* 플랫폼별 최적화된 기본 폰트 제공
* 배포 환경(PyInstaller)에서의 리소스 경로 문제 해결
* 전역적인 테마 및 폰트 상태 공유

## WHAT
* QSS 파일 로드 및 경로 치환 (절대 경로)
* 테마별 SVG 아이콘 로딩
* 폰트(가변폭/고정폭) 설정 관리 및 적용
* 현재 테마의 Dark/Light 여부 판별

## HOW
* Singleton 패턴 적용
* QSS 텍스트 내의 리소스 경로를 런타임에 동적으로 수정
* SettingsManager를 통해 사용자 폰트 설정을 읽어와 동적으로 스타일시트에 병합
"""
import os
import platform
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager
from core.logger import logger
from common.dtos import FontConfig
from common.enums import ThemeType
from common.constants import (
    PLATFORM_WINDOWS, PLATFORM_LINUX, PLATFORM_MACOS,
    FONT_FAMILY_SEGOE, FONT_FAMILY_UBUNTU, FONT_FAMILY_CONSOLAS,
    FONT_FAMILY_MONOSPACE, FONT_FAMILY_MENLO, ConfigKeys
)

class ThemeManager:
    """
    애플리케이션 테마 관리 클래스 (Singleton)
    """
    _instance = None
    _resource_path = None
    _initialized = False

    # 플랫폼별 기본 폰트 설정
    _PROPORTIONAL_FONTS = {
        PLATFORM_WINDOWS: (FONT_FAMILY_SEGOE, 9),
        PLATFORM_LINUX: (FONT_FAMILY_UBUNTU, 9),
        PLATFORM_MACOS: ("SF Pro Text", 9)
    }

    _FIXED_FONTS = {
        PLATFORM_WINDOWS: (FONT_FAMILY_CONSOLAS, 9),
        PLATFORM_LINUX: (FONT_FAMILY_MONOSPACE, 9),
        PLATFORM_MACOS: (FONT_FAMILY_MENLO, 9)
    }

    def __new__(cls, *args, **kwargs):
        """싱글톤 인스턴스 생성"""
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, resource_path: ResourcePath = None):
        """
        ThemeManager 초기화

        Args:
            resource_path: ResourcePath 인스턴스. None이면 기존 경로 유지.
        """
        if resource_path:
            ThemeManager._resource_path = resource_path

        if self._initialized:
            return

        self._current_theme = ThemeType.DARK.value
        self._app = None
        self._settings = SettingsManager()  # 설정 매니저 인스턴스

        # 플랫폼 확인
        system = platform.system()

        # 플랫폼에 따른 기본 폰트 설정
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))

        self._proportional_font = QFont(prop_family, prop_size)
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)

        self._initialized = True

    @staticmethod
    def set_resource_path(resource_path: ResourcePath) -> None:
        """ResourcePath 의존성을 주입합니다."""
        ThemeManager._resource_path = resource_path

    def is_dark_theme(self) -> bool:
        """
        현재 테마가 어두운 배경을 사용하는지 확인합니다.

        Returns:
            bool: 어두운 테마면 True, 밝은 테마면 False
        """
        current = self._current_theme.lower()
        return current in [ThemeType.DARK.value, ThemeType.DRACULA.value]

    def get_available_themes(self) -> list[str]:
        """
        사용 가능한 테마 목록 반환 (파일 스캔 방식)

        Logic:
            - themes 디렉토리의 파일 스캔
            - '*_theme.qss' 패턴과 일치하는 파일 찾기
            - 파일명에서 '_theme.qss' 제거 후 대문자 변환하여 반환

        Returns:
            list[str]: 테마 이름 리스트 (예: ['Dark', 'Light', 'Dracula'])
        """
        themes = []

        # ResourcePath 확인
        if self._resource_path:
            themes_dir = self._resource_path.themes_dir
        else:
            # Fallback
            base_dir = Path(__file__).parent.parent.parent
            themes_dir = base_dir / 'resources' / 'themes'

        if not themes_dir.exists():
            return ["Dark", "Light"]

        try:
            for filename in os.listdir(themes_dir):
                if filename.endswith("_theme.qss"):
                    # 예: dracula_theme.qss -> Dracula
                    name = filename.replace("_theme.qss", "").capitalize()
                    themes.append(name)
        except Exception as e:
            logger.error(f"Error scanning themes directory: {e}")
            return ["Dark", "Light"]

        return sorted(themes)

    def _get_fallback_stylesheet(theme_name: str) -> str:
        """
        테마 파일이 없을 경우 사용할 최소한의 스타일시트를 반환합니다.

        Args:
            theme_name (str): 테마 이름.

        Returns:
            str: 폴백 QSS 문자열.
        """
        if theme_name.lower() == ThemeType.DARK.value:
            return """
            QMainWindow, QWidget { background-color: #2b2b2b; color: #ffffff; }
            QLineEdit, QTextEdit, QPlainTextEdit { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555555; }
            QComboBox, QPushButton { background-color: #444444; color: #ffffff; border: 1px solid #555555; padding: 5px; }
            QHeaderView::section { background-color: #444444; color: #ffffff; }
            QTableView { background-color: #2b2b2b; color: #ffffff; gridline-color: #555555; }
            """
        else:
            return """
            QMainWindow, QWidget { background-color: #f0f0f0; color: #000000; }
            QLineEdit, QTextEdit, QPlainTextEdit { background-color: #ffffff; color: #000000; border: 1px solid #cccccc; }
            QComboBox, QPushButton { background-color: #e0e0e0; color: #000000; border: 1px solid #cccccc; padding: 5px; }
            """

    def _get_theme_file_path(self, theme_name: str) -> Path:
        """
        테마 이름에 해당하는 QSS 파일 경로를 반환합니다.
        """
        filename = f"{theme_name.lower()}_theme.qss"

        if self._resource_path:
            # get_theme_path가 없거나 파일명 규칙이 다를 수 있으므로 직접 구성
            # ResourcePath 클래스 구조에 따라 다를 수 있음. 여기서는 themes_dir 사용.
            return self._resource_path.themes_dir / filename

        # Fallback
        if hasattr(os, '_MEIPASS'):
            base_path = Path(os._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        return base_path / 'resources' / 'themes' / filename

    def _generate_font_stylesheet(self) -> str:
        """
        설정에서 폰트 정보를 읽어와 CSS 문자열을 생성합니다.
        """
        try:
            # 설정에서 폰트 정보 가져오기 (기본값 처리 포함)
            prop_family = self._settings.get(ConfigKeys.PROP_FONT_FAMILY, "Segoe UI")
            prop_size = self._settings.get(ConfigKeys.PROP_FONT_SIZE, 9)
            fixed_family = self._settings.get(ConfigKeys.FIXED_FONT_FAMILY, "Consolas")
            fixed_size = self._settings.get(ConfigKeys.FIXED_FONT_SIZE, 9)

            # 내부 상태 업데이트 (동기화)
            self._proportional_font = QFont(prop_family, prop_size)
            self._fixed_font = QFont(fixed_family, fixed_size)
            self._fixed_font.setStyleHint(QFont.Monospace)

            # CSS 생성
            font_qss = f"""
            * {{
                font-family: "{prop_family}";
                font-size: {prop_size}pt;
            }}
            .fixed-font, QPlainTextEdit, QTextEdit, QSmartTextEdit, QSmartListView {{
                font-family: "{fixed_family}";
                font-size: {fixed_size}pt;
            }}
            """
            return font_qss
        except Exception as e:
            logger.error(f"Failed to generate font stylesheet: {e}")
            return ""

    def load_theme(self, theme_name: str) -> str:
        """
        지정된 테마의 QSS 콘텐츠를 로드합니다.

        Args:
            theme_name (str): 로드할 테마 이름 (예: "Dark", "Dracula").

        Returns:
            str: 결합되고 경로가 수정된 QSS 문자열.
        """
        theme_path = self._get_theme_file_path(theme_name)

        # 공통 QSS 경로
        if self._resource_path:
            common_path = self._resource_path.themes_dir / 'common.qss'
        else:
            common_path = theme_path.parent / 'common.qss'

        qss_content = ""

        # 1. 공통 QSS 로드
        if common_path.exists():
            try:
                with open(common_path, "r", encoding="utf-8") as f:
                    qss_content += f.read() + "\n"
            except Exception as e:
                logger.error(f"Error loading common theme: {e}")
        else:
            logger.warning(f"Common theme file not found: {common_path}")

        # 2. 특정 테마 QSS 로드
        if theme_path.exists():
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    qss_content += f.read()
            except Exception as e:
                logger.error(f"Error loading theme {theme_name}: {e}")
        else:
            logger.warning(f"Theme file not found: {theme_path}")

        # 3. 리소스 경로 절대 경로 치환
        if self._resource_path:
            base_res_path = str(self._resource_path.base_dir).replace('\\', '/')
            qss_content = qss_content.replace('url(resources/', f'url({base_res_path}/resources/')

        return qss_content

    def apply_theme(self, app: QApplication, theme_name: str = ThemeType.DARK.value):
        """
        지정된 테마를 QApplication 인스턴스에 적용합니다.

        Args:
            app (QApplication): 스타일을 적용할 애플리케이션 인스턴스.
            theme_name (str): 적용할 테마 이름.
        """
        self._app = app
        self._current_theme = theme_name

        # 1. 기본 테마 로드 (공통 + 특정)
        base_stylesheet = self.load_theme(theme_name)

        # 2. 폰트 스타일시트 생성
        font_stylesheet = self._generate_font_stylesheet()

        # 3. 결합 및 적용
        full_stylesheet = base_stylesheet + "\n" + font_stylesheet

        if full_stylesheet.strip():
            app.setStyleSheet(full_stylesheet)
            logger.info(f"Theme '{theme_name}' applied successfully.")
        else:
            logger.error(f"Failed to apply theme: {theme_name} (Empty stylesheet)")

    def get_current_theme(self) -> str:
        """현재 테마 이름을 반환합니다."""
        return self._current_theme

    def get_icon(self, name: str) -> QIcon:
        """
        현재 테마에 맞는 아이콘을 반환합니다.
        아이콘 파일명 규칙: {name}_{theme}.svg (예: add_dark.svg, add_light.svg)
        다크 테마(또는 Dracula)인 경우 밝은 아이콘(_dark.svg)을, 라이트 테마인 경우 어두운 아이콘(_light.svg)을 찾습니다.

        Args:
            name (str): 아이콘 이름 (예: "add").

        Returns:
            QIcon: 테마에 맞는 QIcon 객체.
        """
        target_theme = self._current_theme
        if target_theme.lower() in [ThemeType.DRACULA.value, ThemeType.DARK.value]:
            target_theme = ThemeType.DARK.value
        else:
            target_theme = ThemeType.LIGHT.value

        if self._resource_path:
            icon_path = self._resource_path.get_icon_path(name, target_theme)
            if not icon_path.exists():
                # 폴백
                icon_path = self._resource_path.get_icon_path(name)
        else:
            # Fallback for no resource path
            base_dir = Path(__file__).parent.parent.parent
            icon_path = base_dir / 'resources' / 'icons' / target_theme / f"{name}_{target_theme}.svg"

        if icon_path.exists():
            return QIcon(str(icon_path))

        return QIcon()

    # 폰트 관련 메서드들 (설정 저장소 역할도 겸함)
    def set_proportional_font(self, family: str, size: int):
        """
        UI 요소에 사용할 가변폭 폰트를 설정합니다.

        Args:
            family (str): 폰트 패밀리 이름.
            size (int): 폰트 크기 (pt).
        """
        self._proportional_font = QFont(family, size)
        if self._app:
            self.apply_theme(self._app, self._current_theme)

    def set_fixed_font(self, family: str, size: int):
        """
        텍스트 데이터에 사용할 고정폭 폰트를 설정합니다.

        Args:
            family (str): 폰트 패밀리 이름.
            size (int): 폰트 크기 (pt).
        """
        self._fixed_font = QFont(family, size)
        self._fixed_font.setStyleHint(QFont.Monospace)
        if self._app:
            # 테마를 다시 적용하여 QSS 업데이트
            self.apply_theme(self._app, self._current_theme)

    def get_proportional_font(self) -> QFont:
        """
        현재 가변폭 폰트를 반환합니다.

        Returns:
            QFont: 현재 설정된 가변폭 폰트 객체 (복사본).
        """
        return QFont(self._proportional_font)

    def get_proportional_font_info(self) -> tuple[str, int]:
        """
        가변폭 폰트의 정보(패밀리, 크기)를 반환합니다.

        Returns:
            tuple[str, int]: (폰트 패밀리, 폰트 크기) 튜플.
        """
        return self._proportional_font.family(), self._proportional_font.pointSize()

    def get_fixed_font(self) -> QFont:
        """
        현재 고정폭 폰트를 반환합니다.

        Returns:
            QFont: 현재 설정된 고정폭 폰트 객체 (복사본).
        """
        return QFont(self._fixed_font)  # 복사본 반환

    def get_fixed_font_info(self) -> tuple[str, int]:
        """
        고정폭 폰트의 정보(패밀리, 크기)를 반환합니다.

        Returns:
            tuple[str, int]: (폰트 패밀리, 폰트 크기) 튜플.
        """
        return self._fixed_font.family(), self._fixed_font.pointSize()

    # 설정에서 폰트 복원
    def restore_fonts_from_settings(self, settings: dict):
        """
        설정 딕셔너리에서 폰트 설정을 복원합니다.

        Args:
            settings (dict): 애플리케이션 설정 딕셔너리.
        """
        ui_settings = settings.get("ui", {})

        # 가변폭 폰트 복원
        prop_family = ui_settings.get("proportional_font_family")
        prop_size = ui_settings.get("proportional_font_size")
        if prop_family and prop_size:
            self._proportional_font = QFont(prop_family, prop_size)

        # 고정폭 폰트 복원
        fixed_family = ui_settings.get("fixed_font_family")
        fixed_size = ui_settings.get("fixed_font_size")
        if fixed_family and fixed_size:
            self._fixed_font = QFont(fixed_family, fixed_size)
            self._fixed_font.setStyleHint(QFont.Monospace)

        # 참고: apply_theme이 초기화 직후 호출되므로 여기서 바로 적용하지 않아도 됨.
        # 하지만 app이 설정되어 있다면 명시적으로 적용.
        if self._app:
             self.apply_theme(self._app, self._current_theme)

    def get_font_settings(self) -> FontConfig:
        """
        현재 폰트 설정을 FontConfig DTO로 반환합니다.

        Returns:
            FontConfig: 폰트 설정 객체 (저장용).
        """
        prop_family, prop_size = self.get_proportional_font_info()
        fixed_family, fixed_size = self.get_fixed_font_info()
        return FontConfig(
            prop_family=prop_family,
            prop_size=prop_size,
            fixed_family=fixed_family,
            fixed_size=fixed_size
        )

    @staticmethod
    def set_font(app: QApplication, font_family: str, font_size: int = 10):
        """
        애플리케이션 전체 폰트를 설정합니다 (레거시 메서드).

        Args:
            app (QApplication): 애플리케이션 인스턴스.
            font_family (str): 폰트 패밀리 이름.
            font_size (int): 폰트 크기. 기본값은 10.
        """
        font = QFont(font_family, font_size)
        app.setFont(font)

# 전역 인스턴스
theme_manager = ThemeManager()