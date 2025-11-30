from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QAction, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt

from view.panels.left_panel import LeftPanel
from view.panels.right_panel import RightPanel
from view.theme_manager import ThemeManager

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우입니다.
    LeftPanel(포트/제어)과 RightPanel(커맨드/인스펙터)을 조합합니다.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SerialTool v1.0")
        self.resize(1400, 900)
        
        self.init_ui()
        self.init_menu()
        
        # Apply default theme
        self.switch_theme("dark")
        
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
        
        # Font Menu
        font_menu = view_menu.addMenu("Font")
        
        fonts = ["Segoe UI", "Consolas", "Arial", "Verdana"]
        for font in fonts:
            action = QAction(font, self)
            action.triggered.connect(lambda checked, f=font: self.change_font(f))
            font_menu.addAction(action)
            
        font_menu.addSeparator()
        
        custom_font_action = QAction("Custom...", self)
        custom_font_action.triggered.connect(self.open_font_dialog)
        font_menu.addAction(custom_font_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        help_menu.addAction(about_action)

    def switch_theme(self, theme_name: str):
        """Switches the application theme."""
        app = QApplication.instance()
        if app:
            ThemeManager.apply_theme(app, theme_name)

    def change_font(self, font_family: str):
        """Changes the application font."""
        app = QApplication.instance()
        if app:
            ThemeManager.set_font(app, font_family)

    def open_font_dialog(self):
        """Opens a font selection dialog."""
        from PyQt5.QtWidgets import QFontDialog, QApplication
        
        current_font = QApplication.font()
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            app = QApplication.instance()
            if app:
                app.setFont(font)
