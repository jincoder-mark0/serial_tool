"""
ManualControlWidget 모듈

사용자 Command 입력, 전송 제어 및 포트 신호(RTS/DTR) 설정을 담당합니다.

## WHY
* 사용자가 직접 포트에 Command를 전송할 수 있는 인터페이스 필요
* HEX/ASCII 모드, 흐름 제어 등 전송 옵션의 직관적인 설정 필요
* Command History 기능을 통한 반복 작업 효율성 증대

## WHAT
* Command 입력(QSmartTextEdit) 및 전송 버튼
* 제어 옵션(HEX, Prefix, Suffix, Local Echo) 체크박스
* Broadcast 체크박스 추가
* 하드웨어 흐름 제어(RTS, DTR) 체크박스 및 시그널 발생
* Command History(MRU) 관리

## HOW
* QVBoxLayout 및 QGridLayout을 사용한 컴팩트 레이아웃 구성
* QSmartTextEdit로 라인 번호 및 구문 강조 지원
* PyQt Signal을 통해 사용자 입력 이벤트를 상위로 전달
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QPlainTextEdit, QLineEdit, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QSize, Qt
from PyQt5.QtGui import QKeyEvent
from view.custom_qt.smart_plain_text_edit import QSmartTextEdit
from typing import Optional, List
from view.managers.language_manager import language_manager
from common.dtos import ManualCommand, ManualControlState
from common.constants import MAX_COMMAND_HISTORY_SIZE

class ManualControlWidget(QWidget):
    """
    수동 Command 입력 및 전송 위젯 클래스

    사용자 입력을 받아 시그널을 방출하며, 포트 제어 신호를 설정
    """

    # 시그널 정의
    send_requested = pyqtSignal(object)  # ManualCommand DTO 전달
    history_up_requested = pyqtSignal()
    history_down_requested = pyqtSignal()

    # 상태 변경 시그널 (즉시 로직 반영이 필요한 항목들)
    broadcast_changed = pyqtSignal(bool)  # 브로드캐스트 변경 (전송 버튼 활성화 로직용)
    rts_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)

        # UI 컴포넌트 변수 초기화
        self.command_edit: Optional[QSmartTextEdit] = None
        self.send_command_btn: Optional[QPushButton] = None
        self.history_up_btn: Optional[QPushButton] = None
        self.history_down_btn: Optional[QPushButton] = None

        # Checkboxes
        self.hex_chk: Optional[QCheckBox] = None
        self.prefix_chk: Optional[QCheckBox] = None
        self.suffix_chk: Optional[QCheckBox] = None
        self.local_echo_chk: Optional[QCheckBox] = None
        self.broadcast_chk: Optional[QCheckBox] = None
        self.rts_chk: Optional[QCheckBox] = None
        self.dtr_chk: Optional[QCheckBox] = None

        # History State - 저장/복원 안함
        self.command_history: List[str] = []
        self.history_index: int = -1

        self.init_ui()

        # 언어 변경 시그널 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        self.command_edit = QSmartTextEdit()  # 라인 번호 지원 에디터
        self.command_edit.setPlaceholderText(language_manager.get_text("manual_control_txt_command_placeholder"))
        self.command_edit.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.command_edit.setMaximumHeight(80)  # 최대 높이 제한
        # ---------------------------------------------------------
        # 1. 입력 영역 (Input Area)
        # ---------------------------------------------------------
        self.history_up_btn = QPushButton("▲")
        self.history_up_btn.setToolTip(language_manager.get_text("manual_control_btn_history_up_tooltip"))
        self.history_up_btn.setFixedSize(40, 20)
        self.history_up_btn.clicked.connect(self.on_history_up_clicked)

        self.history_down_btn = QPushButton("▼")
        self.history_down_btn.setToolTip(language_manager.get_text("manual_control_btn_history_down_tooltip"))
        self.history_down_btn.setFixedSize(40, 20)
        self.history_down_btn.clicked.connect(self.on_history_down_clicked)

        self.send_command_btn = QPushButton(language_manager.get_text("manual_control_btn_send"))
        self.send_command_btn.setCursor(Qt.PointingHandCursor)
        self.send_command_btn.setProperty("class", "accent")
        self.send_command_btn.setFixedSize(40, 30) # 높이 조정
        self.send_command_btn.clicked.connect(self.on_send_manual_command_clicked)


        self.hex_chk = QCheckBox(language_manager.get_text("manual_control_chk_hex"))
        self.hex_chk.setToolTip(language_manager.get_text("manual_control_chk_hex_tooltip"))
        self.hex_chk.toggled.connect(self.on_hex_toggled)


        self.prefix_chk = QCheckBox(language_manager.get_text("manual_control_chk_prefix"))
        self.suffix_chk = QCheckBox(language_manager.get_text("manual_control_chk_suffix"))

        self.rts_chk = QCheckBox(language_manager.get_text("manual_control_chk_rts"))
        self.rts_chk.setToolTip(language_manager.get_text("manual_control_chk_rts_tooltip"))
        self.rts_chk.stateChanged.connect(lambda state: self.rts_changed.emit(state == Qt.Checked))

        self.dtr_chk = QCheckBox(language_manager.get_text("manual_control_chk_dtr"))
        self.dtr_chk.setToolTip(language_manager.get_text("manual_control_chk_dtr_tooltip"))
        self.dtr_chk.stateChanged.connect(lambda state: self.dtr_changed.emit(state == Qt.Checked))

        self.local_echo_chk = QCheckBox(language_manager.get_text("manual_control_chk_local_echo"))

        # Broadcast 체크박스
        self.broadcast_chk = QCheckBox(language_manager.get_text("manual_control_chk_broadcast"))
        self.broadcast_chk.setToolTip(language_manager.get_text("manual_control_chk_broadcast_tooltip"))
        self.broadcast_chk.stateChanged.connect(
            lambda state: self.broadcast_changed.emit(state == Qt.Checked)
        )

        # 레이아웃 배치
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(2)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.history_up_btn)
        btn_layout.addWidget(self.history_down_btn)
        btn_layout.addWidget(self.send_command_btn)

        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(5)
        send_layout.addWidget(self.command_edit, 1)
        send_layout.addLayout(btn_layout)

        # 전체 레이아웃
        option_layout = QGridLayout()
        option_layout.setContentsMargins(0, 5, 0, 0) # 상단 여백 추가
        option_layout.setSpacing(5) # 간격 조정

        # 1행에 배치
        option_layout.addWidget(self.hex_chk, 0, 0)
        option_layout.addWidget(self.prefix_chk, 0, 1)
        option_layout.addWidget(self.suffix_chk, 0, 2)
        option_layout.addWidget(self.rts_chk, 0, 3)
        option_layout.addWidget(self.dtr_chk, 0, 4)
        option_layout.addWidget(self.local_echo_chk, 0, 5)
        option_layout.addWidget(self.broadcast_chk, 0, 6)

        # 그리드 배치 (Row, Col)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(send_layout)
        layout.addLayout(option_layout)
        layout.addStretch() # 하단 여백 추가

        self.setLayout(layout)

        # 초기 상태 설정
        self.set_controls_enabled(False)

        # QTextEdit에 keyPressEvent 연결
        self.command_edit.keyPressEvent = self._command_input_key_press_event

    def retranslate_ui(self) -> None:
        """
        다국어 텍스트 업데이트
        """
        self.hex_chk.setText(language_manager.get_text("manual_control_chk_hex"))
        self.prefix_chk.setText(language_manager.get_text("manual_control_chk_prefix"))
        self.suffix_chk.setText(language_manager.get_text("manual_control_chk_suffix"))
        self.rts_chk.setText(language_manager.get_text("manual_control_chk_rts"))
        self.dtr_chk.setText(language_manager.get_text("manual_control_chk_dtr"))
        self.local_echo_chk.setText(language_manager.get_text("manual_control_chk_local_echo"))
        self.broadcast_chk.setText(language_manager.get_text("manual_control_chk_broadcast"))
        self.send_command_btn.setText(language_manager.get_text("manual_control_btn_send"))
        self.history_up_btn.setToolTip(language_manager.get_text("manual_control_btn_history_up_tooltip"))
        self.history_down_btn.setToolTip(language_manager.get_text("manual_control_btn_history_down_tooltip"))
        self.command_edit.setPlaceholderText(language_manager.get_text("manual_control_txt_command_placeholder"))

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        전송 버튼 활성화 상태를 제어합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.send_command_btn.setEnabled(enabled)
        # 입력창은 항상 활성화하여 미리 입력할 수 있도록 함

    def _command_input_key_press_event(self, event: QKeyEvent) -> None:
        """
        입력창 키 이벤트 핸들링

        Logic:
            - Ctrl+Enter: 전송
            - Ctrl+Up/Down: History 탐색
            - 기타: 기본 동작

        Args:
            event (QKeyEvent): 키 이벤트 객체
        """
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() == Qt.ControlModifier:
                # Ctrl+Enter: 전송
                self.on_send_manual_command_clicked()
            else:
                # Enter: 새 줄 추가
                QPlainTextEdit.keyPressEvent(self.command_edit, event)
        elif event.key() == Qt.Key_Up and event.modifiers() == Qt.ControlModifier:
            self.on_history_up_clicked()
        elif event.key() == Qt.Key_Down and event.modifiers() == Qt.ControlModifier:
            self.on_history_down_clicked()
        else:
            # 다른 키는 기본 동작
            QPlainTextEdit.keyPressEvent(self.command_edit, event)

    def on_hex_toggled(self, checked: bool) -> None:
        """
        HEX 모드 체크박스 토글 핸들러

        Args:
            checked (bool): 체크 여부.
        """
        # 입력 에디터의 모드 변경 (유효성 검사 적용)
        # self.command_edit.set_hex_mode(checked)   # TODO: QSmartTextEdit HEX 모드 구현
        pass

    @pyqtSlot()
    def on_send_manual_command_clicked(self) -> None:
        """
        전송 버튼 클릭 슬롯
        """
        command = self.command_edit.toPlainText()

        # History에 추가
        if command:
            self.add_to_history(command)
        if not command:
            return

        # 전송 데이터 패키징 (DTO)
        # View(Widget) 내부의 체크박스 상태로 DTO를 완결성 있게 생성합니다.

        # DTO 생성
        command_dto = ManualCommand(
            command=command,
            hex_mode=self.hex_chk.isChecked(),
            prefix_enabled=self.prefix_chk.isChecked(),
            suffix_enabled=self.suffix_chk.isChecked(),
            local_echo_enabled=self.local_echo_chk.isChecked(),
            broadcast_enabled=self.broadcast_chk.isChecked()
        )

        self.send_requested.emit(command_dto)

    def set_input_text(self, text: str) -> None:
        """입력창 텍스트 설정 (Presenter용)"""
        self.command_edit.setPlainText(text)
        cursor = self.command_edit.textCursor()
        cursor.movePosition(cursor.End)
        self.command_edit.setTextCursor(cursor)

    def get_input_text(self) -> str:
        return self.command_edit.toPlainText()

    def clear_input(self) -> None:
        self.command_edit.clear()

    def add_to_history(self, command: str) -> None:
        """
        Command History 추가

        Logic:
            - 중복 제거 (기존 항목 있으면 삭제 후 뒤로 이동)
            - 최대 크기(MAX_COMMAND_HISTORY_SIZE) 제한
            - 인덱스 초기화

        Args:
            command (str): Command 텍스트
        """
        if command in self.command_history:
            self.command_history.remove(command)

        self.command_history.append(command)
        if len(self.command_history) > MAX_COMMAND_HISTORY_SIZE:
            self.command_history.pop(0) # 가장 오래된 항목 제거

        # 인덱스 초기화 (새 명령 입력 시 History 탐색 중단)
        self.history_index = -1

    def on_history_up_clicked(self) -> None:
        """이전 History 탐색"""
        if not self.command_history: return

        if self.history_index == -1:
            # 현재 입력 중인 상태에서 위로 누르면 가장 최근(마지막) 명령
            self.history_index = len(self.command_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1

        self._update_input_from_history()

    def on_history_down_clicked(self) -> None:
        """다음 History 탐색"""
        if not self.command_history or self.history_index == -1: return

        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self._update_input_from_history()
        else:
            # 마지막 항목에서 아래로 누르면 입력창 비우기 (새 명령 모드)
            self.history_index = -1
            self.command_edit.clear()

    def _update_input_from_history(self) -> None:
        """History 내용을 입력창에 반영"""
        if 0 <= self.history_index < len(self.command_history):
            command = self.command_history[self.history_index]
            self.command_edit.setPlainText(command)
            # 커서 끝으로 이동
            cursor = self.command_edit.textCursor()
            cursor.movePosition(cursor.End)
            self.command_edit.setTextCursor(cursor)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        컨트롤 활성화 상태 설정

        Args:
            enabled (bool): 활성화 여부
        """
        self.send_command_btn.setEnabled(enabled)
        self.rts_chk.setEnabled(enabled)
        self.dtr_chk.setEnabled(enabled)
        
        # Hex, Prefix, Suffix, Broadcast 설정은 연결 여부와 무관하게 변경 가능해야 함
        # 따라서 이들은 enabled 인자의 영향을 받지 않도록 따로 처리하거나 그대로 둡니다.
        # self.command_edit.setEnabled(True)
        # self.hex_chk.setEnabled(True)
        # self.prefix_chk.setEnabled(True)
        # self.suffix_chk.setEnabled(True)
        # self.broadcast_chk.setEnabled(True)

    def set_input_focus(self) -> None:
        """입력 필드에 포커스를 설정합니다."""
        self.command_edit.setFocus()

    def set_local_echo_state(self, checked: bool) -> None:
        """
        Local Echo 체크박스 상태 설정

        Args:
            checked (bool): 체크 여부
        """
        self.local_echo_chk.setChecked(checked)

    def get_state(self) -> ManualControlState:
        """
        현재 UI 상태를 DTO로 반환합니다. (저장용)

        Returns:
            ManualControlState: 현재 상태 정보가 담긴 DTO.
        """
        return ManualControlState(
            input_text=self.command_edit.toPlainText(),
            hex_mode=self.hex_chk.isChecked(),
            prefix_enabled=self.prefix_chk.isChecked(),
            suffix_enabled=self.suffix_chk.isChecked(),
            rts_enabled=self.rts_chk.isChecked(),
            dtr_enabled=self.dtr_chk.isChecked(),
            local_echo_enabled=self.local_echo_chk.isChecked(),
            broadcast_enabled=self.broadcast_chk.isChecked()
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
            self.command_edit.setPlainText(state.input_text)
            self.hex_chk.setChecked(state.hex_mode)
            # self.command_edit.set_hex_mode(state.hex_mode)  # 에디터 내부 모드도 동기화

            self.prefix_chk.setChecked(state.prefix_enabled)
            self.suffix_chk.setChecked(state.suffix_enabled)
            self.rts_chk.setChecked(state.rts_enabled)
            self.dtr_chk.setChecked(state.dtr_enabled)
            self.local_echo_chk.setChecked(state.local_echo_enabled)
            self.broadcast_chk.setChecked(state.broadcast_enabled)
        finally:
            self.blockSignals(False)
