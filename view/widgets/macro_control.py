"""
매크로 제어 위젯 모듈

매크로 실행(반복 횟수, 지연 시간) 설정 및 스크립트 파일 관리를 담당합니다.
사용자가 입력한 설정을 바탕으로 자동 반복 실행을 제어합니다.

## WHY
* 매크로의 실행 조건(반복 횟수, 간격)을 정밀하게 제어할 인터페이스 필요
* 스크립트 파일의 저장/로드 기능을 통해 설정 공유 및 백업 지원
* 브로드캐스트 상태 변경을 실시간으로 상위 모듈에 알리기 위함

## WHAT
* 반복 횟수(SpinBox), 지연 시간(LineEdit) 설정 UI
* 시작/정지/일시정지 제어 버튼 및 상태 표시 라벨
* 스크립트 저장/로드 및 Broadcast 옵션 체크박스
* 상태 변경 시그널 발신 (Start, Stop, Pause, Broadcast, Script I/O)

## HOW
* QGridLayout을 사용하여 설정 및 제어 버튼 배치
* 사용자 입력을 `MacroRepeatOption` DTO로 변환하여 시그널 발생
* set_running_state 메서드를 통해 실행 상태에 따른 버튼 활성화 제어
"""
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QLabel, QLineEdit, QSpinBox, QGroupBox, QGridLayout, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, Qt

from view.managers.language_manager import language_manager
from common.dtos import MacroRepeatOption
from common.constants import DEFAULT_MACRO_INTERVAL_MS


class MacroControlWidget(QWidget):
    """
    Command List 실행을 제어하는 위젯 클래스입니다.
    반복 실행 옵션 설정, 실행 제어, 스크립트 파일 관리를 제공합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 매크로 실행 제어 시그널
    macro_repeat_start_requested = pyqtSignal(object)  # MacroRepeatOption DTO 전달
    macro_repeat_stop_requested = pyqtSignal()
    macro_repeat_pause_requested = pyqtSignal()

    # 스크립트 파일 관리 시그널
    script_save_requested = pyqtSignal()
    script_load_requested = pyqtSignal()

    # 브로드캐스트 상태 변경 알림 (전송 버튼 활성화 로직용)
    broadcast_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroControlWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)

        # UI 컴포넌트 선언
        self.execution_settings_grp: Optional[QGroupBox] = None
        self.interval_lbl: Optional[QLabel] = None
        self.repeat_max_lbl: Optional[QLabel] = None
        self.macro_repeat_count_lbl: Optional[QLabel] = None

        self.repeat_interval_ms_edit: Optional[QLineEdit] = None
        self.repeat_max_spin: Optional[QSpinBox] = None
        self.broadcast_chk: Optional[QCheckBox] = None

        self.macro_repeat_start_btn: Optional[QPushButton] = None
        self.macro_repeat_stop_btn: Optional[QPushButton] = None
        self.macro_repeat_pause_btn: Optional[QPushButton] = None
        self.script_save_btn: Optional[QPushButton] = None
        self.script_load_btn: Optional[QPushButton] = None

        self.init_ui()

        # 언어 변경 시그널 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.
        """

        # -----------------------------------------------------
        # Row 0: 설정값 입력 (Interval, Max Count, Broadcast)
        # -----------------------------------------------------
        # Interval
        self.interval_lbl = QLabel(language_manager.get_text("macro_control_lbl_repeat_interval"))
        self.repeat_interval_ms_edit = QLineEdit(str(DEFAULT_MACRO_INTERVAL_MS))
        self.repeat_interval_ms_edit.setFixedWidth(50)
        self.repeat_interval_ms_edit.setAlignment(Qt.AlignRight)
        self.repeat_interval_ms_edit.setToolTip(language_manager.get_text("macro_control_edit_repeat_interval_tooltip"))

        # Repeat Count
        self.repeat_max_lbl = QLabel(language_manager.get_text("macro_control_lbl_repeat_max"))
        self.repeat_max_spin = QSpinBox()
        self.repeat_max_spin.setRange(0, 9999) # 0 = Infinite
        self.repeat_max_spin.setValue(0)
        self.repeat_max_spin.setToolTip(language_manager.get_text("macro_control_spin_repeat_max_tooltip"))

        # Broadcast Checkbox
        self.broadcast_chk = QCheckBox(language_manager.get_text("macro_control_chk_broadcast"))
        self.broadcast_chk.setToolTip(language_manager.get_text("macro_control_chk_broadcast_tooltip"))
        self.broadcast_chk.stateChanged.connect(
            lambda state: self.broadcast_changed.emit(state == Qt.Checked)
        )

        # Script Buttons
        self.script_save_btn = QPushButton(language_manager.get_text("macro_control_btn_save_script"))
        self.script_save_btn.setToolTip(language_manager.get_text("macro_control_btn_save_script_tooltip"))
        self.script_save_btn.clicked.connect(self.on_script_save_requested)

        self.script_load_btn = QPushButton(language_manager.get_text("macro_control_btn_load_script"))
        self.script_load_btn.setToolTip(language_manager.get_text("macro_control_btn_load_script_tooltip"))
        self.script_load_btn.clicked.connect(self.on_script_load_requested)

        # -----------------------------------------------------
        # Row 1: 제어 버튼 (Start, Stop, Pause, Status Label)
        # -----------------------------------------------------
        self.macro_repeat_start_btn = QPushButton(language_manager.get_text("macro_control_btn_repeat_start"))
        self.macro_repeat_start_btn.setToolTip(language_manager.get_text("macro_control_btn_repeat_start_tooltip"))
        self.macro_repeat_start_btn.setProperty("class", "accent") # 테마 스타일 적용
        self.macro_repeat_start_btn.clicked.connect(self.on_macro_repeat_start_clicked)

        self.macro_repeat_stop_btn = QPushButton(language_manager.get_text("macro_control_btn_repeat_stop"))
        self.macro_repeat_stop_btn.setToolTip(language_manager.get_text("macro_control_btn_repeat_stop_tooltip"))
        self.macro_repeat_stop_btn.setEnabled(False)
        self.macro_repeat_stop_btn.setProperty("class", "danger") # 테마 스타일 적용
        self.macro_repeat_stop_btn.clicked.connect(self.on_macro_repeat_stop_clicked)

        self.macro_repeat_pause_btn = QPushButton(language_manager.get_text("macro_control_btn_repeat_pause"))
        self.macro_repeat_pause_btn.setToolTip(language_manager.get_text("macro_control_btn_repeat_pause_tooltip"))
        self.macro_repeat_pause_btn.setEnabled(False)
        self.macro_repeat_pause_btn.setProperty("class", "warning") # 테마 스타일 적용
        self.macro_repeat_pause_btn.clicked.connect(self.on_macro_repeat_pause_clicked)

        self.macro_repeat_count_lbl = QLabel("0 / ∞")
        self.macro_repeat_count_lbl.setAlignment(Qt.AlignCenter)


        execution_layout = QGridLayout()
        execution_layout.setContentsMargins(2, 2, 2, 2)
        execution_layout.setSpacing(5)

        # Row 0 배치
        execution_layout.addWidget(self.interval_lbl, 0, 0)
        execution_layout.addWidget(self.repeat_interval_ms_edit, 0, 1)
        execution_layout.addWidget(self.repeat_max_lbl, 0, 2)
        execution_layout.addWidget(self.repeat_max_spin, 0, 3)
        execution_layout.addWidget(self.broadcast_chk, 0, 4)
        execution_layout.addWidget(self.script_save_btn, 0, 5)
        execution_layout.addWidget(self.script_load_btn, 0, 6)

        # Row 1 배치
        # Span을 사용하여 버튼 크기 조절
        execution_layout.addWidget(self.macro_repeat_start_btn, 1, 0, 1, 3) # Span 3
        execution_layout.addWidget(self.macro_repeat_stop_btn, 1, 3, 1, 2)  # Span 2
        execution_layout.addWidget(self.macro_repeat_pause_btn, 1, 5)
        execution_layout.addWidget(self.macro_repeat_count_lbl, 1, 6)

        # 자동 실행 설정 그룹 (Execution Group)
        self.execution_settings_grp = QGroupBox(language_manager.get_text("macro_control_grp_execution"))
        self.execution_settings_grp.setFixedHeight(100)
        self.execution_settings_grp.setLayout(execution_layout)

        # 메인 레이아웃 적용
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.execution_settings_grp)
        self.setLayout(layout)

        # 초기 상태 설정 (연결 전 비활성화)
        self.set_controls_enabled(False)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.script_save_btn.setText(language_manager.get_text("macro_control_btn_save_script"))
        self.script_save_btn.setToolTip(language_manager.get_text("macro_control_btn_save_script_tooltip"))

        self.script_load_btn.setText(language_manager.get_text("macro_control_btn_load_script"))
        self.script_load_btn.setToolTip(language_manager.get_text("macro_control_btn_load_script_tooltip"))

        self.execution_settings_grp.setTitle(language_manager.get_text("macro_control_grp_execution"))

        self.interval_lbl.setText(language_manager.get_text("macro_control_lbl_repeat_interval"))
        self.repeat_max_lbl.setText(language_manager.get_text("macro_control_lbl_repeat_max"))
        self.repeat_max_spin.setToolTip(language_manager.get_text("macro_control_spin_repeat_max_tooltip"))

        self.broadcast_chk.setText(language_manager.get_text("macro_control_chk_broadcast"))
        self.broadcast_chk.setToolTip(language_manager.get_text("macro_control_chk_broadcast_tooltip"))

        self.macro_repeat_start_btn.setText(language_manager.get_text("macro_control_btn_repeat_start"))
        self.macro_repeat_stop_btn.setText(language_manager.get_text("macro_control_btn_repeat_stop"))
        self.macro_repeat_pause_btn.setText(language_manager.get_text("macro_control_btn_repeat_pause"))

    # -------------------------------------------------------------------------
    # Getters for Encapsulation (캡슐화를 위한 상태 조회 메서드)
    # -------------------------------------------------------------------------
    def is_broadcast_enabled(self) -> bool:
        """
        브로드캐스트 체크박스 상태를 반환합니다.

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        return self.broadcast_chk.isChecked()

    def get_repeat_option(self) -> MacroRepeatOption:
        """
        현재 UI 설정값을 바탕으로 MacroRepeatOption DTO를 생성하여 반환합니다.

        Returns:
            MacroRepeatOption: 실행 옵션 데이터 객체.
        """
        try:
            interval_ms = int(self.repeat_interval_ms_edit.text())
        except ValueError:
            interval_ms = DEFAULT_MACRO_INTERVAL_MS

        max_runs = self.repeat_max_spin.value()
        broadcast_enabled = self.is_broadcast_enabled()

        # stop_on_error는 현재 UI에 없으므로 기본값(True) 사용
        # 필요 시 UI에 체크박스 추가 가능
        return MacroRepeatOption(
            interval_ms=interval_ms,
            max_runs=max_runs,
            broadcast_enabled=broadcast_enabled,
            stop_on_error=True
        )

    # -------------------------------------------------------------------------
    # Handlers & Control Logic
    # -------------------------------------------------------------------------
    def on_macro_repeat_start_clicked(self) -> None:
        """자동 실행 시작 버튼 핸들러"""
        option = self.get_repeat_option()
        self.macro_repeat_start_requested.emit(option)

    def on_macro_repeat_stop_clicked(self) -> None:
        """자동 실행 정지 버튼 핸들러"""
        self.macro_repeat_stop_requested.emit()

    def on_macro_repeat_pause_clicked(self) -> None:
        """자동 실행 일시정지 버튼 핸들러"""
        self.macro_repeat_pause_requested.emit()

    def on_script_save_requested(self) -> None:
        """스크립트 저장 버튼 핸들러"""
        self.script_save_requested.emit()

    def on_script_load_requested(self) -> None:
        """스크립트 로드 버튼 핸들러"""
        self.script_load_requested.emit()

    def set_running_state(self, running: bool, is_repeat: bool = False) -> None:
        """
        매크로 실행 상태에 따라 버튼 활성화/비활성화를 제어합니다.

        Logic:
            - 실행 중(running=True): 시작 버튼 비활성화.
            - 반복 모드(is_repeat=True): 정지/일시정지 버튼 활성화.
            - 정지 상태(running=False): 시작 버튼 활성화, 정지/일시정지 비활성화.

        Args:
            running (bool): 현재 실행 중인지 여부.
            is_repeat (bool): 반복 실행 모드인지 여부.
        """
        if running:
            # 실행 중: 시작 버튼 비활성화
            self.macro_repeat_start_btn.setEnabled(False)

            # 반복 모드일 때만 정지/일시정지 활성화
            if is_repeat:
                self.macro_repeat_stop_btn.setEnabled(True)
                self.macro_repeat_pause_btn.setEnabled(True)
            else:
                # 단일 실행 중일 때는 정지/일시정지 불필요 (금방 끝남)
                self.macro_repeat_stop_btn.setEnabled(False)
                self.macro_repeat_pause_btn.setEnabled(False)
        else:
            # 정지 상태: 시작 버튼 활성화 (단, 연결 상태여야 함)
            # 연결 상태는 set_controls_enabled에서 관리되므로 여기서는 버튼 자체의 활성화만 복구
            self.macro_repeat_start_btn.setEnabled(True)
            self.macro_repeat_stop_btn.setEnabled(False)
            self.macro_repeat_pause_btn.setEnabled(False)

    def update_auto_count(self, current: int, total: int) -> None:
        """
        자동 실행 카운트 라벨을 업데이트합니다.

        Args:
            current (int): 현재 실행 횟수.
            total (int): 전체 설정 횟수 (0이면 무한).
        """
        total_str = "∞" if total == 0 else str(total)
        self.macro_repeat_count_lbl.setText(f"{current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯들의 활성화 상태를 설정합니다. (포트 연결 상태에 연동)

        Logic:
            - 시작 버튼 활성화/비활성화
            - 연결이 끊기면 정지/일시정지도 강제 비활성화
            - 설정값(Broadcast 등)은 변경 가능하도록 유지 (일반적인 UX)

        Args:
            enabled (bool): 활성화 여부.
        """
        # 시작 버튼 활성화 제어
        self.macro_repeat_start_btn.setEnabled(enabled)

        # 연결 끊기면 정지/일시정지도 강제 비활성화
        if not enabled:
            self.macro_repeat_stop_btn.setEnabled(False)
            self.macro_repeat_pause_btn.setEnabled(False)

    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """
        현재 위젯의 상태를 딕셔너리로 반환합니다 (설정 저장용).

        Returns:
            dict: 위젯 상태 데이터.
        """
        return {
            "delay_ms": self.repeat_interval_ms_edit.text(),
            "max_runs": self.repeat_max_spin.value(),
            "broadcast_enabled": self.broadcast_chk.isChecked()
        }

    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        저장된 상태를 위젯에 적용합니다.

        Args:
            state (dict): 위젯 상태 데이터.
        """
        if not state:
            return

        self.repeat_interval_ms_edit.setText(str(state.get("delay_ms", DEFAULT_MACRO_INTERVAL_MS)))
        self.repeat_max_spin.setValue(state.get("max_runs", 0))
        self.broadcast_chk.setChecked(state.get("broadcast_enabled", False))