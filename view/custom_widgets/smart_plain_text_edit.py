"""
QSmartTextEdit - 라인 번호가 표시되는 스마트 텍스트 에디터
"""
from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QTextEdit, QHBoxLayout
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QTextFormat, QPaintEvent, QResizeEvent


class LineNumberArea(QWidget):
    """라인 번호 표시 영역"""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return self.code_editor.line_number_area_width()

    def paintEvent(self, event: QPaintEvent):
        self.code_editor.line_number_area_paint_event(event)


class QSmartTextEdit(QPlainTextEdit):
    """
    라인 번호가 표시되는 스마트 텍스트 에디터
    여러 줄 입력을 지원하며, 왼쪽에 라인 번호를 표시합니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 라인 번호 영역 생성
        self.line_number_area = LineNumberArea(self)

        # 시그널 연결
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        # 초기 설정
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        """라인 번호 영역의 너비를 계산합니다."""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        # 여백 + 숫자 너비
        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        """라인 번호 영역의 너비를 업데이트합니다."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        """스크롤 시 라인 번호 영역을 업데이트합니다."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event: QResizeEvent):
        """위젯 크기 변경 시 라인 번호 영역 크기를 조정합니다."""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event: QPaintEvent):
        """라인 번호를 그립니다."""
        painter = QPainter(self.line_number_area)

        # 배경색 (테마에 따라 조정 가능)
        painter.fillRect(event.rect(), QColor(53, 53, 53))  # 다크 테마 기본

        # 현재 보이는 블록 찾기
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # 라인 번호 그리기
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(128, 128, 128))  # 회색
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
        """현재 커서가 있는 라인을 하이라이트합니다."""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            # 현재 라인 배경색 (약간 밝게)
            line_color = QColor(60, 60, 60)  # 다크 테마 기본
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)
