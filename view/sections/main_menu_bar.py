from PyQt5.QtWidgets import QMenuBar, QAction
from PyQt5.QtCore import pyqtSignal

from view.managers.language_manager import language_manager

class MainMenuBar(QMenuBar):
    """
    메인 윈도우의 메뉴바를 관리하는 클래스입니다.
    """
    # Signals
    tab_new_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)
    font_settings_requested = pyqtSignal()
    language_changed = pyqtSignal(str)
    preferences_requested = pyqtSignal()
    about_requested = pyqtSignal()
    port_open_requested = pyqtSignal()
    tab_close_requested = pyqtSignal()
    data_log_save_requested = pyqtSignal()
    toggle_right_panel_requested = pyqtSignal(bool)
    file_transfer_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Theme action references for checkable state
        self.theme_dark_action = None
        self.theme_light_action = None
        self.init_menu()

    def init_menu(self) -> None:
        """메뉴바를 초기화하고 액션을 설정합니다."""
        self.clear()

        # 파일 메뉴 (File Menu)
        file_menu = self.addMenu(language_manager.get_text("main_menu_file"))

        new_tab_action = QAction(language_manager.get_text("main_menu_new_tab"), self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip(language_manager.get_text("main_menu_new_tab_tooltip"))
        new_tab_action.triggered.connect(self.tab_new_requested.emit)
        file_menu.addAction(new_tab_action)

        open_port_action = QAction(language_manager.get_text("main_menu_open_port"), self)
        open_port_action.setShortcut("Ctrl+O")
        open_port_action.triggered.connect(self.port_open_requested.emit)
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

        # 보기 메뉴 (View Menu)
        view_menu = self.addMenu(language_manager.get_text("main_menu_view"))

        # Right Panel Toggle
        self.toggle_right_panel_action = QAction(language_manager.get_text("main_menu_toggle_right_panel"), self)
        self.toggle_right_panel_action.setCheckable(True)
        self.toggle_right_panel_action.triggered.connect(self.toggle_right_panel_requested.emit)
        view_menu.addAction(self.toggle_right_panel_action)

        view_menu.addSeparator()

        # 테마 서브메뉴
        theme_menu = view_menu.addMenu(language_manager.get_text("main_menu_theme"))

        self.theme_dark_action = QAction(language_manager.get_text("main_menu_theme_dark"), self)
        self.theme_dark_action.setCheckable(True)
        self.theme_dark_action.triggered.connect(lambda: self.theme_changed.emit("dark"))
        theme_menu.addAction(self.theme_dark_action)

        self.theme_light_action = QAction(language_manager.get_text("main_menu_theme_light"), self)
        self.theme_light_action.setCheckable(True)
        self.theme_light_action.triggered.connect(lambda: self.theme_changed.emit("light"))
        theme_menu.addAction(self.theme_light_action)

        # 폰트 설정 액션
        font_action = QAction(language_manager.get_text("main_menu_font"), self)
        font_action.setShortcut("Ctrl+Shift+F")
        font_action.setToolTip(language_manager.get_text("main_menu_font_tooltip"))
        font_action.triggered.connect(self.font_settings_requested.emit)
        view_menu.addAction(font_action)

        # 언어 서브메뉴 (Language Submenu)
        language_menu = view_menu.addMenu(language_manager.get_text("main_menu_lang"))

        language_en_action = QAction(language_manager.get_text("main_menu_language_en"), self)
        language_en_action.triggered.connect(lambda: self.language_changed.emit("en"))
        language_menu.addAction(language_en_action)

        language_ko_action = QAction(language_manager.get_text("main_menu_language_ko"), self)
        language_ko_action.triggered.connect(lambda: self.language_changed.emit("ko"))
        language_menu.addAction(language_ko_action)

        # Preferences 액션
        preferences_action = QAction(language_manager.get_text("main_menu_preferences"), self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.preferences_requested.emit)
        view_menu.addAction(preferences_action)

        # 도구 메뉴 (Tools Menu)
        tools_menu = self.addMenu(language_manager.get_text("main_menu_tools"))

        # 파일 전송 액션
        file_transfer_action = QAction(language_manager.get_text("main_menu_file_transfer"), self)
        file_transfer_action.triggered.connect(self.file_transfer_requested.emit)
        tools_menu.addAction(file_transfer_action)

        # 도움말 메뉴 (Help Menu)
        help_menu = self.addMenu(language_manager.get_text("main_menu_help"))
        about_action = QAction(language_manager.get_text("main_menu_about"), self)
        about_action.triggered.connect(self.about_requested.emit)
        help_menu.addAction(about_action)

    def set_right_panel_checked(self, checked: bool) -> None:
        """우측 패널 토글 액션의 체크 상태를 설정합니다."""
        if hasattr(self, 'toggle_right_panel_action'):
            self.toggle_right_panel_action.setChecked(checked)

    def set_current_theme(self, theme_name: str) -> None:
        """
        현재 테마를 설정하고 메뉴에 체크 표시를 업데이트합니다.

        Args:
            theme_name (str): 테마 이름 ("dark" 또는 "light")
        """
        if self.theme_dark_action and self.theme_light_action:
            self.theme_dark_action.setChecked(theme_name.lower() == "dark")
            self.theme_light_action.setChecked(theme_name.lower() == "light")

    def retranslate_ui(self) -> None:
        """언어 변경 시 메뉴 텍스트를 업데이트합니다."""
        self.init_menu()

