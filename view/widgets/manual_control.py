from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, 
    QLineEdit, QLabel, QFileDialog, QGroupBox, QGridLayout
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
    file_selected = pyqtSignal(str) # filepath (Added)
    save_log_requested = pyqtSignal(str) # filepath
    clear_info_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2) # 간격 최소화
        
        # 1. Control Options Group
        option_group = QGroupBox("Control Options")
        option_layout = QGridLayout()
        option_layout.setContentsMargins(2, 2, 2, 2) # 내부 여백 최소화
        option_layout.setSpacing(5)
        
        self.hex_mode_check = QCheckBox("HEX")
        self.hex_mode_check.setToolTip("Send data as Hex string (e.g. '01 02 FF')")
        
        self.enter_check = QCheckBox("CR/LF")
        self.enter_check.setChecked(True)
        self.enter_check.setToolTip("Append \\r\\n to the command")
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Clear received data and status log")
        self.clear_btn.clicked.connect(self.clear_info_requested.emit)
        
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.setToolTip("Save received data to file")
        self.save_log_btn.clicked.connect(self.on_save_log_clicked)
        
        # Flow Control (RTS/DTR)
        self.rts_check = QCheckBox("RTS")
        self.rts_check.setToolTip("Request To Send")
        self.dtr_check = QCheckBox("DTR")
        self.dtr_check.setToolTip("Data Terminal Ready")
        
        option_layout.addWidget(self.hex_mode_check, 0, 0)
        option_layout.addWidget(self.enter_check, 0, 1)
        option_layout.addWidget(self.rts_check, 0, 2)
        option_layout.addWidget(self.dtr_check, 0, 3)
        
        option_layout.addWidget(self.clear_btn, 1, 0, 1, 2)
        option_layout.addWidget(self.save_log_btn, 1, 2, 1, 2)
        
        option_group.setLayout(option_layout)
        
        # 2. Manual Send Area
        send_group = QGroupBox("Manual Send")
        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(2, 2, 2, 2)
        send_layout.setSpacing(5)
        
        self.input_field = QLineEdit() # QTextEdit -> QLineEdit 변경
        self.input_field.setPlaceholderText("Enter command here...")
        self.input_field.setProperty("class", "fixed-font")  # Apply fixed-width font
        self.input_field.returnPressed.connect(self.on_send_clicked) # Enter 키 지원
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        # self.send_btn.setMinimumHeight(50) # 높이 제한 제거
        # 스타일은 QSS에서 처리 권장 (강조색)
        self.send_btn.setProperty("class", "accent") 
        self.send_btn.clicked.connect(self.on_send_clicked)
        
        send_layout.addWidget(self.input_field, 1)
        send_layout.addWidget(self.send_btn)
        
        send_group.setLayout(send_layout)
        
        # 3. File Transfer Area
        file_group = QGroupBox("File Transfer")
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(2, 2, 2, 2)
        file_layout.setSpacing(5)
        
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("color: gray; border: 1px solid #555; padding: 2px; border-radius: 2px;")
        
        self.select_file_btn = QPushButton("Select")
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
        layout.addStretch() # 하단 여백 추가
        
        self.setLayout(layout)
        
        # Initial State
        self.set_controls_enabled(False)
        
    def on_send_clicked(self) -> None:
        text = self.input_field.text()
        if text:
            self.send_command_requested.emit(
                text, 
                self.hex_mode_check.isChecked(), 
                self.enter_check.isChecked()
            )
            # 입력 후 지우지 않음 (히스토리 기능이 없으므로 유지하는 편이 나음)
            # self.input_field.clear() 
            
    def on_select_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if path:
            self.file_path_label.setText(path)
            self.file_selected.emit(path)
            
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
        self.rts_check.setEnabled(enabled)
        self.dtr_check.setEnabled(enabled)
        
        self.clear_btn.setEnabled(True)
        self.save_log_btn.setEnabled(True)
        self.select_file_btn.setEnabled(True)
