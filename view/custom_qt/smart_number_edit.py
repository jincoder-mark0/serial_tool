"""
스마트 숫자 에디터 모듈

커서 위치 기반 숫자 증감 및 Alt 코드 입력을 지원하는 텍스트 에디터입니다.

## WHY
* 매크로 편집 시 숫자 값 빠른 조정 필요
* Alt 코드로 제어 문자 입력 지원
* 제어 문자 시각화로 디버깅 편의성 향상
* 자릿수 단위 증감으로 정밀한 조정

## WHAT
* QPlainTextEdit 기반 커스텀 위젯
* Ctrl+Up/Down으로 숫자 증감
* 커서 위치 자릿수 단위 증감
* Alt+Numpad로 제어 문자 입력
* 제어 문자 배경색 하이라이트
* 10진수 패턴 매칭

## HOW
* 정규식으로 숫자 패턴 탐지
* EventFilter로 Alt 키 입력 처리
* QTextCursor로 커서 위치 기반 편집
* ExtraSelection으로 제어 문자 하이라이트
* 자릿수 계산으로 증감 단위 결정
"""
import sys
import re
from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent, QTextCursor, QTextCharFormat, QColor


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
                    print("[Debug] Alt pressed")
                    return False

                # Alt + Numpad 숫자 입력
                is_numpad_digit = (Qt.Key_0 <= key <= Qt.Key_9) and (mods & Qt.KeypadModifier)
                if self._alt_pressed and is_numpad_digit:
                    number = key - Qt.Key_0
                    self._alt_input_buffer += str(number)
                    print(f"[Debug] Alt+Numpad pressed: {number}, buffer: '{self._alt_input_buffer}'")
                    return True  # 이벤트 소비 → 중복 방지

                # Alt 상태에서 다른 키 입력 시 버퍼 초기화
                if self._alt_pressed and key != Qt.Key_Alt:
                    print(f"[Debug] Alt pressed but non-Numpad key: {key}, buffer cleared")
                    self._alt_input_buffer = ""
                    return True  # 이벤트 소비

            elif event.type() == QEvent.KeyRelease:
                key_event = event
                if key_event.key() == Qt.Key_Alt and self._alt_pressed:
                    self._alt_pressed = False
                    print(f"[Debug] Alt released, buffer: '{self._alt_input_buffer}'")
                    if self._alt_input_buffer:
                        try:
                            code = int(self._alt_input_buffer)
                            if 0 <= code <= 255:
                                control_char = chr(code)
                                self._alt_handling_in_progress = True
                                self._insert_char(control_char)
                                self._alt_handling_in_progress = False
                                print(f"[Alt Code Inserted] Code: {code}, Char: '{control_char}'")
                        except ValueError as e:
                            print(f"[Error] Invalid Alt buffer: {self._alt_input_buffer}, {e}")
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
            print(f"[Debug] KeyPress ignored due to Alt: {event.key()}, buffer: '{self._alt_input_buffer}'")
            return

        # 디버깅 로그
        print(f"[KeyPress Received] Key: {event.key()} ({hex(event.key())}), Text: '{event.text()}', Modifiers: {event.modifiers()}")

        mods = event.modifiers()
        key = event.key()

        if mods == Qt.ControlModifier:
            if key == Qt.Key_Up:
                print("[Debug] Ctrl+Up detected, increment number")
                self.increment_number(1)
                return
            elif key == Qt.Key_Down:
                print("[Debug] Ctrl+Down detected, decrement number")
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

        print(f"[Debug] increment_number called, cursor pos: {pos}, line_text: '{line_text}'")

        matches = list(self.NUMBER_PATTERN.finditer(line_text))
        target = None
        for m in matches:
            start, end = m.span()
            if start < rel_pos <= end:
                target = m
                break
        if not target:
            print("[Debug] No number found at cursor")
            return

        original_str = target.group()
        start_idx, end_idx = target.span()
        force_plus = original_str.startswith("+")
        digits_str = original_str[1:] if original_str.startswith(('+', '-')) else original_str

        if original_str.startswith(('+', '-')):
            cursor_idx_in_digits = rel_pos - start_idx - 1
        else:
            cursor_idx_in_digits = rel_pos - start_idx

        cursor_idx_left_digit = max(min(cursor_idx_in_digits - 1, len(digits_str) - 1), 0)
        factor = 10 ** (len(digits_str) - 1 - cursor_idx_left_digit)

        try:
            val = int(original_str)
        except ValueError:
            print(f"[Error] Cannot convert '{original_str}' to int")
            return

        val += step * factor
        new_str = str(val) if val >= 0 else str(val)
        if force_plus and val >= 0:
            new_str = f"+{val}"

        print(f"[Debug] Number change: {original_str} -> {new_str}, factor: {factor}, step: {step}")

        cursor.setPosition(start_idx + line_start)
        cursor.setPosition(end_idx + line_start, cursor.KeepAnchor)
        cursor.insertText(new_str)

        len_diff = len(new_str) - len(original_str)
        new_cursor_pos = pos + len_diff

        cursor.setPosition(new_cursor_pos)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


# ---------------- MainWindow ----------------
class MainWindow(QWidget):
    """테스트용 메인 윈도우"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("자리수 기반 숫자 증감 에디터 (Alt 코드 디버깅)")
        self.setGeometry(100, 100, 700, 450)
        layout = QVBoxLayout()
        self.editor = SmartNumberEdit()

        self.editor.setPlainText(
            "Alt 코드 테스트:\n"
            "Alt + 0,1 입력: \n"
            "Alt + 0,4,9 입력: \n"
            "Ctrl+↑/↓로 숫자 증감 테스트: +12345\n"
            "제어 문자 테스트: \x01안녕18|3하세요\n"
        )

        layout.addWidget(self.editor)
        self.setLayout(layout)


# ---------------- 실행 ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
