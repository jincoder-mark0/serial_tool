"""
스마트 리스트 뷰 위젯 모듈

QListView를 기반으로 대량의 로그 데이터를 효율적으로 표시하고 관리하는
커스텀 위젯을 정의합니다. 검색, 하이라이트, 플레이스홀더, 전체 텍스트 추출 기능을 지원합니다.
"""
import re
from typing import List, Any, Optional

from PyQt5.QtWidgets import QListView, QAbstractItemView, QStyle, QStyledItemDelegate
from PyQt5.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QVariant, QSize, QRegExp, pyqtSlot
)
from PyQt5.QtGui import (
    QColor, QTextDocument, QAbstractTextDocumentLayout, QTextCharFormat, QPainter
)

from app_constants import DEFAULT_LOG_MAX_LINES, TRIM_CHUNK_RATIO, LOG_COLOR_TIMESTAMP

class QSmartListView(QListView):
    """
    QListView를 확장하여 로그 뷰어 기능을 캡슐화한 클래스입니다.
    설정값(Newline 등)은 외부에서 주입받습니다.
    검색 탐색(Next/Prev)
    """
    def __init__(self, parent=None):
        """
        QSmartListView를 초기화합니다.

        Args:
            parent (QWidget, optional): 부모 위젯.
        """
        super().__init__(parent)

        # 모델 및 델리게이트 설정
        self.log_model = LogModel()
        self.setModel(self.log_model)

        self.delegate = LogDelegate(self)
        self.setItemDelegate(self.delegate)

        # 뷰 설정
        self.setProperty("class", "fixed-font") # 고정폭 폰트
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setUniformItemSizes(False) # 행 높이가 다를 수 있음
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel) # 부드러운 스크롤

        # 설정 관리자
        self._newline_char = "\n"
        self._placeholder_text = ""

        self.setObjectName("SmartListView")

    def set_newline_char(self, char: str) -> None:
        """
        줄바꿈 문자를 설정합니다.

        Args:
            char (str): 사용할 줄바꿈 문자 (예: '\n', '\r\n').
        """
        self._newline_char = char

    def setPlaceholderText(self, text: str) -> None:
        """
        데이터가 없을 때 표시할 안내 문구(Placeholder)를 설정합니다.

        Args:
            text (str): 표시할 텍스트.
        """
        self._placeholder_text = text
        self.viewport().update()

    def append(self, text: str, timestamp: Optional[str] = None) -> None:
        """
        로그 한 줄을 추가합니다.

        Args:
            text (str): 로그 내용.
            timestamp (Optional[str]): 타임스탬프 문자열.
        """
        # 1. Newline 처리 (주입받은 설정 사용)
        if self._newline_char != "\n":
            text = text.replace(self._newline_char, "\n")

        # 2. 타임스탬프 결합
        if timestamp:
            text = f'<span style="color:{LOG_COLOR_TIMESTAMP};">{timestamp}</span> {text}'

        # 3. 모델에 추가 (단일 항목이지만 리스트로 전달)
        # Note: 대량 추가 시에는 외부에서 리스트로 모아서 append_batch를 호출하는 메서드를 추가하는 것이 좋음
        self.log_model.add_logs([text])

        # 4. 자동 스크롤 (맨 아래에 있을 때만)
        if self.is_at_bottom():
            self.scrollToBottom()

    def append_batch(self, lines: List[str]) -> None:
        """
        여러 줄의 로그를 한 번에 추가합니다.

        Args:
            lines (List[str]): 추가할 로그 리스트.
        """
        self.log_model.add_logs(lines)
        if self.is_at_bottom():
            self.scrollToBottom()

    @pyqtSlot(str)
    def set_search_pattern(self, text: str) -> None:
        """
        검색어를 설정합니다. 정규식으로 컴파일하여 델리게이트에 전달합니다.

        Args:
            text (str): 검색할 문자열 (정규식 지원).
        """
        if not text:
            self.delegate.set_search_pattern(None)
        else:
            # 1. 정규식으로 시도
            pattern = QRegExp(text, Qt.CaseInsensitive)

            # 2. 유효하지 않은 정규식(예: '[')이라면 일반 텍스트로 검색 (Escape 처리)
            if not pattern.isValid():
                pattern = QRegExp(QRegExp.escape(text), Qt.CaseInsensitive)

            self.delegate.set_search_pattern(pattern)

        self.viewport().update() # 화면 갱신

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수.
        """
        self.log_model.set_max_lines(max_lines)

    def clear(self) -> None:
        """로그 뷰의 내용을 모두 지웁니다."""
        self.log_model.clear()

    def is_at_bottom(self) -> bool:
        """
        스크롤바가 맨 아래에 있는지 확인합니다.

        Returns:
            bool: 맨 아래에 있으면 True.
        """
        sb = self.verticalScrollBar()
        # 오차 범위를 두어 판별
        return sb.value() >= (sb.maximum() - 10)

    def find_next(self, text: str) -> bool:
        """
        다음 검색 결과를 찾아 해당 행으로 이동합니다. (Wrap around 지원)

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text: return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
        start_row = current_row + 1 if current_row >= 0 else 0
        total_rows = self.log_model.rowCount()

        # 1. 현재 위치 다음부터 끝까지 검색
        for row in range(start_row, total_rows):
            if self._match_row(row, pattern):
                self._select_and_scroll(row)
                return True

        # 2. 처음부터 현재 위치까지 검색 (Wrap around)
        for row in range(0, start_row):
            if self._match_row(row, pattern):
                self._select_and_scroll(row)
                return True

        return False

    def find_prev(self, text: str) -> bool:
        """
        이전 검색 결과를 찾아 해당 행으로 이동합니다. (Wrap around 지원)

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text: return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
        total_rows = self.log_model.rowCount()
        start_row = current_row - 1 if current_row >= 0 else total_rows - 1

        # 1. 현재 위치 이전부터 처음까지 역순 검색
        for row in range(start_row, -1, -1):
            if self._match_row(row, pattern):
                self._select_and_scroll(row)
                return True

        # 2. 끝에서부터 현재 위치까지 역순 검색 (Wrap around)
        for row in range(total_rows - 1, start_row, -1):
            if self._match_row(row, pattern):
                self._select_and_scroll(row)
                return True

        return False

    def get_all_text(self) -> str:
        """
        모델에 있는 모든 로그 데이터를 가져와 하나의 문자열로 반환합니다.
        HTML 태그는 제거됩니다.

        Returns:
            str: 개행 문자로 구분된 전체 로그 텍스트.
        """
        # 모델에서 태그가 제거된 리스트를 가져옴
        lines = self.log_model.get_plain_text_logs()
        # 줄바꿈으로 연결하여 반환
        return "\n".join(lines)

    def _create_pattern(self, text: str) -> QRegExp:
        """
        검색 문자열을 QRegExp 객체로 변환합니다.

        Args:
            text (str): 검색 문자열.

        Returns:
            QRegExp: 컴파일된 정규식 객체.
        """
        # 대소문자 구분 없음
        pattern = QRegExp(text, Qt.CaseInsensitive)

        # 유효하지 않은 정규식 패턴(예: '[')인 경우 이스케이프 처리하여 일반 텍스트로 검색
        if not pattern.isValid():
            pattern = QRegExp(QRegExp.escape(text), Qt.CaseInsensitive)
        return pattern

    def _match_row(self, row: int, pattern: QRegExp) -> bool:
        """
        특정 행의 데이터가 검색 패턴과 일치하는지 확인합니다.

        Args:
            row (int): 행 인덱스.
            pattern (QRegExp): 검색 패턴.

        Returns:
            bool: 일치하면 True.
        """
        # 모델의 원본 데이터(HTML 포함)에서 검색
        # 성능을 위해 stripHtml을 하지 않고 원본에서 검색합니다.
        # (필요 시 정규식으로 태그 제외 가능)
        text = self.log_model.data(self.log_model.index(row, 0))
        return pattern.indexIn(text) != -1

    def _select_and_scroll(self, row: int) -> None:
        """
        특정 행을 선택하고 화면 중앙으로 스크롤합니다.

        Args:
            row (int): 이동할 행 인덱스.
        """
        """해당 행을 선택하고 화면 중앙으로 스크롤"""
        index = self.log_model.index(row, 0)
        self.setCurrentIndex(index)
        self.scrollTo(index, QAbstractItemView.PositionAtCenter)

    def setReadOnly(self, val: bool) -> None:
        """
        뷰의 읽기 전용 상태를 설정합니다.

        Args:
            val (bool): True일 경우 편집 트리거를 비활성화합니다.
                       (로그 뷰어 특성상 텍스트 선택 및 복사는 여전히 가능합니다)
        """
        if val:
            # 어떠한 동작으로도 편집 모드로 진입하지 않도록 설정
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            # 기본 편집 트리거 복원 (더블 클릭, 키 입력 등)
            self.setEditTriggers(QAbstractItemView.DoubleClicked |
                                 QAbstractItemView.EditKeyPressed |
                                 QAbstractItemView.SelectedClicked)
            # self.setSelectionMode(QAbstractItemView.ExtendedSelection) # 선택 가능 복원

        # 스타일시트 갱신을 위해 속성 설정 및 폴리싱
        self.setProperty("readOnly", val)
        self.style().unpolish(self)
        self.style().polish(self)

    def isReadOnly(self) -> bool:
        """
        뷰가 현재 읽기 전용 상태인지 확인합니다.

        Returns:
            bool: 읽기 전용이면 True.
        """
        return self.editTriggers() == QAbstractItemView.NoEditTriggers

    def paintEvent(self, event) -> None:
        """
        화면을 그립니다. 데이터가 없을 경우 플레이스홀더를 표시합니다.

        Args:
            event (QPaintEvent): 페인트 이벤트.
        """
        super().paintEvent(event)

        # 데이터가 없고 플레이스홀더 텍스트가 설정된 경우 그리기
        if self.model() and self.model().rowCount() == 0 and self._placeholder_text:
            painter = QPainter(self.viewport())
            painter.save()

            # 텍스트 색상 설정 (테마의 PlaceholderText 색상 사용, 실패 시 회색)
            text_color = self.palette().placeholderText().color()
            if not text_color.isValid():
                text_color = QColor(128, 128, 128)

            painter.setPen(text_color)

            # 화면 중앙에 텍스트 그리기
            rect = self.viewport().rect()
            painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, self._placeholder_text)

            painter.restore()

class LogModel(QAbstractListModel):
    """
    대량의 로그 데이터를 관리하는 데이터 모델 클래스입니다.

    QAbstractListModel을 상속받아 데이터를 리스트 형태로 관리하며,
    최대 라인 수 제한(Trim) 로직을 포함합니다.
    """
    def __init__(self, max_lines: int = DEFAULT_LOG_MAX_LINES):
        """
        LogModel을 초기화합니다.

        Args:
            max_lines (int): 유지할 최대 로그 라인 수.
        """
        super().__init__()
        self._data: List[str] = []
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        데이터의 행(row) 개수를 반환합니다.

        Args:
            parent (QModelIndex): 부모 인덱스.

        Returns:
            int: 데이터 개수.
        """
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """
        지정된 인덱스와 역할에 해당하는 데이터를 반환합니다.

        Args:
            index (QModelIndex): 데이터 인덱스.
            role (int): 데이터 역할 (DisplayRole 등).

        Returns:
            Any: 요청된 데이터. 유효하지 않은 경우 QVariant.
        """
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return QVariant()

        if role == Qt.DisplayRole:
            return self._data[index.row()]

        return QVariant()

    def add_logs(self, lines: List[str]) -> None:
        """
        로그 데이터를 배치로 추가하고 필요시 오래된 로그를 삭제(Trim)합니다.

        Args:
            lines (List[str]): 추가할 로그 문자열 리스트.
        """
        if not lines:
            return

        begin_row = len(self._data)
        end_row = begin_row + len(lines) - 1

        self.beginInsertRows(QModelIndex(), begin_row, end_row)
        self._data.extend(lines)
        self.endInsertRows()

        # 최대 라인 수 초과 시 Trim 수행
        if len(self._data) > self._max_lines:
            remove_count = self._trim_size
            # 여유분 계산: 너무 많이 지우지 않도록 안전장치
            if len(self._data) - remove_count < self._max_lines * 0.8:
                 remove_count = len(self._data) - int(self._max_lines * 0.9)

            if remove_count > 0:
                self.beginRemoveRows(QModelIndex(), 0, remove_count - 1)
                del self._data[:remove_count]
                self.endRemoveRows()

    def clear(self) -> None:
        """모든 데이터를 삭제합니다."""
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수.
        """
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)

    def get_plain_text_logs(self) -> List[str]:
        """
        저장된 모든 로그에서 HTML 태그를 제거하여 리스트로 반환합니다.

        Returns:
            List[str]: 태그가 제거된 로그 문자열 리스트.
        """
        # HTML 태그 제거용 정규식 컴파일 (<...>)
        cleaner = re.compile('<.*?>')

        plain_logs = []
        for line in self._data:
            # 정규식으로 태그 제거
            clean_text = re.sub(cleaner, '', line)
            plain_logs.append(clean_text)

        return plain_logs

class LogDelegate(QStyledItemDelegate):
    """
    로그 아이템의 렌더링을 담당하는 델리게이트 클래스입니다.

    HTML 텍스트 렌더링 및 검색어 하이라이트 기능을 수행합니다.
    """
    def __init__(self, parent=None):
        """
        LogDelegate를 초기화합니다.

        Args:
            parent (QObject, optional): 부모 객체.
        """
        super().__init__(parent)
        self.doc = QTextDocument()
        self.search_pattern: Optional[QRegExp] = None

        # 검색 결과 하이라이트 포맷 (노란색 배경)
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("yellow"))
        self.highlight_format.setForeground(QColor("black"))

    def set_search_pattern(self, pattern: Optional[QRegExp]) -> None:
        """
        검색 패턴을 설정합니다.

        Args:
            pattern (Optional[QRegExp]): 검색할 정규식 객체. None이면 해제.
        """
        self.search_pattern = pattern

    def paint(self, painter: QPainter, option: 'QStyleOptionViewItem', index: QModelIndex) -> None:
        """
        아이템을 화면에 그립니다.

        Args:
            painter (QPainter): 페인터 객체.
            option (QStyleOptionViewItem): 스타일 옵션.
            index (QModelIndex): 모델 인덱스.
        """
        painter.save()

        # 선택된 항목 배경 그리기
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # 데이터 설정
        text = index.data(Qt.DisplayRole)
        self.doc.setDefaultFont(option.font)
        self.doc.setHtml(text)

        # [핵심] 정규식 객체를 사용하여 검색 및 하이라이트
        if self.search_pattern and not self.search_pattern.isEmpty():
            cursor = self.doc.find(self.search_pattern)
            while not cursor.isNull():
                cursor.mergeCharFormat(self.highlight_format)
                cursor = self.doc.find(self.search_pattern, cursor)

        # 그리기 위치 조정
        painter.translate(option.rect.left(), option.rect.top())

        # 클리핑 설정 (셀 영역 밖으로 나가지 않도록)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        # 선택된 텍스트의 글자색 처리 (QTextDocument는 기본적으로 HTML 색상 우선)
        # 필요하다면 ctx.palette를 조작할 수 있음

        self.doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option: 'QStyleOptionViewItem', index: QModelIndex) -> QSize:
        """
        아이템의 크기 힌트를 반환합니다.

        Args:
            option (QStyleOptionViewItem): 스타일 옵션.
            index (QModelIndex): 모델 인덱스.

        Returns:
            QSize: 아이템의 크기.
        """
        text = index.data(Qt.DisplayRole)
        self.doc.setHtml(text)
        self.doc.setDefaultFont(option.font)

        # 너비는 리스트뷰 너비에 맞추고 높이만 계산
        self.doc.setTextWidth(option.rect.width())
        return QSize(int(self.doc.idealWidth()), int(self.doc.size().height()))
