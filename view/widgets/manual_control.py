from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QLineEdit, QLabel, QFileDialog, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.language_manager import language_manager

class ManualControlWidget(QWidget):
    """
    수동 명령 전송, 파일 전송, 로그 저장 및 각종 제어 옵션을 제공하는 위젯 클래스입니다.
    (구 OperationArea)
    """

    # 시그널 정의
    send_command_requested = pyqtSignal(str, bool, bool) # text, hex_mode, with_enter
    send_file_requested = pyqtSignal(str) # filepath
    file_selected = pyqtSignal(str) # filepath
    save_log_requested = pyqtSignal(str) # filepath
    save_log_requested = pyqtSignal(str) # filepath
    clear_info_requested = pyqtSignal()

    # 접두사/접미사 상수 (CommandControl과 동일)
    PREFIX_KEY = "prefix"
    SUFFIX_KEY = "suffix"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2) # 간격 최소화

        # 1. 제어 옵션 그룹 (Control Options Group)
        self.option_group = QGroupBox(language_manager.get_text("manual_ctrl_grp_control"))
        option_layout = QGridLayout()
        option_layout.setContentsMargins(2, 2, 2, 2) # 내부 여백 최소화
        option_layout.setSpacing(5)

        self.hex_mode_check = QCheckBox(language_manager.get_text("manual_ctrl_chk_hex"))
        self.hex_mode_check.setToolTip(language_manager.get_text("manual_ctrl_chk_hex_tooltip"))

        # self.enter_check 제거됨 (Suffix로 대체)

        self.clear_btn = QPushButton(language_manager.get_text("manual_ctrl_btn_clear"))
        self.clear_btn.setToolTip(language_manager.get_text("manual_ctrl_btn_clear_tooltip"))
        self.clear_btn.clicked.connect(self.clear_info_requested.emit)

        self.save_log_btn = QPushButton(language_manager.get_text("manual_ctrl_btn_save_log"))
        self.save_log_btn.setToolTip(language_manager.get_text("manual_ctrl_btn_save_log_tooltip"))
        self.save_log_btn.clicked.connect(self.on_save_log_clicked)

        # 흐름 제어 (Flow Control - RTS/DTR)
        self.rts_check = QCheckBox(language_manager.get_text("manual_ctrl_chk_rts"))
        self.rts_check.setToolTip(language_manager.get_text("manual_ctrl_chk_rts_tooltip"))
        self.dtr_check = QCheckBox(language_manager.get_text("manual_ctrl_chk_dtr"))
        self.dtr_check.setToolTip(language_manager.get_text("manual_ctrl_chk_dtr_tooltip"))

        # 접두사/접미사 체크박스 이동
        self.prefix_check = QCheckBox(language_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_check = QCheckBox(language_manager.get_text("manual_ctrl_chk_suffix"))

        option_layout.addWidget(self.hex_mode_check, 0, 0)
        option_layout.addWidget(self.rts_check, 0, 1)
        option_layout.addWidget(self.dtr_check, 0, 2)

        option_layout.addWidget(self.prefix_check, 1, 0)
        option_layout.addWidget(self.suffix_check, 1, 1)

        option_layout.addWidget(self.clear_btn, 2, 0, 1, 2)
        option_layout.addWidget(self.save_log_btn, 2, 2, 1, 2)

        self.option_group.setLayout(option_layout)

        # 2. 접두사/접미사 설정 그룹 (Prefix/Suffix Group) - Removed
        # self.format_group 제거됨

        # 3. 수동 전송 영역 (Manual Send Area)
        self.send_group = QGroupBox(language_manager.get_text("manual_ctrl_grp_manual"))
        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(2, 2, 2, 2)
        send_layout.setSpacing(5)

        self.input_field = QLineEdit() # QTextEdit -> QLineEdit 변경
        self.input_field.setPlaceholderText(language_manager.get_text("manual_ctrl_input_cmd_placeholder"))
        self.input_field.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.input_field.returnPressed.connect(self.on_send_clicked) # Enter 키 지원

        self.send_btn = QPushButton(language_manager.get_text("manual_ctrl_btn_send"))
        self.send_btn.setCursor(Qt.PointingHandCursor)
        # 스타일은 QSS에서 처리 권장 (강조색)
        self.send_btn.setProperty("class", "accent")
        self.send_btn.clicked.connect(self.on_send_clicked)

        send_layout.addWidget(self.input_field, 1)
        send_layout.addWidget(self.send_btn)

        self.send_group.setLayout(send_layout)

        # 3. 파일 전송 영역 (File Transfer Area)
        self.file_group = QGroupBox(language_manager.get_text("manual_ctrl_grp_file"))
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(2, 2, 2, 2)
        file_layout.setSpacing(5)

        self.file_path_label = QLabel(language_manager.get_text("manual_ctrl_lbl_no_file"))
        self.file_path_label.setStyleSheet("color: gray; border: 1px solid #555; padding: 2px; border-radius: 2px;")

        self.select_file_btn = QPushButton(language_manager.get_text("manual_ctrl_btn_select_file"))
        self.select_file_btn.clicked.connect(self.on_select_file_clicked)

        self.send_file_btn = QPushButton(language_manager.get_text("manual_ctrl_btn_send_file"))
        self.send_file_btn.clicked.connect(self.on_send_file_clicked)

        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.select_file_btn)
        file_layout.addWidget(self.send_file_btn)

        self.file_group.setLayout(file_layout)

        layout.addWidget(self.option_group)
        # layout.addWidget(self.format_group) # 제거됨
        layout.addWidget(self.send_group)
        layout.addWidget(self.file_group)
        layout.addStretch() # 하단 여백 추가

        self.setLayout(layout)

        # 초기 상태 설정
        self.set_controls_enabled(False)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.option_group.setTitle(language_manager.get_text("manual_ctrl_grp_control"))
        self.hex_mode_check.setText(language_manager.get_text("manual_ctrl_chk_hex"))
        # self.enter_check.setText(language_manager.get_text("manual_ctrl_chk_enter")) # 제거됨
        self.clear_btn.setText(language_manager.get_text("manual_ctrl_btn_clear"))
        self.save_log_btn.setText(language_manager.get_text("manual_ctrl_btn_save_log"))
        self.rts_check.setText(language_manager.get_text("manual_ctrl_chk_rts"))
        self.dtr_check.setText(language_manager.get_text("manual_ctrl_chk_dtr"))

        # self.format_group.setTitle(language_manager.get_text("manual_ctrl_grp_format")) # 제거됨
        self.prefix_check.setText(language_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_check.setText(language_manager.get_text("manual_ctrl_chk_suffix"))

        self.send_group.setTitle(language_manager.get_text("manual_ctrl_grp_manual"))
        self.send_btn.setText(language_manager.get_text("manual_ctrl_btn_send"))
        self.input_field.setPlaceholderText(language_manager.get_text("manual_ctrl_input_cmd_placeholder"))

        self.file_group.setTitle(language_manager.get_text("manual_ctrl_grp_file"))
        # 파일이 선택되지 않은 상태인지 확인
        if "No file selected" in self.file_path_label.text() or \
           "파일이 선택되지 않음" in self.file_path_label.text():
              self.file_path_label.setText(language_manager.get_text("manual_ctrl_lbl_no_file"))

        self.select_file_btn.setText(language_manager.get_text("manual_ctrl_btn_select_file"))
        self.send_file_btn.setText(language_manager.get_text("manual_ctrl_btn_send_file"))

    def on_send_clicked(self) -> None:
        """전송 버튼 클릭 시 호출됩니다."""
        text = self.input_field.text()
        if text:
            # 접두사/접미사 처리 (설정값 사용)
            # 주의: 실제 값은 컨트롤러나 메인 윈도우에서 처리하는 것이 좋지만,
            # 여기서는 시그널에 포함시켜 보냄.
            # 다만, 현재 구조상 설정값을 직접 가져오기 어려우므로,
            # 상위에서 처리하도록 원본 텍스트와 플래그만 보낼 수도 있고,
            # SettingsManager를 통해 가져올 수도 있음.
            # 일단 여기서는 텍스트 자체를 변경하지 않고 플래그만 전달하거나,
            # (기존 로직 유지) 입력 필드가 사라졌으므로 빈 문자열 처리.

            # 리팩토링: prefix/suffix 내용은 이제 위젯이 직접 알지 못함 (설정에 있음).
            # 따라서, send_command_requested 시그널을 받는 쪽(Controller)에서
            # 설정을 조회하여 붙여야 함.
            # 하지만 기존 시그널은 (text, hex_mode, with_enter) 였음.
            # with_enter는 이제 사용 안함 (False 고정).

            # 변경: prefix_check, suffix_check 상태를 별도로 알릴 방법이 필요하거나,
            # 시그널을 수정해야 함.
            # 여기서는 임시로 text에 태그를 붙이거나,
            # Controller가 위젯의 check 상태를 읽도록 해야 함.
            # 가장 깔끔한 건 시그널에 prefix_enabled, suffix_enabled를 추가하는 것임.
            # 하지만 기존 인터페이스 유지를 위해,
            # 여기서는 text만 보내고 Controller가 알아서 하도록 하거나...
            #
            # 사용자 요구사항: "prefix, suffix가 되는 문자/문자열은 preference로 별도 관리"
            # -> 즉, 전송 시점에 Preference를 읽어서 붙여야 함.
            # View에서 Preference를 읽는 것은 의존성 측면에서 좋지 않으나,
            # SettingsManager가 싱글톤이라면 가능.

            from core.settings_manager import SettingsManager
            settings = SettingsManager()

            final_text = text
            if self.prefix_check.isChecked():
                prefix = settings.get("global.command_prefix", "")
                # 이스케이프 문자 처리
                prefix = prefix.replace("\\r", "\r").replace("\\n", "\n")
                final_text = prefix + final_text

            if self.suffix_check.isChecked():
                suffix = settings.get("global.command_suffix", "\\r\\n")
                suffix = suffix.replace("\\r", "\r").replace("\\n", "\n")
                final_text = final_text + suffix

            self.send_command_requested.emit(
                final_text,
                self.hex_mode_check.isChecked(),
                False # with_enter는 이제 사용 안함 (Suffix로 대체)
            )
            # 입력 후 지우지 않음 (히스토리 기능이 없으므로 유지하는 편이 나음)
            # self.input_field.clear()

    def on_select_file_clicked(self) -> None:
        """파일 선택 버튼 클릭 시 호출됩니다."""
        path, _ = QFileDialog.getOpenFileName(self, language_manager.get_text("manual_ctrl_dialog_select_file"))
        if path:
            self.file_path_label.setText(path)
            self.file_selected.emit(path)

    def on_send_file_clicked(self) -> None:
        """파일 전송 버튼 클릭 시 호출됩니다."""
        path = self.file_path_label.text()
        if path and path != language_manager.get_text("manual_ctrl_lbl_no_file"):
            self.send_file_requested.emit(path)

    def on_save_log_clicked(self) -> None:
        """로그 저장 버튼 클릭 시 호출됩니다."""
        filter_str = f"{language_manager.get_text('manual_ctrl_dialog_file_filter_txt')} (*.txt);;{language_manager.get_text('manual_ctrl_dialog_file_filter_all')} (*)"
        path, _ = QFileDialog.getSaveFileName(self, language_manager.get_text("manual_ctrl_dialog_save_log_title"), "", filter_str)
        if path:
            self.save_log_requested.emit(path)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        포트 연결 상태에 따라 제어 버튼을 활성화/비활성화합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.send_btn.setEnabled(enabled)
        self.send_file_btn.setEnabled(enabled)
        self.rts_check.setEnabled(enabled)
        self.dtr_check.setEnabled(enabled)

        self.clear_btn.setEnabled(True)
        self.save_log_btn.setEnabled(True)
        self.select_file_btn.setEnabled(True)

    def save_state(self) -> dict:
        """
        현재 위젯 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태.
        """
        state = {
            "hex_mode": self.hex_mode_check.isChecked(),
            # "add_enter": self.enter_check.isChecked(), # 제거됨
            "rts": self.rts_check.isChecked(),
            "dtr": self.dtr_check.isChecked(),
            "input_text": self.input_field.text(),
            "use_prefix": self.prefix_check.isChecked(),
            # "prefix": self.prefix_input.text(), # 제거됨
            "use_suffix": self.suffix_check.isChecked(),
            # "suffix": self.suffix_input.text() # 제거됨
        }
        return state

    def load_state(self, state: dict) -> None:
        """
        저장된 상태를 위젯에 적용합니다.

        Args:
            state (dict): 위젯 상태.
        """
        if not state:
            return

        self.hex_mode_check.setChecked(state.get("hex_mode", False))
        # self.enter_check.setChecked(state.get("add_enter", True))
        self.rts_check.setChecked(state.get("rts", False))
        self.dtr_check.setChecked(state.get("dtr", False))
        self.input_field.setText(state.get("input_text", ""))
        self.prefix_check.setChecked(state.get("use_prefix", False))
        # self.prefix_input.setText(state.get("prefix", ""))
        self.suffix_check.setChecked(state.get("use_suffix", False))
        # self.suffix_input.setText(state.get("suffix", ""))
