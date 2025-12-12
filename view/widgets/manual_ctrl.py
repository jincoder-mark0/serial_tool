"""
수동 제어 위젯 모듈

사용자 명령어 입력, 전송 제어 및 포트 신호(RTS/DTR) 설정을 담당합니다.

## WHY
* 사용자가 직접 포트에 명령어를 전송할 수 있는 인터페이스 필요
* HEX/ASCII 모드, 흐름 제어 등 전송 옵션의 직관적인 설정 필요
* 명령어 히스토리 기능을 통한 반복 작업 효율성 증대

## WHAT
* 명령어 입력(QSmartTextEdit) 및 전송 버튼
* 제어 옵션(HEX, Prefix, Suffix, Local Echo) 체크박스
* 하드웨어 흐름 제어(RTS, DTR) 체크박스 및 시그널 발생
* 명령어 히스토리(MRU) 관리

## HOW
* QVBoxLayout 및 QGridLayout을 사용한 컴팩트 레이아웃 구성
* QSmartTextEdit로 라인 번호 및 구문 강조 지원
* PyQt Signal을 통해 사용자 입력 이벤트를 상위로 전달
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QGridLayout, QPlainTextEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeyEvent
from typing import Optional, List
from view.managers.lang_manager import lang_manager
from view.custom_qt.smart_plain_text_edit import QSmartTextEdit
from constants import MAX_CMD_HISTORY_SIZE

class ManualCtrlWidget(QWidget):
    """
    수동 제어 위젯 클래스

    사용자 입력을 받아 시그널을 방출하며, 포트 제어 신호를 설정합니다.
    """

    # 시그널 정의
    manual_cmd_send_requested = pyqtSignal(str, bool, bool, bool, bool) # text, hex, prefix, suffix, local_echo
    rts_changed = pyqtSignal(bool) # RTS 상태 변경
    dtr_changed = pyqtSignal(bool) # DTR 상태 변경
    local_echo_changed = pyqtSignal(bool) # Local Echo 상태 변경

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualCtrlWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.send_manual_cmd_btn = None
        self.history_up_btn = None
        self.history_down_btn = None
        self.manual_cmd_txt = None
        self.dtr_chk = None
        self.rts_chk = None
        self.suffix_chk = None
        self.prefix_chk = None
        self.hex_chk = None
        self.local_echo_chk = None

        # History State
        self.cmd_history: List[str] = []
        self.history_index: int = -1

        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ---------------------------------------------------------
        # 1. 수동 전송 영역 (입력창 + 히스토리/전송 버튼)
        # ---------------------------------------------------------
        self.manual_cmd_txt = QSmartTextEdit()  # 라인 번호 지원 에디터
        self.manual_cmd_txt.setPlaceholderText(lang_manager.get_text("manual_ctrl_txt_cmd_placeholder"))
        self.manual_cmd_txt.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.manual_cmd_txt.setMaximumHeight(80)  # 최대 높이 제한
        # Ctrl+Enter로 전송하도록 keyPressEvent 오버라이드

        # 버튼 레이아웃 (세로 정렬: Up, Down, Send)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(2)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.history_up_btn = QPushButton("▲")
        self.history_up_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_history_up_tooltip"))
        self.history_up_btn.setFixedSize(40, 20)
        self.history_up_btn.clicked.connect(self.on_history_up_clicked)

        self.history_down_btn = QPushButton("▼")
        self.history_down_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_history_down_tooltip"))
        self.history_down_btn.setFixedSize(40, 20)
        self.history_down_btn.clicked.connect(self.on_history_down_clicked)

        self.send_manual_cmd_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_send"))
        self.send_manual_cmd_btn.setCursor(Qt.PointingHandCursor)
        self.send_manual_cmd_btn.setProperty("class", "accent")
        self.send_manual_cmd_btn.setFixedSize(40, 30) # 높이 조정
        self.send_manual_cmd_btn.clicked.connect(self.on_send_manual_cmd_clicked)

        btn_layout.addWidget(self.history_up_btn)
        btn_layout.addWidget(self.history_down_btn)
        btn_layout.addWidget(self.send_manual_cmd_btn)

        send_layout = QHBoxLayout()
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(5)
        send_layout.addWidget(self.manual_cmd_txt, 1)
        send_layout.addLayout(btn_layout)

        # ---------------------------------------------------------
        # 2. 제어 옵션 영역 (체크박스 그리드)
        # ---------------------------------------------------------
        self.hex_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_hex"))
        self.hex_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_hex_tooltip"))

        # 접두사/접미사 체크박스
        self.prefix_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_suffix"))

        # 흐름 제어 (Flow Control - RTS/DTR)
        self.rts_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_rts"))
        self.rts_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_rts_tooltip"))
        # RTS 시그널 연결
        self.rts_chk.stateChanged.connect(lambda state: self.rts_changed.emit(state == Qt.Checked))

        self.dtr_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_dtr"))
        self.dtr_chk.setToolTip(lang_manager.get_text("manual_ctrl_chk_dtr_tooltip"))
        # DTR 시그널 연결
        self.dtr_chk.stateChanged.connect(lambda state: self.dtr_changed.emit(state == Qt.Checked))

        # 로컬 에코 체크박스 추가
        self.local_echo_chk = QCheckBox(lang_manager.get_text("manual_ctrl_chk_local_echo"))
        self.local_echo_chk.stateChanged.connect(lambda state: self.local_echo_changed.emit(state == Qt.Checked))

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

        # 메인 레이아웃에 추가
        layout.addLayout(send_layout)
        layout.addLayout(option_layout)
        layout.addStretch() # 하단 여백 추가

        self.setLayout(layout)

        # 초기 상태 설정
        self.set_controls_enabled(False)

        # QTextEdit에 keyPressEvent 연결
        self.manual_cmd_txt.keyPressEvent = self._cmd_input_key_press_event

    def retranslate_ui(self) -> None:
        """다국어 텍스트 업데이트"""
        self.hex_chk.setText(lang_manager.get_text("manual_ctrl_chk_hex"))
        self.prefix_chk.setText(lang_manager.get_text("manual_ctrl_chk_prefix"))
        self.suffix_chk.setText(lang_manager.get_text("manual_ctrl_chk_suffix"))
        self.rts_chk.setText(lang_manager.get_text("manual_ctrl_chk_rts"))
        self.dtr_chk.setText(lang_manager.get_text("manual_ctrl_chk_dtr"))
        self.local_echo_chk.setText(lang_manager.get_text("manual_ctrl_chk_local_echo"))
        self.send_manual_cmd_btn.setText(lang_manager.get_text("manual_ctrl_btn_send"))
        self.history_up_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_history_up_tooltip"))
        self.history_down_btn.setToolTip(lang_manager.get_text("manual_ctrl_btn_history_down_tooltip"))
        self.manual_cmd_txt.setPlaceholderText(lang_manager.get_text("manual_ctrl_txt_cmd_placeholder"))

    def _cmd_input_key_press_event(self, event: QKeyEvent) -> None:
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
                self.on_send_manual_cmd_clicked()
            else:
                # Enter: 새 줄 추가
                QPlainTextEdit.keyPressEvent(self.manual_cmd_txt, event)
        elif event.key() == Qt.Key_Up and event.modifiers() == Qt.ControlModifier:
            self.on_history_up_clicked()
        elif event.key() == Qt.Key_Down and event.modifiers() == Qt.ControlModifier:
            self.on_history_down_clicked()
        else:
            # 다른 키는 기본 동작
            QPlainTextEdit.keyPressEvent(self.manual_cmd_txt, event)

    def on_hex_mode_changed(self, state: int) -> None:
        """HEX 모드 변경 시 처리 (QTextEdit는 hex 모드 미지원)"""
        # QTextEdit는 QSmartLineEdit와 달리 hex 모드를 지원하지 않음
        # 필요시 입력 검증 로직 추가 가능
        pass

    def on_send_manual_cmd_clicked(self) -> None:
        """전송 버튼 클릭 처리"""
        text = self.manual_cmd_txt.toPlainText()
        if text:
            # 히스토리에 추가
            self.add_to_history(text)

            # View는 원본 입력과 체크박스 상태만 전달
            # prefix/suffix 처리는 Presenter에서 수행
            self.manual_cmd_send_requested.emit(
                text,
                self.hex_chk.isChecked(),
                self.prefix_chk.isChecked(),
                self.suffix_chk.isChecked(),
                self.local_echo_chk.isChecked()
            )
            # 입력 후 지우지 않음 (히스토리 기능이 없으므로 유지하는 편이 나음 -> 히스토리 있으니 지워도 되지만, 보통 남겨두는게 편함)
            # self.manual_cmd_txt.clear()

    def add_to_history(self, cmd: str) -> None:
        """
        명령어 히스토리 추가

        Logic:
            - 중복 제거 (기존 항목 있으면 삭제 후 뒤로 이동)
            - 최대 크기(MAX_CMD_HISTORY_SIZE) 제한
            - 인덱스 초기화

        Args:
            cmd (str): 명령어 텍스트
        """
        if cmd in self.cmd_history:
            self.cmd_history.remove(cmd)

        self.cmd_history.append(cmd)

        # 최대 크기 제한
        if len(self.cmd_history) > MAX_CMD_HISTORY_SIZE:
            self.cmd_history.pop(0) # 가장 오래된 항목 제거

        # 인덱스 초기화 (새 명령 입력 시 히스토리 탐색 중단)
        self.history_index = -1

    def on_history_up_clicked(self) -> None:
        """이전 히스토리 탐색"""
        if not self.cmd_history: return

        if self.history_index == -1:
            # 현재 입력 중인 상태에서 위로 누르면 가장 최근(마지막) 명령
            self.history_index = len(self.cmd_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1

        self._update_input_from_history()

    def on_history_down_clicked(self) -> None:
        """다음 히스토리 탐색"""
        if not self.cmd_history or self.history_index == -1: return

        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self._update_input_from_history()
        else:
            # 마지막 항목에서 아래로 누르면 입력창 비우기 (새 명령 모드)
            self.history_index = -1
            self.manual_cmd_txt.clear()

    def _update_input_from_history(self) -> None:
        """히스토리 내용을 입력창에 반영"""
        if 0 <= self.history_index < len(self.cmd_history):
            cmd = self.cmd_history[self.history_index]
            self.manual_cmd_txt.setPlainText(cmd)
            # 커서 끝으로 이동
            cursor = self.manual_cmd_txt.textCursor()
            cursor.movePosition(cursor.End)
            self.manual_cmd_txt.setTextCursor(cursor)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        컨트롤 활성화 상태 설정

        Args:
            enabled (bool): 활성화 여부
        """
        self.send_manual_cmd_btn.setEnabled(enabled)
        # RTS/DTR은 연결된 상태에서만 제어 가능
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
            "input_text": self.manual_cmd_txt.toPlainText(),  # QTextEdit는 toPlainText() 사용
            "hex_mode": self.hex_chk.isChecked(),
            "prefix_chk": self.prefix_chk.isChecked(),
            "suffix_chk": self.suffix_chk.isChecked(),
            "rts_chk": self.rts_chk.isChecked(),
            "dtr_chk": self.dtr_chk.isChecked(),
            "local_echo": self.local_echo_chk.isChecked(),
            "cmd_history": self.cmd_history # 히스토리 저장
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

        self.hex_chk.setChecked(state.get("hex_mode", False))
        self.prefix_chk.setChecked(state.get("prefix_chk", False))
        self.suffix_chk.setChecked(state.get("suffix_chk", False))
        self.rts_chk.setChecked(state.get("rts_chk", False))
        self.dtr_chk.setChecked(state.get("dtr_chk", False))
        self.local_echo_chk.setChecked(state.get("local_echo", False))
        self.manual_cmd_txt.setPlainText(state.get("input_text", ""))
        self.cmd_history = state.get("cmd_history", [])
