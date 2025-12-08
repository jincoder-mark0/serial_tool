from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from typing import Dict, Any, Optional
import os
from view.language_manager import language_manager
from core.settings_manager import SettingsManager

class PreferencesDialog(QDialog):
    """
    애플리케이션 설정을 관리하는 대화상자입니다.
    General, Serial, Logging 탭으로 구성됩니다.
    """

    settings_changed = pyqtSignal(dict)  # 변경된 설정 딕셔너리 전송

    def __init__(self, parent: Optional[QWidget] = None, current_settings: Dict[str, Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(language_manager.get_text("pref_title"))
        self.resize(500, 400)
        self.settings = SettingsManager()
        self.current_settings = current_settings or {}
        self.init_ui()
        self.load_settings()

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화합니다."""
        layout = QVBoxLayout()

        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), language_manager.get_text("pref_tab_general"))
        self.tabs.addTab(self.create_serial_tab(), language_manager.get_text("pref_tab_serial"))
        self.tabs.addTab(self.create_cmd_tab(), language_manager.get_text("pref_tab_command")) # New Tab
        self.tabs.addTab(self.create_logging_tab(), language_manager.get_text("pref_tab_logging"))

        layout.addWidget(self.tabs)

        # 하단 버튼 (OK / Cancel / Apply)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton(language_manager.get_text("pref_btn_ok"))
        self.ok_btn.clicked.connect(self.accept)

        self.cancel_btn = QPushButton(language_manager.get_text("pref_btn_cancel"))
        self.cancel_btn.clicked.connect(self.reject)

        self.apply_btn = QPushButton(language_manager.get_text("pref_btn_apply"))
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
        ui_group = QGroupBox(language_manager.get_text("pref_grp_ui"))
        ui_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Korean", "ko")

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(10)

        ui_layout.addRow(language_manager.get_text("pref_lbl_theme"), self.theme_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_language"), self.language_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_font_size"), self.font_size_spin)
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
        default_group = QGroupBox(language_manager.get_text("pref_grp_default"))
        default_layout = QFormLayout()

        self.default_baud_combo = QComboBox()
        self.default_baud_combo.addItems(["9600", "115200", "921600"])
        self.default_baud_combo.setEditable(True)

        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1000, 60000)
        self.scan_interval_spin.setSingleStep(1000)
        self.scan_interval_spin.setSuffix(" ms")

        default_layout.addRow(language_manager.get_text("pref_lbl_baud"), self.default_baud_combo)
        default_layout.addRow(language_manager.get_text("pref_lbl_scan"), self.scan_interval_spin)
        default_group.setLayout(default_layout)

        layout.addWidget(default_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_cmd_tab(self) -> QWidget:
        """Command 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Prefix/Suffix 그룹
        format_group = QGroupBox(language_manager.get_text("pref_grp_cmd_format"))
        format_layout = QFormLayout()

        self.prefix_combo = QComboBox()
        self.prefix_combo.setEditable(True)
        self.prefix_combo.addItems(["", "\\r", "\\n", "\\r\\n", "AT", "AT+"])

        self.suffix_combo = QComboBox()
        self.suffix_combo.setEditable(True)
        self.suffix_combo.addItems(["", "\\r", "\\n", "\\r\\n"])

        format_layout.addRow(language_manager.get_text("pref_lbl_prefix"), self.prefix_combo)
        format_layout.addRow(language_manager.get_text("pref_lbl_suffix"), self.suffix_combo)
        format_group.setLayout(format_layout)

        layout.addWidget(format_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_logging_tab(self) -> QWidget:
        """Logging 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # File Logging 그룹
        file_group = QGroupBox(language_manager.get_text("pref_grp_logging"))
        file_layout = QFormLayout()

        path_layout = QHBoxLayout()
        self.log_path_edit = QLabel("Default Path")
        self.log_path_edit.setFrameStyle(QLabel.Sunken | QLabel.Panel)
        self.browse_btn = QPushButton(language_manager.get_text("pref_btn_browse"))
        self.browse_btn.clicked.connect(self.browse_log_path)

        path_layout.addWidget(self.log_path_edit)
        path_layout.addWidget(self.browse_btn)

        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 100000)
        self.max_lines_spin.setSingleStep(100)

        file_layout.addRow(language_manager.get_text("pref_lbl_log_path"), path_layout)
        file_layout.addRow(language_manager.get_text("pref_lbl_max_lines"), self.max_lines_spin)
        file_group.setLayout(file_layout)

        layout.addWidget(file_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def browse_log_path(self) -> None:
        """로그 저장 경로 선택 다이얼로그를 엽니다."""
        directory = QFileDialog.getExistingDirectory(self, language_manager.get_text("pref_dialog_title_select_dir"))
        if directory:
            self.log_path_edit.setText(directory)

    def load_settings(self) -> None:
        """현재 설정을 UI에 반영합니다."""
        # General
        theme = self.settings.get("global.theme", "Dark").capitalize()
        self.theme_combo.setCurrentText(theme)

        lang_code = self.settings.get("global.language", "en")
        index = self.language_combo.findData(lang_code)
        if index != -1:
            self.language_combo.setCurrentIndex(index)

        self.font_size_spin.setValue(self.settings.get("ui.font_size", 10))

        # Serial
        self.default_baud_combo.setCurrentText(str(self.settings.get("serial.baudrate", 115200)))
        self.scan_interval_spin.setValue(self.settings.get("serial.scan_interval", 5000))

        # Command
        self.prefix_combo.setCurrentText(self.settings.get("command.prefix", ""))
        self.suffix_combo.setCurrentText(self.settings.get("command.suffix", "\\r\\n"))

        # Logging
        self.log_path_edit.setText(self.settings.get("logging.path", os.getcwd()))
        self.max_lines_spin.setValue(self.settings.get("ui.log_max_lines", 2000))

    def apply_settings(self) -> None:
        """변경된 설정을 수집하여 시그널을 발생시킵니다."""
        new_settings = {
            "theme": self.theme_combo.currentText(),
            "language": self.language_combo.currentData(),
            "font_size": self.font_size_spin.value(),
            "baudrate": self.default_baud_combo.currentText(),
            "scan_interval": self.scan_interval_spin.value(),
            "cmd_prefix": self.prefix_combo.currentText(),
            "cmd_suffix": self.suffix_combo.currentText(),
            "log_path": self.log_path_edit.text(),
            "max_log_lines": self.max_lines_spin.value()
        }
        self.settings_changed.emit(new_settings)

    def accept(self) -> None:
        """OK 버튼 클릭 시 설정을 적용하고 닫습니다."""
        self.apply_settings()
        super().accept()
