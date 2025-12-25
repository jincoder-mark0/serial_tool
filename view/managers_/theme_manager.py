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
* 테마별 색상 팔레트(Dict) 정의 및 QPalette 생성
* QSS(Qt Style Sheet) 로드: 파일 확인 -> 공통 QSS 병합 -> 리소스 경로 절대경로 치환
* 아이콘 파일 로드 (get_icon) 및 SVG 지원
* 폰트 설정 관리 (가변폭/고정폭) 및 동적 스타일시트 생성

## HOW
* Singleton 패턴으로 전역 접근 허용
* 외부 .qss 파일 존재 시 우선 로드, 없을 경우 내부 f-string 템플릿 사용 (Fallback)
* SettingsManager와 연동하여 폰트 설정 저장 및 복원
* ColorManager 업데이트를 통해 구문 강조 색상 동기화
"""
import os
import platform
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor, QIcon, QFont
from PyQt5.QtCore import Qt, QObject

from core.logger import logger
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager

from common.enums import ThemeType
from common.dtos import FontConfig
from common.constants import (
    PLATFORM_WINDOWS, PLATFORM_LINUX, PLATFORM_MACOS,
    FONT_FAMILY_SEGOE, FONT_FAMILY_UBUNTU, FONT_FAMILY_CONSOLAS,
    FONT_FAMILY_MONOSPACE, FONT_FAMILY_MENLO, ConfigKeys
)


class ThemeManager(QObject):
    """
    애플리케이션 테마(색상, 스타일, 아이콘, 폰트)를 관리하는 관리자 클래스 (Singleton).
    """

    _instance = None

    # -------------------------------------------------------------------------
    # 테마 색상 정의 (Color Definitions - Fallback용)
    # -------------------------------------------------------------------------
    # VS Code 스타일의 다크 테마 색상
    THEME_DARK = {
        "bg_base": "#1E1E1E",          # 기본 배경 (가장 어두움)
        "bg_alt": "#252526",           # 대체 배경 (패널 등)
        "bg_input": "#3C3C3C",         # 입력창 배경
        "fg_primary": "#CCCCCC",       # 기본 텍스트
        "fg_secondary": "#858585",     # 보조 텍스트 (비활성 등)
        "border": "#454545",           # 테두리 색상
        "accent": "#007ACC",           # 강조 색상 (파랑)
        "accent_hover": "#0098FF",     # 강조 호버
        "selection": "#264F78",        # 선택 영역 배경
        "button_bg": "#333333",        # 버튼 배경
        "button_hover": "#444444",     # 버튼 호버
        "table_grid": "#404040",       # 테이블 그리드
        "scrollbar_bg": "#1E1E1E",     # 스크롤바 배경
        "scrollbar_handle": "#424242"  # 스크롤바 핸들
    }

    # 표준 윈도우 스타일의 라이트 테마 색상
    THEME_LIGHT = {
        "bg_base": "#FFFFFF",
        "bg_alt": "#F3F3F3",
        "bg_input": "#FFFFFF",
        "fg_primary": "#000000",
        "fg_secondary": "#666666",
        "border": "#D0D0D0",
        "accent": "#0078D7",
        "accent_hover": "#1084E3",
        "selection": "#CCE8FF",
        "button_bg": "#E1E1E1",
        "button_hover": "#E5F1FB",
        "table_grid": "#E0E0E0",
        "scrollbar_bg": "#F0F0F0",
        "scrollbar_handle": "#CDCDCD"
    }

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
            - 리소스 경로 저장 및 초기 테마 설정
            - 플랫폼별 기본 폰트 설정

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

        self._resource_path = resource_path
        self._settings = SettingsManager()  # 설정 매니저 인스턴스

        # 기본값 초기화
        self._current_theme = ThemeType.DARK.value
        self._app: Optional[QApplication] = None

        # 디렉토리 경로 설정
        self._icon_dir = self._resource_path.icons_dir
        self._theme_dir = self._resource_path.themes_dir

        # 플랫폼 확인 및 기본 폰트 설정
        system = platform.system()
        
        # 1. 가변폭 폰트 (Proportional)
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        self._proportional_font = QFont(prop_family, prop_size)
        
        # 2. 고정폭 폰트 (Fixed)
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)

        # 초기화 완료 플래그 설정
        self._initialized = True

    # -------------------------------------------------------------------------
    # Resource Access (Icon, Theme File)
    # -------------------------------------------------------------------------
    def get_icon(self, icon_name: str) -> QIcon:
        """
        아이콘 이름(파일명)을 받아 현재 테마에 맞는 QIcon 객체를 반환합니다.

        Logic:
            1. 테마별 아이콘({name}_{theme}.svg) 우선 검색
            2. 실패 시 기본 아이콘({name}.svg/png) 검색
            3. 확장자가 없으면 .png를 기본으로 시도

        Args:
            icon_name (str): 아이콘 파일명 (예: 'add', 'settings.png').

        Returns:
            QIcon: 로드된 아이콘 객체.
        """
        # 테마 접미사 결정을 위한 타겟 테마 확인
        target_theme = self._current_theme.lower()
        if target_theme in [ThemeType.DRACULA.value, ThemeType.DARK.value]:
            theme_suffix = ThemeType.DARK.value
        else:
            theme_suffix = ThemeType.LIGHT.value

        # 1. 테마별 아이콘 시도 (ResourcePath 활용)
        icon_path = self._resource_path.get_icon_path(icon_name, theme_suffix)
        
        if not icon_path.exists():
            # 2. 폴백: 테마 접미사 없이 시도
            icon_path = self._resource_path.get_icon_path(icon_name)

        # 3. 직접 경로 확인 (확장자 처리 등 ResourcePath가 실패했을 경우 대비)
        if not icon_path.exists():
             if not icon_name.endswith(('.png', '.svg', '.ico')):
                filename = f"{icon_name}.png"
             else:
                filename = icon_name
             full_path = self._icon_dir / filename
             if full_path.exists():
                 return QIcon(str(full_path))
        else:
             return QIcon(str(icon_path))

        return QIcon()

    def get_available_themes(self) -> List[str]:
        """
        사용 가능한 테마 목록 반환 (파일 스캔 방식).

        Logic:
            - themes 디렉토리의 파일 스캔
            - '*_theme.qss' 패턴과 일치하는 파일 찾기
            - 파일명에서 '_theme.qss' 제거 후 대문자 변환하여 반환

        Returns:
            List[str]: 테마 이름 리스트 (예: ['Dark', 'Light', 'Dracula']).
        """
        themes = ["Dark", "Light"]  # 기본 제공 테마

        if not self._theme_dir.exists():
            return themes

        try:
            for filename in os.listdir(self._theme_dir):
                if filename.endswith("_theme.qss"):
                    # 예: dracula_theme.qss -> Dracula
                    name = filename.replace("_theme.qss", "").capitalize()
                    if name not in themes:
                        themes.append(name)
        except Exception as e:
            logger.error(f"Error scanning themes directory: {e}")
            return ["Dark", "Light"]

        return sorted(themes)

    def is_dark_theme(self) -> bool:
        """
        현재 테마가 어두운 배경을 사용하는지 확인합니다.

        Returns:
            bool: 어두운 테마면 True, 밝은 테마면 False.
        """
        current = self._current_theme.lower()
        return current in [ThemeType.DARK.value, ThemeType.DRACULA.value]

    def _get_theme_file_path(self, theme_name: str) -> Optional[str]:
        """
        테마 이름에 해당하는 외부 .qss 파일 경로를 반환합니다.

        Args:
            theme_name (str): 테마 이름 (예: 'dark').

        Returns:
            Optional[str]: 파일 경로 문자열. 없으면 None.
        """
        if not self._theme_dir.exists():
            return None

        # 파일명 규칙: {theme_name}_theme.qss (소문자 기준)
        filename = f"{theme_name.lower()}_theme.qss"
        
        # ResourcePath를 통해 경로 획득 시도
        path_obj = self._resource_path.get_theme_path(filename)
        
        if path_obj:
            return str(path_obj)
            
        # 직접 경로 조합 (Fallback)
        full_path = self._theme_dir / filename
        if full_path.exists():
            return str(full_path)
            
        return None

    # -------------------------------------------------------------------------
    # Font Management
    # -------------------------------------------------------------------------
    def set_proportional_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """
        UI 전반에 사용될 가변폭 폰트(Proportional Font)를 설정합니다.

        Logic:
            - 내부 변수 업데이트
            - Qt Application 기본 폰트 설정
            - apply_now=True일 경우 테마 재적용

        Args:
            family (str): 폰트 패밀리명.
            size (int): 폰트 크기.
            apply_now (bool): 즉시 갱신 여부.
        """
        self._proportional_font = QFont(family, size)

        # Qt 애플리케이션 기본 폰트 설정
        app = QApplication.instance()
        if app:
            app.setFont(self._proportional_font)
            # 스타일시트에도 반영하기 위해 테마 재적용
            if apply_now:
                self.apply_theme(self._current_theme)

    def get_proportional_font(self) -> QFont:
        """
        현재 설정된 가변폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._proportional_font)

    def get_proportional_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 가변폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._proportional_font.family(), self._proportional_font.pointSize()

    def set_fixed_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """
        로그 및 데이터 뷰에 사용될 고정폭 폰트(Fixed Font)를 설정합니다.

        Args:
            family (str): 폰트 패밀리명.
            size (int): 폰트 크기.
            apply_now (bool): 즉시 갱신 여부.
        """
        self._fixed_font = QFont(family, size)
        self._fixed_font.setStyleHint(QFont.Monospace)
        if apply_now:
            self.apply_theme(self._current_theme)

    def get_fixed_font(self) -> QFont:
        """
        현재 설정된 고정폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._fixed_font)

    def get_fixed_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 고정폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._fixed_font.family(), self._fixed_font.pointSize()

    def get_font_settings(self) -> FontConfig:
        """
        현재 폰트 설정 전체를 DTO로 반환합니다.

        Returns:
            FontConfig: 폰트 설정 DTO.
        """
        prop_fam, prop_size = self.get_proportional_font_info()
        fixed_fam, fixed_size = self.get_fixed_font_info()
        return FontConfig(
            prop_family=prop_fam,
            prop_size=prop_size,
            fixed_family=fixed_fam,
            fixed_size=fixed_size
        )

    def restore_fonts_from_settings(self, settings: Dict[str, Any]) -> None:
        """
        설정 딕셔너리로부터 폰트 설정을 복원합니다.
        (앱 초기화 시 SettingsManager로부터 데이터를 주입받을 때 사용)

        Logic:
            - 설정 딕셔너리에서 ui 섹션 조회
            - 저장된 폰트 정보가 있으면 내부 상태 업데이트
            - 적용(Apply)은 수행하지 않음 (LifecycleManager에서 일괄 처리)

        Args:
            settings (Dict[str, Any]): 설정 데이터 딕셔너리.
        """
        ui_settings = settings.get("ui", {})

        # 가변폭 폰트 복원
        prop_family = ui_settings.get(ConfigKeys.PROP_FONT_FAMILY)
        prop_size = ui_settings.get(ConfigKeys.PROP_FONT_SIZE)
        if prop_family and prop_size:
            self._proportional_font = QFont(prop_family, prop_size)

        # 고정폭 폰트 복원
        fixed_family = ui_settings.get(ConfigKeys.FIXED_FONT_FAMILY)
        fixed_size = ui_settings.get(ConfigKeys.FIXED_FONT_SIZE)
        if fixed_family and fixed_size:
            self._fixed_font = QFont(fixed_family, fixed_size)
            self._fixed_font.setStyleHint(QFont.Monospace)

    def _generate_font_stylesheet(self) -> str:
        """
        현재 폰트 설정을 기반으로 CSS 폰트 규칙을 생성합니다.

        Logic:
            - 가변폭 폰트: 전역 위젯(*)에 적용 (일부 특수 위젯 제외)
            - 고정폭 폰트: 텍스트 에디터, 테이블 뷰, .fixed-font 클래스에 적용

        Returns:
            str: 폰트 관련 QSS 문자열.
        """
        prop_fam = self._proportional_font.family()
        prop_size = self._proportional_font.pointSize()
        fixed_fam = self._fixed_font.family()
        fixed_size = self._fixed_font.pointSize()

        return f"""
        /* Proportional Font (Global) */
        * {{
            font-family: "{prop_fam}", "Malgun Gothic", sans-serif;
            font-size: {prop_size}pt;
        }}

        /* Fixed Font (Log/Data Views) */
        .fixed-font, QTextEdit, QPlainTextEdit, QTableView, QSmartTextEdit, QSmartListView {{
            font-family: "{fixed_fam}", "Consolas", monospace;
            font-size: {fixed_size}pt;
        }}

        /* Table Header uses Proportional Font */
        QHeaderView::section {{
            font-family: "{prop_fam}", "Malgun Gothic", sans-serif;
            font-size: {prop_size}pt;
        }}
        """

    # -------------------------------------------------------------------------
    # Theme Application
    # -------------------------------------------------------------------------
    def load_theme_file_content(self, theme_name: str) -> str:
        """
        지정된 테마 파일 및 공통 파일을 로드하고 경로를 치환하여 QSS 문자열을 반환합니다.

        Logic:
            1. common.qss 로드
            2. {theme_name}_theme.qss 로드
            3. 리소스 경로(url)를 절대 경로로 치환 (PyInstaller 대응)

        Args:
            theme_name (str): 테마 이름.

        Returns:
            str: 처리된 QSS 문자열.
        """
        theme_path = self._get_theme_file_path(theme_name)
        
        # common.qss 경로 찾기
        common_path_obj = self._resource_path.get_theme_path('common') 
        if not common_path_obj:
             common_path = str(self._theme_dir / 'common.qss')
        else:
             common_path = str(common_path_obj)

        qss_content = ""

        # 1. 공통 QSS 로드
        if os.path.exists(common_path):
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
                logger.debug(f"Loaded theme from file: {theme_path}")
            except Exception as e:
                logger.error(f"Error loading theme {theme_name}: {e}")
        else:
            logger.warning(f"Theme file not found: {theme_path}")

        # 3. 리소스 경로 절대 경로 치환
        # (예: url(resources/icons/...) -> url(C:/App/resources/icons/...))
        base_res_path = str(self._resource_path.base_dir).replace('\\', '/')
        qss_content = qss_content.replace('url(resources/', f'url({base_res_path}/resources/')

        return qss_content

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
        # [중요] 순환 참조 방지를 위해 함수 내부에서 import
        from view.managers.color_manager import color_manager

        app = QApplication.instance()
        if not app:
            logger.warning("QApplication instance not found. Theme might not apply immediately.")
            return

        theme_name = theme_name.lower()
        
        # 파일 경로 확인 (유효성 검사)
        file_path = self._get_theme_file_path(theme_name)
        if not file_path and theme_name not in ["dark", "light"]:
            logger.warning(f"Unknown theme '{theme_name}'. Falling back to 'dark'.")
            theme_name = "dark"

        previous_theme = self._current_theme
        self._current_theme = theme_name
        self._app = app  # App 인스턴스 저장

        # Fallback용 색상 팔레트 선택
        is_dark = self.is_dark_theme()
        colors = self.THEME_DARK if is_dark else self.THEME_LIGHT

        # 1. QPalette 적용
        palette = self._create_palette(colors)
        app.setPalette(palette)

        # 2. Stylesheet 로드
        # 파일에서 로드 시도 (common.qss 포함)
        stylesheet = self.load_theme_file_content(theme_name)
        
        # 파일 로드 실패 또는 내용 없음 -> Fallback 생성
        if not stylesheet.strip():
            stylesheet = self._get_fallback_stylesheet(colors, theme_name)

        # 3. 폰트 스타일 병합
        font_qss = self._generate_font_stylesheet()
        full_stylesheet = stylesheet + "\n" + font_qss

        app.setStyleSheet(full_stylesheet)

        # 4. ColorManager 업데이트 (구문 강조 등)
        color_manager.update_theme(theme_name)

        # 로그 출력 제어
        if previous_theme != theme_name:
            logger.info(f"Theme changed to '{theme_name}'.")
        else:
            logger.debug(f"Theme '{theme_name}' refreshed (style/font update).")

    def get_current_theme(self) -> str:
        """현재 적용된 테마 이름을 반환합니다."""
        return self._current_theme

    def _create_palette(self, c: Dict[str, str]) -> QPalette:
        """
        색상 딕셔너리를 기반으로 QPalette 객체를 생성합니다.

        Args:
            c (Dict[str, str]): 색상 맵.

        Returns:
            QPalette: 설정된 팔레트 객체.
        """
        palette = QPalette()

        # 기본 색상 설정
        palette.setColor(QPalette.Window, QColor(c["bg_alt"]))
        palette.setColor(QPalette.WindowText, QColor(c["fg_primary"]))
        palette.setColor(QPalette.Base, QColor(c["bg_base"]))
        palette.setColor(QPalette.AlternateBase, QColor(c["bg_alt"]))
        palette.setColor(QPalette.ToolTipBase, QColor(c["bg_alt"]))
        palette.setColor(QPalette.ToolTipText, QColor(c["fg_primary"]))
        palette.setColor(QPalette.Text, QColor(c["fg_primary"]))
        palette.setColor(QPalette.Button, QColor(c["bg_alt"]))
        palette.setColor(QPalette.ButtonText, QColor(c["fg_primary"]))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(c["accent"]))
        palette.setColor(QPalette.Highlight, QColor(c["selection"]))
        palette.setColor(QPalette.HighlightedText, QColor(c["fg_primary"]))

        # 비활성 상태 색상
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c["fg_secondary"]))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(c["fg_secondary"]))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(c["fg_secondary"]))

        return palette

    def _get_fallback_stylesheet(self, c: Dict[str, str], theme_name: str) -> str:
        """
        외부 파일이 없을 경우 사용할 기본 스타일시트를 생성합니다.

        Logic:
            - 색상 변수(c)를 주입하여 동적 QSS 문자열 생성
            - 테마별(Dark/Light) 특화 스타일(Tooltip 등) 추가

        Args:
            c (Dict[str, str]): 색상 맵.
            theme_name (str): 테마 이름.

        Returns:
            str: QSS 문자열.
        """
        qss = f"""
        /* 전역 위젯 배경/글자색 (폰트는 _generate_font_stylesheet에서 처리) */
        QWidget {{
            background-color: {c['bg_alt']};
            color: {c['fg_primary']};
            selection-background-color: {c['selection']};
            selection-color: {c['fg_primary']};
        }}
        
        QMainWindow {{
            background-color: {c['bg_alt']};
        }}

        /* 입력 필드 */
        QLineEdit, QSpinBox, QComboBox {{
            background-color: {c['bg_input']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 2px;
            color: {c['fg_primary']};
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border: 1px solid {c['accent']};
        }}
        QLineEdit:read-only {{
            background-color: {c['bg_alt']};
            color: {c['fg_secondary']};
        }}

        /* 텍스트 에디터 배경 (폰트는 별도 적용) */
        QTextEdit, QPlainTextEdit {{
            background-color: {c['bg_input']};
            border: 1px solid {c['border']};
            color: {c['fg_primary']};
        }}

        /* 버튼 */
        QPushButton {{
            background-color: {c['button_bg']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 5px 10px;
            min-width: 60px;
        }}
        QPushButton:hover {{
            background-color: {c['button_hover']};
            border-color: {c['accent']};
        }}
        QPushButton:pressed {{
            background-color: {c['selection']};
        }}
        QPushButton:disabled {{
            background-color: {c['bg_alt']};
            color: {c['fg_secondary']};
            border-color: {c['border']};
        }}

        /* 체크박스 */
        QCheckBox {{
            spacing: 5px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {c['border']};
            background: {c['bg_input']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c['accent']};
            border: 1px solid {c['accent']};
        }}

        /* 그룹박스 */
        QGroupBox {{
            border: 1px solid {c['border']};
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            left: 10px;
            color: {c['accent']};
        }}

        /* 테이블 뷰 */
        QTableView {{
            background-color: {c['bg_base']};
            gridline-color: {c['table_grid']};
            border: 1px solid {c['border']};
            selection-background-color: {c['selection']};
        }}
        QHeaderView::section {{
            background-color: {c['button_bg']};
            color: {c['fg_primary']};
            border: 1px solid {c['table_grid']};
            padding: 4px;
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {c['button_bg']};
            border: 1px solid {c['table_grid']};
        }}
        
        /* 탭 위젯 */
        QTabWidget::pane {{
            border: 1px solid {c['border']};
            background-color: {c['bg_base']};
        }}
        QTabBar::tab {{
            background-color: {c['bg_alt']};
            border: 1px solid {c['border']};
            padding: 6px 12px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {c['bg_base']};
            border-bottom-color: {c['bg_base']};
            color: {c['accent']};
            font-weight: bold;
        }}
        QTabBar::tab:hover {{
            background-color: {c['button_hover']};
        }}

        /* 스크롤바 */
        QScrollBar:vertical {{
            border: none;
            background: {c['scrollbar_bg']};
            width: 12px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {c['scrollbar_handle']};
            min-height: 20px;
            border-radius: 6px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            border: none;
            background: {c['scrollbar_bg']};
            height: 12px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['scrollbar_handle']};
            min-width: 20px;
            border-radius: 6px;
        }}

        /* 스플리터 */
        QSplitter::handle {{
            background-color: {c['border']};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}

        /* 메뉴바 */
        QMenuBar {{
            background-color: {c['bg_alt']};
            border-bottom: 1px solid {c['border']};
        }}
        QMenuBar::item {{
            spacing: 3px;
            padding: 1px 4px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background-color: {c['selection']};
        }}
        QMenu {{
            background-color: {c['bg_alt']};
            border: 1px solid {c['border']};
        }}
        QMenu::item {{
            padding: 4px 20px;
        }}
        QMenu::item:selected {{
            background-color: {c['selection']};
        }}
        """

        if theme_name == "dark":
            qss += f"""
            QToolTip {{
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid #767676;
            }}
            """

        return qss

# 전역 싱글톤 인스턴스 생성
theme_manager = ThemeManager()