from PyQt5.QtWidgets import QToolBar, QAction
from PyQt5.QtCore import Qt, pyqtSignal
from view.language_manager import language_manager

class MainToolBar(QToolBar):
    open_requested = pyqtSignal()
    close_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    save_log_requested = pyqtSignal()
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
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        self.clear()

        # Open
        self.open_action = QAction("Open", self) # TODO: Add lang key
        self.open_action.triggered.connect(self.open_requested.emit)
        self.addAction(self.open_action)

        # Close
        self.close_action = QAction("Close", self) # TODO: Add lang key
        self.close_action.triggered.connect(self.close_requested.emit)
        self.addAction(self.close_action)

        # Clear
        self.clear_action = QAction("Clear", self) # TODO: Add lang key
        self.clear_action.triggered.connect(self.clear_requested.emit)
        self.addAction(self.clear_action)

        # Save Log
        self.save_log_action = QAction("Save Log", self) # TODO: Add lang key
        self.save_log_action.triggered.connect(self.save_log_requested.emit)
        self.addAction(self.save_log_action)

        # Settings
        self.settings_action = QAction("Settings", self) # TODO: Add lang key
        self.settings_action.triggered.connect(self.settings_requested.emit)
        self.addAction(self.settings_action)

    def retranslate_ui(self):
        self.open_action.setText("Open")
        self.close_action.setText("Close")
        self.clear_action.setText("Clear")
        self.save_log_action.setText("Save Log")
        self.settings_action.setText("Settings")
