import os
import platform
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

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
    
    def __init__(self):
        """ThemeManager를 초기화하고 플랫폼별 기본 폰트를 설정합니다."""
        self._current_theme = "dark"
        self._app = None
        
        # 플랫폼 확인
        system = platform.system()
        
        # 플랫폼에 따른 기본 폰트 설정
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))
        
        self._proportional_font = QFont(prop_family, prop_size)
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)
    
    @staticmethod
    def load_theme(theme_name: str = "dark") -> str:
        """
        지정된 테마의 QSS 콘텐츠를 로드합니다. 공통 스타일을 먼저 로드합니다.
        
        Args:
            theme_name (str): 로드할 테마 이름 ("dark" 또는 "light"). 기본값은 "dark".
            
        Returns:
            str: 결합된 QSS 문자열.
        """
        common_path = "resources/themes/common.qss"
        theme_files = {
            "dark": "resources/themes/dark_theme.qss",
            "light": "resources/themes/light_theme.qss"
        }
        
        qss_content = ""
        
        # 1. 공통 QSS 로드
        if os.path.exists(common_path):
            try:
                with open(common_path, "r", encoding="utf-8") as f:
                    qss_content += f.read() + "\n"
            except Exception as e:
                print(f"공통 테마 로드 오류: {e}")
        else:
            print(f"공통 테마 파일을 찾을 수 없음: {common_path}")
            
        # 2. 특정 테마 QSS 로드
        qss_path = theme_files.get(theme_name)
        if qss_path and os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    qss_content += f.read()
            except Exception as e:
                print(f"테마 {theme_name} 로드 오류: {e}")
        else:
            print(f"테마 파일을 찾을 수 없음: {qss_path}")
            
        return qss_content

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
            print(f"테마 적용 실패: {theme_name}")
            
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
        return (self._proportional_font.family(), self._proportional_font.pointSize())
    
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
        return (self._fixed_font.family(), self._fixed_font.pointSize())
    
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

