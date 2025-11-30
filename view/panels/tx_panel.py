from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QCheckBox, QLabel, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt

class TxPanel(QWidget):
    send_requested = pyqtSignal(str, bool, bool) # text, hex_mode, with_enter
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Input Area
        self.input_edit = QTextEdit()
        self.input_edit.setMaximumHeight(60)
        self.input_edit.setPlaceholderText("Enter command here...")
        self.input_edit.setToolTip("Enter data to send (Ctrl+Enter to send)")
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.hex_check = QCheckBox("HEX")
        self.hex_check.setToolTip("Send as Hex string (e.g. '41 42')")
        self.cr_check = QCheckBox("CR")
        self.cr_check.setChecked(True)
        self.cr_check.setToolTip("Append Carriage Return (\\r)")
        self.lf_check = QCheckBox("LF")
        self.lf_check.setChecked(True)
        self.lf_check.setToolTip("Append Line Feed (\\n)")
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.on_send)
        self.send_btn.setToolTip("Send data (Enter)")
        self.send_btn.setStyleSheet("font-weight: bold; background-color: #2196F3; color: white;")
        
        controls_layout.addWidget(self.hex_check)
        controls_layout.addWidget(self.cr_check)
        controls_layout.addWidget(self.lf_check)
        controls_layout.addStretch()
        controls_layout.addWidget(self.send_btn)
        
        # History (Simple ComboBox for now, or just a list below)
        self.history_combo = QComboBox()
        self.history_combo.setPlaceholderText("History...")
        self.history_combo.setToolTip("Command history")
        self.history_combo.currentIndexChanged.connect(self.on_history_selected)
        
        layout.addWidget(QLabel("TX Input"))
        layout.addWidget(self.input_edit)
        layout.addLayout(controls_layout)
        layout.addWidget(self.history_combo)
        
        self.setLayout(layout)
        
    def on_send(self):
        text = self.input_edit.toPlainText()
        if not text:
            return
            
        hex_mode = self.hex_check.isChecked()
        
        # Handle CR/LF manually if needed, or pass flags to presenter
        # Here passing flags to presenter is cleaner
        with_enter = False # Logic moved to presenter or handled here?
        # Specification says: "Enter(\r\n) Option"
        # Let's construct the suffix based on checkboxes
        suffix = ""
        if self.cr_check.isChecked(): suffix += "\r"
        if self.lf_check.isChecked(): suffix += "\n"
        
        # If not hex mode, append suffix. If hex mode, user should provide hex codes for CR/LF if needed?
        # Usually HEX mode implies raw bytes.
        
        if not hex_mode:
            text += suffix
            
        self.send_requested.emit(text, hex_mode, False) # False for "with_enter" arg if we handled it manually
        
        # Add to history
        if self.history_combo.findText(text.strip()) == -1:
            self.history_combo.addItem(text.strip())

    def on_history_selected(self, index):
        if index >= 0:
            self.input_edit.setPlainText(self.history_combo.itemText(index))
