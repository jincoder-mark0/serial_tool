import os
from PyQt5.QtWidgets import QApplication

class ThemeManager:
    @staticmethod
    def load_theme(theme_name: str = "dark") -> str:
        """Loads the QSS content for the specified theme."""
        theme_files = {
            "dark": "resources/themes/dark_theme.qss",
            "light": "resources/themes/light_theme.qss"
        }
        
        qss_path = theme_files.get(theme_name)
        if not qss_path or not os.path.exists(qss_path):
            print(f"Theme file not found: {qss_path}")
            return ""
        
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error loading theme {theme_name}: {e}")
            return ""

    @staticmethod
    def apply_theme(app: QApplication, theme_name: str = "dark"):
        """Applies the specified theme to the QApplication instance."""
        stylesheet = ThemeManager.load_theme(theme_name)
        if stylesheet:
            app.setStyleSheet(stylesheet)
        else:
            print(f"Failed to apply theme: {theme_name}")

    @staticmethod
    def set_font(app: QApplication, font_family: str, font_size: int = 10):
        """Sets the application-wide font."""
        from PyQt5.QtGui import QFont
        font = QFont(font_family, font_size)
        app.setFont(font)
