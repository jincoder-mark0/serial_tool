"""
스마트 숫자 에디터 모듈

커서 위치 기반 숫자 증감 및 Alt 코드 입력을 지원하는 텍스트 에디터입니다.

## WHY
* 매크로 편집 시 값을 빠르고 정밀하게 조정할 필요성
* 제어 문자(Non-printable char) 입력 및 시각화 지원

## WHAT
* QPlainTextEdit 기반 커스텀 위젯
* 방향키(Up/Down)를 이용한 커서 위치별 숫자 증감
* Alt + Numpad 조합을 통한 아스키/제어 문자 입력
* 제어 문자 배경색 하이라이팅

## HOW
* EventFilter를 통한 키 입력 가로채기
* 정규식을 이용한 숫자 및 제어 문자 탐지
* ExtraSelection을 활용한 텍스트 하이라이팅
"""
import re
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent, QTextCursor, QTextCharFormat, QColor
from core.logger import logger

class SmartNumberEdit(QPlainTextEdit):
    """
    커서 위치 기반 숫자 증감 QPlainTextEdit

    Alt 코드 입력 및 제어 문자 배경색 표시를 지원합니다.
    """

    NUMBER_PATTERN = re.compile(r'([+-]?\d+)')
    CONTROL_BG_COLOR = QColor(255, 200, 200, 150)

    def __init__(self, parent=None):
        """SmartNumberEdit 초기화"""
        super().__init__(parent)

        self._alt_pressed = False
        self._alt_input_buffer = ""
        self._alt_handling_in_progress = False

        self.installEventFilter(self)
        self.document().contentsChanged.connect(self._update_control_char_highlight)

    # ---------------- Alt 코드 입력 처리 ----------------
    def eventFilter(self, obj, event):
        """
        Alt 코드 입력 처리

        Logic:
            - Alt 키 눌림 감지 및 버퍼 초기화
            - Alt+Numpad 숫자 입력을 버퍼에 저장
            - Alt 키 릴리즈 시 버퍼를 ASCII 코드로 변환하여 삽입
            - 중복 입력 방지를 위해 이벤트 소비
        """
        if obj is self:
            if event.type() == QEvent.KeyPress:
                key_event = event
                key = key_event.key()
                mods = key_event.modifiers()

                # Alt 눌림
                if key == Qt.Key_Alt:
                    self._alt_pressed = True
                    self._alt_input_buffer = ""
                    return False

                # Alt + Numpad 숫자 입력
                is_numpad_digit = (Qt.Key_0 <= key <= Qt.Key_9) and (mods & Qt.KeypadModifier)
                if self._alt_pressed and is_numpad_digit:
                    number = key - Qt.Key_0
                    self._alt_input_buffer += str(number)
                    return True  # 이벤트 소비 → 중복 방지

                # Alt 상태에서 다른 키 입력 시 버퍼 초기화
                if self._alt_pressed and key != Qt.Key_Alt:
                    self._alt_input_buffer = ""
                    return True  # 이벤트 소비

            elif event.type() == QEvent.KeyRelease:
                key_event = event
                if key_event.key() == Qt.Key_Alt and self._alt_pressed:
                    self._alt_pressed = False
                    if self._alt_input_buffer:
                        try:
                            code = int(self._alt_input_buffer)
                            if 0 <= code <= 255:
                                control_char = chr(code)
                                self._alt_handling_in_progress = True
                                self._insert_char(control_char)
                                self._alt_handling_in_progress = False
                        except ValueError:
                            pass
                        finally:
                            self._alt_input_buffer = ""
                    return True  # 이벤트 소비
        return super().eventFilter(obj, event)

    # ---------------- 일반 KeyPress 처리 ----------------
    def keyPressEvent(self, event: QKeyEvent):
        """
        키 입력 처리

        Logic:
            - Alt 입력 중이면 일반 KeyPress 무시
            - Ctrl+Up: 숫자 증가
            - Ctrl+Down: 숫자 감소
        """
        if self._alt_pressed or self._alt_handling_in_progress:
            # Alt 입력 중이면 일반 KeyPress 무시
            return

        mods = event.modifiers()
        key = event.key()

        if mods == Qt.ControlModifier:
            if key == Qt.Key_Up:
                self.increment_number(1)
                return
            elif key == Qt.Key_Down:
                self.increment_number(-1)
                return

        super().keyPressEvent(event)

    # ---------------- 문자 삽입 ----------------
    def _insert_char(self, char: str):
        """문자 삽입"""
        cursor = self.textCursor()
        cursor.insertText(char)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    # ---------------- 제어 문자 하이라이트 ----------------
    def _get_control_char_format(self) -> QTextCharFormat:
        """제어 문자 포맷 반환"""
        fmt = QTextCharFormat()
        fmt.setBackground(self.CONTROL_BG_COLOR)
        return fmt

    def _update_control_char_highlight(self):
        """
        제어 문자 하이라이트 업데이트

        Logic:
            - 문서 전체에서 제어 문자 탐색 (\\x01-\\x1F)
            - 각 제어 문자에 배경색 적용
            - ExtraSelection으로 하이라이트 표시
        """
        document = self.document()
        highlight_format = self._get_control_char_format()
        selections = []

        text = self.toPlainText()
        control_char_regex = re.compile(r'[\x01-\x1F]')

        for match in control_char_regex.finditer(text):
            start, end = match.span()
            selection = QTextEdit.ExtraSelection()
            selection.format = highlight_format
            selection.cursor = QTextCursor(document)
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.KeepAnchor)
            selections.append(selection)

        self.setExtraSelections(selections)

    # ---------------- 커서 위치 기반 숫자 증감 ----------------
    def increment_number(self, step: int):
        """
        커서 위치의 숫자를 자릿수 단위로 증감

        Logic:
            - 현재 라인에서 숫자 패턴 탐색
            - 커서가 위치한 숫자 찾기
            - 커서 위치 자릿수 계산 (1의 자리, 10의 자리 등)
            - 해당 자릿수 단위로 증감
            - 부호 유지 (+, - 처리)

        Args:
            step: 증감 방향 (1: 증가, -1: 감소)
        """
        cursor = self.textCursor()
        pos = cursor.position()
        line_text = cursor.block().text()
        line_start = cursor.block().position()
        rel_pos = pos - line_start

        matches = list(self.NUMBER_PATTERN.finditer(line_text))
        target = None
        for m in matches:
            start, end = m.span()
            if start < rel_pos <= end:
                target = m
                break
        if not target:
            return

        original_str = target.group()
        start_index, end_index = target.span()
        force_plus = original_str.startswith("+")
        digits_str = original_str[1:] if original_str.startswith(('+', '-')) else original_str

        if original_str.startswith(('+', '-')):
            cursor_index_in_digits = rel_pos - start_index - 1
        else:
            cursor_index_in_digits = rel_pos - start_index

        cursor_index_left_digit = max(min(cursor_index_in_digits - 1, len(digits_str) - 1), 0)
        factor = 10 ** (len(digits_str) - 1 - cursor_index_left_digit)

        try:
            val = int(original_str)
        except ValueError:
            return

        val += step * factor
        new_str = str(val) if val >= 0 else str(val)
        if force_plus and val >= 0:
            new_str = f"+{val}"

        cursor.setPosition(start_index + line_start)
        cursor.setPosition(end_index + line_start, cursor.KeepAnchor)
        cursor.insertText(new_str)

        len_diff = len(new_str) - len(original_str)
        new_cursor_pos = pos + len_diff

        cursor.setPosition(new_cursor_pos)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()