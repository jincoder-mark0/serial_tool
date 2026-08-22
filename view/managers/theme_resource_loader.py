"""
테마 리소스 로더 모듈

아이콘 해석, 테마 파일 탐색, QSS 로드·폴백·팔레트 생성을 담당합니다.

## WHY
* `ThemeManager`(833줄, S-050 조사)의 6가지 관심사 중 "리소스에서 무엇을 읽어올지"만
  떼어낸다 — 싱글톤 수명·폰트·오케스트레이션과 분리하면 아이콘 라우팅이나 QSS 폴백
  로직만 독립적으로 테스트할 수 있다 (S-053).
* S-050이 발견한 캐싱 함정을 이번에 함께 고친다: 기존 `ThemeManager.__init__`은
  `self._theme_dir`를 생성 시점에 한 번만 캐싱해서, 이후 `_resource_path`만
  재주입해도 테마 경로 리다이렉트가 무효였다. 이 로더는 `themes_dir`/`icons_dir`를
  프로퍼티로 두고 매번 `self.resource_path`에서 다시 읽으므로, `resource_path`
  교체만으로 즉시 반영된다.

## WHAT
* `get_icon`: 아이콘 이름 -> 테마별 디렉터리 우선 검색, 실패 시 폴백 경로들을
  순서대로 시도.
* `get_available_themes`/`get_theme_file_path`: 테마 파일 탐색.
* `load_theme_file_content`: common.qss + `{theme}_theme.qss` 병합, 리소스 절대
  경로 치환.
* `get_theme_colors`/`create_palette`/`get_fallback_stylesheet`: 외부 QSS 파일이
  없을 때 쓰는 폴백용 색상 팔레트(Dict)와 QPalette/QSS 생성.

## HOW
* `resource_path`를 인스턴스 속성으로 보관하되, 파생 경로(`icons_dir`/`themes_dir`)는
  캐싱하지 않고 프로퍼티로 매번 다시 계산한다.
"""
import os
from typing import Dict, List, Optional

from PyQt5.QtGui import QPalette, QColor, QIcon
from PyQt5.QtCore import Qt

from core.logger import logger
from core.resource_path import ResourcePath
from common.enums import ThemeType


class ThemeResourceLoader:
    """
    테마 관련 자원(아이콘·테마 파일·QSS·팔레트)을 읽어오는 역할만 담당하는 클래스
    (ThemeManager로부터 분리, S-053).
    """

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

    def __init__(self, resource_path: ResourcePath) -> None:
        """
        ThemeResourceLoader 초기화.

        Args:
            resource_path: 리소스 경로 소스. 이후 `resource_path` 속성을 직접
                재주입하면 `icons_dir`/`themes_dir`도 다음 접근부터 즉시 따라간다.
        """
        self.resource_path = resource_path

    # -------------------------------------------------------------------------
    # 파생 경로 (캐싱하지 않는다 - S-050/S-053 캐싱 함정 수정)
    # -------------------------------------------------------------------------
    @property
    def icons_dir(self):
        """아이콘 디렉터리 경로. 매 접근마다 `resource_path`에서 다시 읽는다."""
        return self.resource_path.icons_dir

    @property
    def themes_dir(self):
        """테마 디렉터리 경로. 매 접근마다 `resource_path`에서 다시 읽는다."""
        return self.resource_path.themes_dir

    # -------------------------------------------------------------------------
    # Icon Resolution
    # -------------------------------------------------------------------------
    def get_icon(self, icon_name: str, current_theme: str) -> QIcon:
        """
        아이콘 이름(파일명)을 받아 지정된 테마에 맞는 QIcon 객체를 반환합니다.

        Logic:
            1. 테마별 아이콘({name}_{theme}.svg) 우선 검색
            2. 실패 시 기본 아이콘({name}.svg/png) 검색
            3. 확장자가 없으면 .png를 기본으로 시도

        Args:
            icon_name (str): 아이콘 파일명 (예: 'add', 'settings.png').
            current_theme (str): 라우팅 기준이 되는 테마 이름 (예: 'dark').

        Returns:
            QIcon: 로드된 아이콘 객체.
        """
        # 테마 접미사 결정을 위한 타겟 테마 확인
        # 실제 테마명을 그대로 사용 (dark/light/dracula 각각의 아이콘 디렉토리 존재)
        target_theme = current_theme.lower()
        valid_suffixes = {ThemeType.DARK.value, ThemeType.LIGHT.value, ThemeType.DRACULA.value}
        if target_theme in valid_suffixes:
            theme_suffix = target_theme
        else:
            # 미확인 테마는 dark로 폴백
            theme_suffix = ThemeType.DARK.value

        # 1. 테마별 아이콘 시도 (ResourcePath 활용)
        icon_path = self.resource_path.get_icon_path(icon_name, theme_suffix)

        if not icon_path.exists():
            # 2. 폴백: 테마 접미사 없이 시도
            icon_path = self.resource_path.get_icon_path(icon_name)

        # 3. 직접 경로 확인 (확장자 처리 등 ResourcePath가 실패했을 경우 대비)
        if not icon_path.exists():
            if not icon_name.endswith(('.png', '.svg', '.ico')):
                filename = f"{icon_name}.png"
            else:
                filename = icon_name
            full_path = self.icons_dir / filename
            if full_path.exists():
                return QIcon(str(full_path))
        else:
            return QIcon(str(icon_path))

        return QIcon()

    # -------------------------------------------------------------------------
    # Theme File Discovery
    # -------------------------------------------------------------------------
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

        if not self.themes_dir.exists():
            return themes

        try:
            for filename in os.listdir(self.themes_dir):
                if filename.endswith("_theme.qss"):
                    # 예: dracula_theme.qss -> Dracula
                    name = filename.replace("_theme.qss", "").capitalize()
                    if name not in themes:
                        themes.append(name)
        except Exception as e:
            logger.error(f"Error scanning themes directory: {e}")
            return ["Dark", "Light"]

        return sorted(themes)

    def get_theme_file_path(self, theme_name: str) -> Optional[str]:
        """
        테마 이름에 해당하는 외부 .qss 파일 경로를 반환합니다.

        Args:
            theme_name (str): 테마 이름 (예: 'dark').

        Returns:
            Optional[str]: 파일 경로 문자열. 없으면 None.
        """
        if not self.themes_dir.exists():
            return None

        theme_key = theme_name.lower()
        # 파일명 규칙: {theme_name}_theme.qss (소문자 기준)
        filename = f"{theme_key}_theme.qss"

        # ResourcePath 딕셔너리 조회 (테마 키 기준 - 정상 경로)
        path_obj = self.resource_path.get_theme_path(theme_key)

        if path_obj and path_obj.exists():
            return str(path_obj)

        # 직접 경로 조합 (Fallback) - ResourcePath.theme_files에 미등록된 테마
        full_path = self.themes_dir / filename
        if full_path.exists():
            logger.warning(
                f"Theme '{theme_key}' not registered in ResourcePath.theme_files; "
                f"using direct path fallback: {full_path}"
            )
            return str(full_path)

        return None

    # -------------------------------------------------------------------------
    # QSS Loading
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
        theme_path = self.get_theme_file_path(theme_name)

        # common.qss 경로 찾기
        common_path_obj = self.resource_path.get_theme_path('common')
        if not common_path_obj:
            common_path = str(self.themes_dir / 'common.qss')
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
        base_res_path = str(self.resource_path.base_dir).replace('\\', '/')
        qss_content = qss_content.replace('url(resources/', f'url({base_res_path}/resources/')

        return qss_content

    # -------------------------------------------------------------------------
    # Fallback Palette / Stylesheet
    # -------------------------------------------------------------------------
    def get_theme_colors(self, is_dark: bool) -> Dict[str, str]:
        """
        폴백용 색상 팔레트(Dict)를 반환합니다.

        Args:
            is_dark (bool): 어두운 테마 계열 여부.

        Returns:
            Dict[str, str]: 색상 맵.
        """
        return self.THEME_DARK if is_dark else self.THEME_LIGHT

    def create_palette(self, c: Dict[str, str]) -> QPalette:
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

    def get_fallback_stylesheet(self, c: Dict[str, str], theme_name: str) -> str:
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
        /* Global widget background/text color (font handled in _generate_font_stylesheet) */
        QWidget {{
            background-color: {c['bg_alt']};
            color: {c['fg_primary']};
            selection-background-color: {c['selection']};
            selection-color: {c['fg_primary']};
        }}

        QMainWindow {{
            background-color: {c['bg_alt']};
        }}

        /* Input fields */
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

        /* Text editor background (font applied separately) */
        QTextEdit, QPlainTextEdit {{
            background-color: {c['bg_input']};
            border: 1px solid {c['border']};
            color: {c['fg_primary']};
        }}

        /* Buttons */
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

        /* Checkbox */
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

        /* GroupBox */
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

        /* Table view */
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

        /* Tab widget */
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

        /* Scrollbar */
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

        /* Splitter */
        QSplitter::handle {{
            background-color: {c['border']};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}

        /* Menu bar */
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
            qss += """
            QToolTip {
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid #767676;
            }
            """

        return qss
