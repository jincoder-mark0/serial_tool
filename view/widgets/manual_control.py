from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, 
    QTextEdit, QLabel, QFileDialog, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional

class ManualControlWidget(QWidget):
    """
    수동 명령 전송, 파일 전송, 로그 저장 및 각종 제어 옵션을 제공하는 위젯입니다.
    (구 OperationArea)
    """
    
    # Signals
    send_command_requested = pyqtSignal(str, bool, bool) # text, hex_mode, with_enter
    send_file_requested = pyqtSignal(str) # filepath
    save_log_requested = pyqtSignal(str) # filepath
    clear_info_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 1. Control Options Group
        option_group = QGroupBox("Control Options")
        option_layout = QGridLayout()
        option_layout.setContentsMargins(5, 5, 5, 5)
        
        self.hex_mode_check = QCheckBox("HEX Mode")
        self.hex_mode_check.setToolTip("Send data as Hex string (e.g. '01 02 FF')")
        
        self.enter_check = QCheckBox("Add CR/LF")
        self.enter_check.setChecked(True)
        self.enter_check.setToolTip("Append \\r\\n to the command")
        
        self.clear_btn = QPushButton("Clear Info")
        self.clear_btn.setToolTip("Clear received data and status log")
        self.clear_btn.clicked.connect(self.clear_info_requested.emit)
        
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.setToolTip("Save received data to file")
        self.save_log_btn.clicked.connect(self.on_save_log_clicked)
        
        option_layout.addWidget(self.hex_mode_check, 0, 0)
        option_layout.addWidget(self.enter_check, 0, 1)
        option_layout.addWidget(self.clear_btn, 0, 2)
        option_layout.addWidget(self.save_log_btn, 0, 3)
        
        option_group.setLayout(option_layout)
        
        # 2. Manual Send Area
        send_group = QGroupBox("Manual Send")
        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(5, 5, 5, 5)
        
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(50)
        self.input_text.setPlaceholderText("Enter command here...")
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumHeight(50)
        self.send_btn.setStyleSheet("font-weight: bold;")
        self.send_btn.clicked.connect(self.on_send_clicked)
        
        send_layout.addWidget(self.input_text, 1)
        send_layout.addWidget(self.send_btn)
        
        send_group.setLayout(send_layout)
        
        # 3. File Transfer Area
        file_group = QGroupBox("File Transfer")
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(5, 5, 5, 5)
        
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("color: gray; border: 1px solid #ccc; padding: 2px;")
        
        self.select_file_btn = QPushButton("Select File")
        self.select_file_btn.clicked.connect(self.on_select_file_clicked)
        
        self.send_file_btn = QPushButton("Send File")
        self.send_file_btn.clicked.connect(self.on_send_file_clicked)
        
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.select_file_btn)
        file_layout.addWidget(self.send_file_btn)
        
        file_group.setLayout(file_layout)
        
        layout.addWidget(option_group)
        layout.addWidget(send_group)
        layout.addWidget(file_group)
        
        self.setLayout(layout)
        
        # Initial State
        self.set_controls_enabled(False)
        
    def on_send_clicked(self) -> None:
        text = self.input_text.toPlainText()
        if text:
            self.send_command_requested.emit(
                text, 
                self.hex_mode_check.isChecked(), 
                self.enter_check.isChecked()
            )
            
    def on_select_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if path:
            self.file_path_label.setText(path)
            
    def on_send_file_clicked(self) -> None:
        path = self.file_path_label.text()
        if path and path != "No file selected":
            self.send_file_requested.emit(path)
            
    def on_save_log_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.save_log_requested.emit(path)

    def set_controls_enabled(self, enabled: bool) -> None:
        """포트 연결 상태에 따라 제어 버튼 활성화/비활성화"""
        self.send_btn.setEnabled(enabled)
        self.send_file_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(True) # Clear는 항상 가능하게? (보통 로그 지우기는 연결 무관)
        self.save_log_btn.setEnabled(True) # 로그 저장도 항상 가능
        
        # Select File은 항상 가능 (요청사항)
        self.select_file_btn.setEnabled(True)
        
        # 입력창은? 보통 연결 안되면 입력도 막거나, 입력은 되되 전송만 막음.
        # 여기서는 전송 버튼만 막음.
