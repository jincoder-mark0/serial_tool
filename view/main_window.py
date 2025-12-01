from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QAction, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt

from view.panels.left_panel import LeftPanel
from view.panels.right_panel import RightPanel
from view.theme_manager import ThemeManager
from core.settings_manager import SettingsManager

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우입니다.
    LeftPanel(포트/제어)과 RightPanel(커맨드/인스펙터)을 조합합니다.
    """
    
    def __init__(self) -> None:
        super().__init__()
        
        # Initialize Settings Manager
        self.settings = SettingsManager()
        
        # Initialize Theme Manager (instance-based)
        self.theme_manager = ThemeManager()
        
        self.setWindowTitle("SerialTool v1.0")
        self.resize(1400, 900)
        
        self.init_ui()
        self.init_menu()
        
        # Apply theme and fonts from settings
        theme = self.settings.get('global.theme', 'dark')
        self.switch_theme(theme)
        
        # Restore fonts from settings
        settings_dict = self.settings.get_all_settings()
        self.theme_manager.restore_fonts_from_settings(settings_dict)
        
        # Apply proportional font to application
        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)
        
        # Load window geometry if saved
        self._load_window_state()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Splitter (Left: Port/Control, Right: Command/Inspector)
        splitter = QSplitter(Qt.Horizontal)
        
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 1) # Left side
        splitter.setStretchFactor(1, 1) # Right side
        
        main_layout.addWidget(splitter)
        
        # Global Status Bar
        self.global_status_bar = QStatusBar()
        self.setStatusBar(self.global_status_bar)
        self.global_status_bar.showMessage("Ready")

    def init_menu(self) -> None:
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        new_tab_action = QAction("New Port Tab", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip("Open a new serial port tab")
        # LeftPanel의 add_new_port_tab 호출
        new_tab_action.triggered.connect(self.left_panel.add_new_port_tab)
        file_menu.addAction(new_tab_action)
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View Menu (Theme)
        view_menu = menubar.addMenu("View")
        
        theme_menu = view_menu.addMenu("Theme")
        
        dark_action = QAction("Dark", self)
        dark_action.triggered.connect(lambda: self.switch_theme("dark"))
        theme_menu.addAction(dark_action)
        
        light_action = QAction("Light", self)
        light_action.triggered.connect(lambda: self.switch_theme("light"))
        theme_menu.addAction(light_action)
        
        # Font Menu (Updated for Dual Font System)
        font_menu = view_menu.addMenu("Font")
        
        font_settings_action = QAction("Font Settings...", self)
        font_settings_action.setShortcut("Ctrl+Shift+F")
        font_settings_action.setToolTip("Configure proportional and fixed fonts")
        font_settings_action.triggered.connect(self.open_font_settings_dialog)
        font_menu.addAction(font_settings_action)
        
        font_menu.addSeparator()
        
        # Quick font presets (legacy support)
        fonts = ["Segoe UI", "Consolas", "Arial", "Verdana"]
        for font in fonts:
            action = QAction(font, self)
            action.triggered.connect(lambda checked, f=font: self.change_font(f))
            font_menu.addAction(action)
        
        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        help_menu.addAction(about_action)

    def switch_theme(self, theme_name: str) -> None:
        """테마를 전환합니다."""
        self.theme_manager.apply_theme(QApplication.instance(), theme_name)
        
        # Save theme to settings
        if hasattr(self, 'settings'):
            self.settings.set('global.theme', theme_name)
        
        if theme_name == "dark":
            self.global_status_bar.showMessage("Theme changed to Dark", 2000)
        else:
            self.global_status_bar.showMessage("Theme changed to Light", 2000)

    def change_font(self, font_family: str) -> None:
        """Changes the application font (legacy method - sets proportional font)."""
        self.theme_manager.set_proportional_font(font_family, 9)
        self.global_status_bar.showMessage(f"Font changed to {font_family}", 2000)

    def open_font_settings_dialog(self) -> None:
        """Opens the dual font settings dialog."""
        from view.dialogs.font_settings_dialog import FontSettingsDialog
        
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            # Save font settings
            font_settings = self.theme_manager.get_font_settings()
            for key, value in font_settings.items():
                self.settings.set(f'ui.{key}', value)
            
            # Apply proportional font to application
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)
            
            self.global_status_bar.showMessage("Font settings updated", 2000)

    
    def _load_window_state(self) -> None:
        """
        저장된 윈도우 상태를 로드합니다.
        (크기, 위치)
        """
        # Window geometry
        width = self.settings.get('ui.window_width', 1400)
        height = self.settings.get('ui.window_height', 900)
        self.resize(width, height)
        
        # Position (optional)
        x = self.settings.get('ui.window_x')
        y = self.settings.get('ui.window_y')
        if x is not None and y is not None:
            self.move(x, y)
    
    def _save_window_state(self) -> None:
        """
        현재 윈도우 상태를 설정에 저장합니다.
        """
        # Save window geometry
        self.settings.set('ui.window_width', self.width())
        self.settings.set('ui.window_height', self.height())
        self.settings.set('ui.window_x', self.x())
        self.settings.set('ui.window_y', self.y())
    
    def closeEvent(self, event) -> None:
        """
        윈도우 종료 이벤트를 처리합니다.
        설정을 저장하고 종료합니다.
        
        Args:
            event: 종료 이벤트
        """
        # Save window state
        self._save_window_state()
        
        # Save settings to file
        self.settings.save_settings()
        
        # Accept the close event
        event.accept()
