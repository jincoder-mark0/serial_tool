"""
테마 관리자 모듈

애플리케이션의 시각적 테마(QSS)와 폰트, 아이콘을 관리합니다.

## WHY
* 다크/라이트 모드 지원 및 일관된 디자인 언어 유지
* 플랫폼별 최적화된 기본 폰트 제공
* 배포 환경(PyInstaller)에서의 리소스 경로 문제 해결

## WHAT
* QSS 파일 로드 및 경로 치환 (절대 경로)
* 테마별 SVG 아이콘 로딩
* 폰트(가변폭/고정폭) 설정 관리 및 적용
* 현재 테마의 Dark/Light 여부 판별

## HOW
* QSS 텍스트 내의 리소스 경로를 런타임에 동적으로 수정
* QApplication.setStyleSheet 및 setFont를 통한 전역 스타일 적용
"""
import os
import platform
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor, QFont, QIcon
from pathlib import Path
from core.resource_path import ResourcePath
from core.logger import logger
from common.dtos import FontConfig
from common.enums import ThemeType
from common.constants import (
    PLATFORM_WINDOWS, PLATFORM_LINUX, PLATFORM_MACOS,
    FONT_FAMILY_SEGOE, FONT_FAMILY_UBUNTU, FONT_FAMILY_CONSOLAS,
    FONT_FAMILY_MONOSPACE, FONT_FAMILY_MENLO
)

class ThemeManager:
    """애플리케이션 테마와 폰트 관리자"""

    # 플랫폼별 기본 폰트 설정 [Constants Use]
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

    def __init__(self, resource_path=None):
        """
        ThemeManager를 초기화하고 플랫폼별 기본 폰트를 설정합니다.

        Args:
            resource_path: ResourcePath 인스턴스. None이면 기본 경로 사용
        """
        self._current_theme = ThemeType.DARK.value
        self._app = None
        self._resource_path = resource_path

        # 플랫폼 확인
        system = platform.system()

        # 플랫폼에 따른 기본 폰트 설정
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))

        self._proportional_font = QFont(prop_family, prop_size)
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)

    def is_dark_theme(self) -> bool:
        """
        현재 테마가 어두운 배경을 사용하는지 확인합니다.
        Dracula도 Dark 계열로 취급합니다.

        Returns:
            bool: 어두운 테마면 True, 밝은 테마면 False
        """
        current = self._current_theme.lower()
        # Dark 또는 Dracula는 True 반환
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
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            themes_dir = os.path.join(base_dir, 'resources', 'themes')

        if not os.path.exists(themes_dir):
            return ["Dark", "Light"] # 기본값

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

    def load_theme(self, theme_name: str = ThemeType.DARK.value) -> str:
        """
        지정된 테마의 QSS 콘텐츠를 로드합니다.

        Logic:
            - 공통 QSS와 테마별 QSS를 로드하여 병합합니다.
            - QSS 내부의 'url(resources/...' 상대 경로를 절대 경로로 치환합니다.
            - 이는 PyInstaller 배포 시 리소스 경로 문제 해결을 위함입니다.

        Args:
            theme_name (str): 로드할 테마 이름 (예: "Dark", "Dracula").

        Returns:
            str: 결합되고 경로가 수정된 QSS 문자열.
        """
        # 이름 소문자 변환 및 파일명 구성
        theme_file = f"{theme_name.lower()}_theme.qss"

        if self._resource_path is not None:
            # AppConfig가 제공되었으면 그것을 사용
            common_path = self._resource_path.get_theme_path('common')
            theme_path = self._resource_path.get_theme_path(theme_name)

            # 리소스 경로에 등록되지 않은 새 테마일 수 있으므로 직접 구성 시도
            if not theme_path:
                theme_file = f"{theme_name}_theme.qss"
                theme_path = self._resource_path.themes_dir / theme_file

        else:
            # Fallback
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            themes_dir = os.path.join(base_dir, 'resources', 'themes')
            common_path = os.path.join(themes_dir, 'common.qss')
            theme_path = os.path.join(themes_dir, theme_file)

        qss_content = ""

        # 1. 공통 QSS 로드
        if common_path and os.path.exists(common_path):
            try:
                with open(common_path, "r", encoding="utf-8") as f:
                    qss_content += f.read() + "\n"
            except Exception as e:
                logger.error(f"Error loading common theme: {e}")
        else:
            logger.warning(f"Common theme file not found: {common_path}")

        # 2. 특정 테마 QSS 로드
        if theme_path and os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    qss_content += f.read()
            except Exception as e:
                logger.error(f"Error loading theme {theme_name}: {e}")
        else:
            logger.warning(f"Theme file not found: {theme_path}")

        # 3. 폴백 스타일시트 (파일 로드 실패 시)
        if not qss_content.strip():
            logger.warning("Failed to load theme file, using fallback stylesheet.")
            qss_content = self._get_fallback_stylesheet(theme_name)

        # 4. 리소스 경로 절대 경로 치환
        # PyInstaller 배포 환경에서는 상대 경로가 깨질 수 있으므로 절대 경로로 변환
        if self._resource_path:
            # 윈도우 경로 역슬래시를 슬래시로 변환 (CSS url 호환성)
            base_res_path = str(self._resource_path.base_dir).replace('\\', '/')
            # QSS 내의 url(resources/...) 패턴을 url(절대경로/resources/...)로 변경
            qss_content = qss_content.replace('url(resources/', f'url({base_res_path}/resources/')

        return qss_content

    @staticmethod
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


    def _generate_font_stylesheet(self) -> str:
        """
        설정에서 폰트 정보를 읽어와 CSS 문자열을 생성합니다.
        [동작되는 버전의 핵심 로직 이식]
        """
        try:
            # 설정에서 폰트 정보 가져오기 (기본값 처리 포함)
            prop_family = self._settings.get(ConfigKeys.UI_PROPORTIONAL_FONT_FAMILY, "Segoe UI")
            prop_size = self._settings.get(ConfigKeys.UI_PROPORTIONAL_FONT_SIZE, 9)
            fixed_family = self._settings.get(ConfigKeys.UI_FIXED_FONT_FAMILY, "Consolas")
            fixed_size = self._settings.get(ConfigKeys.UI_FIXED_FONT_SIZE, 9)

            # CSS 생성
            # * : 전역 폰트 (가변폭)
            # .fixed-font : 고정폭 폰트가 필요한 위젯용 클래스
            font_qss = f"""
            * {{
                font-family: "{prop_family}";
                font-size: {prop_size}pt;
            }}
            .fixed-font, QPlainTextEdit, QTextEdit {{
                font-family: "{fixed_family}";
                font-size: {fixed_size}pt;
            }}
            """
            return font_qss
        except Exception as e:
            logger.error(f"Failed to generate font stylesheet: {e}")
            return ""

    def _get_theme_file_path(self, theme_name: str) -> Path:
        """
        테마 이름에 해당하는 QSS 파일 경로를 반환합니다.
        """
        filename = f"{theme_name.lower()}.qss"

        # 1. ResourcePath가 설정되어 있으면 그것을 사용
        if self._resource_path:
            return self._resource_path.get_theme_path(filename)

        # 2. Fallback: 상대 경로 추론 (테스트 환경 또는 PyInstaller)
        if hasattr(os, '_MEIPASS'):
            base_path = Path(os._MEIPASS)
        else:
            # view/managers/theme_manager.py -> project_root
            base_path = Path(__file__).parent.parent.parent

        return base_path / 'resources' / 'themes' / filename

    def apply_theme(self, app: QApplication, theme_name: str = ThemeType.DARK.value):
        """
        지정된 테마를 QApplication 인스턴스에 적용합니다.

        Args:
            app (QApplication): 스타일을 적용할 애플리케이션 인스턴스.
            theme_name (str): 적용할 테마 이름. 기본값은 "dark".
        """
        self._app = app
        self._current_theme = theme_name

        # 1. 기본 테마 로드 (공통 + 특정)
        base_stylesheet = self.load_theme(theme_name)

        # 2. 폰트 스타일시트 생성
        font_stylesheet = self._generate_font_stylesheet()

        # 3. 결합 및 적용
        full_stylesheet = base_stylesheet + "\n" + font_stylesheet

        if full_stylesheet:
            app.setStyleSheet(full_stylesheet)
        else:
            logger.error(f"Failed to apply theme: {theme_name}")


    # def apply_theme(self, app: QApplication, theme_name: str) -> None:
    #     """
    #     지정된 테마(QSS 파일 + 폰트 설정)를 애플리케이션 전체에 적용합니다.
    #     """
    #     self.current_theme = theme_name.lower()
    #     qss_path = self._get_theme_file_path(self.current_theme)

    #     logger.info(f"Applying theme: {self.current_theme} from {qss_path}")

    #     try:
    #         full_stylesheet = ""

    #         # 1. QSS 파일 로드
    #         if qss_path.exists():
    #             with open(qss_path, 'r', encoding='utf-8') as f:
    #                 qss_content = f.read()

    #                 # 아이콘 경로 치환 (@ICON_PATH -> 실제 경로)
    #                 if self._resource_path:
    #                     icon_path = str(self._resource_path.icons_dir).replace('\\', '/')
    #                     qss_content = qss_content.replace("@ICON_PATH", icon_path)

    #                 full_stylesheet += qss_content
    #         else:
    #             logger.error(f"Theme file not found: {qss_path}")

    #         # 2. 폰트 스타일시트 생성 및 병합
    #         font_stylesheet = self._generate_font_stylesheet()
    #         full_stylesheet += "\n" + font_stylesheet

    #         # 3. 최종 스타일시트 적용
    #         if full_stylesheet.strip():
    #             app.setStyleSheet(full_stylesheet)
    #         else:
    #             logger.warning("Empty stylesheet applied.")

    #     except Exception as e:
    #         logger.error(f"Failed to apply theme: {e}")

    def get_current_theme(self) -> str:
        """
        현재 테마 이름을 반환합니다.

        Returns:
            str: 현재 테마 이름.
        """
        return self._current_theme

    # 가변폭(Proportional) 폰트 메서드
    def set_proportional_font(self, family: str, size: int):
        """
        UI 요소에 사용할 가변폭 폰트를 설정합니다.

        Args:
            family (str): 폰트 패밀리 이름.
            size (int): 폰트 크기 (pt).
        """
        self._proportional_font = QFont(family, size)
        if self._app:
            self._app.setFont(self._proportional_font)
            # 테마를 다시 적용하여 QSS 업데이트
            self.apply_theme(self._app, self._current_theme)

    def get_proportional_font(self) -> QFont:
        """
        현재 가변폭 폰트를 반환합니다.

        Returns:
            QFont: 현재 설정된 가변폭 폰트 객체 (복사본).
        """
        return QFont(self._proportional_font)  # 복사본 반환

    def get_proportional_font_info(self) -> tuple[str, int]:
        """
        가변폭 폰트의 정보(패밀리, 크기)를 반환합니다.

        Returns:
            tuple[str, int]: (폰트 패밀리, 폰트 크기) 튜플.
        """
        return self._proportional_font.family(), self._proportional_font.pointSize()

    # 고정폭(Fixed) 폰트 메서드
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

        # Dict 대신 DTO 반환
        return FontConfig(
            prop_family=prop_family,
            prop_size=prop_size,
            fixed_family=fixed_family,
            fixed_size=fixed_size
        )

    # 레거시 호환성
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
        # Dracula 등 다크 계열 테마는 white 아이콘(dark 접미사) 사용
        target_theme = self._current_theme
        if target_theme.lower() in [ThemeType.DRACULA.value, ThemeType.DARK.value]:
            target_theme = ThemeType.DARK.value
        else:
            target_theme = ThemeType.LIGHT.value

        if self._resource_path is not None:
            # AppConfig가 제공되었으면 그것을 사용
            icon_path = self._resource_path.get_icon_path(name, target_theme)

            if not os.path.exists(icon_path):
                # 폴백: 테마 접미사 없이 시도
                fallback_path = self._resource_path.get_icon_path(name)
                if os.path.exists(fallback_path):
                    return QIcon(str(fallback_path))
                return QIcon()

            return QIcon(str(icon_path))
        else:
            # 하위 호환성: 기존 경로 사용
            icon_path = f"resources/icons/{name}_{target_theme}.svg"

            if not os.path.exists(icon_path):
                # 폴백: 테마 접미사 없이 시도
                fallback_path = f"resources/icons/{name}.svg"
                if os.path.exists(fallback_path):
                    return QIcon(fallback_path)
                # 파일이 없으면 빈 아이콘 반환
                return QIcon()

            return QIcon(icon_path)
