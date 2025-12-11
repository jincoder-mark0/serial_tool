from PyQt5.QtWidgets import QToolBar, QAction
from PyQt5.QtCore import Qt, pyqtSignal
from view.managers.lang_manager import lang_manager

class MainToolBar(QToolBar):
    open_requested = pyqtSignal()
    close_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    log_save_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_action = None
        self.save_log_action = None
        self.clear_action = None
        self.close_action = None
        self.open_action = None
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.init_ui()
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        self.clear()

        # Open
        self.open_action = QAction(lang_manager.get_text("toolbar_open"), self)
        self.open_action.triggered.connect(self.open_requested.emit)
        self.addAction(self.open_action)

        # Close
        self.close_action = QAction(lang_manager.get_text("toolbar_close"), self)
        self.close_action.triggered.connect(self.close_requested.emit)
        self.addAction(self.close_action)

        # Clear
        self.clear_action = QAction(lang_manager.get_text("toolbar_clear"), self)
        self.clear_action.triggered.connect(self.clear_requested.emit)
        self.addAction(self.clear_action)

        # Save Log
        self.save_log_action = QAction(lang_manager.get_text("toolbar_save_log"), self)
        self.save_log_action.triggered.connect(self.log_save_requested.emit)
        self.addAction(self.save_log_action)

        # Settings
        self.settings_action = QAction(lang_manager.get_text("toolbar_settings"), self)
        self.settings_action.triggered.connect(self.settings_requested.emit)
        self.addAction(self.settings_action)

    def retranslate_ui(self):
        self.open_action.setText(lang_manager.get_text("toolbar_open"))
        self.close_action.setText(lang_manager.get_text("toolbar_close"))
        self.clear_action.setText(lang_manager.get_text("toolbar_clear"))
        self.save_log_action.setText(lang_manager.get_text("toolbar_save_log"))
        self.settings_action.setText(lang_manager.get_text("toolbar_settings"))

