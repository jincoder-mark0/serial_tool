from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox,
    QLabel, QLineEdit, QSpinBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.language_manager import language_manager

class CommandControlWidget(QWidget):
    """
    Command List 실행을 제어하는 위젯 클래스입니다.
    실행(Run), 정지(Stop), 자동 실행(Auto Run), 스크립트 저장/로드 기능을 제공합니다.
    """

    # 시그널 정의
    run_single_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    start_auto_requested = pyqtSignal(int, int) # delay_ms, max_runs
    repeat_stop_requested = pyqtSignal()

    save_script_requested = pyqtSignal()
    load_script_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        CommandControlWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.auto_run_count_lbl = None
        self.repeat_stop_btn = None
        self.repeat_start_btn = None
        self.repeat_spin = None
        self.repeat_max_lbl = None
        self.repeat_delay = None
        self.interval_lbl = None
        self.stop_run_btn = None
        self.run_once_btn = None
        self.execution_grp = None
        self.load_script_btn = None
        self.save_script_btn = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. 상단 행: 스크립트 제어 및 접두사/접미사 (Top Row)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.save_script_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_save_script"))
        self.save_script_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_save_script_tooltip"))
        self.save_script_btn.clicked.connect(self.save_script_requested.emit)

        self.load_script_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_load_script"))
        self.load_script_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_load_script_tooltip"))
        self.load_script_btn.clicked.connect(self.load_script_requested.emit)

        top_layout.addStretch()
        top_layout.addWidget(self.save_script_btn)
        top_layout.addWidget(self.load_script_btn)

        # 2. 자동 실행 설정 그룹 (Auto Run Settings Group)
        self.execution_grp = QGroupBox(language_manager.get_text("cmd_ctrl_grp_execution"))
        execution_layout = QGridLayout()
        execution_layout.setContentsMargins(2, 2, 2, 2)
        execution_layout.setSpacing(5)

        # Row 0: 단일 실행 및 정지
        self.run_once_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_run_once"))
        self.run_once_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_run_once_tooltip"))
        self.run_once_btn.clicked.connect(self.run_single_requested.emit)

        self.stop_run_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_stop_run"))
        self.stop_run_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_stop_run_tooltip"))
        self.stop_run_btn.clicked.connect(self.stop_requested.emit)
        self.stop_run_btn.setEnabled(False)
        self.stop_run_btn.setProperty("class", "danger") # 빨간색 스타일

        execution_layout.addWidget(self.run_once_btn, 0, 0, 1, 2)
        execution_layout.addWidget(self.stop_run_btn, 0, 2, 1, 2)

        # Row 1: 자동 실행 설정
        self.interval_lbl = QLabel(language_manager.get_text("cmd_ctrl_lbl_interval"))
        execution_layout.addWidget(self.interval_lbl, 1, 0)

        self.repeat_delay = QLineEdit("1000")
        self.repeat_delay.setFixedWidth(50)
        self.repeat_delay.setAlignment(Qt.AlignRight)
        execution_layout.addWidget(self.repeat_delay, 1, 1)

        self.repeat_max_lbl = QLabel(language_manager.get_text("cmd_ctrl_lbl_repeat_max"))
        execution_layout.addWidget(self.repeat_max_lbl, 1, 2)

        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(0, 9999)
        self.repeat_spin.setValue(0)
        self.repeat_spin.setToolTip(language_manager.get_text("cmd_ctrl_spin_repeat_tooltip"))
        execution_layout.addWidget(self.repeat_spin, 1, 3)

        # Row 2: 자동 실행 제어
        self.repeat_start_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_repeat_start"))
        self.repeat_start_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_repeat_start_tooltip"))
        self.repeat_start_btn.setProperty("class", "accent") # 초록색 스타일
        self.repeat_start_btn.clicked.connect(self.on_repeat_start)

        self.repeat_stop_btn = QPushButton(language_manager.get_text("cmd_ctrl_btn_repeat_stop"))
        self.repeat_stop_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_repeat_stop_tooltip"))
        self.repeat_stop_btn.clicked.connect(self.repeat_stop_requested.emit)
        self.repeat_stop_btn.setEnabled(False)

        self.auto_run_count_lbl = QLabel("0 / ∞")
        self.auto_run_count_lbl.setAlignment(Qt.AlignCenter)

        execution_layout.addWidget(self.repeat_start_btn, 2, 0, 1, 2)
        execution_layout.addWidget(self.repeat_stop_btn, 2, 2)
        execution_layout.addWidget(self.auto_run_count_lbl, 2, 3)

        self.execution_grp.setLayout(execution_layout)

        layout.addLayout(top_layout)
        layout.addWidget(self.execution_grp)

        self.setLayout(layout)

        # 초기 상태: 연결 전까지 비활성화
        self.set_controls_enabled(False)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.save_script_btn.setText(language_manager.get_text("cmd_ctrl_btn_save_script"))
        self.save_script_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_save_script_tooltip"))

        self.load_script_btn.setText(language_manager.get_text("cmd_ctrl_btn_load_script"))
        self.load_script_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_load_script_tooltip"))

        self.execution_grp.setTitle(language_manager.get_text("cmd_ctrl_grp_execution"))

        self.run_once_btn.setText(language_manager.get_text("cmd_ctrl_btn_run_once"))
        self.run_once_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_run_once_tooltip"))

        self.stop_run_btn.setText(language_manager.get_text("cmd_ctrl_btn_stop_run"))
        self.stop_run_btn.setToolTip(language_manager.get_text("cmd_ctrl_btn_stop_run_tooltip"))

        self.interval_lbl.setText(language_manager.get_text("cmd_ctrl_lbl_interval"))
        self.repeat_max_lbl.setText(language_manager.get_text("cmd_ctrl_lbl_repeat_max"))
        self.repeat_spin.setToolTip(language_manager.get_text("cmd_ctrl_spin_repeat_tooltip"))

        self.repeat_start_btn.setText(language_manager.get_text("cmd_ctrl_btn_repeat_start"))
        self.repeat_stop_btn.setText(language_manager.get_text("cmd_ctrl_btn_repeat_stop"))

    def on_repeat_start(self) -> None:
        """자동 실행 시작 버튼 핸들러"""
        try:
            delay = int(self.repeat_delay.text())
        except ValueError:
            delay = 1000
        max_runs = self.repeat_spin.value()
        self.start_auto_requested.emit(delay, max_runs)

    def set_running_state(self, running: bool, is_auto: bool = False) -> None:
        """
        실행 상태에 따라 버튼 활성화/비활성화를 설정합니다.

        Args:
            running (bool): 실행 중 여부.
            is_auto (bool): 자동 실행 모드 여부.
        """
        if running:
            self.run_once_btn.setEnabled(False)
            self.repeat_start_btn.setEnabled(False)
            self.stop_run_btn.setEnabled(True)
            if is_auto:
                self.repeat_stop_btn.setEnabled(True)
        else:
            self.run_once_btn.setEnabled(True)
            self.repeat_start_btn.setEnabled(True)
            self.stop_run_btn.setEnabled(False)
            self.repeat_stop_btn.setEnabled(False)

    def update_auto_count(self, current: int, total: int) -> None:
        """
        자동 실행 카운트를 업데이트합니다.

        Args:
            current (int): 현재 실행 횟수.
            total (int): 전체 실행 횟수 (0이면 무한).
        """
        total_str = "∞" if total == 0 else str(total)
        self.auto_run_count_lbl.setText(f"{current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯들의 활성화 상태를 설정합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.run_once_btn.setEnabled(enabled)
        self.repeat_start_btn.setEnabled(enabled)
        # Stop 버튼들은 실행 상태에 따라 별도 관리되므로 여기서는 건드리지 않음

    def save_state(self) -> dict:
        """
        현재 위젯의 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 위젯 상태 데이터.
        """
        state = {
            "delay": self.repeat_delay.text(),
            "max_runs": self.repeat_spin.value()
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

        self.repeat_delay.setText(state.get("delay", "1000"))
        self.repeat_spin.setValue(state.get("max_runs", 0))

