"""
스마트 텍스트 에디터 모듈

라인 번호가 표시되고 현재 줄을 강조하는 향상된 텍스트 에디터입니다.

## WHY
* 로그 뷰어 및 스크립트 편집 시 가독성 향상
* 다중 라인 데이터의 위치 파악 용이성 제공
* 코드나 데이터 구조를 명확하게 식별할 필요성

## WHAT
* QPlainTextEdit 기반 커스텀 위젯
* 좌측 라인 번호 표시 영역 (LineNumberArea) 제공
* 현재 커서가 위치한 라인 배경색 하이라이팅
* QSS 프로퍼티를 통한 동적 스타일링 지원

## HOW
* 별도의 QWidget(LineNumberArea)을 사이드바에 배치하여 페인팅 처리
* updateRequest 및 blockCountChanged 시그널을 통해 영역 너비와 내용을 동적으로 갱신
* QPainter를 사용하여 라인 번호를 직접 그림
"""
from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from PyQt5.QtCore import Qt, QRect, pyqtProperty, QSize
from PyQt5.QtGui import QPainter, QColor, QTextFormat, QPaintEvent, QResizeEvent


class LineNumberArea(QWidget):
    """
    라인 번호를 표시하는 사이드바 위젯입니다.
    QSmartTextEdit의 좌측에 부착되어 라인 번호를 그립니다.
    """

    def __init__(self, editor: 'QSmartTextEdit') -> None:
        """
        LineNumberArea 초기화

        Args:
            editor (QSmartTextEdit): 부모 에디터 인스턴스.
        """
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        """
        위젯의 권장 크기를 반환합니다.

        Returns:
            QSize: 권장 크기.
        """
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        그리기 이벤트 핸들러.
        실제 그리기 작업은 부모 에디터에 위임합니다.

        Args:
            event (QPaintEvent): 페인트 이벤트.
        """
        self.code_editor.line_number_area_paint_event(event)


class QSmartTextEdit(QPlainTextEdit):
    """
    라인 번호가 표시되는 스마트 텍스트 에디터 클래스입니다.

    QPlainTextEdit를 상속받아 좌측에 라인 번호 영역을 추가하고,
    현재 커서 위치의 라인을 강조하는 기능을 제공합니다.
    """

    def __init__(self, parent: QWidget = None) -> None:
        """
        QSmartTextEdit 초기화

        Args:
            parent (QWidget, optional): 부모 위젯.
        """
        super().__init__(parent)

        # 기본 색상 설정 (테마 적용 전 초기값)
        self._line_number_bg_color = QColor(53, 53, 53)
        self._line_number_color = QColor(128, 128, 128)
        self._current_line_color = QColor(60, 60, 60)

        # 라인 번호 영역 위젯 생성
        self.line_number_area = LineNumberArea(self)

        # 시그널 연결
        # 1. 블록(라인) 수 변경 시 너비 재계산
        self.blockCountChanged.connect(self.update_line_number_area_width)
        # 2. 업데이트 요청 시(스크롤 등) 라인 번호 영역 갱신
        self.updateRequest.connect(self.update_line_number_area)
        # 3. 커서 이동 시 현재 라인 하이라이트
        self.cursorPositionChanged.connect(self.highlight_current_line)

        # 초기 상태 설정
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    # ----------------------------------------------------------------------
    # Properties for QSS Styling (Q_PROPERTY)
    # ----------------------------------------------------------------------
    def get_line_number_bg_color(self) -> QColor:
        """라인 번호 영역 배경색 반환"""
        return self._line_number_bg_color

    def set_line_number_bg_color(self, color: QColor) -> None:
        """
        라인 번호 영역 배경색 설정

        Args:
            color (QColor): 설정할 배경색.
        """
        self._line_number_bg_color = QColor(color)
        self.line_number_area.update()

    def get_line_number_color(self) -> QColor:
        """라인 번호 텍스트 색상 반환"""
        return self._line_number_color

    def set_line_number_color(self, color: QColor) -> None:
        """
        라인 번호 텍스트 색상 설정

        Args:
            color (QColor): 설정할 텍스트 색상.
        """
        self._line_number_color = QColor(color)
        self.line_number_area.update()

    def get_current_line_color(self) -> QColor:
        """현재 라인 하이라이트 색상 반환"""
        return self._current_line_color

    def set_current_line_color(self, color: QColor) -> None:
        """
        현재 라인 하이라이트 색상 설정

        Args:
            color (QColor): 설정할 하이라이트 색상.
        """
        self._current_line_color = QColor(color)
        self.highlight_current_line()

    # QSS에서 접근 가능한 프로퍼티 정의
    lineNumberBackgroundColor = pyqtProperty(QColor, get_line_number_bg_color, set_line_number_bg_color)
    lineNumberColor = pyqtProperty(QColor, get_line_number_color, set_line_number_color)
    currentLineColor = pyqtProperty(QColor, get_current_line_color, set_current_line_color)

    # ----------------------------------------------------------------------
    # Line Number Area Logic
    # ----------------------------------------------------------------------
    def line_number_area_width(self) -> int:
        """
        라인 번호 영역의 필요한 너비를 계산합니다.

        Logic:
            - 현재 라인 수(blockCount)를 기준으로 자릿수 계산
            - 폰트 메트릭을 사용하여 숫자의 너비 계산
            - 좌우 여백 추가

        Returns:
            int: 라인 번호 영역의 너비 (픽셀).
        """
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        # 여백(8px) + 숫자 너비('9' 기준)
        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _: int) -> None:
        """
        라인 번호 영역의 너비를 업데이트합니다.
        블록 수가 변경될 때 호출됩니다.

        Args:
            _: 변경된 블록 수 (사용하지 않음).
        """
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        """
        스크롤이나 업데이트 요청 시 라인 번호 영역을 다시 그립니다.

        Args:
            rect (QRect): 업데이트가 필요한 영역.
            dy (int): 수직 스크롤 변화량.
        """
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        위젯 크기가 변경될 때 호출됩니다.
        라인 번호 영역의 지오메트리를 조정합니다.

        Args:
            event (QResizeEvent): 리사이즈 이벤트.
        """
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event: QPaintEvent) -> None:
        """
        라인 번호 영역을 실제로 그리는 메서드입니다.
        LineNumberArea의 paintEvent에서 호출됩니다.

        Logic:
            - 배경색 채우기
            - 현재 보이는 첫 번째 블록 찾기
            - 뷰포트 내의 모든 블록을 순회하며 번호 그리기
            - 우측 정렬로 숫자 표시

        Args:
            event (QPaintEvent): 페인트 이벤트.
        """
        painter = QPainter(self.line_number_area)

        # 배경색 그리기
        painter.fillRect(event.rect(), self._line_number_bg_color)

        # 현재 뷰포트에 보이는 첫 번째 블록 찾기
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()

        # 블록의 상단 위치 계산 (contentOffset 고려)
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # 뷰포트 높이 범위 내에 있는 블록들에 대해 번호 그리기
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self._line_number_color)

                # 텍스트 그리기 (우측 정렬)
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 4,  # 우측 여백 4px
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self) -> None:
        """
        현재 커서가 위치한 라인을 강조 표시합니다.

        Logic:
            - 읽기 전용 상태가 아닐 때만 수행
            - ExtraSelection을 생성하여 현재 라인에 배경색 적용
            - 전체 너비(FullWidthSelection)로 설정
        """
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            # 현재 라인 배경색 설정
            selection.format.setBackground(self._current_line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)

            # 커서 위치 설정
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()

            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)