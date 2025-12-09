from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QLineEdit, QSpinBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.tools.lang_manager import lang_manager

class MacroCtrlWidget(QWidget):
    """
    Command List 실행을 제어하는 위젯 클래스입니다.
    Repeat, 스크립트 저장/로드 기능을 제공합니다.
    """

    # 시그널 정의
    cmd_repeat_start_requested = pyqtSignal(int, int) # delay_ms, max_runs
    cmd_repeat_stop_requested = pyqtSignal()
    cmd_repeat_pause_requested = pyqtSignal()

    script_save_requested = pyqtSignal()
    script_load_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroCtrlWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.cmd_repeat_count_lbl = None
        self.cmd_repeat_stop_btn = None
        self.cmd_repeat_start_btn = None
        self.repeat_count_spin = None
        self.repeat_max_lbl = None
        self.repeat_delay_line_edit = None
        self.interval_lbl = None
        self.execution_settings_grp = None
        self.script_load_btn = None
        self.script_save_btn = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. 상단 행: 스크립트 제어 및 접두사/접미사 (Top Row)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.script_save_btn = QPushButton(lang_manager.get_text("macro_ctrl_btn_save_script"))
        self.script_save_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_save_script_tooltip"))
        self.script_save_btn.clicked.connect(self.on_script_save_requested)

        self.script_load_btn = QPushButton(lang_manager.get_text("macro_ctrl_btn_load_script"))
        self.script_load_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_load_script_tooltip"))
        self.script_load_btn.clicked.connect(self.on_script_load_requested)

        top_layout.addStretch()
        top_layout.addWidget(self.script_save_btn)
        top_layout.addWidget(self.script_load_btn)

        # 2. 자동 실행 설정 그룹 (Repeat Settings Group)
        self.execution_settings_grp = QGroupBox(lang_manager.get_text("macro_ctrl_grp_execution"))
        execution_layout = QGridLayout()
        execution_layout.setContentsMargins(2, 2, 2, 2)
        execution_layout.setSpacing(5)

        # Row 0: 자동 실행 설정
        self.interval_lbl = QLabel(lang_manager.get_text("macro_ctrl_lbl_interval"))
        execution_layout.addWidget(self.interval_lbl, 0, 0)

        self.repeat_delay_line_edit = QLineEdit("1000")
        self.repeat_delay_line_edit.setFixedWidth(50)
        self.repeat_delay_line_edit.setAlignment(Qt.AlignRight)
        execution_layout.addWidget(self.repeat_delay_line_edit, 1, 1)

        self.repeat_max_lbl = QLabel(lang_manager.get_text("macro_ctrl_lbl_repeat_max"))
        execution_layout.addWidget(self.repeat_max_lbl, 0, 2)

        self.repeat_count_spin = QSpinBox()
        self.repeat_count_spin.setRange(0, 9999)
        self.repeat_count_spin.setValue(0)
        self.repeat_count_spin.setToolTip(lang_manager.get_text("macro_ctrl_spin_repeat_tooltip"))
        execution_layout.addWidget(self.repeat_count_spin, 0, 3)

        # Row 1: 자동 실행 제어
        self.cmd_repeat_start_btn = QPushButton(lang_manager.get_text("macro_ctrl_btn_repeat_start"))
        self.cmd_repeat_start_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_repeat_start_tooltip"))
        self.cmd_repeat_start_btn.setProperty("class", "accent") # 초록색 스타일
        self.cmd_repeat_start_btn.clicked.connect(self.on_cmd_repeat_start_clicked)

        self.cmd_repeat_stop_btn = QPushButton(lang_manager.get_text("macro_ctrl_btn_repeat_stop"))
        self.cmd_repeat_stop_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_repeat_stop_tooltip"))
        self.cmd_repeat_stop_btn.setEnabled(False)
        self.cmd_repeat_stop_btn.setProperty("class", "danger") # 빨간색 스타일
        self.cmd_repeat_stop_btn.clicked.connect(self.on_cmd_repeat_stop_clicked)

        self.cmd_repeat_pause_btn = QPushButton(lang_manager.get_text("macro_ctrl_btn_repeat_pause"))
        self.cmd_repeat_pause_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_repeat_pause_tooltip"))
        self.cmd_repeat_pause_btn.setEnabled(False)
        self.cmd_repeat_pause_btn.setProperty("class", "warning") # 노란색 스타일
        self.cmd_repeat_pause_btn.clicked.connect(self.on_cmd_repeat_pause_clicked)

        self.cmd_repeat_count_lbl = QLabel("0 / ∞")
        self.cmd_repeat_count_lbl.setAlignment(Qt.AlignCenter)

        execution_layout.addWidget(self.cmd_repeat_start_btn, 1, 0, 1, 2)
        execution_layout.addWidget(self.cmd_repeat_stop_btn, 1, 2)
        execution_layout.addWidget(self.cmd_repeat_count_lbl, 1, 3)

        self.execution_settings_grp.setLayout(execution_layout)

        layout.addLayout(top_layout)
        layout.addWidget(self.execution_settings_grp)

        self.setLayout(layout)

        # 초기 상태: 연결 전까지 비활성화
        self.set_controls_enabled(False)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.script_save_btn.setText(lang_manager.get_text("macro_ctrl_btn_save_script"))
        self.script_save_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_save_script_tooltip"))

        self.script_load_btn.setText(lang_manager.get_text("macro_ctrl_btn_load_script"))
        self.script_load_btn.setToolTip(lang_manager.get_text("macro_ctrl_btn_load_script_tooltip"))

        self.execution_settings_grp.setTitle(lang_manager.get_text("macro_ctrl_grp_execution"))

        self.interval_lbl.setText(lang_manager.get_text("macro_ctrl_lbl_interval"))
        self.repeat_max_lbl.setText(lang_manager.get_text("macro_ctrl_lbl_repeat_max"))
        self.repeat_count_spin.setToolTip(lang_manager.get_text("macro_ctrl_spin_repeat_tooltip"))

        self.cmd_repeat_start_btn.setText(lang_manager.get_text("macro_ctrl_btn_repeat_start"))
        self.cmd_repeat_stop_btn.setText(lang_manager.get_text("macro_ctrl_btn_repeat_stop"))

    def on_cmd_repeat_start_clicked(self) -> None:
        """자동 실행 시작 버튼 핸들러"""
        try:
            delay = int(self.repeat_delay_line_edit.text())
        except ValueError:
            delay = 1000
        max_runs = self.repeat_count_spin.value()
        self.cmd_repeat_start_requested.emit(delay, max_runs)

    def on_cmd_repeat_stop_clicked(self) -> None:
        """자동 실행 정지 버튼 핸들러"""
        self.cmd_repeat_stop_requested.emit()

    def on_cmd_repeat_pause_clicked(self) -> None:
        """자동 실행 정지 버튼 핸들러"""
        self.cmd_repeat_pause_requested.emit()

    def on_script_save_requested(self) -> None:
        """스크립트 저장 버튼 핸들러"""
        self.script_save_requested.emit()

    def on_script_load_requested(self) -> None:
        """스크립트 로드 버튼 핸들러"""
        self.script_load_requested.emit()

    def set_running_state(self, running: bool, is_repeat: bool = False) -> None:
        """
        실행 상태에 따라 버튼 활성화/비활성화를 설정합니다.

        Args:
            running (bool): 실행 중 여부.
            is_repeat (bool): 자동 실행 모드 여부.
        """
        if running:
            self.cmd_repeat_start_btn.setEnabled(False)
            if is_repeat:
                self.cmd_repeat_stop_btn.setEnabled(True)
        else:
            self.cmd_repeat_start_btn.setEnabled(True)
            self.cmd_repeat_stop_btn.setEnabled(False)

    def update_auto_count(self, current: int, total: int) -> None:
        """
        자동 실행 카운트를 업데이트합니다.

        Args:
            current (int): 현재 실행 횟수.
            total (int): 전체 실행 횟수 (0이면 무한).
        """
        total_str = "∞" if total == 0 else str(total)
        self.cmd_repeat_count_lbl.setText(f"{current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯들의 활성화 상태를 설정합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.cmd_repeat_start_btn.setEnabled(enabled)
        # Stop 버튼은 실행 상태에 따라 별도 관리되므로 여기서는 건드리지 않음

    def save_state(self) -> dict:
        """
        현재 위젯의 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태 데이터.
        """
        state = {
            "delay": self.repeat_delay_line_edit.text(),
            "max_runs": self.repeat_count_spin.value()
        }
        return state

    def load_state(self, state: dict) -> None:
        """
        저장된 상태를 위젯에 적용합니다.

        Args:
            state (dict): 위젯 상태 데이터.
        """
        if not state:
            return

        self.repeat_delay_line_edit.setText(state.get("delay", "1000"))
        self.repeat_count_spin.setValue(state.get("max_runs", 0))

