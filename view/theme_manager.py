import os
import platform
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

class ThemeManager:
    """Manages application themes and fonts."""
    
    # Default fonts by platform
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
        """Initialize ThemeManager with platform-specific default fonts."""
        self._current_theme = "dark"
        self._app = None
        
        # Get platform
        system = platform.system()
        
        # Set default fonts based on platform
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))
        
        self._proportional_font = QFont(prop_family, prop_size)
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)
    
    @staticmethod
    def load_theme(theme_name: str = "dark") -> str:
        """Loads the QSS content for the specified theme, prepending common styles."""
        common_path = "resources/themes/common.qss"
        theme_files = {
            "dark": "resources/themes/dark_theme.qss",
            "light": "resources/themes/light_theme.qss"
        }
        
        qss_content = ""
        
        # 1. Load Common QSS
        if os.path.exists(common_path):
            try:
                with open(common_path, "r", encoding="utf-8") as f:
                    qss_content += f.read() + "\n"
            except Exception as e:
                print(f"Error loading common theme: {e}")
        else:
            print(f"Common theme file not found: {common_path}")
            
        # 2. Load Specific Theme QSS
        qss_path = theme_files.get(theme_name)
        if qss_path and os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    qss_content += f.read()
            except Exception as e:
                print(f"Error loading theme {theme_name}: {e}")
        else:
            print(f"Theme file not found: {qss_path}")
            
        return qss_content

    def apply_theme(self, app: QApplication, theme_name: str = "dark"):
        """Applies the specified theme to the QApplication instance."""
        self._app = app
        self._current_theme = theme_name
        stylesheet = self.load_theme(theme_name)
        if stylesheet:
            app.setStyleSheet(stylesheet)
        else:
            print(f"Failed to apply theme: {theme_name}")
    
    def get_current_theme(self) -> str:
        """Returns the current theme name."""
        return self._current_theme
    
    # Proportional Font Methods
    def set_proportional_font(self, family: str, size: int):
        """Sets the proportional (variable-width) font for UI elements."""
        self._proportional_font = QFont(family, size)
        if self._app:
            self._app.setFont(self._proportional_font)
    
    def get_proportional_font(self) -> QFont:
        """Returns the current proportional font."""
        return QFont(self._proportional_font)  # Return a copy
    
    def get_proportional_font_info(self) -> tuple[str, int]:
        """Returns (family, size) of proportional font."""
        return (self._proportional_font.family(), self._proportional_font.pointSize())
    
    # Fixed Font Methods
    def set_fixed_font(self, family: str, size: int):
        """Sets the fixed-width (monospace) font for text data."""
        self._fixed_font = QFont(family, size)
        self._fixed_font.setStyleHint(QFont.Monospace)
    
    def get_fixed_font(self) -> QFont:
        """Returns the current fixed-width font."""
        return QFont(self._fixed_font)  # Return a copy
    
    def get_fixed_font_info(self) -> tuple[str, int]:
        """Returns (family, size) of fixed font."""
        return (self._fixed_font.family(), self._fixed_font.pointSize())
    
    # Font restoration from settings
    def restore_fonts_from_settings(self, settings: dict):
        """Restores fonts from settings dictionary."""
        ui_settings = settings.get("ui", {})
        
        # Restore proportional font
        prop_family = ui_settings.get("proportional_font_family")
        prop_size = ui_settings.get("proportional_font_size")
        if prop_family and prop_size:
            self.set_proportional_font(prop_family, prop_size)
        
        # Restore fixed font
        fixed_family = ui_settings.get("fixed_font_family")
        fixed_size = ui_settings.get("fixed_font_size")
        if fixed_family and fixed_size:
            self.set_fixed_font(fixed_family, fixed_size)
    
    def get_font_settings(self) -> dict:
        """Returns current font settings as a dictionary."""
        prop_family, prop_size = self.get_proportional_font_info()
        fixed_family, fixed_size = self.get_fixed_font_info()
        
        return {
            "proportional_font_family": prop_family,
            "proportional_font_size": prop_size,
            "fixed_font_family": fixed_family,
            "fixed_font_size": fixed_size
        }
    
    # Legacy compatibility
    @staticmethod
    def set_font(app: QApplication, font_family: str, font_size: int = 10):
        """Sets the application-wide font (legacy method)."""
        font = QFont(font_family, font_size)
        app.setFont(font)

