"""
메인 메뉴바 모듈

애플리케이션의 상단 메뉴 구성을 담당합니다.

## WHY
* 기능 접근성 향상 및 단축키 안내
* 테마, 언어 등 동적 메뉴 항목의 관리

## WHAT
* File, View, Tools, Help 메뉴 구성
* 동적 테마/언어 목록 스캔 및 메뉴 아이템 생성
* 각 액션에 대한 시그널 정의

## HOW
* QMenuBar 상속
* ThemeManager/LanguageManager와 연동하여 메뉴 아이템 동적 생성
"""
from PyQt5.QtWidgets import QMenuBar, QAction, QActionGroup
from PyQt5.QtCore import pyqtSignal

from view.managers.language_manager import language_manager
from view.managers.theme_manager import ThemeManager

class MainMenuBar(QMenuBar):
    """
    메인 윈도우의 메뉴바를 관리하는 클래스입니다.
    테마와 언어 메뉴를 동적으로 구성합니다.
    """
    # Signals
    tab_new_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)
    font_settings_requested = pyqtSignal()
    language_changed = pyqtSignal(str)
    preferences_requested = pyqtSignal()
    about_requested = pyqtSignal()
    connect_requested = pyqtSignal()
    tab_close_requested = pyqtSignal()
    data_log_save_requested = pyqtSignal()
    toggle_right_section_requested = pyqtSignal(bool)
    file_transfer_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_action_group = None
        self.init_menu()

    def init_menu(self) -> None:
        """메뉴바를 초기화하고 액션을 설정합니다."""
        self.clear()

        # ---------------------------------------------------------
        # 1. 파일 메뉴 (File Menu)
        # ---------------------------------------------------------
        file_menu = self.addMenu(language_manager.get_text("main_menu_file"))

        new_tab_action = QAction(language_manager.get_text("main_menu_new_tab"), self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip(language_manager.get_text("main_menu_new_tab_tooltip"))
        new_tab_action.triggered.connect(self.tab_new_requested.emit)
        file_menu.addAction(new_tab_action)

        open_port_action = QAction(language_manager.get_text("main_menu_open_port"), self)
        open_port_action.setShortcut("Ctrl+O")
        open_port_action.triggered.connect(self.connect_requested.emit)
        file_menu.addAction(open_port_action)

        close_tab_action = QAction(language_manager.get_text("main_menu_close_tab"), self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(self.tab_close_requested.emit)
        file_menu.addAction(close_tab_action)

        save_data_log_action = QAction(language_manager.get_text("main_menu_save_data_log"), self)
        save_data_log_action.setShortcut("Ctrl+Shift+S")
        save_data_log_action.triggered.connect(self.data_log_save_requested.emit)
        file_menu.addAction(save_data_log_action)

        file_menu.addSeparator()

        exit_action = QAction(language_manager.get_text("main_menu_exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip(language_manager.get_text("main_menu_exit_tooltip"))
        exit_action.triggered.connect(self.exit_requested.emit)
        file_menu.addAction(exit_action)

        # ---------------------------------------------------------
        # 2. 보기 메뉴 (View Menu)
        # ---------------------------------------------------------
        view_menu = self.addMenu(language_manager.get_text("main_menu_view"))

        # Right Panel Toggle
        self.toggle_right_section_action = QAction(language_manager.get_text("main_menu_toggle_right_section"), self)
        self.toggle_right_section_action.setCheckable(True)
        self.toggle_right_section_action.triggered.connect(self.toggle_right_section_requested.emit)
        view_menu.addAction(self.toggle_right_section_action)

        view_menu.addSeparator()

        # 테마 서브메뉴 (Theme Submenu)
        theme_menu = view_menu.addMenu(language_manager.get_text("main_menu_theme"))
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        # ThemeManager에서 사용 가능한 테마 목록 스캔
        theme_manager = ThemeManager()
        available_themes = theme_manager.get_available_themes()

        for theme_name in available_themes:
            # 메뉴에 표시할 이름 (예: Dark, Light, Dracula)
            # 언어 키가 있으면 번역, 없으면 이름 그대로 사용
            # 예: main_menu_theme_dark -> Dark (번역)
            #     Dracula -> Dracula (그대로)

            # 1. 번역 시도
            lang_key = f"main_menu_theme_{theme_name.lower()}"
            display_name = language_manager.get_text(lang_key)
            if display_name == lang_key: # 번역 키가 없으면
                display_name = theme_name # 파일명(폴더명) 그대로 사용

            action = QAction(display_name, self)
            action.setCheckable(True)
            # 데이터에 실제 테마 이름 저장 (소문자로 통일해서 처리 권장)
            action.setData(theme_name)

            # 람다 캡처 주의: name=theme_name
            action.triggered.connect(lambda checked, name=theme_name: self.theme_changed.emit(name.lower()))

            theme_menu.addAction(action)
            self.theme_action_group.addAction(action)

        # 폰트 설정 액션
        font_action = QAction(language_manager.get_text("main_menu_font"), self)
        font_action.setShortcut("Ctrl+Shift+F")
        font_action.setToolTip(language_manager.get_text("main_menu_font_tooltip"))
        font_action.triggered.connect(self.font_settings_requested.emit)
        view_menu.addAction(font_action)

        # 언어 서브메뉴 (Language Submenu)
        language_menu = view_menu.addMenu(language_manager.get_text("main_menu_lang"))

        # LanguageManager에서 사용 가능한 언어 목록 스캔
        available_langs = language_manager.get_available_languages() # {'en': 'English', 'ko': '한국어'}

        for code, name in available_langs.items():
            action = QAction(name, self)
            # 람다 캡처 주의: c=code
            action.triggered.connect(lambda checked, c=code: self.language_changed.emit(c))
            language_menu.addAction(action)

        # Preferences 액션
        preferences_action = QAction(language_manager.get_text("main_menu_preferences"), self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.preferences_requested.emit)
        view_menu.addAction(preferences_action)

        # ---------------------------------------------------------
        # 3. 도구 메뉴 (Tools Menu)
        # ---------------------------------------------------------
        tools_menu = self.addMenu(language_manager.get_text("main_menu_tools"))

        # 파일 전송 액션
        file_transfer_action = QAction(language_manager.get_text("main_menu_file_transfer"), self)
        file_transfer_action.triggered.connect(self.file_transfer_requested.emit)
        tools_menu.addAction(file_transfer_action)

        # ---------------------------------------------------------
        # 4. 도움말 메뉴 (Help Menu)
        # ---------------------------------------------------------
        help_menu = self.addMenu(language_manager.get_text("main_menu_help"))
        about_action = QAction(language_manager.get_text("main_menu_about"), self)
        about_action.triggered.connect(self.about_requested.emit)
        help_menu.addAction(about_action)

    def set_right_section_checked(self, checked: bool) -> None:
        """우측 패널 토글 액션의 체크 상태를 설정합니다."""
        if hasattr(self, 'toggle_right_section_action'):
            self.toggle_right_section_action.setChecked(checked)

    def set_current_theme(self, theme_name: str) -> None:
        """
        현재 테마를 설정하고 메뉴에 체크 표시를 업데이트합니다.
        동적으로 생성된 액션 중에서 data가 일치하는 것을 찾아 체크합니다.

        Args:
            theme_name (str): 테마 이름 ("dark", "light", "dracula" 등)
        """
        if not self.theme_action_group:
            return

        for action in self.theme_action_group.actions():
            # 저장된 데이터(테마 이름)와 비교 (대소문자 무시)
            if str(action.data()).lower() == theme_name.lower():
                action.setChecked(True)
                break

    def retranslate_ui(self) -> None:
        """언어 변경 시 메뉴 텍스트를 업데이트합니다."""
        # 메뉴 전체 재생성 (동적 항목 번역 반영)
        self.init_menu()

