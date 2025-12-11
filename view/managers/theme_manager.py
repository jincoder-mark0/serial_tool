import os
import platform
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon
from core.logger import logger

class ThemeManager:
    """애플리케이션 테마와 폰트를 관리하는 클래스입니다."""

    # 플랫폼별 기본 폰트 설정
    _PROPORTIONAL_FONTS = {
        "Windows": ("Segoe UI", 9),
        "Linux": ("Ubuntu", 9),
        "Darwin": ("SF Pro Text", 9)  # macOS
    }

    _FIXED_FONTS = {
        "Windows": ("Consolas", 9),
        "Linux": ("Monospace", 9),
        "Darwin": ("Menlo", 9)  # macOS
    }

    def __init__(self, resource_path=None):
        """
        ThemeManager를 초기화하고 플랫폼별 기본 폰트를 설정합니다.

        Args:
            resource_path: ResourcePath 인스턴스. None이면 기본 경로 사용 (하위 호환성)
        """
        self._current_theme = "dark"
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

    def load_theme(self, theme_name: str = "dark") -> str:
        """
        지정된 테마의 QSS 콘텐츠를 로드합니다. 공통 스타일을 먼저 로드합니다.

        Args:
            theme_name (str): 로드할 테마 이름 ("dark" 또는 "light"). 기본값은 "dark".

        Returns:
            str: 결합된 QSS 문자열.
        """
        if self._resource_path is not None:
            # AppConfig가 제공되었으면 그것을 사용
            common_path = self._resource_path.get_theme_file('common')
            theme_path = self._resource_path.get_theme_file(theme_name)
        else:
            # 하위 호환성: 기존 경로 사용
            common_path = "resources/themes/common.qss"
            theme_files = {
                "dark": "resources/themes/dark_theme.qss",
                "light": "resources/themes/light_theme.qss"
            }
            theme_path = theme_files.get(theme_name)

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
        if theme_name == "dark":
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

    def apply_theme(self, app: QApplication, theme_name: str = "dark"):
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

    def _generate_font_stylesheet(self) -> str:
        """
        현재 폰트 설정에 대한 QSS를 생성합니다.

        Returns:
            str: 폰트 설정이 포함된 QSS 문자열.
        """
        prop_family = self._proportional_font.family()
        prop_size = self._proportional_font.pointSize()

        fixed_family = self._fixed_font.family()
        fixed_size = self._fixed_font.pointSize()

        return f"""
        /* 동적 폰트 설정 */

        /* 전역 폰트 (가변폭) */
        QWidget {{
            font-family: "{prop_family}", sans-serif;
            font-size: {prop_size}pt;
        }}

        .proportional-font {{
            font-family: "{prop_family}", sans-serif;
            font-size: {prop_size}pt;
        }}

        .fixed-font {{
            font-family: "{fixed_family}", monospace;
            font-size: {fixed_size}pt;
        }}

        /* 고정폭 폰트를 텍스트 데이터 위젯에 적용 */
        QTextEdit.fixed-font,
        QPlainTextEdit.fixed-font,
        QLineEdit.fixed-font,
        QTableView.fixed-font {{
            font-family: "{fixed_family}", monospace;
            font-size: {fixed_size}pt;
        }}
        """

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

    def get_font_settings(self) -> dict:
        """
        현재 폰트 설정을 딕셔너리로 반환합니다.

        Returns:
            dict: 폰트 설정 딕셔너리 (저장용).
        """
        prop_family, prop_size = self.get_proportional_font_info()
        fixed_family, fixed_size = self.get_fixed_font_info()

        return {
            "proportional_font_family": prop_family,
            "proportional_font_size": prop_size,
            "fixed_font_family": fixed_family,
            "fixed_font_size": fixed_size
        }

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
        다크 테마인 경우 밝은 아이콘(_dark.svg)을, 라이트 테마인 경우 어두운 아이콘(_light.svg)을 찾습니다.

        Args:
            name (str): 아이콘 이름 (예: "add").

        Returns:
            QIcon: 테마에 맞는 QIcon 객체.
        """
        if self._resource_path is not None:
            # AppConfig가 제공되었으면 그것을 사용
            icon_path = self._resource_path.get_icon_path(name, self._current_theme)

            if not os.path.exists(icon_path):
                # 폴백: 테마 접미사 없이 시도
                fallback_path = self._resource_path.get_icon_path(name)
                if os.path.exists(fallback_path):
                    return QIcon(str(fallback_path))
                return QIcon()

            return QIcon(str(icon_path))
        else:
            # 하위 호환성: 기존 경로 사용
            icon_path = f"resources/icons/{name}_{self._current_theme}.svg"

            if not os.path.exists(icon_path):
                # 폴백: 테마 접미사 없이 시도
                fallback_path = f"resources/icons/{name}.svg"
                if os.path.exists(fallback_path):
                    return QIcon(fallback_path)
                # 파일이 없으면 빈 아이콘 반환
                return QIcon()

            return QIcon(icon_path)

