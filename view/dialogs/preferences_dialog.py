from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QListWidget, QCheckBox, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, Any
import os
from view.managers.language_manager import language_manager
from view.managers.theme_manager import ThemeManager
from common.constants import (
    VALID_BAUDRATES,
    DEFAULT_LOG_MAX_LINES,
    MIN_SCAN_INTERVAL_MS,
    MAX_SCAN_INTERVAL_MS,
    MAX_PACKET_SIZE,
    ConfigKeys
)
from common.enums import NewlineMode, ThemeType # [New]
from common.dtos import PreferencesState
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QListWidget, QCheckBox, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, Any
import os

class PreferencesDialog(QDialog):
    """
    설정 관리 대화상자
    MVP 패턴 준수: View는 데이터를 보여주고 사용자 입력을 수집하여 반환만 함.
    SettingsManager에 직접 접근하지 않음.
    """

    # 변경된 설정을 DTO로 전달
    settings_changed = pyqtSignal(object) # PreferencesState

    def __init__(self, parent: Optional[QWidget] = None, state: PreferencesState = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(language_manager.get_text("pref_title"))
        self.resize(500, 400)

        # DTO가 없으면 기본값 생성
        self.state = state if state else PreferencesState()

        self.init_ui()
        self.set_state_to_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화"""
        layout = QVBoxLayout()

        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), language_manager.get_text("pref_tab_general"))
        self.tabs.addTab(self.create_serial_tab(), language_manager.get_text("pref_tab_serial"))
        self.tabs.addTab(self.create_command_tab(), language_manager.get_text("pref_tab_command"))
        self.tabs.addTab(self.create_packet_tab(), language_manager.get_text("pref_tab_packet"))
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
        """General 탭 생성."""
        widget = QWidget()
        layout = QVBoxLayout()

        # UI Appearance 그룹
        ui_group = QGroupBox(language_manager.get_text("pref_grp_ui"))
        ui_layout = QFormLayout()

        # 테마 목록 동적 로드
        self.theme_combo = QComboBox()
        theme_manager = ThemeManager()
        themes = theme_manager.get_available_themes()
        if not themes:
            themes = [ThemeType.DARK.value.capitalize(), ThemeType.LIGHT.value.capitalize()]
        self.theme_combo.addItems(themes)

        # 언어 목록 동적 로드
        self.language_combo = QComboBox()
        languages = language_manager.get_available_languages()

        # 정렬하여 추가 (영어 우선 등 필요한 경우 로직 추가 가능)
        # 여기서는 단순히 추가
        for code, name in languages.items():
            self.language_combo.addItem(name, code)

        # Fallback if empty
        if self.language_combo.count() == 0:
            self.language_combo.addItem("English", "en")
            self.language_combo.addItem("Korean", "ko")

        self.proportional_font_size_spin = QSpinBox()
        self.proportional_font_size_spin.setRange(8, 24)
        self.proportional_font_size_spin.setValue(10)

        ui_layout.addRow(language_manager.get_text("pref_lbl_theme"), self.theme_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_language"), self.language_combo)
        ui_layout.addRow(language_manager.get_text("pref_lbl_font_size"), self.proportional_font_size_spin)
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

        self.port_baudrate_combo = QComboBox()
        self.port_baudrate_combo.addItems([str(baudrate) for baudrate in VALID_BAUDRATES])
        self.port_baudrate_combo.setEditable(True)

        self.port_newline_combo = QComboBox()

        self.port_newline_combo.addItems([mode.value for mode in NewlineMode])
        self.port_newline_combo.setEditable(True)

        self.port_local_echo_chk = QCheckBox(language_manager.get_text("pref_chk_local_echo"))

        self.port_scan_interval_spin = QSpinBox()
        self.port_scan_interval_spin.setRange(MIN_SCAN_INTERVAL_MS, MAX_SCAN_INTERVAL_MS)
        self.port_scan_interval_spin.setSingleStep(1000)
        self.port_scan_interval_spin.setSuffix(" ms")

        default_layout.addRow(language_manager.get_text("pref_lbl_baudrate"), self.port_baudrate_combo)
        default_layout.addRow(language_manager.get_text("pref_lbl_newline"), self.port_newline_combo)
        default_layout.addRow(language_manager.get_text("pref_lbl_local_echo"), self.port_local_echo_chk)
        default_layout.addRow(language_manager.get_text("pref_lbl_scan"), self.port_scan_interval_spin)
        default_group.setLayout(default_layout)

        layout.addWidget(default_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_command_tab(self) -> QWidget:
        """Command 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Prefix/Suffix 그룹
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
        """Logging 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # File Logging 그룹
        file_group = QGroupBox(language_manager.get_text("pref_grp_logging"))
        file_layout = QFormLayout()

        path_layout = QHBoxLayout()
        self.log_path_edit = QLabel("Default ResourcePath")
        self.log_path_edit.setFrameStyle(QLabel.Sunken | QLabel.Panel)
        self.browse_btn = QPushButton(language_manager.get_text("pref_btn_browse"))
        self.browse_btn.clicked.connect(self.browse_log_path)

        path_layout.addWidget(self.log_path_edit)
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
        """Packet 설정 탭을 생성합니다."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Parser Type 그룹
        parser_type_group = QGroupBox(language_manager.get_text("pref_grp_parser_type"))
        parser_type_layout = QVBoxLayout()

        self.parser_type_button_group = QButtonGroup(self)
        self.parser_type_auto = QRadioButton(language_manager.get_text("pref_parser_type_auto"))
        self.parser_type_at = QRadioButton(language_manager.get_text("pref_parser_type_at"))
        self.parser_type_delimiter = QRadioButton(language_manager.get_text("pref_parser_type_delimiter"))
        self.parser_type_fixed = QRadioButton(language_manager.get_text("pref_parser_type_fixed"))
        self.parser_type_raw = QRadioButton(language_manager.get_text("pref_parser_type_raw"))

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
        delimiter_group = QGroupBox(language_manager.get_text("pref_grp_delimiter"))
        delimiter_layout = QVBoxLayout()

        self.delimiter_list = QListWidget()
        # 기본값은 set_state_to_ui에서 처리하므로 여기서는 비워둡니다.
        # self.delimiter_list.addItems(["\\r\\n", "0xFF", "0x7E"])

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

        # Fixed Length 설정 그룹
        fixed_length_group = QGroupBox(language_manager.get_text("pref_grp_fixed_length"))
        fixed_length_layout = QFormLayout()

        self.packet_length_spin = QSpinBox()
        self.packet_length_spin.setRange(1, MAX_PACKET_SIZE)
        self.packet_length_spin.setValue(64)

        fixed_length_layout.addRow(language_manager.get_text("pref_lbl_packet_length"), self.packet_length_spin)
        fixed_length_group.setLayout(fixed_length_layout)

        # AT Color Rules 그룹
        at_color_group = QGroupBox(language_manager.get_text("pref_grp_at_colors"))
        at_color_layout = QVBoxLayout()

        self.at_color_ok_chk = QCheckBox(language_manager.get_text("pref_chk_at_ok"))
        self.at_color_error_chk = QCheckBox(language_manager.get_text("pref_chk_at_error"))
        self.at_color_urc_chk = QCheckBox(language_manager.get_text("pref_chk_at_urc"))
        self.at_color_prompt_chk = QCheckBox(language_manager.get_text("pref_chk_at_prompt"))

        at_color_layout.addWidget(self.at_color_ok_chk)
        at_color_layout.addWidget(self.at_color_error_chk)
        at_color_layout.addWidget(self.at_color_urc_chk)
        at_color_layout.addWidget(self.at_color_prompt_chk)
        at_color_group.setLayout(at_color_layout)

        # Inspector Options 그룹
        packet_group = QGroupBox(language_manager.get_text("pref_grp_packet_options"))
        packet_layout = QFormLayout()

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setValue(100)

        self.realtime_tracking_chk = QCheckBox(language_manager.get_text("pref_chk_realtime_tracking"))
        self.realtime_tracking_chk.setChecked(True)

        self.auto_scroll_chk = QCheckBox(language_manager.get_text("pref_chk_auto_scroll"))
        self.auto_scroll_chk.setChecked(True)

        packet_layout.addRow(language_manager.get_text("pref_lbl_buffer_size"), self.buffer_size_spin)
        packet_layout.addRow("", self.realtime_tracking_chk)
        packet_layout.addRow("", self.auto_scroll_chk)
        packet_group.setLayout(packet_layout)

        # 레이아웃 배치
        # 좌우 2열로 배치하여 공간 활용
        h_layout = QHBoxLayout()
        left_v_layout = QVBoxLayout()
        right_v_layout = QVBoxLayout()

        left_v_layout.addWidget(parser_type_group)
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
        directory = QFileDialog.getExistingDirectory(self, language_manager.get_text("pref_dialog_title_select_dir"))
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

    def set_state_to_ui(self) -> None:
        """
        DTO 상태를 UI에 반영합니다.
        """
        # General
        # 대소문자 무시하고 매칭 (Dark vs dark)
        index = self.theme_combo.findText(self.state.theme, Qt.MatchFixedString)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
        else:
             # 테마가 없을 경우 기본값 0번
             self.theme_combo.setCurrentIndex(0)

        index = self.language_combo.findData(self.state.language)
        if index != -1:
            self.language_combo.setCurrentIndex(index)

        self.proportional_font_size_spin.setValue(self.state.font_size)
        self.max_lines_spin.setValue(self.state.max_log_lines)

        # Serial
        self.port_baudrate_combo.setCurrentText(str(self.state.baudrate))
        self.port_newline_combo.setCurrentText(self.state.newline)
        self.port_local_echo_chk.setChecked(self.state.local_echo)
        self.port_scan_interval_spin.setValue(self.state.scan_interval)

        # Command
        self.prefix_combo.setCurrentText(self.state.cmd_prefix)
        self.suffix_combo.setCurrentText(self.state.cmd_suffix)

        # Logging
        self.log_path_edit.setText(self.state.log_path or os.getcwd())

        # Packet
        btn = self.parser_type_button_group.button(self.state.parser_type)
        if btn:
            btn.setChecked(True)

        self.delimiter_list.clear()
        self.delimiter_list.addItems(self.state.delimiters)

        self.packet_length_spin.setValue(self.state.packet_length)

        self.at_color_ok_chk.setChecked(self.state.at_color_ok)
        self.at_color_error_chk.setChecked(self.state.at_color_error)
        self.at_color_urc_chk.setChecked(self.state.at_color_urc)
        self.at_color_prompt_chk.setChecked(self.state.at_color_prompt)

        self.buffer_size_spin.setValue(self.state.packet_buffer_size)
        self.realtime_tracking_chk.setChecked(self.state.packet_realtime)
        self.auto_scroll_chk.setChecked(self.state.packet_autoscroll)

    def apply_settings(self) -> None:
        """변경된 설정을 DTO로 수집하여 시그널을 발생시킵니다."""
        delimiters = [self.delimiter_list.item(i).text() for i in range(self.delimiter_list.count())]

        newline_val = self.port_newline_combo.currentText()

        try:
            baud_val = int(self.port_baudrate_combo.currentText())
        except ValueError:
            baud_val = 115200

        new_state = PreferencesState(
            theme=self.theme_combo.currentText(),
            language=self.language_combo.currentData(),
            font_size=self.proportional_font_size_spin.value(),
            max_log_lines=self.max_lines_spin.value(),
            baudrate=baud_val,
            newline=newline_val,
            local_echo=self.port_local_echo_chk.checkState() == Qt.Checked,
            scan_interval=self.port_scan_interval_spin.value(),
            cmd_prefix=self.prefix_combo.currentText(),
            cmd_suffix=self.suffix_combo.currentText(),
            log_path=self.log_path_edit.text(),

            # Packet Settings
            parser_type=self.parser_type_button_group.checkedId(),
            delimiters=delimiters,
            packet_length=self.packet_length_spin.value(),
            at_color_ok=self.at_color_ok_chk.checkState() == Qt.Checked,
            at_color_error=self.at_color_error_chk.checkState() == Qt.Checked,
            at_color_urc=self.at_color_urc_chk.checkState() == Qt.Checked,
            at_color_prompt=self.at_color_prompt_chk.checkState() == Qt.Checked,
            packet_buffer_size=self.buffer_size_spin.value(),
            packet_realtime=self.realtime_tracking_chk.checkState() == Qt.Checked,
            packet_autoscroll=self.auto_scroll_chk.checkState() == Qt.Checked
        )

        self.settings_changed.emit(new_state)

    def accept(self) -> None:
        """OK 버튼 클릭 시 설정을 적용하고 닫습니다."""
        self.apply_settings()
        super().accept()
