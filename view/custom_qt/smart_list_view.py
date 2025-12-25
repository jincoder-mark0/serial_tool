"""
스마트 리스트 뷰 위젯 모듈

QListView를 기반으로 대량의 로그 데이터를 효율적으로 표시하고 관리하는 커스텀 위젯입니다.

## WHY
* 대량 데이터(로그)의 고성능 렌더링 및 메모리 관리 필요
* 검색, 필터링, 하이라이트, HEX 뷰 등 고급 기능 통합 필요
* 텍스트 에디터(QTextEdit)의 성능 한계 극복

## WHAT
* QAbstractListModel 기반의 고속 데이터 관리 (LogModel)
* 검색 탐색(Next/Prev) 및 정규식 필터링 (QSortFilterProxyModel)
* HEX/ASCII 모드 전환 및 스마트 타임스탬프 지원
* ColorRule 주입을 통한 동적 색상 적용 및 HTML 렌더링

## HOW
* QSortFilterProxyModel로 검색어 필터링 구현 (디바운싱 적용)
* QStyledItemDelegate로 HTML 텍스트 및 하이라이트 커스텀 렌더링
* ColorService를 활용한 텍스트 포맷팅 및 테마별 색상 보정
* deque를 사용한 원본 데이터 버퍼링 및 메모리 제한
"""
import re
import datetime
from typing import List, Any, Optional
from collections import deque

from PyQt5.QtWidgets import QListView, QAbstractItemView, QStyle, QStyledItemDelegate
from PyQt5.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QVariant, QSize, QRegExp, pyqtSlot,
    QSortFilterProxyModel, QTimer, QDateTime
)
from PyQt5.QtGui import (
    QColor, QTextDocument, QAbstractTextDocumentLayout, QTextCharFormat, QPainter, QPalette
)

from common.constants import DEFAULT_LOG_MAX_LINES, TRIM_CHUNK_RATIO
from common.dtos import ColorRule
from view.services.color_service import ColorService
from view.managers.theme_manager import theme_manager


class QSmartListView(QListView):
    """
    QListView를 확장하여 로그 뷰어 기능을 캡슐화한 클래스입니다.

    설정값(Newline, Hex 모드 등)은 외부에서 주입받으며,
    검색 탐색(Next/Prev) 및 필터링 기능을 제공합니다.
    """

    def __init__(self, parent=None):
        """
        QSmartListView를 초기화합니다.

        Args:
            parent (QWidget, optional): 부모 위젯.
        """
        super().__init__(parent)

        # ---------------------------------------------------------
        # 1. 모델 및 델리게이트 설정
        # ---------------------------------------------------------
        # 데이터 모델 생성
        self.log_model = LogModel()

        # 프록시 모델 설정 (필터링 지원)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.log_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # 전체 열에 대해 필터링 (로그는 0번 컬럼 하나임)
        self.proxy_model.setFilterKeyColumn(0)

        self.setModel(self.proxy_model)

        # 델리게이트 설정 (렌더링 담당)
        self.delegate = LogDelegate(self)
        self.setItemDelegate(self.delegate)

        # ---------------------------------------------------------
        # 2. 뷰 속성 설정
        # ---------------------------------------------------------
        self.setProperty("class", "fixed-font")  # 고정폭 폰트 적용 (QSS)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # 성능 최적화: 모든 항목이 동일한 높이라고 가정
        # 대량 로그 처리 시 스크롤 계산 성능 크게 향상
        self.setUniformItemSizes(True)

        # 스크롤 모드: PerPixel이 부드럽지만, 대량 데이터에서는 PerItem이 더 빠를 수 있음
        # 여기서는 부드러운 스크롤을 위해 PerPixel 사용
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # ---------------------------------------------------------
        # 3. 내부 상태 변수 초기화
        # ---------------------------------------------------------
        self._newline_char = "\n"
        self._placeholder_text = ""
        self._filter_enabled = False
        self._current_pattern = None

        # 선택적 기능 (기본값 = 비활성화)
        self._hex_mode = False
        self._timestamp_enabled = False
        self._timestamp_timeout_ms = 100

        # 색상 규칙 (외부 주입)
        self._color_rules: List[ColorRule] = []

        self._last_data_time = None

        # HEX 모드 전환을 위한 원본 bytes 데이터 저장 (원형 버퍼로 메모리 최적화)
        self._original_data: deque = deque(maxlen=DEFAULT_LOG_MAX_LINES)

        # 필터링 디바운스 타이머 (입력 멈춤 감지)
        # 복잡한 정규식 입력 시 UI 프리징 방지
        self._filter_debounce_timer = QTimer()
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.setInterval(300)  # 300ms 대기
        self._filter_debounce_timer.timeout.connect(self._execute_filter_update)

        self.setObjectName("SmartListView")

    def set_color_rules(self, rules: List[ColorRule]) -> None:
        """
        색상 규칙을 설정합니다 (Dependency Injection).

        Args:
            rules (List[ColorRule]): 적용할 ColorRule 리스트.
        """
        self._color_rules = rules
        # 규칙이 변경되면 기존 데이터 다시 렌더링
        self._refresh_all_data()

    def set_newline_char(self, char: Optional[str]) -> None:
        """
        줄바꿈 문자를 설정합니다.

        Args:
            char (Optional[str]): 사용할 줄바꿈 문자 (예: '\n', '\r\n'). None이면 Raw 모드.
        """
        self._newline_char = char

    def set_hex_mode_enabled(self, enabled: bool) -> None:
        """
        HEX 모드 활성화/비활성화를 설정합니다.
        모드 변경 시 원본 데이터를 사용하여 화면을 다시 렌더링합니다.

        Args:
            enabled (bool): HEX 모드 활성화 여부.
        """
        if self._hex_mode == enabled:
            return

        self._hex_mode = enabled
        self._refresh_all_data()

    def set_timestamp_enabled(self, enabled: bool, timeout_ms: int = 100) -> None:
        """
        타임스탬프 기능을 활성화합니다.

        Args:
            enabled (bool): 타임스탬프 활성화 여부.
            timeout_ms (int): Raw 모드에서 타임스탬프를 찍을 최소 간격 (ms).
        """
        self._timestamp_enabled = enabled
        self._timestamp_timeout_ms = timeout_ms

    def setPlaceholderText(self, text: str) -> None:
        """
        데이터가 없을 때 표시할 안내 문구(Placeholder)를 설정합니다.

        Args:
            text (str): 표시할 텍스트.
        """
        self._placeholder_text = text
        self.viewport().update()

    def append(self, text: str, line_formatter=None) -> None:
        """
        로그 데이터를 모델에 추가합니다.
        설정된 newline 문자로 분할하여 여러 줄로 추가하며, 각 라인에 formatter를 적용합니다.

        Args:
            text (str): 로그 내용 (newline 포함 가능).
            line_formatter (callable, optional): 각 라인을 포맷팅할 함수.
                                                 signature: formatter(line: str) -> str
        """
        # 1. Newline으로 분할
        if self._newline_char and self._newline_char in text:
            lines = text.split(self._newline_char)
            # 마지막이 빈 문자열이면 제거 (예: "abc\n" -> ["abc", ""])
            if lines and lines[-1] == "":
                lines.pop()
        else:
            # newline이 없으면 단일 라인으로 처리
            lines = [text] if text else []

        # 2. 각 라인에 formatter 적용 (제공된 경우)
        if line_formatter:
            lines = [line_formatter(line) for line in lines]

        # 3. 모델에 배치(Batch) 추가
        if lines:
            self.log_model.add_logs(lines)

            # 4. 자동 스크롤 (맨 아래에 있을 때만)
            if self.is_at_bottom():
                self.scrollToBottom()

    def append_bytes(self, data: bytes) -> None:
        """
        바이트 데이터를 받아 내부 설정에 따라 처리 후 추가합니다.

        Logic:
            1. 원본 데이터 저장 (HEX 모드 전환용)
            2. 설정에 따라 HEX 문자열 또는 디코딩된 문자열로 변환
            3. 타임스탬프 및 색상 적용을 위한 포맷터 생성
            4. append() 호출

        Args:
            data (bytes): 수신된 바이트 데이터.
        """
        # 원본 데이터 저장 (HEX 모드 전환용, deque가 maxlen 관리)
        self._original_data.append(data)

        # 1. 텍스트 변환
        if self._hex_mode:
            text = " ".join([f"{b:02X}" for b in data]) + " "
        else:
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)

        # 2. 타임스탬프 판단 (스마트 로직)
        should_add_timestamp = self._should_add_timestamp()

        # 3. Formatter 생성 (클로저)
        formatter = self._create_line_formatter(should_add_timestamp)

        # 4. 모델에 추가
        self.append(text, formatter)

    def _create_line_formatter(self, add_timestamp: bool):
        """
        라인 포맷터 함수(클로저)를 생성합니다.

        Args:
            add_timestamp (bool): 타임스탬프 추가 여부.

        Returns:
            callable: 생성된 포맷터 함수.
        """
        # 캡처 시점의 테마 상태 확인 (다크 모드 여부)
        is_dark = theme_manager.is_dark_theme()

        def formatter(line: str) -> str:
            """
            개별 라인을 포맷팅하는 내부 함수.

            Args:
                line (str): 원본 라인 텍스트.

            Returns:
                str: 포맷팅된(타임스탬프, HTML 색상) 텍스트.
            """
            formatted = line

            if add_timestamp:
                ts = datetime.datetime.now().strftime("[%H:%M:%S]")
                formatted = f"{ts} {formatted}"

            if self._color_rules:
                # ColorService를 통해 규칙 적용 (테마 반영)
                formatted = ColorService.apply_rules(formatted, self._color_rules, is_dark)

            return formatted
        return formatter

    def _should_add_timestamp(self) -> bool:
        """
        타임스탬프를 추가할지 결정합니다.

        Logic:
            - 비활성화 상태면 False
            - Newline 모드면 항상 True (각 줄마다 찍힘)
            - Raw 모드면 이전 데이터와의 시간 간격이 timeout_ms 이상일 때만 True

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
        모든 데이터를 다시 렌더링합니다.
        HEX 모드 변경 또는 테마 변경 시 호출됩니다.
        """
        if not self._original_data:
            return

        scroll_pos = self.verticalScrollBar().value()
        was_at_bottom = self.is_at_bottom()

        # 모델 초기화
        self.log_model.clear()

        # 현재 테마 상태 확인
        is_dark = theme_manager.is_dark_theme()

        # 원본 데이터 순회하며 재생성
        for data in self._original_data:
            if self._hex_mode:
                text = " ".join([f"{b:02X}" for b in data]) + " "
            else:
                try:
                    text = data.decode('utf-8', errors='replace')
                except Exception:
                    text = str(data)

            # 재생성 시에는 타임스탬프를 정확히 복원하기 어려우므로 생략하거나
            # 저장된 타임스탬프가 있다면 그것을 써야 함.
            # 현재 구조에서는 단순 텍스트 재구성이므로 타임스탬프 생략 (또는 규칙만 적용)
            formatter = None
            if self._color_rules:
                formatter = lambda line: ColorService.apply_rules(line, self._color_rules, is_dark)

            self.append(text, formatter)

        # 스크롤 위치 복원
        if was_at_bottom:
            self.scrollToBottom()
        else:
            self.verticalScrollBar().setValue(scroll_pos)

    def set_max_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 최대 라인 수.
        """
        self.log_model.set_max_lines(max_lines)
        # deque의 크기도 조정 (기존 데이터 유지하며 리사이징)
        self._original_data = deque(self._original_data, maxlen=max_lines)

    def is_at_bottom(self) -> bool:
        """
        스크롤바가 맨 아래에 있는지 확인합니다.

        Returns:
            bool: 맨 아래에 있으면 True.
        """
        sb = self.verticalScrollBar()
        # 약간의 오차 범위를 두어 판별
        return sb.value() >= (sb.maximum() - 10)

    def clear(self) -> None:
        """
        로그 모델과 원본 데이터 버퍼를 초기화합니다.
        """
        self.log_model.clear()
        self._original_data.clear()

    @pyqtSlot(str)
    def set_search_pattern(self, text: str) -> None:
        """
        검색어를 설정하고 하이라이트 및 필터링을 갱신합니다.

        Logic:
            - 정규식 컴파일 (실패 시 일반 텍스트 이스케이프)
            - 델리게이트에 패턴 전달 (하이라이트 즉시 갱신)
            - 필터링은 디바운싱 타이머 시작 (UI 프리징 방지)

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
        검색어 필터링 모드를 설정합니다.

        Args:
            enabled (bool): True면 검색어가 포함된 라인만 표시.
        """
        self._filter_enabled = enabled
        # 모드 변경은 즉시 적용
        self._execute_filter_update()

    def _execute_filter_update(self) -> None:
        """
        [Slot] 디바운스 타이머 종료 후 실제 필터링을 수행합니다.
        QSortFilterProxyModel의 필터를 업데이트하여 뷰를 갱신합니다.
        """
        if self._filter_enabled and self._current_pattern:
            self.proxy_model.setFilterRegExp(self._current_pattern)
        else:
            self.proxy_model.setFilterRegExp("")  # 필터 해제

    def find_next(self, text: str) -> bool:
        """
        다음 검색 결과를 찾아 해당 행으로 이동합니다 (Wrap around 지원).
        현재 보이는(필터링된) 항목 내에서 검색합니다.

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text:
            return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
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
        이전 검색 결과를 찾아 해당 행으로 이동합니다 (Wrap around 지원).

        Args:
            text (str): 검색할 문자열.

        Returns:
            bool: 찾았으면 True, 아니면 False.
        """
        if not text:
            return False

        pattern = self._create_pattern(text)
        current_row = self.currentIndex().row()
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
        모델에 있는 모든 로그 데이터를 가져와 하나의 문자열로 반환합니다.
        HTML 태그는 제거됩니다.

        Returns:
            str: 개행 문자로 구분된 전체 로그 텍스트.
        """
        lines = self.log_model.get_plain_text_logs()
        return "\n".join(lines)

    @staticmethod
    def _create_pattern(text: str) -> QRegExp:
        """
        검색 문자열을 QRegExp 객체로 변환합니다.

        Args:
            text (str): 검색 문자열.

        Returns:
            QRegExp: 컴파일된 정규식 객체.
        """
        pattern = QRegExp(text, Qt.CaseInsensitive)
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
        index = self.model().index(row, 0)
        text = self.model().data(index)
        return pattern.indexIn(text) != -1

    def _select_and_scroll(self, row: int) -> None:
        """
        특정 행을 선택하고 화면 중앙으로 스크롤합니다.

        Args:
            row (int): 이동할 행 인덱스.
        """
        index = self.model().index(row, 0)
        self.setCurrentIndex(index)
        self.scrollTo(index, QAbstractItemView.PositionAtCenter)

    def setReadOnly(self, val: bool) -> None:
        """
        뷰의 읽기 전용 상태를 설정합니다.
        (로그 뷰어 특성상 텍스트 선택 및 복사는 항상 가능합니다)

        Args:
            val (bool): True일 경우 편집 트리거를 비활성화.
        """
        if val:
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            self.setEditTriggers(QAbstractItemView.DoubleClicked |
                                 QAbstractItemView.EditKeyPressed |
                                 QAbstractItemView.SelectedClicked)

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
            clean_text = re.sub(cleaner, '', line)
            plain_logs.append(clean_text)

        return plain_logs


class LogDelegate(QStyledItemDelegate):
    """
    로그 아이템의 렌더링을 담당하는 델리게이트 클래스입니다.

    QTextDocument를 사용하여 HTML 텍스트를 렌더링하고,
    검색 결과 하이라이트 기능을 수행합니다.
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

        Logic:
            1. 선택 상태에 따른 배경 그리기
            2. 테마에 맞는 텍스트 색상 결정 (QPalette)
            3. 데이터(HTML) 설정 및 검색어 하이라이트 적용
            4. QTextDocument를 사용하여 페인팅

        Args:
            painter (QPainter): 페인터 객체.
            option (QStyleOptionViewItem): 스타일 옵션.
            index (QModelIndex): 모델 인덱스.
        """
        painter.save()

        # 1. 배경 그리기
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # 2. 텍스트 색상 결정 (테마 및 선택 상태 반영)
        if option.state & QStyle.State_Selected:
            text_color = option.palette.highlightedText().color().name()
        else:
            text_color = option.palette.text().color().name()

        # 3. 데이터 설정 및 HTML 래핑
        raw_text = index.data(Qt.DisplayRole)

        # 문서 기본 폰트 설정
        self.doc.setDefaultFont(option.font)

        # 색상이 적용된 HTML 생성 (기본 텍스트 색상 강제)
        styled_html = f'<div style="color: {text_color};">{raw_text}</div>'
        self.doc.setHtml(styled_html)

        # 4. 검색 하이라이트 적용
        if self.search_pattern and not self.search_pattern.isEmpty():
            cursor = self.doc.find(self.search_pattern)
            while not cursor.isNull():
                cursor.mergeCharFormat(self.highlight_format)
                cursor = self.doc.find(self.search_pattern, cursor)

        # 5. 그리기
        painter.translate(option.rect.left(), option.rect.top())
        ctx = QAbstractTextDocumentLayout.PaintContext()

        # 선택된 경우 텍스트 색상 강제 조정 (QPalette 활용)
        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.highlightedText().color())

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