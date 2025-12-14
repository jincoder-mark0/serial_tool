"""
ManualControlWidget 모듈

사용자 명령어 입력, 전송 제어 및 포트 신호(RTS/DTR) 설정을 담당합니다.

## WHY
* 사용자가 직접 포트에 명령어를 전송할 수 있는 인터페이스 필요
* HEX/ASCII 모드, 흐름 제어 등 전송 옵션의 직관적인 설정 필요
* 명령어 히스토리 기능을 통한 반복 작업 효율성 증대

## WHAT
* 명령어 입력(QSmartTextEdit) 및 전송 버튼
* 제어 옵션(HEX, Prefix, Suffix, Local Echo) 체크박스
* Broadcast 체크박스 추가
* 하드웨어 흐름 제어(RTS, DTR) 체크박스 및 시그널 발생
* 명령어 히스토리(MRU) 관리

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
from common.dtos import ManualCommand
from common.constants import MAX_COMMAND_HISTORY_SIZE

class ManualControlWidget(QWidget):
    """
    수동 명령어 입력 및 전송 위젯 클래스

    사용자 입력을 받아 시그널을 방출하며, 포트 제어 신호를 설정
    """

    # 시그널 정의
    send_requested = pyqtSignal(object)

    # 하드웨어 제어 신호 변경 시그널
    rts_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)

        # UI 컴포넌트 선언
        self.send_manual_command_btn: Optional[QPushButton] = None
        self.history_up_btn: Optional[QPushButton] = None
        self.history_down_btn: Optional[QPushButton] = None
        self.manual_command_txt = None
        self.dtr_chk: Optional[QCheckBox] = None
        self.rts_chk: Optional[QCheckBox] = None
        self.suffix_chk: Optional[QCheckBox] = None
        self.prefix_chk: Optional[QCheckBox] = None
        self.hex_chk: Optional[QCheckBox] = None
        self.local_echo_chk: Optional[QCheckBox] = None
        self.broadcast_chk: Optional[QCheckBox] = None

        # History State
        self.command_history: List[str] = []
        self.history_index: int = -1

        self.init_ui()

        # 언어 변경 이벤트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""

        # 1. 입력 및 전송 영역
        self.manual_command_txt = QSmartTextEdit()  # 라인 번호 지원 에디터
        self.manual_command_txt.setPlaceholderText(language_manager.get_text("manual_control_txt_command_placeholder"))
        self.manual_command_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.manual_command_txt.setMaximumHeight(80)  # 최대 높이 제한
        # Ctrl+Enter로 전송하도록 keyPressEvent 오버라이드

        # 버튼 레이아웃 (세로 정렬: Up, Down, Send)
        self.history_up_btn = QPushButton("▲")
        self.history_up_btn.setToolTip(language_manager.get_text("manual_control_btn_history_up_tooltip"))
        self.history_up_btn.setFixedSize(40, 20)
        self.history_up_btn.clicked.connect(self.on_history_up_clicked)

        self.history_down_btn = QPushButton("▼")
        self.history_down_btn.setToolTip(language_manager.get_text("manual_control_btn_history_down_tooltip"))
        self.history_down_btn.setFixedSize(40, 20)
        self.history_down_btn.clicked.connect(self.on_history_down_clicked)

        self.send_manual_command_btn = QPushButton(language_manager.get_text("manual_control_btn_send"))
        self.send_manual_command_btn.setCursor(Qt.PointingHandCursor)
        self.send_manual_command_btn.setProperty("class", "accent")
        self.send_manual_command_btn.setFixedSize(40, 30) # 높이 조정
        self.send_manual_command_btn.clicked.connect(self.on_send_manual_command_clicked)

        # 2. 옵션 영역
        self.hex_chk = QCheckBox(language_manager.get_text("manual_control_chk_hex"))
        self.hex_chk.setToolTip(language_manager.get_text("manual_control_chk_hex_tooltip"))

        # 접두사/접미사 체크박스
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
        self.broadcast_chk = QCheckBox("Broadcast") # 추후 언어 키 추가 권장
        self.broadcast_chk.setToolTip("Send command to all active ports that allow broadcasting")

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(2)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.history_up_btn)
        btn_layout.addWidget(self.history_down_btn)
        btn_layout.addWidget(self.send_manual_command_btn)

        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(5)
        send_layout.addWidget(self.manual_command_txt, 1)
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

        # 메인 레이아웃에 추가
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
        self.manual_command_txt.keyPressEvent = self._command_input_key_press_event

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
        self.send_manual_command_btn.setText(language_manager.get_text("manual_control_btn_send"))
        self.history_up_btn.setToolTip(language_manager.get_text("manual_control_btn_history_up_tooltip"))
        self.history_down_btn.setToolTip(language_manager.get_text("manual_control_btn_history_down_tooltip"))
        self.manual_command_txt.setPlaceholderText(language_manager.get_text("manual_control_txt_command_placeholder"))

    def _command_input_key_press_event(self, event: QKeyEvent) -> None:
        """
        입력창 키 이벤트 핸들링

        Logic:
            - Ctrl+Enter: 전송
            - Ctrl+Up/Down: 히스토리 탐색
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
                QPlainTextEdit.keyPressEvent(self.manual_command_txt, event)
        elif event.key() == Qt.Key_Up and event.modifiers() == Qt.ControlModifier:
            self.on_history_up_clicked()
        elif event.key() == Qt.Key_Down and event.modifiers() == Qt.ControlModifier:
            self.on_history_down_clicked()
        else:
            # 다른 키는 기본 동작
            QPlainTextEdit.keyPressEvent(self.manual_command_txt, event)

    def on_hex_mode_changed(self, state: int) -> None:
        """HEX 모드 변경 시 처리 (QTextEdit는 hex 모드 미지원)"""
        # QTextEdit는 QSmartLineEdit와 달리 hex 모드를 지원하지 않음
        # 필요시 입력 검증 로직 추가 가능
        pass

    @pyqtSlot()
    def on_send_manual_command_clicked(self) -> None:
        """
        전송 버튼 클릭 슬롯
        """
        text = self.manual_command_txt.text()
        if text:
            # 히스토리에 추가
            self.add_to_history(text)
        if not text:
            return

        # 전송 데이터 패키징 (DTO)
        # View(Widget) 내부의 체크박스 상태로 DTO를 완결성 있게 생성합니다.
        command = ManualCommand(
            text=text,
            hex_mode=self.hex_chk.isChecked(),
            prefix=self.prefix_chk.isChecked(),
            suffix=self.suffix_chk.isChecked(),
            local_echo=self.local_echo_chk.isChecked(),
            is_broadcast=self.broadcast_chk.isChecked() # Broadcast 상태 반영
        )

        self.send_requested.emit(command)

    def add_to_history(self, command: str) -> None:
        """
        명령어 히스토리 추가

        Logic:
            - 중복 제거 (기존 항목 있으면 삭제 후 뒤로 이동)
            - 최대 크기(MAX_COMMAND_HISTORY_SIZE) 제한
            - 인덱스 초기화

        Args:
            command (str): 명령어 텍스트
        """
        if command in self.command_history:
            self.command_history.remove(command)

        self.command_history.append(command)
        if len(self.command_history) > MAX_COMMAND_HISTORY_SIZE:
            self.command_history.pop(0) # 가장 오래된 항목 제거

        # 인덱스 초기화 (새 명령 입력 시 히스토리 탐색 중단)
        self.history_index = -1

    def on_history_up_clicked(self) -> None:
        """이전 히스토리 탐색"""
        if not self.command_history: return

        if self.history_index == -1:
            # 현재 입력 중인 상태에서 위로 누르면 가장 최근(마지막) 명령
            self.history_index = len(self.command_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1

        self._update_input_from_history()

    def on_history_down_clicked(self) -> None:
        """다음 히스토리 탐색"""
        if not self.command_history or self.history_index == -1: return

        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self._update_input_from_history()
        else:
            # 마지막 항목에서 아래로 누르면 입력창 비우기 (새 명령 모드)
            self.history_index = -1
            self.manual_command_txt.clear()

    def _update_input_from_history(self) -> None:
        """히스토리 내용을 입력창에 반영"""
        if 0 <= self.history_index < len(self.command_history):
            command = self.command_history[self.history_index]
            self.manual_command_txt.setPlainText(command)
            # 커서 끝으로 이동
            cursor = self.manual_command_txt.textCursor()
            cursor.movePosition(cursor.End)
            self.manual_command_txt.setTextCursor(cursor)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        컨트롤 활성화 상태 설정

        Args:
            enabled (bool): 활성화 여부
        """
        self.send_manual_command_btn.setEnabled(enabled)
        self.rts_chk.setEnabled(enabled)
        self.dtr_chk.setEnabled(enabled)

    def set_local_echo_state(self, checked: bool) -> None:
        """
        Local Echo 체크박스 상태 설정

        Args:
            checked (bool): 체크 여부
        """
        self.local_echo_chk.setChecked(checked)

    def save_state(self) -> dict:
        """
        상태 저장

        Returns:
            dict: 현재 위젯 상태
        """
        state = {
            "input_text": self.manual_command_txt.toPlainText(),
            "hex_mode": self.hex_chk.isChecked(),
            "prefix_chk": self.prefix_chk.isChecked(),
            "suffix_chk": self.suffix_chk.isChecked(),
            "rts_chk": self.rts_chk.isChecked(),
            "dtr_chk": self.dtr_chk.isChecked(),
            "local_echo_chk": self.local_echo_chk.isChecked(),
            "broadcast_chk": self.broadcast_chk.isChecked(), # 상태 저장
            "command_history": self.command_history
        }
        return state

    def load_state(self, state: dict) -> None:
        """
        상태 복원

        Args:
            state (dict): 복원할 상태 데이터
        """
        if not state:
            return
        self.manual_command_txt.setPlainText(state.get("input_text", ""))
        self.hex_chk.setChecked(state.get("hex_mode", False))
        self.prefix_chk.setChecked(state.get("prefix_chk", False))
        self.suffix_chk.setChecked(state.get("suffix_chk", False))
        self.rts_chk.setChecked(state.get("rts_chk", False))
        self.dtr_chk.setChecked(state.get("dtr_chk", False))
        self.local_echo_chk.setChecked(state.get("local_echo_chk", False))
        self.broadcast_chk.setChecked(state.get("broadcast_chk", False))
        self.command_history = state.get("command_history", [])
