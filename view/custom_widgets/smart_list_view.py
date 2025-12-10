from PyQt5.QtWidgets import QListView, QAbstractItemView, QStyle, QStyledItemDelegate
from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex, QVariant, QSize, QRegExp
from PyQt5.QtGui import QColor, QTextDocument, QAbstractTextDocumentLayout, QTextCharFormat

from typing import List, Any, Optional

from core.settings_manager import SettingsManager
from core.constants import DEFAULT_LOG_MAX_LINES, TRIM_CHUNK_RATIO, LOG_COLOR_TIMESTAMP

class QSmartListView(QListView):
    """
    QListView를 확장하여 로그 뷰어 기능을 캡슐화한 클래스입니다.
    설정값(Newline 등)은 외부에서 주입받습니다.
    """
    def __init__(self, parent=None):
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

    def set_newline_char(self, char: str) -> None:
        """줄바꿈 문자를 설정합니다 (외부 주입)."""
        self._newline_char = char

    def append_log(self, text: str, timestamp: Optional[str] = None):
        """
        로그를 추가합니다. 설정된 Newline 처리 및 타임스탬프 결합을 수행합니다.
        
        Args:
            text (str): 로그 내용.
            timestamp (str, optional): 타임스탬프.
        """
        # 1. Newline 처리 (주입받은 설정 사용)
        if self._newline_char != "\n":
            text = text.replace(self._newline_char, "\n")
            
        # 2. 타임스탬프 결합
        if timestamp:
            text = f'<span style="color:{LOG_COLOR_TIMESTAMP};">{timestamp}</span> {text}'
            
        # 3. 모델에 추가 (단일 항목이지만 리스트로 전달)
        # Note: 대량 추가 시에는 외부에서 리스트로 모아서 add_logs_batch를 호출하는 메서드를 추가하는 것이 좋음
        self.log_model.add_logs([text])
        
        # 4. 자동 스크롤 (맨 아래에 있을 때만)
        if self.is_at_bottom():
            self.scrollToBottom()

    def add_logs_batch(self, lines: List[str]):
        """배치 처리를 위한 메서드 (직접 호출용)"""
        # 여기서도 newline 처리 등을 할 수 있지만, 
        # 성능을 위해 호출자가 처리된 문자열을 보내는 구조가 나을 수 있음.
        # 현재 구조상 append_log 호출 전에 이미 가공된 문자열이므로 바로 전달.
        self.log_model.add_logs(lines)
        if self.is_at_bottom():
            self.scrollToBottom()

    def set_search_pattern(self, text: str):
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

    def set_max_lines(self, max_lines: int):
        self.log_model.set_max_lines(max_lines)

    def clear(self):
        self.log_model.clear()

    def is_at_bottom(self) -> bool:
        """스크롤바가 맨 아래에 있는지 확인합니다."""
        sb = self.verticalScrollBar()
        return sb.value() >= (sb.maximum() - 10)

class LogModel(QAbstractListModel):
    """
    대량의 로그 데이터를 관리하는 모델입니다.
    데이터 추가 및 최대 라인 수 제한(Trim)을 담당합니다.
    """
    def __init__(self, max_lines: int = DEFAULT_LOG_MAX_LINES):
        super().__init__()
        self._data: List[str] = []
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return QVariant()
        
        if role == Qt.DisplayRole:
            return self._data[index.row()]
        
        return QVariant()

    def add_logs(self, lines: List[str]) -> None:
        """로그 데이터를 배치로 추가하고 필요시 Trim을 수행합니다."""
        if not lines:
            return

        begin_row = len(self._data)
        end_row = begin_row + len(lines) - 1
        
        self.beginInsertRows(QModelIndex(), begin_row, end_row)
        self._data.extend(lines)
        self.endInsertRows()

        # Trim 로직
        if len(self._data) > self._max_lines:
            remove_count = self._trim_size
            if len(self._data) - remove_count < self._max_lines * 0.8:
                 remove_count = len(self._data) - int(self._max_lines * 0.9)

            if remove_count > 0:
                self.beginRemoveRows(QModelIndex(), 0, remove_count - 1)
                del self._data[:remove_count]
                self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def set_max_lines(self, max_lines: int) -> None:
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)


class LogDelegate(QStyledItemDelegate):
    """
    HTML 렌더링 및 검색어(RegExp) 하이라이트를 담당하는 델리게이트
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = QTextDocument()
        self.search_pattern: Optional[QRegExp] = None # QRegExp 객체 저장
        
        # 하이라이트 포맷
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("yellow"))
        self.highlight_format.setForeground(QColor("black"))

    def set_search_pattern(self, pattern: Optional[QRegExp]):
        """검색 패턴(QRegExp)을 설정합니다."""
        self.search_pattern = pattern

    def paint(self, painter, option, index):
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

    def sizeHint(self, option, index):
        text = index.data(Qt.DisplayRole)
        self.doc.setHtml(text)
        self.doc.setDefaultFont(option.font)

        # 너비는 리스트뷰 너비에 맞추고 높이만 계산
        self.doc.setTextWidth(option.rect.width())
        return QSize(int(self.doc.idealWidth()), int(self.doc.size().height()))
