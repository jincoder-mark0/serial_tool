"""
스마트 리스트 뷰 위젯 모듈

QListView를 기반으로 대량의 로그 데이터를 효율적으로 표시하고 관리하는
커스텀 위젯을 정의 검색, 하이라이트, 플레이스홀더, 전체 텍스트 추출 기능을 지원
"""
import re
from typing import List, Any, Optional
from collections import deque
import datetime

from PyQt5.QtWidgets import QListView, QAbstractItemView, QStyle, QStyledItemDelegate
from PyQt5.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QVariant, QSize, QRegExp, pyqtSlot,
    QSortFilterProxyModel, QTimer, QDateTime
)
from PyQt5.QtGui import (
    QColor, QTextDocument, QAbstractTextDocumentLayout, QTextCharFormat, QPainter
)

from common.constants import DEFAULT_LOG_MAX_LINES, TRIM_CHUNK_RATIO
from common.dtos import ColorRule
from view.services.color_service import ColorService

class QSmartListView(QListView):
    """
    QListView를 확장하여 로그 뷰어 기능을 캡슐화한 클래스입니다.
    설정값(Newline 등)은 외부에서 주입받습니다.
    검색 탐색(Next/Prev) 및 필터링 기능을 제공
    """
    def __init__(self, parent=None):
        """
        QSmartListView를 초기화

        Args:
            parent (QWidget, optional): 부모 위젯.
        """
        super().__init__(parent)

        # 모델 설정
        self.log_model = LogModel()

        # 프록시 모델 설정 (필터링 지원)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.log_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # 전체 열에 대해 필터링 (로그는 0번 컬럼 하나임)
        self.proxy_model.setFilterKeyColumn(0)

        self.setModel(self.proxy_model)

        self.delegate = LogDelegate(self)
        self.setItemDelegate(self.delegate)

        # 뷰 설정
        self.setProperty("class", "fixed-font") # 고정폭 폰트
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # 성능 최적화: 모든 항목이 동일한 높이라고 가정
        # 대량 로그 처리 시 스크롤 성능 크게 향상
        self.setUniformItemSizes(True)

        # 스크롤 모드: PerPixel이 부드럽지만, 대량 데이터에서는 PerItem이 더 빠름
        # 필요시 ScrollPerItem으로 변경 가능
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # 설정 관리자
        self._newline_char = "\n"
        self._placeholder_text = ""
        self._filter_enabled = False
        self._current_pattern = None

        # 선택적 기능 (기본값 = 비활성화)
        self._hex_mode = False
        self._timestamp_enabled = False
        self._timestamp_timeout_ms = 100

        # ColorManager 의존성 제거 -> ColorRule 리스트 사용
        self._color_rules: List[ColorRule] = []

        self._last_data_time = None

        # HEX 모드 전환을 위한 원본 bytes 데이터 저장 (원형 버퍼로 메모리 최적화)
        self._original_data: deque = deque(maxlen=DEFAULT_LOG_MAX_LINES)

        # 필터링 디바운스 타이머 (입력 멈춤 감지)
        # 복잡한 정규식 입력 시 UI 프리징 방지
        self._filter_debounce_timer = QTimer()
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.setInterval(300) # 300ms 대기
        self._filter_debounce_timer.timeout.connect(self._execute_filter_update)

        self.setObjectName("SmartListView")

    def set_color_rules(self, rules: List[ColorRule]) -> None:
        """
        색상 규칙 설정 (Dependency Injection)

        Args:
            rules: 적용할 ColorRule 리스트
        """
        self._color_rules = rules
        # 규칙이 변경되면 기존 데이터 다시 렌더링
        self._refresh_all_data()

    def set_newline_char(self, char: str) -> None:
        """
        줄바꿈 문자를 설정

        Args:
            char (str): 사용할 줄바꿈 문자 (예: '\n', '\r\n').
        """
        self._newline_char = char

    def set_hex_mode_enabled(self, enabled: bool) -> None:
        """
        HEX 모드 활성화/비활성화를 설정
        모드 변경 시 모든 데이터를 다시 렌더링

        Args:
            enabled: HEX 모드 활성화 여부
        """
        if self._hex_mode == enabled:
            return

        self._hex_mode = enabled

        # 모든 데이터를 다시 렌더링
        self._refresh_all_data()

    def set_timestamp_enabled(self, enabled: bool, timeout_ms: int = 100) -> None:
        """
        타임스탬프 활성화

        Args:
            enabled: 타임스탬프 활성화 여부
            timeout_ms: Raw 모드에서 타임스탬프를 찍을 최소 간격 (ms)
        """
        self._timestamp_enabled = enabled
        self._timestamp_timeout_ms = timeout_ms

    def setPlaceholderText(self, text: str) -> None:
        """
        데이터가 없을 때 표시할 안내 문구(Placeholder)를 설정

        Args:
            text (str): 표시할 텍스트.
        """
        self._placeholder_text = text
        self.viewport().update()

    def append(self, text: str, line_formatter=None) -> None:
        """
        로그 데이터를 추가
        newline 문자로 분할하여 여러 줄로 추가하며, 각 라인에 formatter를 적용할 수 있습니다.

        Args:
            text (str): 로그 내용 (newline 포함 가능).
            line_formatter (callable, optional): 각 라인을 포맷팅할 함수.
                                                 함수 시그니처: formatter(line: str) -> str
        """
        # 1. Newline으로 분할
        if self._newline_char and self._newline_char in text:
            lines = text.split(self._newline_char)
            # 마지막이 빈 문자열이면 제거 (예: "abc\n" -> ["abc", ""])
            if lines and lines[-1] == "":
                lines.pop()
        else:
            # newline이 없으면 단일 라인
            lines = [text] if text else []

        # 2. 각 라인에 formatter 적용 (제공된 경우)
        if line_formatter:
            lines = [line_formatter(line) for line in lines]

        # 3. 모델에 batch 추가
        if lines:
            self.log_model.add_logs(lines)

            # 4. 자동 스크롤 (맨 아래에 있을 때만)
            if self.is_at_bottom():
                self.scrollToBottom()

    def append_bytes(self, data: bytes) -> None:
        """
        바이트 데이터를 추가

        Args:
            data (bytes): 추가할 바이트 데이터.
        """
        self._original_data.append(data)

        if self._hex_mode:
            text = " ".join([f"{b:02X}" for b in data]) + " "
        else:
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)

        should_add_timestamp = self._should_add_timestamp()

        # Formatter 생성
        # [Refactor] ColorService 사용
        formatter = self._create_line_formatter(should_add_timestamp)

        self.append(text, formatter)

    def _create_line_formatter(self, add_timestamp: bool):
        """
        라인 포맷터 함수를 생성

        Args:
            add_timestamp (bool): 타임스탬프 추가 여부.

        Returns:
            callable: 생성된 포맷터 함수.
        """
        def formatter(line: str) -> str:
            """
            라인 포맷터 함수

            Args:
                line (str): 포맷팅할 라인.

            Returns:
                str: 포맷팅된 라인.
            """
            formatted = line

            if add_timestamp:
                ts = datetime.datetime.now().strftime("[%H:%M:%S]")
                formatted = f"{ts} {formatted}"

            # [Refactor] ColorService를 사용하여 규칙 적용 (Stateless)
            if self._color_rules:
                formatted = ColorService.apply_rules(formatted, self._color_rules)

            return formatted
        return formatter

    def _should_add_timestamp(self) -> bool:
        """
        타임스탬프를 추가할지 결정

        Returns:
            bool: 타임스탬프 추가 여부.
        """
        if not self._timestamp_enabled:
            return False

        now = QDateTime.currentMSecsSinceEpoch()
        if self._newline_char:
            return True

        if self._last_data_time is None:
            self._last_data_time = now
            return True

        time_diff = now - self._last_data_time
        if time_diff >= self._timestamp_timeout_ms:
            self._last_data_time = now
            return True

        self._last_data_time = now
        return False

    def _refresh_all_data(self) -> None:
        """
        모든 데이터를 다시 렌더링
        HEX 모드 변경 시 호출됩니다.
        """
        if not self._original_data:
            return

        scroll_pos = self.verticalScrollBar().value()
        was_at_bottom = self.is_at_bottom()

        self.log_model.clear()

        for data in self._original_data:
            if self._hex_mode:
                text = " ".join([f"{b:02X}" for b in data]) + " "
            else:
                try:
                    text = data.decode('utf-8', errors='replace')
                except Exception:
                    text = str(data)

            # Re-apply color rules (no timestamps on refresh for now to keep simple)
            formatter = None
            if self._color_rules:
                formatter = lambda line: ColorService.apply_rules(line, self._color_rules)

            self.append(text, formatter)

        if was_at_bottom:
            self.scrollToBottom()
        else:
            self.verticalScrollBar().setValue(scroll_pos)

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정

        Args:
            max_lines (int): 최대 라인 수.
        """
        self.log_model.set_max_lines(max_lines)
        # deque는 maxlen 변경이 불가하므로 새 deque 생성 (기존 데이터 유지)
        self._original_data = deque(self._original_data, maxlen=max_lines)

    def is_at_bottom(self) -> bool:
        """
        스크롤바가 맨 아래에 있는지 확인

        Returns:
            bool: 맨 아래에 있으면 True.
        """
        sb = self.verticalScrollBar()
        # 오차 범위를 두어 판별
        return sb.value() >= (sb.maximum() - 10)

    def clear(self) -> None:
        """
        로그 모델과 원본 데이터를 초기화
        """
        self.log_model.clear()
        self._original_data.clear()

    @pyqtSlot(str)
    def set_search_pattern(self, text: str) -> None:
        """
        검색어를 설정 정규식으로 컴파일하여 델리게이트에 전달하고,
        필터 모드일 경우 프록시 모델의 필터도 업데이트

        [Perf] 디바운싱 적용:
        - 하이라이트(Delegate)는 즉시 적용하여 반응성 확보
        - 필터링(ProxyModel)은 타이머를 통해 지연 적용하여 UI 프리징 방지

        Args:
            text (str): 검색할 문자열 (정규식 지원).
        """
        if not text:
            self._current_pattern = None
            self.delegate.set_search_pattern(None)
        else:
            # 1. 정규식으로 시도
            pattern = QRegExp(text, Qt.CaseInsensitive)

            # 2. 유효하지 않은 정규식(예: '[')이라면 일반 텍스트로 검색 (Escape 처리)
            if not pattern.isValid():
                pattern = QRegExp(QRegExp.escape(text), Qt.CaseInsensitive)

            self._current_pattern = pattern
            self.delegate.set_search_pattern(pattern)

        # 즉시 화면 갱신 (하이라이트 적용)
        self.viewport().update()

        # 필터 업데이트는 디바운싱 처리 (입력 중단 후 실행)
        self._filter_debounce_timer.start()

    def set_filter_mode(self, enabled: bool) -> None:
        """
        검색어 필터링 모드를 설정

        Args:
            enabled (bool): True면 검색어가 포함된 라인만 표시.
        """
        self._filter_enabled = enabled
        # 모드 변경은 즉시 적용
        self._execute_filter_update()

    def _execute_filter_update(self) -> None:
        """
        [Slot] 디바운스 타이머 종료 후 실제 필터링을 수행
        QSortFilterProxyModel의 필터를 업데이트하여 뷰를 갱신
        """
        if self._filter_enabled and self._current_pattern:
            self.proxy_model.setFilterRegExp(self._current_pattern)
        else:
            self.proxy_model.setFilterRegExp("") # 필터 해제

    def find_next(self, text: str) -> bool:
        """
        다음 검색 결과를 찾아 해당 행으로 이동 (Wrap around 지원)
        현재 보이는(필터링된) 항목 내에서 검색

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text: return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
        # 현재 모델(프록시)의 행 수 사용
        total_rows = self.model().rowCount()

        start_row = current_row + 1 if current_row >= 0 else 0

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
        이전 검색 결과를 찾아 해당 행으로 이동 (Wrap around 지원)
        현재 보이는(필터링된) 항목 내에서 검색

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text: return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
        # 현재 모델(프록시)의 행 수 사용
        total_rows = self.model().rowCount()

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
        모델에 있는 모든 로그 데이터를 가져와 하나의 문자열로 반환
        HTML 태그는 제거됩니다.

        Returns:
            str: 개행 문자로 구분된 전체 로그 텍스트.
        """
        # 모델에서 태그가 제거된 리스트를 가져옴
        lines = self.log_model.get_plain_text_logs()
        # 줄바꿈으로 연결하여 반환
        return "\n".join(lines)

    @staticmethod
    def _create_pattern(text: str) -> QRegExp:
        """
        검색 문자열을 QRegExp 객체로 변환

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
        특정 행의 데이터가 검색 패턴과 일치하는지 확인
        현재 모델(프록시)의 데이터를 기준으로 확인

        Args:
            row (int): 행 인덱스.
            pattern (QRegExp): 검색 패턴.

        Returns:
            bool: 일치하면 True.
        """
        # 현재 모델(프록시)에서 데이터 가져오기
        index = self.model().index(row, 0)
        text = self.model().data(index)
        return pattern.indexIn(text) != -1

    def _select_and_scroll(self, row: int) -> None:
        """
        특정 행을 선택하고 화면 중앙으로 스크롤

        Args:
            row (int): 이동할 행 인덱스.
        """
        # 현재 모델(프록시)의 인덱스 사용
        index = self.model().index(row, 0)
        self.setCurrentIndex(index)
        self.scrollTo(index, QAbstractItemView.PositionAtCenter)

    def setReadOnly(self, val: bool) -> None:
        """
        뷰의 읽기 전용 상태를 설정

        Args:
            val (bool): True일 경우 편집 트리거를 비활성화
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
        뷰가 현재 읽기 전용 상태인지 확인

        Returns:
            bool: 읽기 전용이면 True.
        """
        return self.editTriggers() == QAbstractItemView.NoEditTriggers

    def paintEvent(self, event) -> None:
        """
        화면을 그립니다. 데이터가 없을 경우 플레이스홀더를 표시

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

    def append_bytes(self, data: bytes) -> None:
        """
        bytes 데이터를 받아 내부 설정에 따라 처리

        - hex_mode: HEX 문자열로 변환
        - timestamp_enabled: 스마트 타임스탬프 추가
        - color_manager: 색상 규칙 적용
        - newline_char: 줄바꿈 분할

        Args:
            data: 수신된 바이트 데이터
        """
        # 원본 데이터 저장 (HEX 모드 전환용)
        self._original_data.append(data)

        # 1. HEX 변환 (옵션)
        if self._hex_mode:
            text = " ".join([f"{b:02X}" for b in data]) + " "
        else:
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)

        # 2. 타임스탬프 판단 (스마트 로직)
        should_add_timestamp = self._should_add_timestamp()

        # 3. Formatter 정의
        formatter = None
        if self._timestamp_enabled or self._color_manager:
            formatter = self._create_line_formatter(should_add_timestamp)

        # 4. 기존 append() 호출
        self.append(text, formatter)

    def _should_add_timestamp(self) -> bool:
        """
        타임스탬프를 추가할지 판단

        Returns:
            bool: 타임스탬프 추가 여부
        """
        if not self._timestamp_enabled:
            return False

        now = QDateTime.currentMSecsSinceEpoch()

        # Newline 모드: 각 줄 시작에 타임스탬프
        if self._newline_char:
            # append()의 formatter에서 각 라인마다 적용됨
            return True

        # Raw 모드: 시간 간격 체크
        if self._last_data_time is None:
            self._last_data_time = now
            return True

        time_diff = now - self._last_data_time
        if time_diff >= self._timestamp_timeout_ms:
            self._last_data_time = now
            return True

        self._last_data_time = now
        return False

    def _create_line_formatter(self, add_timestamp: bool):
        """
        라인 포맷터 함수를 생성

        Args:
            add_timestamp (bool): 타임스탬프 추가 여부

        Returns:
            callable: 생성된 포맷터 함수
        """
        def formatter(line: str) -> str:
            """
            라인 포맷터 함수

            Args:
                line (str): 포맷팅할 라인

            Returns:
                str: 포맷팅된 라인
            """
            formatted = line

            # 타임스탬프 추가
            if add_timestamp:
                ts = datetime.datetime.now().strftime("[%H:%M:%S]")
                formatted = f"{ts} {formatted}"

            # 색상 규칙 적용 (옵션)
            if self._color_manager:
                formatted = self._color_manager.apply_rules(formatted)

            return formatted

        return formatter

    def _refresh_all_data(self) -> None:
        """
        원본 데이터를 모두 다시 처리하여 화면을 갱신
        HEX 모드 변경 시 호출됩니다.
        """
        if not self._original_data:
            return

        # 현재 스크롤 위치 저장
        scroll_pos = self.verticalScrollBar().value()
        was_at_bottom = self.is_at_bottom()

        # 모델 초기화
        self.log_model.clear()

        # 모든 원본 데이터를 다시 처리
        for data in self._original_data:
            # HEX 변환
            if self._hex_mode:
                text = " ".join([f"{b:02X}" for b in data]) + " "
            else:
                try:
                    text = data.decode('utf-8', errors='replace')
                except Exception:
                    text = str(data)

            # Formatter(타임스탬프는 원본 시간을 알 수 없으므로 생략)
            formatter = None
            if self._color_manager:
                formatter = lambda line: self._color_manager.apply_rules(line)

            # Append (newline split은 기존 설정 사용)
            self.append(text, formatter)

        # 스크롤 위치 복원
        if was_at_bottom:
            self.scrollToBottom()
        else:
            self.verticalScrollBar().setValue(scroll_pos)

class LogModel(QAbstractListModel):
    """
    대량의 로그 데이터를 관리하는 데이터 모델 클래스입니다.

    QAbstractListModel을 상속받아 데이터를 리스트 형태로 관리하며,
    최대 라인 수 제한(Trim) 로직을 포함
    """
    def __init__(self, max_lines: int = DEFAULT_LOG_MAX_LINES):
        """
        LogModel을 초기화

        Args:
            max_lines (int): 유지할 최대 로그 라인 수.
        """
        super().__init__()
        self._data: List[str] = []
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        데이터의 행(row) 개수를 반환

        Args:
            parent (QModelIndex): 부모 인덱스.

        Returns:
            int: 데이터 개수.
        """
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """
        지정된 인덱스와 역할에 해당하는 데이터를 반환

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
        로그 데이터를 배치로 추가하고 필요시 오래된 로그를 삭제(Trim)

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
        """
        모든 데이터를 삭제
        """
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정

        Args:
            max_lines (int): 최대 라인 수.
        """
        self._max_lines = max_lines
        self._trim_size = int(max_lines * TRIM_CHUNK_RATIO)

    def get_plain_text_logs(self) -> List[str]:
        """
        저장된 모든 로그에서 HTML 태그를 제거하여 리스트로 반환

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

    HTML 텍스트 렌더링 및 검색어 하이라이트 기능을 수행
    """
    def __init__(self, parent=None):
        """
        LogDelegate를 초기화

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
        검색 패턴을 설정

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

        # 테마 색상 적용
        # QTextDocument는 기본적으로 검은색 글자를 사용하므로,
        # 테마가 다크 모드일 때 글자가 안 보이는 문제를 해결하기 위해
        # option.palette에서 텍스트 색상을 가져와 기본 스타일시트로 설정합니다.
        text_color = option.palette.text().color()
        self.doc.setDefaultStyleSheet(f"body {{ color: {text_color.name()}; }}")

        # 선택된 항목 배경 그리기
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

            # 선택된 경우 텍스트 색상을 HighlightedText 색상으로 변경 (선택적)
            # highlighted_text_color = option.palette.highlightedText().color()
            # self.doc.setDefaultStyleSheet(f"body {{ color: {highlighted_text_color.name()}; }}")

        # 데이터 설정
        text = index.data(Qt.DisplayRole)
        self.doc.setDefaultFont(option.font)
        self.doc.setHtml(text)

        # 정규식 객체를 사용하여 검색 및 하이라이트
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
        아이템의 크기 힌트를 반환

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
