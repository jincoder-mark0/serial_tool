"""
시스템 로그 위젯 모듈

애플리케이션의 동작 상태 및 오류 메시지를 표시합니다.

## WHY
* 사용자에게 시스템 내부 동작 상황(연결, 에러, 파일 저장 등) 전달
* 통신 데이터와 구분된 시스템 이벤트 기록 및 가시성 확보

## WHAT
* QSmartListView 기반의 고성능 로그 뷰어
* 로그 레벨(INFO, ERROR 등)에 따른 색상 구분
* 검색, 필터링, 로그 파일 저장 기능

## HOW
* ColorService를 사용하여 로그 레벨별 색상 태그 적용
* SystemLogEvent DTO를 통해 정형화된 데이터 수신
* QTimer 및 QFileDialog를 활용한 부가 기능 구현
"""
import datetime
from typing import Optional, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QLineEdit, QFileDialog
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QRegExp

from view.managers.language_manager import language_manager
from view.managers.theme_manager import theme_manager
from view.custom_qt.smart_list_view import QSmartListView
from view.widgets.log_toolbar import (
    create_search_bar, create_filter_checkbox, create_logging_toggle_button,
    apply_recording_style, LogSearchController,
)
from common.constants import (
    DEFAULT_LOG_MAX_LINES,
    LAYOUT_MARGIN_NONE, LAYOUT_SPACING_TIGHT
)
from common.dtos import ColorRule, SystemLogEvent
from view.services.color_service import ColorService


class SystemLogWidget(QWidget):
    """
    시스템 상태 메시지 및 에러 로그를 표시하는 위젯 클래스입니다.

    QSmartListView를 사용하여 대량의 로그를 효율적으로 렌더링하며,
    검색 및 필터링 기능을 제공합니다.
    """

    # 로깅 제어 시그널 (S-052: DataLogWidget과 대칭 — 인자 없는 요청 시그널)
    sys_logging_start_requested = pyqtSignal()
    sys_logging_stop_requested = pyqtSignal()

    # 화면에 실제로 한 줄이 추가될 때마다 발행 (S-055: 실제 파일 기록 연동용).
    # View는 파일을 직접 쓰지 않는다 — Presenter가 이 시그널을 구독해 텍스트
    # 라이터(core/text_log_writer.py)에 같은 줄을 넘긴다. 화면 필터가 걸려
    # 있으면(검색어+필터 체크박스) 화면에서 숨겨지는 줄은 이 시그널도 받지
    # 않는다 — "저장 대상은 화면에 표시되는 라인 그대로"라는 결정(S-055) 때문.
    system_log_line_appended = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        SystemLogWidget를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # ---------------------------------------------------------
        # 1. 상태 변수 초기화
        # ---------------------------------------------------------
        # UI Components
        self.sys_log_title: Optional[QLabel] = None
        self.sys_log_list: Optional[QSmartListView] = None
        self.sys_log_search_input: Optional[QLineEdit] = None
        self.sys_log_search_prev_btn: Optional[QPushButton] = None
        self.sys_log_search_next_btn: Optional[QPushButton] = None
        self.sys_log_toggle_logging_btn: Optional[QPushButton] = None
        self.sys_log_clear_log_btn: Optional[QPushButton] = None
        self.sys_log_filter_chk: Optional[QCheckBox] = None

        self.filter_enabled = False
        self.tab_name = ""  # 파일 저장 시 제목 생성용

        # 색상 규칙 저장소
        self._color_rules: List[ColorRule] = []

        # ---------------------------------------------------------
        # 2. UI 구성 및 시그널 연결
        # ---------------------------------------------------------
        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def set_color_rules(self, rules: List[ColorRule]) -> None:
        """
        색상 규칙을 설정합니다.

        Args:
            rules (List[ColorRule]): 적용할 색상 규칙 리스트.
        """
        self._color_rules = rules
        if self.sys_log_list:
            self.sys_log_list.set_color_rules(rules)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            - 높이를 고정하여 레이아웃 안정성 확보
            - 툴바(검색, 필터, 버튼) 구성
            - 로그 뷰(QSmartListView) 배치
        """
        # 고정 높이(100)는 폰트 확대 시 로그 영역이 잘리는 원인이었음(S-024).
        # 최소 높이만 보장하고 수직으로는 필요 시 확장 가능하도록 완화.
        # 100 -> 60 (S-026): 시스템 로그는 보조 정보라 최소 2~3줄이면 충분 — 창 최소 높이 완화 목적.
        self.setMinimumHeight(60)

        # 1. 툴바 영역 (타이틀 + 도구들)
        # 타이틀 섹션
        self.sys_log_title = QLabel(language_manager.get_text("sys_log_title"))
        self.sys_log_title.setProperty("class", "section-title")

        # 도구 섹션 (검색, 옵션, 액션) — 공통 팩토리(view/widgets/log_toolbar.py, S-049)
        self.sys_log_search_input, self.sys_log_search_prev_btn, self.sys_log_search_next_btn = create_search_bar(
            object_name_prefix="sys_log",
            placeholder=language_manager.get_text("sys_log_edit_search_placeholder"),
            input_tooltip=language_manager.get_text("sys_log_edit_search_tooltip"),
            prev_tooltip=language_manager.get_text("sys_log_btn_search_prev_tooltip"),
            next_tooltip=language_manager.get_text("sys_log_btn_search_next_tooltip"),
        )
        self.sys_log_search_input.returnPressed.connect(self.on_sys_log_search_next_clicked)
        # 검색어 변경 시 실시간 하이라이트 갱신
        self.sys_log_search_input.textChanged.connect(self.on_sys_log_search_text_changed)
        self.sys_log_search_prev_btn.clicked.connect(self.on_sys_log_search_prev_clicked)
        self.sys_log_search_next_btn.clicked.connect(self.on_sys_log_search_next_clicked)

        self.sys_log_clear_log_btn = QPushButton(language_manager.get_text("sys_log_btn_clear"))
        self.sys_log_clear_log_btn.setToolTip(language_manager.get_text("sys_log_btn_clear_tooltip"))
        self.sys_log_clear_log_btn.clicked.connect(self.on_clear_sys_log_clicked)

        self.sys_log_toggle_logging_btn = create_logging_toggle_button(
            language_manager.get_text("sys_log_btn_toggle_logging"),
            language_manager.get_text("sys_log_btn_toggle_logging_tooltip"),
        )
        self.sys_log_toggle_logging_btn.toggled.connect(self.on_sys_log_logging_toggled)

        # Options
        self.sys_log_filter_chk = create_filter_checkbox(
            language_manager.get_text("sys_log_chk_filter"),
            language_manager.get_text("sys_log_chk_filter_tooltip"),
        )
        self.sys_log_filter_chk.stateChanged.connect(self.on_sys_log_filter_changed)

        # 2. 로그 뷰 영역
        self.sys_log_list = QSmartListView()
        self.sys_log_list.set_max_lines(DEFAULT_LOG_MAX_LINES)
        self.sys_log_list.setReadOnly(True)
        self.sys_log_list.setPlaceholderText(language_manager.get_text("sys_log_list_log_placeholder"))
        self.sys_log_list.setToolTip(language_manager.get_text("sys_log_list_log_tooltip"))
        self.sys_log_list.setProperty("class", "fixed-font")

        # 검색 다음/이전/실시간 하이라이트 배선 (공통 컨트롤러 — S-049)
        self._search_controller = LogSearchController(self.sys_log_search_input, self.sys_log_list)

        # 레이아웃 배치
        # DataLogWidget과 동일하게 타이틀 뒤에 stretch를 두어 툴바 우측 정렬 규칙을 통일 (S-025)
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.sys_log_title)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.sys_log_search_input)
        toolbar_layout.addWidget(self.sys_log_search_prev_btn)
        toolbar_layout.addWidget(self.sys_log_search_next_btn)
        toolbar_layout.addWidget(self.sys_log_filter_chk)
        toolbar_layout.addWidget(self.sys_log_clear_log_btn)
        toolbar_layout.addWidget(self.sys_log_toggle_logging_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE,
                                   LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)
        layout.setSpacing(LAYOUT_SPACING_TIGHT)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.sys_log_list)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 현재 언어 설정에 맞게 업데이트합니다."""
        # Labels & Tooltips
        self.sys_log_title.setText(language_manager.get_text("sys_log_title"))
        self.sys_log_list.setToolTip(language_manager.get_text("sys_log_list_log_tooltip"))
        self.sys_log_list.setPlaceholderText(language_manager.get_text("sys_log_list_log_placeholder"))

        # Search Components
        self.sys_log_search_input.setPlaceholderText(language_manager.get_text("sys_log_edit_search_placeholder"))
        self.sys_log_search_input.setToolTip(language_manager.get_text("sys_log_edit_search_tooltip"))
        self.sys_log_search_prev_btn.setToolTip(language_manager.get_text("sys_log_btn_search_prev_tooltip"))
        self.sys_log_search_next_btn.setToolTip(language_manager.get_text("sys_log_btn_search_next_tooltip"))

        # Checkboxes
        self.sys_log_filter_chk.setText(language_manager.get_text("sys_log_chk_filter"))
        self.sys_log_filter_chk.setToolTip(language_manager.get_text("sys_log_chk_filter_tooltip"))

        # Buttons
        self.sys_log_clear_log_btn.setText(language_manager.get_text("sys_log_btn_clear"))
        self.sys_log_clear_log_btn.setToolTip(language_manager.get_text("sys_log_btn_clear_tooltip"))

        # 로깅 버튼 텍스트는 상태에 따라 달라짐 (토글 시)
        if not self.sys_log_toggle_logging_btn.isChecked():
            self.sys_log_toggle_logging_btn.setText(language_manager.get_text("sys_log_btn_toggle_logging"))
        self.sys_log_toggle_logging_btn.setToolTip(language_manager.get_text("sys_log_btn_toggle_logging_tooltip"))

    def append_log(self, event: SystemLogEvent) -> None:
        """
        상태 메시지를 로그에 추가합니다.

        Logic:
            - DTO에서 데이터 추출 (메시지, 레벨, 타임스탬프)
            - 타임스탬프 포맷팅 ([HH:MM:SS])
            - ColorService를 사용하여 색상 규칙 적용 (다크/라이트 테마 반영)
            - 뷰에 추가

        Args:
            event (SystemLogEvent): 시스템 로그 이벤트 DTO.
        """
        # 1. 메시지 포맷팅: [LEVEL] Message
        text = f"[{event.level}] {event.message}"

        # 2. 타임스탬프 포맷팅
        dt = datetime.datetime.fromtimestamp(event.timestamp)
        timestamp_str = dt.strftime("[%H:%M:%S]")
        # plain_text: 색상 HTML 마크업이 섞이기 전의 순수 텍스트.
        # 파일에 저장할 때는 이 값을 쓴다 — HTML 태그는 화면 표시 전용이라
        # 파일에 그대로 쓰면 사람이 읽기 어렵다(S-055).
        plain_text = f"{timestamp_str} {text}"
        full_text = plain_text

        # 3. 색상 규칙 적용
        if self._color_rules:
            # 현재 테마 상태 조회 및 전달
            is_dark = theme_manager.is_dark_theme()
            full_text = ColorService.apply_rules(full_text, self._color_rules, is_dark)

        # 4. 뷰에 추가
        self.sys_log_list.append(full_text)

        # 5. 실제 파일 기록용 시그널 발행 (S-055).
        # 화면 검색 필터가 켜져 있고 현재 라인이 필터에 걸리지 않으면(=화면에
        # 보이지 않으면) 저장도 하지 않는다 — "보이는 것 = 저장되는 것" 결정.
        if self._passes_display_filter(plain_text):
            self.system_log_line_appended.emit(plain_text)

    def _passes_display_filter(self, plain_text: str) -> bool:
        """
        현재 화면 필터(검색어 + 필터 체크박스) 기준으로 해당 라인이 화면에
        보이는 상태인지 판단합니다.

        Logic:
            - 필터 체크박스가 꺼져 있거나 검색어가 비어 있으면 항상 통과(True).
            - `QSmartListView`(view/custom_qt/smart_list_view.py)의
              `set_search_pattern()`/`_execute_filter_update()`와 동일한 방식
              (대소문자 무시 정규식, 무효 패턴은 일반 텍스트로 이스케이프)으로
              매칭해 화면에 보이는 규칙과 일치시킨다.
            - 이 위젯은 필터링을 위해 `QSortFilterProxyModel`을 직접 다루지
              않으므로(그 로직은 QSmartListView 내부), 여기서는 동일한 판정
              규칙만 재현한다 — 실제 표시 여부의 최종 권한은 여전히
              QSmartListView에 있다.

        Args:
            plain_text: 색상 마크업이 적용되기 전의 순수 로그 라인.

        Returns:
            bool: 현재 필터 기준으로 화면에 표시되면(=저장 대상이면) True.
        """
        if not self.filter_enabled:
            return True

        search_text = self.sys_log_search_input.text() if self.sys_log_search_input else ""
        if not search_text:
            return True

        pattern = QRegExp(search_text, Qt.CaseInsensitive)
        if not pattern.isValid():
            pattern = QRegExp(QRegExp.escape(search_text), Qt.CaseInsensitive)

        return pattern.indexIn(plain_text) != -1

    def clear(self) -> None:
        """로그를 초기화합니다."""
        self.sys_log_list.clear()

    # -------------------------------------------------------------------------
    # 사용자 액션 처리 (검색, 옵션, 버튼)
    # -------------------------------------------------------------------------
    @pyqtSlot()
    def on_sys_log_search_next_clicked(self) -> None:
        """검색창의 텍스트로 다음 항목을 찾습니다."""
        self._search_controller.search_next()

    @pyqtSlot()
    def on_sys_log_search_prev_clicked(self) -> None:
        """검색창의 텍스트로 이전 항목을 찾습니다."""
        self._search_controller.search_prev()

    @pyqtSlot(str)
    def on_sys_log_search_text_changed(self, text: str) -> None:
        """검색어가 변경되면 하이라이트 패턴을 즉시 업데이트합니다."""
        self._search_controller.on_text_changed(text)

    @pyqtSlot()
    def on_clear_sys_log_clicked(self) -> None:
        """화면에 표시된 로그와 대기 중인 버퍼를 모두 지웁니다."""
        self.clear()

    @pyqtSlot(bool)
    def on_sys_log_logging_toggled(self, checked: bool) -> None:
        """
        로깅 시작/중단 토글 핸들러입니다.

        Logic:
            - UI 상태 변경 없이 오직 요청 시그널만 발행한다.
            - 실제 파일 다이얼로그 표시(`show_save_log_dialog()`)와 REC 스타일
              전환(`set_logging_active()`)은 Presenter가 호출할 때만 일어난다.

        Note (S-052, 통일 완료):
            S-049에서는 이 위젯이 "자기 권위" 제어 흐름이었다 — 토글 즉시 위젯
            스스로 QFileDialog를 띄우고 REC 스타일도 직접 바꿨다. `DataLogWidget`
            ("Presenter 권위": 토글은 의도만 내보내고 스타일 전환은 Presenter의
            `set_logging_active()` 호출로만 일어남)과 반대 방향이던 불일치를
            이번 태스크에서 DataLog 패턴으로 통일했다 — 이제 두 위젯 모두 토글
            시 인자 없는 요청 시그널만 emit하고, 파일 선택과 스타일 전환은
            Presenter가 `show_save_log_dialog()`/`set_logging_active()`를 통해
            수행한다(`data_log.py`의 `on_data_log_logging_toggled` 참고).

        Args:
            checked (bool): 버튼 체크 상태.
        """
        if checked:
            self.sys_logging_start_requested.emit()
        else:
            self.sys_logging_stop_requested.emit()

    def set_logging_active(self, active: bool) -> None:
        """
        외부(Presenter)에서 로깅 상태를 설정합니다.
        성공적으로 시작/중지되었을 때 호출됩니다(DataLogWidget과 동일 계약, S-052).

        Args:
            active (bool): 로깅 활성화 여부.
        """
        self.sys_log_toggle_logging_btn.blockSignals(True)
        self.sys_log_toggle_logging_btn.setChecked(active)
        self.sys_log_toggle_logging_btn.blockSignals(False)

        apply_recording_style(
            self.sys_log_toggle_logging_btn,
            active,
            inactive_text=language_manager.get_text("sys_log_btn_toggle_logging"),
        )

    def show_save_log_dialog(self) -> str:
        """
        파일 저장 다이얼로그 표시 (Presenter가 호출).

        DataLogWidget.show_save_log_dialog()과 동일한 패턴(S-052) — 위젯은
        토글 시 스스로 다이얼로그를 열지 않고, Presenter가 이 메서드를 명시적으로
        호출했을 때만 QFileDialog가 뜬다.

        Returns:
            str: 선택된 파일 경로 (취소 시 빈 문자열).
        """
        title = language_manager.get_text("sys_log_btn_toggle_logging")
        if self.tab_name:
            title = f"{self.tab_name}::{title}"

        # 시스템 로그는 항상 줄 단위 텍스트이므로(S-055) 텍스트 확장자를 기본으로 안내한다.
        # (기존 "Binary Files (*.bin)"는 DataLogWidget과의 복사·구현 과정에서 남은
        # 오기였다 — 시스템 로그는 바이너리 포맷을 지원한 적이 없다.)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            title,
            "",
            "Text Files (*.txt *.log);;All Files (*)"
        )
        return filename

    @pyqtSlot(int)
    def on_sys_log_filter_changed(self, state: int) -> None:
        """
        필터 모드 토글을 처리합니다.

        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        self.filter_enabled = (state == Qt.Checked)
        self.sys_log_list.set_filter_mode(self.filter_enabled)

    # -------------------------------------------------------------------------
    # 설정 및 상태 관리
    # -------------------------------------------------------------------------
    def get_state(self) -> dict:
        """
        현재 상태를 반환합니다 (설정 저장용).

        Returns:
            dict: 저장된 상태 정보 (필터 설정, 검색어).
        """
        state = {
            "filter_enabled": self.filter_enabled,
            "search_text": self.sys_log_search_input.text(),
        }
        return state

    def apply_state(self, state: dict) -> None:
        """
        저장된 상태 딕셔너리를 UI에 적용합니다.

        Args:
            state (dict): 복원할 상태 정보.
        """
        if not state:
            return

        # 체크박스 상태 업데이트
        self.sys_log_filter_chk.setChecked(state.get("filter_enabled", False))
        self.sys_log_search_input.setText(state.get("search_text", ""))

    def closeEvent(self, event) -> None:
        """
        위젯 종료 시 리소스 정리.

        Args:
            event (QCloseEvent): 종료 이벤트.
        """
        # if self.ui_update_timer.isActive():
        #     self.ui_update_timer.stop()
        super().closeEvent(event)
