"""
스마트 숫자 에디터 모듈

커서 위치 기반 숫자 증감 및 Alt 코드 입력을 지원하는 텍스트 에디터입니다.

## WHY
* 매크로 편집 시 값을 빠르고 정밀하게 조정할 필요성
* 제어 문자(Non-printable char) 입력 및 시각화 지원

## WHAT
* QPlainTextEdit 기반 커스텀 위젯
* 방향키(Up/Down)를 이용한 커서 위치별 숫자 증감 (Smart Increment)
* Alt + Numpad 조합을 통한 아스키/제어 문자 입력
* 제어 문자 배경색 하이라이팅

## HOW
* EventFilter를 통한 키 입력 가로채기 및 상태 머신 구현
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
    커서 위치 기반 숫자 증감 기능을 제공하는 텍스트 에디터입니다.

    Alt 코드 입력 및 제어 문자 배경색 표시를 지원합니다.
    """

    # 숫자(부호 포함) 매칭 정규식
    NUMBER_PATTERN = re.compile(r'([+-]?\d+)')
    # 제어 문자 하이라이트 배경색 (옅은 붉은색)
    CONTROL_BG_COLOR = QColor(255, 200, 200, 150)

    def __init__(self, parent=None) -> None:
        """
        SmartNumberEdit를 초기화합니다.

        Args:
            parent (QWidget, optional): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # Alt 입력 상태 관리 변수
        self._alt_pressed = False
        self._alt_input_buffer = ""
        self._alt_handling_in_progress = False

        # 이벤트 필터 설치 및 시그널 연결
        self.installEventFilter(self)
        self.document().contentsChanged.connect(self._update_control_char_highlight)

    # -------------------------------------------------------------------------
    # Alt 코드 입력 처리 (Event Filter)
    # -------------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        """
        키보드 이벤트를 가로채어 Alt 코드 입력을 처리합니다.

        Logic:
            1. KeyPress:
               - Alt 키가 눌리면 상태 플래그 설정 및 버퍼 초기화
               - Alt가 눌린 상태에서 Numpad 숫자가 입력되면 버퍼에 누적
               - 다른 키가 입력되면 버퍼 초기화
            2. KeyRelease:
               - Alt 키가 떼어지면 누적된 버퍼를 확인
               - 유효한 ASCII 코드(0~255)라면 해당 문자로 변환하여 삽입
            3. 중복 입력 방지를 위해 처리된 이벤트는 True를 반환하여 소비

        Args:
            obj (QObject): 이벤트 발생 객체.
            event (QEvent): 발생한 이벤트.

        Returns:
            bool: 이벤트를 필터링(소비)했으면 True, 아니면 False.
        """
        if obj is self:
            if event.type() == QEvent.KeyPress:
                key_event = event
                key = key_event.key()
                mods = key_event.modifiers()

                # Alt 눌림 감지
                if key == Qt.Key_Alt:
                    self._alt_pressed = True
                    self._alt_input_buffer = ""
                    return False  # 기본 동작 허용 (메뉴 단축키 등 방해 금지)

                # Alt + Numpad 숫자 입력 감지
                is_numpad_digit = (Qt.Key_0 <= key <= Qt.Key_9) and (mods & Qt.KeypadModifier)
                if self._alt_pressed and is_numpad_digit:
                    number = key - Qt.Key_0
                    self._alt_input_buffer += str(number)
                    return True  # 이벤트 소비 (에디터에 숫자 입력 방지)

                # Alt 상태에서 다른 키 입력 시 버퍼 초기화 (Alt 입력 취소)
                if self._alt_pressed and key != Qt.Key_Alt:
                    self._alt_input_buffer = ""
                    # Alt 조합 단축키일 수 있으므로 이벤트 소비하지 않음
                    return False

            elif event.type() == QEvent.KeyRelease:
                key_event = event
                # Alt 키 릴리즈 시 입력 처리
                if key_event.key() == Qt.Key_Alt and self._alt_pressed:
                    self._alt_pressed = False
                    if self._alt_input_buffer:
                        try:
                            code = int(self._alt_input_buffer)
                            if 0 <= code <= 255:
                                control_char = chr(code)
                                # 재귀 호출 방지 플래그 설정
                                self._alt_handling_in_progress = True
                                self._insert_char(control_char)
                                self._alt_handling_in_progress = False
                        except ValueError:
                            pass
                        finally:
                            self._alt_input_buffer = ""
                    # Alt 릴리즈 이벤트는 소비하지 않음 (포커스 문제 방지)
                    return False

        return super().eventFilter(obj, event)

    # -------------------------------------------------------------------------
    # 스마트 증감 처리 (KeyPress Event)
    # -------------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        키 입력 이벤트를 처리합니다.

        Logic:
            - Alt 코드 입력 중이면 일반 키 입력 무시
            - Ctrl + Up: 숫자 증가 (increment_number(1))
            - Ctrl + Down: 숫자 감소 (increment_number(-1))
            - 그 외: 부모 클래스의 기본 동작 수행

        Args:
            event (QKeyEvent): 키보드 입력 이벤트.
        """
        # Alt 입력 처리 중 간섭 방지
        if self._alt_pressed or self._alt_handling_in_progress:
            return

        mods = event.modifiers()
        key = event.key()

        # Ctrl + 방향키 조합 처리
        if mods == Qt.ControlModifier:
            if key == Qt.Key_Up:
                self.increment_number(1)
                return
            elif key == Qt.Key_Down:
                self.increment_number(-1)
                return

        super().keyPressEvent(event)

    # -------------------------------------------------------------------------
    # 헬퍼 메서드
    # -------------------------------------------------------------------------
    def _insert_char(self, char: str) -> None:
        """
        현재 커서 위치에 문자를 삽입합니다.

        Args:
            char (str): 삽입할 문자.
        """
        cursor = self.textCursor()
        cursor.insertText(char)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _get_control_char_format(self) -> QTextCharFormat:
        """
        제어 문자 하이라이트용 포맷을 반환합니다.

        Returns:
            QTextCharFormat: 배경색이 설정된 텍스트 포맷.
        """
        fmt = QTextCharFormat()
        fmt.setBackground(self.CONTROL_BG_COLOR)
        return fmt

    def _update_control_char_highlight(self) -> None:
        """
        문서 내의 제어 문자를 찾아 하이라이트합니다.

        Logic:
            - 문서 전체 내용을 가져옴
            - 정규식을 사용하여 제어 문자(ASCII 0x01 ~ 0x1F) 탐색
            - 발견된 위치에 ExtraSelection 적용하여 배경색 변경
        """
        document = self.document()
        highlight_format = self._get_control_char_format()
        selections = []

        text = self.toPlainText()
        # 제어 문자 정규식 (Tab, Newline 제외)
        control_char_regex = re.compile(r'[\x01-\x08\x0B\x0C\x0E-\x1F]')

        for match in control_char_regex.finditer(text):
            start, end = match.span()
            selection = QTextEdit.ExtraSelection()
            selection.format = highlight_format
            selection.cursor = QTextCursor(document)
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.KeepAnchor)
            selections.append(selection)

        self.setExtraSelections(selections)

    def increment_number(self, step: int) -> None:
        """
        커서 위치의 숫자를 자릿수 단위로 증감합니다.

        Logic:
            1. 현재 커서가 위치한 라인의 텍스트를 가져옵니다.
            2. 정규식을 사용하여 라인 내의 모든 숫자(부호 포함) 패턴을 찾습니다.
            3. 현재 커서 위치가 어떤 숫자 범위 내에 있는지 판별합니다.
            4. 커서 위치를 기준으로 조작할 자릿수(1의 자리, 10의 자리 등)를 계산합니다.
            5. 해당 자릿수만큼 숫자를 더하거나 뺍니다.
            6. 변경된 숫자로 텍스트를 교체하고 커서 위치를 적절히 복원합니다.

        Args:
            step (int): 증감 방향 (1: 증가, -1: 감소).
        """
        cursor = self.textCursor()
        pos = cursor.position()
        block = cursor.block()
        line_text = block.text()
        line_start = block.position()
        rel_pos = pos - line_start  # 라인 내 상대적 커서 위치

        # 라인 내 모든 숫자 찾기
        matches = list(self.NUMBER_PATTERN.finditer(line_text))
        target = None

        # 커서가 위치한 숫자 찾기
        for m in matches:
            start, end = m.span()
            # 커서가 숫자 바로 뒤에 있거나 내부에 있는 경우
            if start <= rel_pos <= end:
                target = m
                break

        if not target:
            return

        original_str = target.group()
        start_index, end_index = target.span()

        # 부호 처리 확인
        force_plus = original_str.startswith("+")

        # 순수 숫자 부분 추출 (부호 제외)
        if original_str.startswith(('+', '-')):
            digits_str = original_str[1:]
            # 커서가 부호 위에 있거나 부호 바로 뒤인 경우 처리 보정
            cursor_index_in_digits = rel_pos - start_index - 1
        else:
            digits_str = original_str
            cursor_index_in_digits = rel_pos - start_index

        # 자릿수 계산 (오른쪽 끝이 0번 인덱스, 1의 자리)
        # 커서가 숫자 범위를 벗어난 경우(맨 뒤 등) 클램핑
        cursor_index_in_digits = max(0, min(cursor_index_in_digits, len(digits_str)))

        # 자릿수 인덱스: 뒤에서부터 몇 번째인지 (0-based)
        # 예: "123"에서 커서가 '3' 뒤에 있으면(len=3) -> 1의 자리 조작
        digit_power = len(digits_str) - cursor_index_in_digits

        # 커서가 숫자 뒤에 있으면 1의 자리, 숫자 중간이면 해당 자릿수
        # 예: 1|23 -> 100의 자리 (power=2)
        if digit_power < 0: digit_power = 0

        factor = 10 ** digit_power

        try:
            val = int(original_str)
        except ValueError:
            return

        # 값 변경
        val += step * factor

        # 문자열로 변환 (부호 유지)
        new_str = str(val)
        if force_plus and val >= 0:
            new_str = f"+{val}"

        # 텍스트 교체 (Undo/Redo 지원을 위해 insertText 사용)
        cursor.setPosition(line_start + start_index)
        cursor.setPosition(line_start + end_index, QTextCursor.KeepAnchor)
        cursor.insertText(new_str)

        # 커서 위치 보정 (길이 변화 반영)
        len_diff = len(new_str) - len(original_str)
        new_cursor_pos = pos + len_diff

        cursor.setPosition(new_cursor_pos)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()