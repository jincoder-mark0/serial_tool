"""
스마트 텍스트 에디터 모듈

라인 번호가 표시되는 향상된 텍스트 에디터입니다.

## WHY
* 코드 편집 및 로그 뷰어에서 라인 번호 필요
* 현재 라인 하이라이트로 가독성 향상
* QSS로 테마 커스터마이징 지원
* 다중 라인 입력 편의성 제공

## WHAT
* QPlainTextEdit 기반 커스텀 위젯
* 왼쪽 라인 번호 영역
* 현재 라인 하이라이트
* QSS Property로 색상 커스터마이징
* 자동 너비 조정

## HOW
* LineNumberArea Widget으로 라인 번호 표시
* blockCountChanged Signal로 너비 자동 조정
* QPainter로 라인 번호 렌더링
* ExtraSelection으로 현재 라인 하이라이트
* pyqtProperty로 QSS 스타일링 지원
"""
from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from PyQt5.QtCore import Qt, QRect, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QTextFormat, QPaintEvent, QResizeEvent


class LineNumberArea(QWidget):
    """라인 번호 표시 영역"""

    def __init__(self, editor):
        """
        LineNumberArea 초기화

        Args:
            editor: 부모 QSmartTextEdit 인스턴스
        """
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        """권장 크기 반환"""
        return self.code_editor.line_number_area_width()

    def paintEvent(self, event: QPaintEvent):
        """라인 번호 그리기 이벤트"""
        self.code_editor.line_number_area_paint_event(event)


class QSmartTextEdit(QPlainTextEdit):
    """
    라인 번호가 표시되는 스마트 텍스트 에디터

    여러 줄 입력을 지원하며, 왼쪽에 라인 번호를 표시합니다.
    """

    def __init__(self, parent=None):
        """QSmartTextEdit 초기화"""
        super().__init__(parent)

        # 기본 색상 설정 (다크 테마 기준)
        self._line_number_bg_color = QColor(53, 53, 53)
        self._line_number_color = QColor(128, 128, 128)
        self._current_line_color = QColor(60, 60, 60)

        # 라인 번호 영역 생성
        self.line_number_area = LineNumberArea(self)

        # Signal 연결
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        # 초기 설정
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    # ----------------------------------------------------------------------
    # Properties for QSS Styling
    # ----------------------------------------------------------------------
    def get_line_number_bg_color(self):
        """라인 번호 영역 배경색 반환"""
        return self._line_number_bg_color

    def set_line_number_bg_color(self, color):
        """라인 번호 영역 배경색 설정"""
        self._line_number_bg_color = QColor(color)
        self.line_number_area.update()

    def get_line_number_color(self):
        """라인 번호 텍스트 색상 반환"""
        return self._line_number_color

    def set_line_number_color(self, color):
        """라인 번호 텍스트 색상 설정"""
        self._line_number_color = QColor(color)
        self.line_number_area.update()

    def get_current_line_color(self):
        """현재 라인 하이라이트 색상 반환"""
        return self._current_line_color

    def set_current_line_color(self, color):
        """현재 라인 하이라이트 색상 설정"""
        self._current_line_color = QColor(color)
        self.highlight_current_line()

    lineNumberBackgroundColor = pyqtProperty(QColor, get_line_number_bg_color, set_line_number_bg_color)
    lineNumberColor = pyqtProperty(QColor, get_line_number_color, set_line_number_color)
    currentLineColor = pyqtProperty(QColor, get_current_line_color, set_current_line_color)

    def line_number_area_width(self):
        """
        라인 번호 영역의 너비 계산

        Logic:
            - 최대 라인 번호의 자릿수 계산
            - 폰트 너비 기반으로 필요한 너비 계산
            - 여백 추가

        Returns:
            int: 라인 번호 영역 너비 (pixels)
        """
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        # 여백 + 숫자 너비
        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        """라인 번호 영역의 너비 업데이트"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        """
        스크롤 시 라인 번호 영역 업데이트

        Args:
            rect: 업데이트 영역
            dy: 수직 스크롤 오프셋
        """
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event: QResizeEvent):
        """위젯 크기 변경 시 라인 번호 영역 크기 조정"""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event: QPaintEvent):
        """
        라인 번호 렌더링

        Logic:
            - 배경색 채우기
            - 현재 보이는 블록 찾기
            - 각 블록의 라인 번호 그리기
            - 오른쪽 정렬로 숫자 표시
        """
        painter = QPainter(self.line_number_area)

        # 배경색
        painter.fillRect(event.rect(), self._line_number_bg_color)

        # 현재 보이는 블록 찾기
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # 라인 번호 그리기
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self._line_number_color)
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        """
        현재 커서가 있는 라인 하이라이트

        Logic:
            - 읽기 전용이 아닐 때만 하이라이트
            - ExtraSelection으로 배경색 설정
            - 전체 라인 너비로 하이라이트
        """
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            # 현재 라인 배경색
            selection.format.setBackground(self._current_line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)
