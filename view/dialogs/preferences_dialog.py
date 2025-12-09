from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QListWidget, QCheckBox, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Dict, Any, Optional
import os
from view.tools.lang_manager import lang_manager

class PreferencesDialog(QDialog):
    """
    애플리케이션 설정을 관리하는 대화상자입니다.
    General, Serial, Logging 탭으로 구성됩니다.
    MVP 패턴을 준수하여 SettingsManager에 직접 접근하지 않고
    부모로부터 전달받은 설정만 사용합니다.
    """

    settings_changed = pyqtSignal(dict)  # 변경된 설정 딕셔너리 전송

    def __init__(self, parent: Optional[QWidget] = None, current_settings: Dict[str, Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang_manager.get_text("pref_title"))
        self.resize(500, 400)
        self.current_settings = current_settings or {}
        self.init_ui()
        self.load_settings()

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화합니다."""
        layout = QVBoxLayout()

        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), lang_manager.get_text("pref_tab_general"))
        self.tabs.addTab(self.create_serial_tab(), lang_manager.get_text("pref_tab_serial"))
        self.tabs.addTab(self.create_cmd_tab(), lang_manager.get_text("pref_tab_command"))
        self.tabs.addTab(self.create_parser_tab(), lang_manager.get_text("pref_tab_parser"))
        self.tabs.addTab(self.create_logging_tab(), lang_manager.get_text("pref_tab_logging"))

        layout.addWidget(self.tabs)

        # 하단 버튼 (OK / Cancel / Apply)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton(lang_manager.get_text("pref_btn_ok"))
        self.ok_btn.clicked.connect(self.accept)

        self.cancel_btn = QPushButton(lang_manager.get_text("pref_btn_cancel"))
        self.cancel_btn.clicked.connect(self.reject)

        self.apply_btn = QPushButton(lang_manager.get_text("pref_btn_apply"))
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
        ui_group = QGroupBox(lang_manager.get_text("pref_grp_ui"))
        ui_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Korean", "ko")

        self.proportional_font_size_spin = QSpinBox()
        self.proportional_font_size_spin.setRange(8, 24)
        self.proportional_font_size_spin.setValue(10)

        ui_layout.addRow(lang_manager.get_text("pref_lbl_theme"), self.theme_combo)
        ui_layout.addRow(lang_manager.get_text("pref_lbl_language"), self.language_combo)
        ui_layout.addRow(lang_manager.get_text("pref_lbl_font_size"), self.proportional_font_size_spin)
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
        default_group = QGroupBox(lang_manager.get_text("pref_grp_default"))
        default_layout = QFormLayout()

        self.port_baud_combo = QComboBox()
        self.port_baud_combo.addItems(["9600", "115200", "921600"])
        self.port_baud_combo.setEditable(True)

        self.port_newline_combo = QComboBox()
        self.port_newline_combo.addItems(["\r", "\n", "\r\n"])
        self.port_newline_combo.setEditable(True)

        self.port_scan_interval_spin = QSpinBox()
        self.port_scan_interval_spin.setRange(1000, 60000)
        self.port_scan_interval_spin.setSingleStep(1000)
        self.port_scan_interval_spin.setSuffix(" ms")

        default_layout.addRow(lang_manager.get_text("pref_lbl_baud"), self.port_baud_combo)
        default_layout.addRow(lang_manager.get_text("pref_lbl_newline"), self.port_newline_combo)
        default_layout.addRow(lang_manager.get_text("pref_lbl_scan"), self.port_scan_interval_spin)
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
        format_group = QGroupBox(lang_manager.get_text("pref_grp_cmd_format"))
        format_layout = QFormLayout()

        self.prefix_combo = QComboBox()
        self.prefix_combo.setEditable(True)
        self.prefix_combo.addItems(["", "\\r", "\\n", "\\r\\n", "AT", "AT+"])

        self.suffix_combo = QComboBox()
        self.suffix_combo.setEditable(True)
        self.suffix_combo.addItems(["", "\\r", "\\n", "\\r\\n"])

        format_layout.addRow(lang_manager.get_text("pref_lbl_prefix"), self.prefix_combo)
        format_layout.addRow(lang_manager.get_text("pref_lbl_suffix"), self.suffix_combo)
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
        file_group = QGroupBox(lang_manager.get_text("pref_grp_logging"))
        file_layout = QFormLayout()

        path_layout = QHBoxLayout()
        self.log_path_edit = QLabel("Default Path")
        self.log_path_edit.setFrameStyle(QLabel.Sunken | QLabel.Panel)
        self.browse_btn = QPushButton(lang_manager.get_text("pref_btn_browse"))
        self.browse_btn.clicked.connect(self.browse_log_path)

        path_layout.addWidget(self.log_path_edit)
        path_layout.addWidget(self.browse_btn)

        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 100000)
        self.max_lines_spin.setSingleStep(100)

        file_layout.addRow(lang_manager.get_text("pref_lbl_log_path"), path_layout)
        file_layout.addRow(lang_manager.get_text("pref_lbl_max_lines"), self.max_lines_spin)
        file_group.setLayout(file_layout)

        layout.addWidget(file_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_parser_tab(self) -> QWidget:
        """Parser 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Parser Type 그룹
        parser_type_group = QGroupBox(lang_manager.get_text("pref_grp_parser_type"))
        parser_type_layout = QVBoxLayout()

        self.parser_type_button_group = QButtonGroup(self)
        self.parser_type_auto = QRadioButton(lang_manager.get_text("pref_parser_type_auto"))
        self.parser_type_at = QRadioButton(lang_manager.get_text("pref_parser_type_at"))
        self.parser_type_delimiter = QRadioButton(lang_manager.get_text("pref_parser_type_delimiter"))
        self.parser_type_fixed = QRadioButton(lang_manager.get_text("pref_parser_type_fixed"))
        self.parser_type_raw = QRadioButton(lang_manager.get_text("pref_parser_type_raw"))

        self.parser_type_button_group.addButton(self.parser_type_auto, 0)
        self.parser_type_button_group.addButton(self.parser_type_at, 1)
        self.parser_type_button_group.addButton(self.parser_type_delimiter, 2)
        self.parser_type_button_group.addButton(self.parser_type_fixed, 3)
        self.parser_type_button_group.addButton(self.parser_type_raw, 4)
        self.parser_type_auto.setChecked(True)

        parser_type_layout.addWidget(self.parser_type_auto)
        parser_type_layout.addWidget(self.parser_type_at)
        parser_type_layout.addWidget(self.parser_type_delimiter)
        parser_type_layout.addWidget(self.parser_type_fixed)
        parser_type_layout.addWidget(self.parser_type_raw)
        parser_type_group.setLayout(parser_type_layout)

        # Delimiter 설정 그룹
        delimiter_group = QGroupBox(lang_manager.get_text("pref_grp_delimiter"))
        delimiter_layout = QVBoxLayout()

        self.delimiter_list = QListWidget()
        self.delimiter_list.addItems(["\\r\\n", "0xFF", "0x7E"])

        delimiter_btn_layout = QHBoxLayout()
        self.delimiter_input = QLineEdit()
        self.delimiter_input.setPlaceholderText("0x00 or \\r\\n")
        self.add_delimiter_btn = QPushButton(lang_manager.get_text("pref_btn_add_delimiter"))
        self.del_delimiter_btn = QPushButton(lang_manager.get_text("pref_btn_del_delimiter"))
        self.add_delimiter_btn.clicked.connect(self._on_add_delimiter)
        self.del_delimiter_btn.clicked.connect(self._on_del_delimiter)

        delimiter_btn_layout.addWidget(self.delimiter_input)
        delimiter_btn_layout.addWidget(self.add_delimiter_btn)
        delimiter_btn_layout.addWidget(self.del_delimiter_btn)

        delimiter_layout.addWidget(self.delimiter_list)
        delimiter_layout.addLayout(delimiter_btn_layout)
        delimiter_group.setLayout(delimiter_layout)

        # Fixed Length 설정 그룹
        fixed_length_group = QGroupBox(lang_manager.get_text("pref_grp_fixed_length"))
        fixed_length_layout = QFormLayout()

        self.packet_length_spin = QSpinBox()
        self.packet_length_spin.setRange(1, 4096)
        self.packet_length_spin.setValue(64)

        fixed_length_layout.addRow(lang_manager.get_text("pref_lbl_packet_length"), self.packet_length_spin)
        fixed_length_group.setLayout(fixed_length_layout)

        # Inspector Options 그룹
        inspector_group = QGroupBox(lang_manager.get_text("pref_grp_inspector_options"))
        inspector_layout = QFormLayout()

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setValue(100)

        self.realtime_tracking_chk = QCheckBox(lang_manager.get_text("pref_chk_realtime_tracking"))
        self.realtime_tracking_chk.setChecked(True)

        self.auto_scroll_chk = QCheckBox(lang_manager.get_text("pref_chk_auto_scroll"))
        self.auto_scroll_chk.setChecked(True)

        inspector_layout.addRow(lang_manager.get_text("pref_lbl_buffer_size"), self.buffer_size_spin)
        inspector_layout.addRow("", self.realtime_tracking_chk)
        inspector_layout.addRow("", self.auto_scroll_chk)
        inspector_group.setLayout(inspector_layout)

        layout.addWidget(parser_type_group)
        layout.addWidget(delimiter_group)
        layout.addWidget(fixed_length_group)
        layout.addWidget(inspector_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _on_add_delimiter(self) -> None:
        """구분자 추가 버튼 핸들러"""
        text = self.delimiter_input.text().strip()
        if text and self.delimiter_list.findItems(text, Qt.MatchExactly) == []:
            self.delimiter_list.addItem(text)
            self.delimiter_input.clear()

    def _on_del_delimiter(self) -> None:
        """구분자 삭제 버튼 핸들러"""
        current_item = self.delimiter_list.currentItem()
        if current_item:
            self.delimiter_list.takeItem(self.delimiter_list.row(current_item))

    def browse_log_path(self) -> None:
        """로그 저장 경로 선택 다이얼로그를 엽니다."""
        directory = QFileDialog.getExistingDirectory(self, lang_manager.get_text("pref_dialog_title_select_dir"))
        if directory:
            self.log_path_edit.setText(directory)

    def _get_setting(self, key: str, default: Any = None) -> Any:
        """
        중첩된 설정 키에 안전하게 접근합니다.

        Args:
            key (str): 점(.)으로 구분된 설정 키 (예: "settings.theme")
            default (Any): 키가 없을 때 반환할 기본값

        Returns:
            Any: 설정 값 또는 기본값
        """
        keys = key.split('.')
        value = self.current_settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def load_settings(self) -> None:
        """현재 설정을 UI에 반영합니다."""
        # General
        theme = self._get_setting("settings.theme", "Dark").capitalize()
        self.theme_combo.setCurrentText(theme)

        lang_code = self._get_setting("settings.language", "en")
        index = self.language_combo.findData(lang_code)
        if index != -1:
            self.language_combo.setCurrentIndex(index)

        self.proportional_font_size_spin.setValue(self._get_setting("settings.proportional_font_size", 10))
        self.max_lines_spin.setValue(self._get_setting("settings.rx_max_lines", 2000))

        # Serial
        self.port_baud_combo.setCurrentText(str(self._get_setting("settings.port_baudrate", 115200)))
        self.port_newline_combo.setCurrentText(str(self._get_setting("settings.port_newline", "\n")))
        self.port_scan_interval_spin.setValue(self._get_setting("settings.port_scan_interval", 5000))

        # Command
        self.prefix_combo.setCurrentText(self._get_setting("settings.cmd_prefix", ""))
        self.suffix_combo.setCurrentText(self._get_setting("settings.cmd_suffix", ""))

        # Logging
        self.log_path_edit.setText(self._get_setting("logging.path", os.getcwd()))

    def apply_settings(self) -> None:
        """변경된 설정을 수집하여 시그널을 발생시킵니다."""
        new_settings = {
            "theme": self.theme_combo.currentText(),
            "language": self.language_combo.currentData(),
            "proportional_font_size": self.proportional_font_size_spin.value(),
            "port_baudrate": self.port_baud_combo.currentText(),
            "port_newline": self.port_newline_combo.currentText(),
            "port_scan_interval": self.port_scan_interval_spin.value(),
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
