"""
수동 제어 위젯 모듈

사용자로부터 명령어 입력을 받고 전송을 요청하는 위젯입니다.
HEX 입력 모드, 체크박스 옵션(RTS/DTR 등)을 제공합니다.

## WHY
* 직관적인 명령어 입력 인터페이스 제공
* 다양한 전송 옵션(Hex, Local Echo, Broadcast)의 통합 제어
* 하드웨어 제어 신호(RTS, DTR)의 실시간 토글 필요

## WHAT
* 명령어 입력창 (QSmartLineEdit)
* 전송 버튼 및 옵션 체크박스 그룹
* 상태 저장 및 복원 기능 (DTO 기반)

## HOW
* DTO(ManualCommand)를 생성하여 상위로 전달
* 입력 검증 및 UI 상태 관리
* QSmartLineEdit를 활용한 입력 필터링
"""
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QGridLayout, QGroupBox
)
from PyQt5.QtCore import pyqtSignal

from view.managers.language_manager import language_manager
from view.custom_qt.smart_line_edit import QSmartLineEdit
from common.dtos import ManualCommand, ManualControlState


class ManualControlWidget(QWidget):
    """
    수동 제어 위젯 클래스

    사용자 입력을 받아 ManualCommand DTO로 변환하여 전송을 요청합니다.
    """

    # 시그널 정의
    send_requested = pyqtSignal(object)  # ManualCommand DTO 전달
    dtr_changed = pyqtSignal(bool)
    rts_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)

        # UI 컴포넌트 변수 초기화
        self.input_edit: Optional[QSmartLineEdit] = None
        self.btn_send: Optional[QPushButton] = None

        # Checkboxes
        self.chk_hex: Optional[QCheckBox] = None
        self.chk_prefix: Optional[QCheckBox] = None
        self.chk_suffix: Optional[QCheckBox] = None
        self.chk_local_echo: Optional[QCheckBox] = None
        self.chk_broadcast: Optional[QCheckBox] = None
        self.chk_rts: Optional[QCheckBox] = None
        self.chk_dtr: Optional[QCheckBox] = None

        self.init_ui()

        # 언어 변경 시그널 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 구성 및 레이아웃 설정

        Logic:
            1. 입력 영역 (LineEdit + Send Button)
            2. 옵션 영역 (GroupBox + Grid Layout)
            3. 각 컴포넌트 시그널 연결
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # ---------------------------------------------------------
        # 1. 입력 영역 (Input Area)
        # ---------------------------------------------------------
        input_layout = QHBoxLayout()

        self.input_edit = QSmartLineEdit()
        self.input_edit.setPlaceholderText(language_manager.get_text("manual_input_placeholder"))
        self.input_edit.returnPressed.connect(self.on_send_clicked)

        self.btn_send = QPushButton(language_manager.get_text("manual_btn_send"))
        self.btn_send.clicked.connect(self.on_send_clicked)

        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.btn_send)

        # ---------------------------------------------------------
        # 2. 옵션 영역 (Options GroupBox)
        # ---------------------------------------------------------
        option_group = QGroupBox(language_manager.get_text("manual_group_options"))
        grid = QGridLayout()
        grid.setContentsMargins(5, 5, 5, 5)

        # 체크박스 생성
        self.chk_hex = QCheckBox("HEX")
        self.chk_hex.setToolTip(language_manager.get_text("manual_chk_hex_tooltip"))
        self.chk_hex.toggled.connect(self.on_hex_toggled)

        self.chk_prefix = QCheckBox(language_manager.get_text("manual_chk_prefix"))
        self.chk_prefix.setToolTip(language_manager.get_text("manual_chk_prefix_tooltip"))

        self.chk_suffix = QCheckBox(language_manager.get_text("manual_chk_suffix"))
        self.chk_suffix.setToolTip(language_manager.get_text("manual_chk_suffix_tooltip"))

        self.chk_local_echo = QCheckBox(language_manager.get_text("manual_chk_local_echo"))
        self.chk_local_echo.setToolTip(language_manager.get_text("manual_chk_local_echo_tooltip"))

        self.chk_broadcast = QCheckBox(language_manager.get_text("manual_chk_broadcast"))
        self.chk_broadcast.setToolTip(language_manager.get_text("manual_chk_broadcast_tooltip"))

        self.chk_rts = QCheckBox("RTS")
        self.chk_rts.setToolTip(language_manager.get_text("manual_chk_rts_tooltip"))
        self.chk_rts.toggled.connect(self.rts_changed.emit)

        self.chk_dtr = QCheckBox("DTR")
        self.chk_dtr.setToolTip(language_manager.get_text("manual_chk_dtr_tooltip"))
        self.chk_dtr.toggled.connect(self.dtr_changed.emit)

        # 그리드 배치 (Row, Col)
        grid.addWidget(self.chk_hex, 0, 0)
        grid.addWidget(self.chk_local_echo, 0, 1)
        grid.addWidget(self.chk_broadcast, 0, 2)

        grid.addWidget(self.chk_prefix, 1, 0)
        grid.addWidget(self.chk_suffix, 1, 1)

        grid.addWidget(self.chk_rts, 2, 0)
        grid.addWidget(self.chk_dtr, 2, 1)

        option_group.setLayout(grid)

        layout.addLayout(input_layout)
        layout.addWidget(option_group)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """
        언어 변경 시 UI 텍스트를 업데이트합니다.
        """
        self.input_edit.setPlaceholderText(language_manager.get_text("manual_input_placeholder"))
        self.btn_send.setText(language_manager.get_text("manual_btn_send"))

        self.chk_prefix.setText(language_manager.get_text("manual_chk_prefix"))
        self.chk_suffix.setText(language_manager.get_text("manual_chk_suffix"))
        self.chk_local_echo.setText(language_manager.get_text("manual_chk_local_echo"))
        self.chk_broadcast.setText(language_manager.get_text("manual_chk_broadcast"))

        # 툴팁 업데이트
        self.chk_hex.setToolTip(language_manager.get_text("manual_chk_hex_tooltip"))
        self.chk_prefix.setToolTip(language_manager.get_text("manual_chk_prefix_tooltip"))
        self.chk_suffix.setToolTip(language_manager.get_text("manual_chk_suffix_tooltip"))
        self.chk_local_echo.setToolTip(language_manager.get_text("manual_chk_local_echo_tooltip"))
        self.chk_broadcast.setToolTip(language_manager.get_text("manual_chk_broadcast_tooltip"))
        self.chk_rts.setToolTip(language_manager.get_text("manual_chk_rts_tooltip"))
        self.chk_dtr.setToolTip(language_manager.get_text("manual_chk_dtr_tooltip"))

        # 그룹박스 타이틀 업데이트 (Layout 순서에 의존)
        if self.layout().count() > 1:
            group_box = self.layout().itemAt(1).widget()
            if isinstance(group_box, QGroupBox):
                group_box.setTitle(language_manager.get_text("manual_group_options"))

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        전송 버튼 활성화 상태를 제어합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.btn_send.setEnabled(enabled)
        # 입력창은 항상 활성화하여 미리 입력할 수 있도록 함

    def on_hex_toggled(self, checked: bool) -> None:
        """
        HEX 모드 체크박스 토글 핸들러

        Args:
            checked (bool): 체크 여부.
        """
        # 입력 에디터의 모드 변경 (유효성 검사 적용)
        self.input_edit.set_hex_mode(checked)

    def on_send_clicked(self) -> None:
        """
        전송 버튼 클릭 또는 엔터 키 입력 핸들러

        Logic:
            - UI 입력값 수집
            - ManualCommand DTO 생성
            - 시그널 발행 (Presenter로 전달)
        """
        text = self.input_edit.text()

        # DTO 생성
        command_dto = ManualCommand(
            command=text,
            hex_mode=self.chk_hex.isChecked(),
            prefix_enabled=self.chk_prefix.isChecked(),
            suffix_enabled=self.chk_suffix.isChecked(),
            local_echo_enabled=self.chk_local_echo.isChecked(),
            broadcast_enabled=self.chk_broadcast.isChecked()
        )

        self.send_requested.emit(command_dto)

    def get_state(self) -> ManualControlState:
        """
        현재 UI 상태를 DTO로 반환합니다. (저장용)

        Returns:
            ManualControlState: 현재 상태 정보가 담긴 DTO.
        """
        return ManualControlState(
            input_text=self.input_edit.text(),
            hex_mode=self.chk_hex.isChecked(),
            prefix_enabled=self.chk_prefix.isChecked(),
            suffix_enabled=self.chk_suffix.isChecked(),
            rts_enabled=self.chk_rts.isChecked(),
            dtr_enabled=self.chk_dtr.isChecked(),
            local_echo_enabled=self.chk_local_echo.isChecked(),
            broadcast_enabled=self.chk_broadcast.isChecked()
        )

    def apply_state(self, state: ManualControlState) -> None:
        """
        저장된 상태 DTO를 UI에 적용합니다. (복원용)

        Args:
            state (ManualControlState): 복원할 상태 DTO.
        """
        if not isinstance(state, ManualControlState):
            return

        # 시그널 차단 (상태 복원 중 불필요한 이벤트 발생 방지)
        self.blockSignals(True)
        try:
            self.input_edit.setText(state.input_text)
            self.chk_hex.setChecked(state.hex_mode)
            self.input_edit.set_hex_mode(state.hex_mode)  # 에디터 내부 모드도 동기화

            self.chk_prefix.setChecked(state.prefix_enabled)
            self.chk_suffix.setChecked(state.suffix_enabled)
            self.chk_rts.setChecked(state.rts_enabled)
            self.chk_dtr.setChecked(state.dtr_enabled)
            self.chk_local_echo.setChecked(state.local_echo_enabled)
            self.chk_broadcast.setChecked(state.broadcast_enabled)
        finally:
            self.blockSignals(False)