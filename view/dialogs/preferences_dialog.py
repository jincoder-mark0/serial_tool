"""
환경 설정 대화상자 모듈

애플리케이션 전반의 설정을 탭 형태로 편집하고 PreferencesState DTO로 반환합니다.
View는 설정 표현/수집만 담당하며 SettingsManager에는 직접 접근하지 않습니다.
"""
import os
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from common.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_LOG_MAX_LINES,
    LANGUAGE_DISPLAY_NAME_KOREAN,
    MAX_PACKET_SIZE,
    MAX_SCAN_INTERVAL_MS,
    MIN_SCAN_INTERVAL_MS,
    VALID_BAUDRATES,
)
from common.defaults import (
    DEFAULT_PACKET_AUTOSCROLL,
    DEFAULT_PACKET_BUFFER_SIZE,
    DEFAULT_PACKET_GAP_MS,
    DEFAULT_PACKET_LENGTH,
    DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
    DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
    DEFAULT_PACKET_LENGTH_FIELD_SIZE,
    DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
    DEFAULT_PACKET_PARSER_TYPE,
    DEFAULT_PACKET_REALTIME,
    DEFAULT_PORT_LOCAL_ECHO,
    DEFAULT_PORT_NEWLINE,
    DEFAULT_PORT_SCAN_INTERVAL_MS,
    DEFAULT_PROP_FONT_SIZE,
)
from common.dtos import PreferencesState
from common.enums import (
    ByteOrder,
    LanguageType,
    LengthFieldSize,
    NewlineMode,
    ParserPreferenceIndex,
    ThemeType,
)
from view.managers.language_manager import language_manager
from view.managers.theme_manager import ThemeManager


class PreferencesDialog(QDialog):
    """환경 설정을 표시하고 PreferencesState로 수집하는 View."""

    settings_changed = pyqtSignal(object)  # PreferencesState

    def __init__(
        self,
        theme_manager: ThemeManager,
        parent: Optional[QWidget] = None,
        state: PreferencesState = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.setWindowTitle(language_manager.get_text("pref_title"))
        self.resize(500, 400)
        self.state = state if state else PreferencesState()
        self.init_ui()
        self.set_state_to_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), language_manager.get_text("pref_tab_general"))
        self.tabs.addTab(self.create_serial_tab(), language_manager.get_text("pref_tab_serial"))
        self.tabs.addTab(self.create_command_tab(), language_manager.get_text("pref_tab_command"))
        self.tabs.addTab(self.create_packet_tab(), language_manager.get_text("pref_tab_packet"))
        self.tabs.addTab(self.create_logging_tab(), language_manager.get_text("pref_tab_logging"))
        layout.addWidget(self.tabs)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)

        self.ok_btn = self.button_box.button(QDialogButtonBox.Ok)
        self.cancel_btn = self.button_box.button(QDialogButtonBox.Cancel)
        self.apply_btn = self.button_box.button(QDialogButtonBox.Apply)
        self.ok_btn.setText(language_manager.get_text("pref_btn_ok"))
        self.cancel_btn.setText(language_manager.get_text("pref_btn_cancel"))
        self.apply_btn.setText(language_manager.get_text("pref_btn_apply"))
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        ui_group = QGroupBox(language_manager.get_text("pref_grp_ui"))
        ui_layout = QFormLayout()

        self.theme_combo = QComboBox()
        themes = self._theme_manager.get_available_themes()
        if not themes:
            themes = [ThemeType.DARK.value, ThemeType.LIGHT.value]
        for theme_name in themes:
            lang_key = f"main_menu_theme_{theme_name.lower()}"
            display_name = language_manager.get_text(lang_key)
            if display_name == lang_key:
                display_name = theme_name
            self.theme_combo.addItem(display_name, theme_name)

        self.language_combo = QComboBox()
        for code, name in language_manager.get_available_languages().items():
            self.language_combo.addItem(name, code)
        if self.language_combo.count() == 0:
            self.language_combo.addItem("English", LanguageType.ENGLISH.value)
            self.language_combo.addItem(LANGUAGE_DISPLAY_NAME_KOREAN, LanguageType.KOREAN.value)

        self.proportional_font_size_spin = QSpinBox()
        self.proportional_font_size_spin.setRange(8, 24)
        self.proportional_font_size_spin.setValue(DEFAULT_PROP_FONT_SIZE)

        ui_layout.addRow(language_manager.get_text("pref_lbl_theme"), self.theme_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_language"), self.language_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_font_size"), self.proportional_font_size_spin)
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_serial_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        default_group = QGroupBox(language_manager.get_text("pref_grp_default"))
        default_layout = QFormLayout()

        self.port_baudrate_combo = QComboBox()
        self.port_baudrate_combo.addItems([str(value) for value in VALID_BAUDRATES])
        self.port_baudrate_combo.setEditable(True)
        self.port_baudrate_combo.setCurrentText(str(DEFAULT_BAUDRATE))

        self.port_newline_combo = QComboBox()
        self.port_newline_combo.addItems([mode.value for mode in NewlineMode])
        self.port_newline_combo.setEditable(True)
        self.port_newline_combo.setCurrentText(DEFAULT_PORT_NEWLINE)

        self.port_local_echo_chk = QCheckBox(language_manager.get_text("pref_chk_local_echo"))
        self.port_local_echo_chk.setChecked(DEFAULT_PORT_LOCAL_ECHO)

        self.port_scan_interval_ms_spin = QSpinBox()
        self.port_scan_interval_ms_spin.setRange(MIN_SCAN_INTERVAL_MS, MAX_SCAN_INTERVAL_MS)
        self.port_scan_interval_ms_spin.setSingleStep(DEFAULT_PORT_SCAN_INTERVAL_MS)
        self.port_scan_interval_ms_spin.setValue(DEFAULT_PORT_SCAN_INTERVAL_MS)
        self.port_scan_interval_ms_spin.setSuffix(" ms")

        default_layout.addRow(language_manager.get_text("pref_lbl_baudrate"), self.port_baudrate_combo)
        default_layout.addRow(language_manager.get_text("pref_lbl_newline"), self.port_newline_combo)
        default_layout.addRow(language_manager.get_text("pref_lbl_local_echo"), self.port_local_echo_chk)
        default_layout.addRow(language_manager.get_text("pref_lbl_scan"), self.port_scan_interval_ms_spin)
        default_group.setLayout(default_layout)
        layout.addWidget(default_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_command_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        format_group = QGroupBox(language_manager.get_text("pref_grp_command_format"))
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
        widget = QWidget()
        layout = QVBoxLayout()
        file_group = QGroupBox(language_manager.get_text("pref_grp_logging"))
        file_layout = QFormLayout()

        path_layout = QHBoxLayout()
        self.log_path_lbl = QLabel(language_manager.get_text("pref_lbl_log_path_placeholder"))
        self.log_path_lbl.setFrameStyle(QLabel.Sunken | QLabel.Panel)
        self.browse_btn = QPushButton(language_manager.get_text("pref_btn_browse"))
        self.browse_btn.clicked.connect(self.browse_log_path)
        path_layout.addWidget(self.log_path_lbl)
        path_layout.addWidget(self.browse_btn)

        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 100000)
        self.max_lines_spin.setSingleStep(100)
        self.max_lines_spin.setValue(DEFAULT_LOG_MAX_LINES)

        file_layout.addRow(language_manager.get_text("pref_lbl_log_path"), path_layout)
        file_layout.addRow(language_manager.get_text("pref_lbl_max_lines"), self.max_lines_spin)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_packet_tab(self) -> QWidget:
        widget = QWidget()

        parser_type_group = QGroupBox(language_manager.get_text("pref_grp_parser_type"))
        parser_type_layout = QVBoxLayout()
        self.parser_type_button_group = QButtonGroup(self)

        parser_buttons = [
            ("parser_type_auto", "pref_parser_type_auto", ParserPreferenceIndex.AUTO),
            ("parser_type_at", "pref_parser_type_at", ParserPreferenceIndex.AT),
            ("parser_type_delimiter", "pref_parser_type_delimiter", ParserPreferenceIndex.DELIMITER),
            ("parser_type_fixed", "pref_parser_type_fixed", ParserPreferenceIndex.FIXED_LENGTH),
            ("parser_type_raw", "pref_parser_type_raw", ParserPreferenceIndex.RAW),
            ("parser_type_length_field", "pref_parser_type_length_field", ParserPreferenceIndex.LENGTH_FIELD),
            ("parser_type_gap", "pref_parser_type_gap", ParserPreferenceIndex.GAP),
        ]
        for attr_name, lang_key, preference_index in parser_buttons:
            button = QRadioButton(language_manager.get_text(lang_key))
            setattr(self, attr_name, button)
            self.parser_type_button_group.addButton(button, int(preference_index))
            parser_type_layout.addWidget(button)
        self.parser_type_button_group.button(DEFAULT_PACKET_PARSER_TYPE).setChecked(True)
        parser_type_group.setLayout(parser_type_layout)

        delimiter_group = QGroupBox(language_manager.get_text("pref_grp_delimiter"))
        delimiter_layout = QVBoxLayout()
        self.delimiter_list = QListWidget()
        delimiter_btn_layout = QHBoxLayout()
        self.delimiter_input = QLineEdit()
        self.delimiter_input.setPlaceholderText("0x00 or \\r\\n")
        self.add_delimiter_btn = QPushButton(language_manager.get_text("pref_btn_add_delimiter"))
        self.del_delimiter_btn = QPushButton(language_manager.get_text("pref_btn_del_delimiter"))
        self.add_delimiter_btn.clicked.connect(self._on_add_delimiter)
        self.del_delimiter_btn.clicked.connect(self._on_del_delimiter)
        delimiter_btn_layout.addWidget(self.delimiter_input)
        delimiter_btn_layout.addWidget(self.add_delimiter_btn)
        delimiter_btn_layout.addWidget(self.del_delimiter_btn)
        delimiter_layout.addWidget(self.delimiter_list)
        delimiter_layout.addLayout(delimiter_btn_layout)
        delimiter_group.setLayout(delimiter_layout)

        length_field_group = QGroupBox(language_manager.get_text("pref_grp_length_field"))
        length_field_layout = QFormLayout()
        self.length_field_offset_spin = QSpinBox()
        self.length_field_offset_spin.setRange(0, MAX_PACKET_SIZE)
        self.length_field_offset_spin.setValue(DEFAULT_PACKET_LENGTH_FIELD_OFFSET)

        self.length_field_size_combo = QComboBox()
        for size in LengthFieldSize:
            self.length_field_size_combo.addItem(str(size.value), size.value)
        size_idx = self.length_field_size_combo.findData(DEFAULT_PACKET_LENGTH_FIELD_SIZE)
        if size_idx >= 0:
            self.length_field_size_combo.setCurrentIndex(size_idx)

        self.length_field_endian_combo = QComboBox()
        self.length_field_endian_combo.addItem(
            language_manager.get_text("pref_endian_big"), ByteOrder.BIG.value
        )
        self.length_field_endian_combo.addItem(
            language_manager.get_text("pref_endian_little"), ByteOrder.LITTLE.value
        )
        endian_idx = self.length_field_endian_combo.findData(DEFAULT_PACKET_LENGTH_FIELD_ENDIAN)
        if endian_idx >= 0:
            self.length_field_endian_combo.setCurrentIndex(endian_idx)

        self.length_includes_header_chk = QCheckBox(
            language_manager.get_text("pref_chk_length_includes_header")
        )
        self.length_includes_header_chk.setChecked(DEFAULT_PACKET_LENGTH_INCLUDES_HEADER)

        length_field_layout.addRow(
            language_manager.get_text("pref_lbl_length_field_offset"),
            self.length_field_offset_spin,
        )
        length_field_layout.addRow(
            language_manager.get_text("pref_lbl_length_field_size"),
            self.length_field_size_combo,
        )
        length_field_layout.addRow(
            language_manager.get_text("pref_lbl_length_field_endian"),
            self.length_field_endian_combo,
        )
        length_field_layout.addRow(self.length_includes_header_chk)
        length_field_group.setLayout(length_field_layout)

        gap_group = QGroupBox(language_manager.get_text("pref_grp_gap"))
        gap_layout = QFormLayout()
        self.gap_ms_spin = QSpinBox()
        self.gap_ms_spin.setRange(1, MAX_SCAN_INTERVAL_MS)
        self.gap_ms_spin.setValue(DEFAULT_PACKET_GAP_MS)
        gap_layout.addRow(language_manager.get_text("pref_lbl_gap_ms"), self.gap_ms_spin)
        gap_group.setLayout(gap_layout)

        fixed_length_group = QGroupBox(language_manager.get_text("pref_grp_fixed_length"))
        fixed_length_layout = QFormLayout()
        self.packet_length_spin = QSpinBox()
        self.packet_length_spin.setRange(1, MAX_PACKET_SIZE)
        self.packet_length_spin.setValue(DEFAULT_PACKET_LENGTH)
        fixed_length_layout.addRow(language_manager.get_text("pref_lbl_packet_length"), self.packet_length_spin)
        fixed_length_group.setLayout(fixed_length_layout)

        at_color_group = QGroupBox(language_manager.get_text("pref_grp_at_colors"))
        at_color_layout = QVBoxLayout()
        self.at_color_ok_chk = QCheckBox(language_manager.get_text("pref_chk_at_ok"))
        self.at_color_error_chk = QCheckBox(language_manager.get_text("pref_chk_at_error"))
        self.at_color_urc_chk = QCheckBox(language_manager.get_text("pref_chk_at_urc"))
        self.at_color_prompt_chk = QCheckBox(language_manager.get_text("pref_chk_at_prompt"))
        for checkbox in (
            self.at_color_ok_chk,
            self.at_color_error_chk,
            self.at_color_urc_chk,
            self.at_color_prompt_chk,
        ):
            at_color_layout.addWidget(checkbox)
        at_color_group.setLayout(at_color_layout)

        packet_group = QGroupBox(language_manager.get_text("pref_grp_packet_options"))
        packet_layout = QFormLayout()
        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setValue(DEFAULT_PACKET_BUFFER_SIZE)
        self.realtime_tracking_chk = QCheckBox(language_manager.get_text("pref_chk_realtime_tracking"))
        self.realtime_tracking_chk.setChecked(DEFAULT_PACKET_REALTIME)
        self.auto_scroll_chk = QCheckBox(language_manager.get_text("pref_chk_auto_scroll"))
        self.auto_scroll_chk.setChecked(DEFAULT_PACKET_AUTOSCROLL)
        packet_layout.addRow(language_manager.get_text("pref_lbl_buffer_size"), self.buffer_size_spin)
        packet_layout.addRow("", self.realtime_tracking_chk)
        packet_layout.addRow("", self.auto_scroll_chk)
        packet_group.setLayout(packet_layout)

        h_layout = QHBoxLayout()
        left_v_layout = QVBoxLayout()
        right_v_layout = QVBoxLayout()
        left_v_layout.addWidget(parser_type_group)
        left_v_layout.addWidget(length_field_group)
        left_v_layout.addWidget(gap_group)
        left_v_layout.addWidget(delimiter_group)
        right_v_layout.addWidget(fixed_length_group)
        right_v_layout.addWidget(at_color_group)
        right_v_layout.addWidget(packet_group)
        right_v_layout.addStretch()
        h_layout.addLayout(left_v_layout)
        h_layout.addLayout(right_v_layout)
        widget.setLayout(h_layout)
        return widget

    def _on_add_delimiter(self) -> None:
        text = self.delimiter_input.text().strip()
        if text and self.delimiter_list.findItems(text, Qt.MatchExactly) == []:
            self.delimiter_list.addItem(text)
            self.delimiter_input.clear()

    def _on_del_delimiter(self) -> None:
        current_item = self.delimiter_list.currentItem()
        if current_item:
            self.delimiter_list.takeItem(self.delimiter_list.row(current_item))

    def browse_log_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, language_manager.get_text("pref_dialog_title_select_dir")
        )
        if directory:
            self.log_path_lbl.setText(directory)

    def set_state_to_ui(self) -> None:
        theme_index = -1
        for index in range(self.theme_combo.count()):
            if str(self.theme_combo.itemData(index)).lower() == str(self.state.theme).lower():
                theme_index = index
                break
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
        elif self.theme_combo.count() > 0:
            self.theme_combo.setCurrentIndex(0)

        language_index = self.language_combo.findData(self.state.language)
        if language_index >= 0:
            self.language_combo.setCurrentIndex(language_index)

        self.proportional_font_size_spin.setValue(self.state.font_size)
        self.max_lines_spin.setValue(self.state.max_log_lines)
        self.port_baudrate_combo.setCurrentText(str(self.state.baudrate))
        self.port_newline_combo.setCurrentText(self.state.newline)
        self.port_local_echo_chk.setChecked(self.state.local_echo_enabled)
        self.port_scan_interval_ms_spin.setValue(self.state.scan_interval_ms)
        self.prefix_combo.setCurrentText(self.state.command_prefix)
        self.suffix_combo.setCurrentText(self.state.command_suffix)
        self.log_path_lbl.setText(self.state.log_dir or os.getcwd())

        parser_button = self.parser_type_button_group.button(self.state.parser_type)
        if parser_button:
            parser_button.setChecked(True)
        self.delimiter_list.clear()
        self.delimiter_list.addItems(self.state.delimiters)
        self.packet_length_spin.setValue(self.state.packet_length)
        self.length_field_offset_spin.setValue(self.state.length_field_offset)

        size_idx = self.length_field_size_combo.findData(self.state.length_field_size)
        if size_idx >= 0:
            self.length_field_size_combo.setCurrentIndex(size_idx)
        endian_idx = self.length_field_endian_combo.findData(self.state.length_field_endian)
        if endian_idx >= 0:
            self.length_field_endian_combo.setCurrentIndex(endian_idx)

        self.length_includes_header_chk.setChecked(self.state.length_includes_header)
        self.gap_ms_spin.setValue(self.state.gap_ms)
        self.at_color_ok_chk.setChecked(self.state.at_color_ok)
        self.at_color_error_chk.setChecked(self.state.at_color_error)
        self.at_color_urc_chk.setChecked(self.state.at_color_urc)
        self.at_color_prompt_chk.setChecked(self.state.at_color_prompt)
        self.buffer_size_spin.setValue(self.state.packet_buffer_size)
        self.realtime_tracking_chk.setChecked(self.state.packet_realtime)
        self.auto_scroll_chk.setChecked(self.state.packet_autoscroll)

    def apply_settings(self) -> None:
        delimiters = [self.delimiter_list.item(i).text() for i in range(self.delimiter_list.count())]
        try:
            baud_val = int(self.port_baudrate_combo.currentText())
        except ValueError:
            baud_val = DEFAULT_BAUDRATE

        new_state = PreferencesState(
            theme=self.theme_combo.currentData(),
            language=self.language_combo.currentData(),
            font_size=self.proportional_font_size_spin.value(),
            max_log_lines=self.max_lines_spin.value(),
            baudrate=baud_val,
            newline=self.port_newline_combo.currentText(),
            local_echo_enabled=self.port_local_echo_chk.checkState() == Qt.Checked,
            scan_interval_ms=self.port_scan_interval_ms_spin.value(),
            command_prefix=self.prefix_combo.currentText(),
            command_suffix=self.suffix_combo.currentText(),
            log_dir=self.log_path_lbl.text(),
            parser_type=self.parser_type_button_group.checkedId(),
            delimiters=delimiters,
            packet_length=self.packet_length_spin.value(),
            length_field_offset=self.length_field_offset_spin.value(),
            length_field_size=self.length_field_size_combo.currentData(),
            length_field_endian=self.length_field_endian_combo.currentData(),
            length_includes_header=self.length_includes_header_chk.checkState() == Qt.Checked,
            gap_ms=self.gap_ms_spin.value(),
            at_color_ok=self.at_color_ok_chk.checkState() == Qt.Checked,
            at_color_error=self.at_color_error_chk.checkState() == Qt.Checked,
            at_color_urc=self.at_color_urc_chk.checkState() == Qt.Checked,
            at_color_prompt=self.at_color_prompt_chk.checkState() == Qt.Checked,
            packet_buffer_size=self.buffer_size_spin.value(),
            packet_realtime=self.realtime_tracking_chk.checkState() == Qt.Checked,
            packet_autoscroll=self.auto_scroll_chk.checkState() == Qt.Checked,
        )
        self.settings_changed.emit(new_state)

    def accept(self) -> None:
        self.apply_settings()
        super().accept()
