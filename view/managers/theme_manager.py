"""
테마 관리자 모듈

애플리케이션의 전체적인 룩앤필(Look & Feel)을 관리하는 싱글톤 클래스입니다.
Dark/Light 모드 전환, 외부 QSS 파일 로드, 동적 색상/폰트 적용을 담당합니다.

## WHY
* 운영체제 설정이나 사용자 선호에 따른 시각적 테마 제공 필요
* 위젯별 색상 하드코딩 방지 및 중앙 집중식 스타일 관리 (유지보수성)
* 런타임 폰트 변경 및 외부 스타일시트 파일 지원을 통한 확장성 확보

## WHAT
* 테마별 색상 팔레트(Dict) 정의
* QSS(Qt Style Sheet) 로드 및 생성 (파일 로드 시도 -> 실패 시 코드 생성)
* 아이콘 파일 로드 (get_icon) 및 폰트 설정 관리
* QPalette 및 Application StyleSheet 적용

## HOW
* Singleton 패턴으로 전역 접근 허용
* 외부 .qss 파일 존재 시 우선 로드, 없을 경우 내부 f-string 템플릿 사용 (Fallback)
* 폰트 설정은 별도 메서드(_generate_font_stylesheet)로 분리하여 동적 병합
"""
import os
from typing import Dict, Any, Optional, List, Tuple

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor, QIcon, QFont
from PyQt5.QtCore import Qt, QObject

from core.logger import logger

from common.enums import ThemeType
from common.dtos import FontConfig

class ThemeManager(QObject):
    """
    애플리케이션 테마(색상, 스타일, 아이콘, 폰트)를 관리하는 관리자 클래스
    """

    _instance = None

    # -------------------------------------------------------------------------
    # 테마 색상 정의 (Color Definitions)
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

    def __init__(self, resource_path: Optional[str] = None) -> None:
        """
        ThemeManager 초기화

        Logic:
            - 플래그 체크로 중복 초기화 방지
            - super().__init__() 호출 (QObject 필수)
            - 리소스 경로 저장 및 초기 테마 설정
            - 기본 폰트 설정

        Args:
            resource_path (Optional[str]): 리소스 파일 경로 (main.py에서 전달됨).
        """
        # 싱글톤 중복 초기화 방지
        if hasattr(self, '_initialized') and self._initialized:
            return

        super().__init__()

        self._resource_path = resource_path
        self._current_theme = "dark"  # 기본값

        # 기본 폰트 설정 (Family, Size)
        self._font_prop = ("Segoe UI", 9)
        self._font_fixed = ("Consolas", 10)

        # 아이콘 디렉토리 경로 설정
        if self._resource_path:
             self._icon_dir = os.path.join(self._resource_path, 'icons')
             self._theme_dir = os.path.join(self._resource_path, 'themes')
        else:
            # Fallback: 현재 파일 기준 상대 경로
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._icon_dir = os.path.join(base_dir, '..', '..', 'resources', 'icons')
            self._theme_dir = os.path.join(base_dir, '..', '..', 'resources', 'themes')

        self._initialized = True

    # -------------------------------------------------------------------------
    # Resource Access (Icon, Theme File)
    # -------------------------------------------------------------------------
    def get_icon(self, icon_name: str) -> QIcon:
        """
        아이콘 이름(파일명)을 받아 QIcon 객체를 반환합니다.

        Logic:
            1. 아이콘 디렉토리에서 파일 탐색
            2. 확장자가 없으면 .png를 기본으로 시도
            3. 파일이 존재하면 QIcon 생성, 없으면 빈 아이콘 반환

        Args:
            icon_name (str): 아이콘 파일명 (예: 'add', 'settings.png').

        Returns:
            QIcon: 로드된 아이콘 객체.
        """
        if not icon_name.endswith(('.png', '.svg', '.ico')):
            filename = f"{icon_name}.png"
        else:
            filename = icon_name

        full_path = os.path.join(self._icon_dir, filename)

        if os.path.exists(full_path):
            return QIcon(full_path)
        else:
            return QIcon()

    def get_available_themes(self) -> List[str]:
        """
        사용 가능한 테마 목록 반환 (파일 스캔 방식)

        Logic:
            - themes 디렉토리의 파일 스캔
            - '*_theme.qss' 패턴과 일치하는 파일 찾기
            - 파일명에서 '_theme.qss' 제거 후 대문자 변환하여 반환
            - 실패 시 기본 목록 반환

        Returns:
            List[str]: 테마 이름 리스트 (예: ['Dark', 'Light', 'Dracula']).
        """
        themes = ["Dark", "Light"]  # 기본 제공 테마

        if not os.path.exists(self._theme_dir):
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
            bool: 어두운 테마면 True, 밝은 테마면 False
        """
        current = self._current_theme.lower()
        return current in [ThemeType.DARK.value, ThemeType.DRACULA.value]

    def _get_theme_file_path(self, theme_name: str) -> Optional[str]:
        """
        테마 이름에 해당하는 외부 .qss 파일 경로를 반환합니다.

        Args:
            theme_name (str): 테마 이름 (예: 'dark').

        Returns:
            Optional[str]: 파일 경로. 없으면 None.
        """
        if not os.path.exists(self._theme_dir):
            return None

        # 파일명 규칙: {theme_name}_theme.qss (소문자 기준)
        filename = f"{theme_name.lower()}_theme.qss"
        full_path = os.path.join(self._theme_dir, filename)

        if os.path.exists(full_path):
            return full_path
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
        self._font_prop = (family, size)

        # Qt 애플리케이션 기본 폰트 설정
        font = QFont(family, size)
        app = QApplication.instance()
        if app:
            app.setFont(font)
            # 스타일시트에도 반영하기 위해 테마 재적용
            if apply_now:
                self.apply_theme(self._current_theme)

    def get_proportional_font(self) -> QFont:
        """
        현재 설정된 가변폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._font_prop[0], self._font_prop[1])

    def get_proportional_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 가변폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._font_prop

    def set_fixed_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """
        로그 및 데이터 뷰에 사용될 고정폭 폰트(Fixed Font)를 설정합니다.

        Args:
            family (str): 폰트 패밀리명.
            size (int): 폰트 크기.
            apply_now (bool): 즉시 갱신 여부.
        """
        self._font_fixed = (family, size)
        if apply_now:
            self.apply_theme(self._current_theme)

    def get_fixed_font(self) -> QFont:
        """
        현재 설정된 고정폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._font_fixed[0], self._font_fixed[1])

    def get_fixed_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 고정폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._font_fixed

    def get_font_settings(self) -> FontConfig:
        """
        현재 폰트 설정 전체를 DTO로 반환합니다.

        Returns:
            FontConfig: 폰트 설정 DTO.
        """
        prop_family, prop_size = self.get_proportional_font_info()
        fixed_family, fixed_size = self.get_fixed_font_info()
        return FontConfig(
            prop_family=prop_family,
            prop_size=prop_size,
            fixed_family=fixed_family,
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

    def _generate_font_stylesheet(self) -> str:
        """
        현재 폰트 설정을 기반으로 CSS 폰트 규칙을 생성합니다.

        Logic:
            - 가변폭 폰트: 전역 위젯(*)에 적용 (일부 특수 위젯 제외)
            - 고정폭 폰트: 텍스트 에디터, 테이블 뷰, .fixed-font 클래스에 적용

        Returns:
            str: 폰트 관련 QSS 문자열.
        """
        prop_fam, prop_size = self._font_prop
        fixed_fam, fixed_size = self._font_fixed

        return f"""
        /* Proportional Font (Global) */
        QWidget {{
            font-family: '{prop_fam}', 'Malgun Gothic', sans-serif;
            font-size: {prop_size}pt;
        }}

        /* Fixed Font (Log/Data Views) */
        QTextEdit, QPlainTextEdit, QTableView, .fixed-font {{
            font-family: '{fixed_fam}', 'Consolas', monospace;
            font-size: {fixed_size}pt;
        }}

        /* Table Header uses Proportional Font */
        QHeaderView::section {{
            font-family: '{prop_fam}', 'Malgun Gothic', sans-serif;
            font-size: {prop_size}pt;
        }}
        """

    # -------------------------------------------------------------------------
    # Theme Application
    # -------------------------------------------------------------------------
    def apply_theme(self, theme_name: str = "dark") -> None:
        """
        지정된 테마를 애플리케이션 전체에 적용합니다.

        Logic:
            1. 테마 이름 유효성 확인 (기본값: dark)
            2. 해당 테마의 색상 맵 가져오기
            3. QPalette 설정 (Qt 기본 위젯 색상)
            4. Stylesheet 설정 (색상 및 폰트 주입)
            5. ColorManager 업데이트 (구문 강조 색상 동기화)

        Args:
            theme_name (str): 적용할 테마 이름 ('dark' 또는 'light').
        """
        from view.managers.color_manager import color_manager

        app = QApplication.instance()
        if not app:
            logger.warning("QApplication instance not found. Theme might not apply immediately.")
            return

        theme_name = theme_name.lower()
        if theme_name not in ["dark", "light"]:
            logger.warning(f"Unknown theme '{theme_name}'. Falling back to 'dark'.")
            theme_name = "dark"

        # 이전 테마와 비교를 위해 저장
        previous_theme = self._current_theme
        self._current_theme = theme_name

        # Fallback용 색상 팔레트 선택 (어두운 테마 계열은 Dark Palette 사용)
        is_dark = self.is_dark_theme()
        colors = self.THEME_DARK if is_dark else self.THEME_LIGHT

        # 1. QPalette 적용
        palette = self._create_palette(colors)
        app.setPalette(palette)

        # 2. Stylesheet 적용
        stylesheet = ""

        # 2-1. 외부 파일 확인
        file_path = self._get_theme_file_path(theme_name)
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    stylesheet = f.read()
                logger.debug(f"Loaded theme from file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to load theme file {file_path}: {e}")

        # 2-2. 파일이 없거나 비었으면 Fallback(내부 코드) 사용
        if not stylesheet:
            stylesheet = self._get_fallback_stylesheet(colors, theme_name)

        # 2-3. 폰트 스타일 병합
        font_qss = self._generate_font_stylesheet()
        full_stylesheet = stylesheet + "\n" + font_qss

        app.setStyleSheet(full_stylesheet)

        # 3. ColorManager 업데이트
        color_manager.update_theme(theme_name)

        # 불필요한 로그 노이즈 감소
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

        # 어두운 테마일 경우 ToolTip 스타일 추가
        if self.is_dark_theme():
            qss += f"""
            QToolTip {{
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid #767676;
            }}
            """

        return qss

# 전역에서 접근 가능한 싱글톤 인스턴스
theme_manager = ThemeManager()