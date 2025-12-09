from PyQt5.QtWidgets import QMenuBar, QAction
from PyQt5.QtCore import pyqtSignal
from pygments.lexers.sql import language_re

from view.lang_manager import lang_manager

class MainMenuBar(QMenuBar):
    """
    메인 윈도우의 메뉴바를 관리하는 클래스입니다.
    """
    # Signals
    new_tab_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)
    font_settings_requested = pyqtSignal()
    language_changed = pyqtSignal(str)
    preferences_requested = pyqtSignal()
    about_requested = pyqtSignal()
    open_port_requested = pyqtSignal()
    close_tab_requested = pyqtSignal()
    save_log_requested = pyqtSignal()
    toggle_right_panel_requested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_menu()

    def init_menu(self) -> None:
        """메뉴바를 초기화하고 액션을 설정합니다."""
        self.clear()

        # 파일 메뉴 (File Menu)
        file_menu = self.addMenu(lang_manager.get_text("main_menu_file"))

        new_tab_action = QAction(lang_manager.get_text("main_menu_new_tab"), self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip(lang_manager.get_text("main_menu_new_tab_tooltip"))
        new_tab_action.triggered.connect(self.new_tab_requested.emit)
        file_menu.addAction(new_tab_action)

        open_port_action = QAction("Open Port", self) # TODO: Add lang key
        open_port_action.setShortcut("Ctrl+O")
        open_port_action.triggered.connect(self.open_port_requested.emit)
        file_menu.addAction(open_port_action)

        close_tab_action = QAction("Close Tab", self) # TODO: Add lang key
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(self.close_tab_requested.emit)
        file_menu.addAction(close_tab_action)

        save_log_action = QAction("Save Log", self) # TODO: Add lang key
        save_log_action.setShortcut("Ctrl+Shift+S")
        save_log_action.triggered.connect(self.save_log_requested.emit)
        file_menu.addAction(save_log_action)

        file_menu.addSeparator()

        exit_action = QAction(lang_manager.get_text("main_menu_exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip(lang_manager.get_text("main_menu_exit_tooltip"))
        exit_action.triggered.connect(self.exit_requested.emit)
        file_menu.addAction(exit_action)

        # 보기 메뉴 (View Menu)
        view_menu = self.addMenu(lang_manager.get_text("main_menu_view"))

        # Right Panel Toggle
        self.toggle_right_panel_action = QAction("Show Right Panel", self) # TODO: Add lang key
        self.toggle_right_panel_action.setCheckable(True)
        self.toggle_right_panel_action.setChecked(True) # Default, will be updated by MainWindow
        self.toggle_right_panel_action.triggered.connect(self.toggle_right_panel_requested.emit)
        view_menu.addAction(self.toggle_right_panel_action)

        view_menu.addSeparator()

        # 테마 서브메뉴
        theme_menu = view_menu.addMenu(lang_manager.get_text("main_menu_theme"))

        theme_dark_action = QAction(lang_manager.get_text("main_menu_theme_dark"), self)
        theme_dark_action.triggered.connect(lambda: self.theme_changed.emit("dark"))
        theme_menu.addAction(theme_dark_action)

        theme_light_action = QAction(lang_manager.get_text("main_menu_theme_light"), self)
        theme_light_action.triggered.connect(lambda: self.theme_changed.emit("light"))
        theme_menu.addAction(theme_light_action)

        # 폰트 설정 액션
        font_action = QAction(lang_manager.get_text("main_menu_font"), self)
        font_action.setShortcut("Ctrl+Shift+F")
        font_action.setToolTip(lang_manager.get_text("main_menu_font_tooltip"))
        font_action.triggered.connect(self.font_settings_requested.emit)
        view_menu.addAction(font_action)

        # 언어 서브메뉴 (Language Submenu)
        lang_menu = view_menu.addMenu(lang_manager.get_text("main_menu_lang"))

        lang_en_action = QAction(lang_manager.get_text("main_menu_lang_en"), self)
        lang_en_action.triggered.connect(lambda: self.language_changed.emit("en"))
        lang_menu.addAction(lang_en_action)

        lang_ko_action = QAction(lang_manager.get_text("main_menu_lang_ko"), self)
        lang_ko_action.triggered.connect(lambda: self.language_changed.emit("ko"))
        lang_menu.addAction(lang_ko_action)

        # Preferences 액션
        preferences_action = QAction(lang_manager.get_text("main_menu_preferences"), self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.preferences_requested.emit)
        view_menu.addAction(preferences_action)

        # 도구 메뉴 (Tools Menu)
        tools_menu = self.addMenu(lang_manager.get_text("main_menu_tools"))

        # 도움말 메뉴 (Help Menu)
        help_menu = self.addMenu(lang_manager.get_text("main_menu_help"))
        about_action = QAction(lang_manager.get_text("main_menu_about"), self)
        about_action.triggered.connect(self.about_requested.emit)
        help_menu.addAction(about_action)

    def set_right_panel_checked(self, checked: bool) -> None:
        """우측 패널 토글 액션의 체크 상태를 설정합니다."""
        if hasattr(self, 'toggle_right_panel_action'):
            self.toggle_right_panel_action.setChecked(checked)

    def retranslate_ui(self) -> None:
        """언어 변경 시 메뉴 텍스트를 업데이트합니다."""
        self.init_menu()
