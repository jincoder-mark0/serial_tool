from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QLabel, QFileDialog, QGroupBox, QGridLayout, QTextEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeyEvent
from typing import Optional
from view.tools.lang_manager import lang_manager

class ManualCtrlWidget(QWidget):
    """
    수동 명령 전송, 파일 전송, 로그 저장 및 각종 제어 옵션을 제공하는 위젯 클래스입니다.
    (구 OperationArea)
    """

    # 시그널 정의
    manual_cmd_send_requested = pyqtSignal(str, bool, bool, bool) # text, hex_mode, cmd_prefix, cmd_suffix
    transfer_file_send_requested = pyqtSignal(str) # filepath
    transfer_file_selected = pyqtSignal(str) # filepath
    manual_log_save_requested = pyqtSignal(str) # filepath
    manual_options_clear_requested = pyqtSignal()

    # 접두사/접미사 상수 (CommandControl과 동일)
    PREFIX_KEY = "prefix"
    SUFFIX_KEY = "suffix"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualCtrlWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.send_transfer_file_btn = None
        self.select_transfer_file_btn = None
        self.transfer_file_path_lbl = None
        self.file_transfer_grp = None
        self.send_manual_cmd_btn = None
        self.manual_cmd_input = None
        self.manual_send_grp = None
        self.save_manual_log_btn = None
        self.clear_manual_options_btn = None
        self.dtr_chk = None
        self.rts_chk = None
        self.suffix_chk = None
        self.prefix_chk = None
        self.hex_chk = None
        self.manual_options_grp = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2) # 간격 최소화

        # 1. 제어 옵션 그룹 (Control Options Group)
        self.manual_options_grp = QGroupBox(lang_manager.get_text("manual_ctrl_grp_control"))
        option_layout = QGridLayout()
        option_layout.setContentsMargins(2, 2, 2, 2) # 내부 여백 최소화
        option_layout.setSpacing(5)

        self.hex_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_hex"))
        self.hex_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_hex_tooltip"))
        self.hex_chk.stateChanged.connect(self.on_hex_mode_changed)

        # 접두사/접미사 체크박스
        self.prefix_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_suffix"))

        # 흐름 제어 (Flow Control - RTS/DTR)
        self.rts_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_rts"))
        self.rts_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_rts_tooltip"))
        self.dtr_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_dtr"))
        self.dtr_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_dtr_tooltip"))

        self.clear_manual_options_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_clear"))
        self.clear_manual_options_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_clear_tooltip"))
        self.clear_manual_options_btn.clicked.connect(self.on_manual_options_clear_clicked)

        self.save_manual_log_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_save_log"))
        self.save_manual_log_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_save_log_tooltip"))
        self.save_manual_log_btn.clicked.connect(self.on_save_manual_log_clicked)

        option_layout.addWidget(self.hex_chk, 0, 0)
        option_layout.addWidget(self.prefix_chk, 0, 1)
        option_layout.addWidget(self.suffix_chk, 0, 2)
        option_layout.addWidget(self.rts_chk, 0, 3)
        option_layout.addWidget(self.dtr_chk, 0, 4)

        option_layout.addWidget(self.clear_manual_options_btn, 2, 0, 1, 2)
        option_layout.addWidget(self.save_manual_log_btn, 2, 2, 1, 2)

        self.manual_options_grp.setLayout(option_layout)

        # 3. 수동 전송 영역 (Manual Send Area)
        self.manual_send_grp = QGroupBox(lang_manager.get_text("manual_ctrl_grp_manual"))
        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(2, 2, 2, 2)
        send_layout.setSpacing(5)

        self.manual_cmd_input = QTextEdit()  # 여러 줄 입력 지원
        self.manual_cmd_input.setPlaceholderText(lang_manager.get_text("manual_ctrl_input_cmd_placeholder"))
        self.manual_cmd_input.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.manual_cmd_input.setMaximumHeight(80)  # 최대 높이 제한
        self.manual_cmd_input.setAcceptRichText(False)  # 일반 텍스트만 허용
        # Ctrl+Enter로 전송하도록 keyPressEvent 오버라이드

        self.send_manual_cmd_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_send"))
        self.send_manual_cmd_btn.setCursor(Qt.PointingHandCursor)
        # 스타일은 QSS에서 처리 권장 (강조색)
        self.send_manual_cmd_btn.setProperty("class", "accent")
        self.send_manual_cmd_btn.clicked.connect(self.on_send_manual_cmd_clicked)

        send_layout.addWidget(self.manual_cmd_input, 1)
        send_layout.addWidget(self.send_manual_cmd_btn)

        self.manual_send_grp.setLayout(send_layout)

        # 3. 파일 전송 영역 (File Transfer Area)
        self.file_transfer_grp = QGroupBox(lang_manager.get_text("manual_ctrl_grp_file"))
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(2, 2, 2, 2)
        file_layout.setSpacing(5)

        self.transfer_file_path_lbl = QLabel(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))
        self.transfer_file_path_lbl.setStyleSheet("color: gray; border: 1px solid #555; padding: 2px; border-radius: 2px;")

        self.select_transfer_file_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.select_transfer_file_btn.clicked.connect(self.on_select_transfer_file_clicked)

        self.send_transfer_file_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_send_file"))
        self.send_transfer_file_btn.clicked.connect(self.on_send_transfer_file_clicked)

        file_layout.addWidget(self.transfer_file_path_lbl, 1)
        file_layout.addWidget(self.select_transfer_file_btn)
        file_layout.addWidget(self.send_transfer_file_btn)

        self.file_transfer_grp.setLayout(file_layout)

        layout.addWidget(self.manual_options_grp)
        layout.addWidget(self.manual_send_grp)
        layout.addWidget(self.file_transfer_grp)
        layout.addStretch() # 하단 여백 추가

        self.setLayout(layout)

        # 초기 상태 설정
        self.set_controls_enabled(False)

        # QTextEdit에 keyPressEvent 연결
        self.manual_cmd_input.keyPressEvent = self._cmd_input_key_press_event

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.manual_options_grp.setTitle(lang_manager.get_text("manual_ctrl_grp_control"))
        self.hex_chk.setText(lang_manager.get_text("manual_ctrl_chk_hex"))
        self.prefix_chk.setText(lang_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_chk.setText(lang_manager.get_text("manual_ctrl_chk_suffix"))
        self.rts_chk.setText(lang_manager.get_text("manual_ctrl_chk_rts"))
        self.dtr_chk.setText(lang_manager.get_text("manual_ctrl_chk_dtr"))
        self.clear_manual_options_btn.setText(lang_manager.get_text("manual_ctrl_btn_clear"))
        self.save_manual_log_btn.setText(lang_manager.get_text("manual_ctrl_btn_save_log"))

        self.manual_send_grp.setTitle(lang_manager.get_text("manual_ctrl_grp_manual"))
        self.send_manual_cmd_btn.setText(lang_manager.get_text("manual_ctrl_btn_send"))
        self.manual_cmd_input.setPlaceholderText(lang_manager.get_text("manual_ctrl_input_cmd_placeholder"))

        self.file_transfer_grp.setTitle(lang_manager.get_text("manual_ctrl_grp_file"))
        # 파일이 선택되지 않은 상태인지 확인
        if lang_manager.text_matches_key(self.transfer_file_path_lbl.text(), "manual_ctrl_lbl_file_path_no_file"):
            self.transfer_file_path_lbl.setText(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))

        self.select_transfer_file_btn.setText(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.send_transfer_file_btn.setText(lang_manager.get_text("manual_ctrl_btn_send_file"))

    def _cmd_input_key_press_event(self, event: QKeyEvent) -> None:
        """
        QTextEdit의 키 입력 이벤트를 처리합니다.
        Ctrl+Enter: 전송
        Enter: 새 줄 추가
        """
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() == Qt.ControlModifier:
                # Ctrl+Enter: 전송
                self.on_send_manual_cmd_clicked()
            else:
                # Enter: 새 줄 추가
                QTextEdit.keyPressEvent(self.manual_cmd_input, event)
        else:
            # 다른 키는 기본 동작
            QTextEdit.keyPressEvent(self.manual_cmd_input, event)

    def on_hex_mode_changed(self, state: int) -> None:
        """HEX 모드 변경 시 처리 (QTextEdit는 hex 모드 미지원)"""
        # QTextEdit는 QSmartLineEdit와 달리 hex 모드를 지원하지 않음
        # 필요시 입력 검증 로직 추가 가능
        pass

    def on_send_manual_cmd_clicked(self) -> None:
        """전송 버튼 클릭 시 호출됩니다."""
        text = self.manual_cmd_input.toPlainText()  # QTextEdit는 toPlainText() 사용
        if text:
            # View는 원본 입력과 체크박스 상태만 전달
            # prefix/suffix 처리는 Presenter에서 수행
            self.manual_cmd_send_requested.emit(
                text,
                self.hex_chk.isChecked(),
                self.prefix_chk.isChecked(),
                self.suffix_chk.isChecked()
            )
            # 입력 후 지우지 않음 (히스토리 기능이 없으므로 유지하는 편이 나음)
            # self.manual_cmd_input.clear()

    def on_select_transfer_file_clicked(self) -> None:
        """파일 선택 버튼 클릭 시 호출됩니다."""
        path, _ = QFileDialog.getOpenFileName(self, lang_manager.get_text("manual_ctrl_dialog_select_file"))
        if path:
            self.transfer_file_path_lbl.setText(path)
            self.transfer_file_selected.emit(path)

    def on_send_transfer_file_clicked(self) -> None:
        """파일 전송 버튼 클릭 시 호출됩니다."""
        path = self.transfer_file_path_lbl.text()
        if path and path != lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"):
            self.transfer_file_send_requested.emit(path)

    def on_manual_options_clear_clicked(self) -> None:
        """제어 옵션 초기화 버튼 클릭 시 호출됩니다."""
        self.manual_options_clear_requested.emit()

    def on_save_manual_log_clicked(self) -> None:
        """로그 저장 버튼 클릭 시 호출됩니다."""
        filter_str = f"{lang_manager.get_text('manual_ctrl_dialog_file_filter_txt')} (*.txt);;{lang_manager.get_text('manual_ctrl_dialog_file_filter_all')} (*)"
        path, _ = QFileDialog.getSaveFileName(self, lang_manager.get_text("manual_ctrl_dialog_save_log_title"), "", filter_str)
        if path:
            self.manual_log_save_requested.emit(path)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        포트 연결 상태에 따라 제어 버튼을 활성화/비활성화합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.send_manual_cmd_btn.setEnabled(enabled)
        self.send_transfer_file_btn.setEnabled(enabled)
        self.rts_chk.setEnabled(enabled)
        self.dtr_chk.setEnabled(enabled)

        self.clear_manual_options_btn.setEnabled(True)
        self.save_manual_log_btn.setEnabled(True)
        self.select_transfer_file_btn.setEnabled(True)

    def save_state(self) -> dict:
        """
        현재 위젯 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태.
        """
        state = {
            "input_text": self.manual_cmd_input.toPlainText(),  # QTextEdit는 toPlainText() 사용
            "hex_mode": self.hex_chk.isChecked(),
            "prefix_chk": self.prefix_chk.isChecked(),
            "suffix_chk": self.suffix_chk.isChecked(),
            "rts_chk": self.rts_chk.isChecked(),
            "dtr_chk": self.dtr_chk.isChecked(),
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

        self.hex_chk.setChecked(state.get("hex_mode", False))
        self.prefix_chk.setChecked(state.get("prefix_chk", False))
        self.suffix_chk.setChecked(state.get("suffix_chk", False))
        self.rts_chk.setChecked(state.get("rts_chk", False))
        self.dtr_chk.setChecked(state.get("dtr_chk", False))
        self.manual_cmd_input.setPlainText(state.get("input_text", ""))  # QTextEdit는 setPlainText() 사용
