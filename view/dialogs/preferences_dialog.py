from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QComboBox, QSpinBox, QCheckBox, QPushButton, 
    QFileDialog, QGroupBox, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from typing import Dict, Any, Optional
import os

class PreferencesDialog(QDialog):
    """
    애플리케이션 설정을 관리하는 대화상자입니다.
    General, Serial, Logging 탭으로 구성됩니다.
    """
    
    settings_changed = pyqtSignal(dict)  # 변경된 설정 딕셔너리 전송

    def __init__(self, parent: Optional[QWidget] = None, current_settings: Dict[str, Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(500, 400)
        self.current_settings = current_settings or {}
        self.init_ui()
        self.load_settings()

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화합니다."""
        layout = QVBoxLayout()
        
        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), "General")
        self.tabs.addTab(self.create_serial_tab(), "Serial")
        self.tabs.addTab(self.create_logging_tab(), "Logging")
        
        layout.addWidget(self.tabs)
        
        # 하단 버튼 (OK / Cancel / Apply)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_settings)
        
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def create_general_tab(self) -> QWidget:
        """General 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # UI Appearance 그룹
        ui_group = QGroupBox("UI Appearance")
        ui_layout = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Korean"])
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(10)
        
        ui_layout.addRow("Theme:", self.theme_combo)
        ui_layout.addRow("Language:", self.language_combo)
        ui_layout.addRow("Font Size:", self.font_size_spin)
        ui_group.setLayout(ui_layout)
        
        layout.addWidget(ui_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_serial_tab(self) -> QWidget:
        """Serial 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Defaults 그룹
        default_group = QGroupBox("Default Parameters")
        default_layout = QFormLayout()
        
        self.default_baud_combo = QComboBox()
        self.default_baud_combo.addItems(["9600", "115200", "921600"])
        self.default_baud_combo.setEditable(True)
        
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1000, 60000)
        self.scan_interval_spin.setSingleStep(1000)
        self.scan_interval_spin.setSuffix(" ms")
        
        default_layout.addRow("Default Baudrate:", self.default_baud_combo)
        default_layout.addRow("Auto Scan Interval:", self.scan_interval_spin)
        default_group.setLayout(default_layout)
        
        layout.addWidget(default_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_logging_tab(self) -> QWidget:
        """Logging 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # File Logging 그룹
        file_group = QGroupBox("File Logging")
        file_layout = QFormLayout()
        
        path_layout = QHBoxLayout()
        self.log_path_edit = QLabel("Default Path")
        self.log_path_edit.setFrameStyle(QLabel.Sunken | QLabel.Panel)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_log_path)
        
        path_layout.addWidget(self.log_path_edit)
        path_layout.addWidget(self.browse_btn)
        
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 100000)
        self.max_lines_spin.setSingleStep(100)
        
        file_layout.addRow("Log Directory:", path_layout)
        file_layout.addRow("Max Log Lines (UI):", self.max_lines_spin)
        file_group.setLayout(file_layout)
        
        layout.addWidget(file_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def browse_log_path(self) -> None:
        """로그 저장 경로 선택 다이얼로그를 엽니다."""
        directory = QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if directory:
            self.log_path_edit.setText(directory)

    def load_settings(self) -> None:
        """현재 설정을 UI에 반영합니다."""
        # General
        self.theme_combo.setCurrentText(self.current_settings.get("theme", "Dark").capitalize())
        self.language_combo.setCurrentText(self.current_settings.get("language", "English"))
        self.font_size_spin.setValue(self.current_settings.get("font_size", 10))
        
        # Serial
        self.default_baud_combo.setCurrentText(str(self.current_settings.get("default_baudrate", 115200)))
        self.scan_interval_spin.setValue(self.current_settings.get("scan_interval", 5000))
        
        # Logging
        self.log_path_edit.setText(self.current_settings.get("log_path", os.getcwd()))
        self.max_lines_spin.setValue(self.current_settings.get("max_log_lines", 2000))

    def apply_settings(self) -> None:
        """변경된 설정을 수집하여 시그널을 발생시킵니다."""
        new_settings = {
            "theme": self.theme_combo.currentText().lower(),
            "language": self.language_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "default_baudrate": int(self.default_baud_combo.currentText()),
            "scan_interval": self.scan_interval_spin.value(),
            "log_path": self.log_path_edit.text(),
            "max_log_lines": self.max_lines_spin.value()
        }
        self.settings_changed.emit(new_settings)
        
    def accept(self) -> None:
        """OK 버튼 클릭 시 설정을 적용하고 닫습니다."""
        self.apply_settings()
        super().accept()
