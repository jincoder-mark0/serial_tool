"""
로그 위젯 공통 툴바 조각 모듈

`DataLogWidget`과 `SystemLogWidget`이 각자 구현하던 검색바(입력 + 이전/다음 버튼),
필터 체크박스, REC 토글 버튼의 **생성**과 REC 상태 전환(**스타일**)을 한 곳으로 모은다.

## WHY
* 두 위젯이 150~200줄 분량의 같은 UI 조각을 중복 구현해 한쪽을 고치면 다른 쪽을
  빠뜨리기 쉬웠다 (S-049, `doc/refactor_audit_20260822.md` C-7).
* 상속 vs 컴포지션 판단(S-049 확정 설계): 두 위젯은 툴바 레이아웃 구조 자체가
  다르다 — DataLog는 옵션이 많아 2행(S-026), SystemLog는 옵션이 적어 1행이고
  버튼 배치 순서도 다르다. 공통 QWidget 베이스를 상속시키면 그 레이아웃 차이를
  베이스 쪽 파라미터로 흡수해야 해서 결합이 세지고, 두 위젯 중 하나만 레이아웃을
  바꿔도 베이스가 흔들리는 위험이 생긴다. 대신 여기서는 **컴포지션**을 선택했다:
  이 모듈은 QWidget을 상속하지 않는 순수 팩토리 함수 + 얇은 컨트롤러 클래스만
  제공하고, 실제 레이아웃 배치(`addWidget` 순서, 행 구성)는 각 위젯의 `init_ui`가
  그대로 소유한다 — 캡처 회귀(레이아웃 변경) 위험을 최소화하는 선택.
* 시그널 계약과 제어 흐름은 S-052에서 Presenter 권위로 통일되었다 —
  `logging_start_requested`/`sys_logging_start_requested` 등 두 위젯 모두
  인자 없는 요청 시그널만 emit하고, 파일 다이얼로그(`show_save_log_dialog()`)와
  REC 스타일 전환(`set_logging_active()`)은 Presenter가 호출할 때만 일어난다.
  이 모듈 자체는 여전히 그 계약·흐름에 관여하지 않는다 — 각 위젯이 자신의
  토글 핸들러에서 이 모듈의 헬퍼를 호출할 시점과 방식을 스스로 결정한다.

## WHAT
* `create_search_bar()` — 검색 QLineEdit + 이전/다음 QPushButton 3종 생성
  (언어 키로 뽑은 문구·objectName은 호출자가 주입).
* `create_filter_checkbox()` — 필터 QCheckBox 생성.
* `create_logging_toggle_button()` — REC 토글용 checkable QPushButton 생성.
* `apply_recording_style()` — `setProperty("state", "recording")` +
  `style().unpolish/polish()` 시퀀스로 REC 진입/해제 스타일을 전환.
* `LogSearchController` — 검색 입력창 ↔ `QSmartListView`(find_next/find_prev/
  set_search_pattern) 사이의 다음/이전/실시간 하이라이트 배선을 캡슐화.

## HOW
* 전부 QWidget 비상속 — 각 위젯이 결과물을 자신의 레이아웃에 원하는 순서로
  배치한다. `LogSearchController`도 지정된 두 객체(입력창, 로그뷰)에 대한
  얇은 위임일 뿐 상태를 소유하지 않는다.
"""
from typing import Optional, Tuple

from PyQt5.QtWidgets import QLineEdit, QPushButton, QCheckBox

from common.constants import ICON_BUTTON_SIZE

# REC 진입 시 공통으로 쓰는 표시 문구 (두 위젯 모두 동일하게 사용해 왔음).
RECORDING_BUTTON_TEXT = "● REC"  # "● REC"


def create_search_bar(
    object_name_prefix: str,
    placeholder: str,
    input_tooltip: str,
    prev_tooltip: str,
    next_tooltip: str,
    max_width: int = 200,
    min_width: Optional[int] = None,
) -> Tuple[QLineEdit, QPushButton, QPushButton]:
    """
    검색 입력창 + 이전/다음 버튼을 생성합니다.

    Args:
        object_name_prefix: 버튼 objectName 접두어 (예: "data_log", "sys_log").
            결과 objectName은 `f"{prefix}_search_prev_btn"` / `f"{prefix}_search_next_btn"`으로
            기존 두 위젯의 objectName 문자열과 동일하게 유지된다.
        placeholder: 검색 입력창 placeholder (언어 키로 이미 해석된 문자열).
        input_tooltip: 검색 입력창 툴팁.
        prev_tooltip: 이전 버튼 툴팁.
        next_tooltip: 다음 버튼 툴팁.
        max_width: 입력창 최대 폭.
        min_width: 입력창 최소 폭 (S-026 압착 방지용, 필요한 위젯만 지정).

    Returns:
        (검색 입력창, 이전 버튼, 다음 버튼) 튜플.
    """
    search_input = QLineEdit()
    search_input.setPlaceholderText(placeholder)
    search_input.setToolTip(input_tooltip)
    search_input.setMaximumWidth(max_width)
    if min_width is not None:
        search_input.setMinimumWidth(min_width)

    prev_btn = QPushButton()
    prev_btn.setObjectName(f"{object_name_prefix}_search_prev_btn")
    prev_btn.setText("<")  # 아이콘이 없을 경우를 대비한 텍스트
    prev_btn.setToolTip(prev_tooltip)
    prev_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)

    next_btn = QPushButton()
    next_btn.setObjectName(f"{object_name_prefix}_search_next_btn")
    next_btn.setText(">")  # 아이콘이 없을 경우를 대비한 텍스트
    next_btn.setToolTip(next_tooltip)
    next_btn.setFixedSize(ICON_BUTTON_SIZE, ICON_BUTTON_SIZE)

    return search_input, prev_btn, next_btn


def create_filter_checkbox(text: str, tooltip: str) -> QCheckBox:
    """필터 체크박스를 생성합니다 (문구는 호출자가 언어 키로 주입)."""
    checkbox = QCheckBox(text)
    checkbox.setToolTip(tooltip)
    return checkbox


def create_logging_toggle_button(text: str, tooltip: str) -> QPushButton:
    """REC 토글용 checkable 버튼을 생성합니다 (문구는 호출자가 언어 키로 주입)."""
    button = QPushButton(text)
    button.setToolTip(tooltip)
    button.setCheckable(True)
    return button


def apply_recording_style(
    button: QPushButton,
    active: bool,
    inactive_text: str,
    recording_text: str = RECORDING_BUTTON_TEXT,
) -> None:
    """
    REC 토글 버튼의 텍스트와 동적 `state` 프로퍼티를 전환합니다.

    QSS `[state="recording"]` 규칙이 이 프로퍼티를 보고 배경색 등을 바꾸므로,
    값을 바꾼 뒤 반드시 `unpolish/polish`로 스타일 재적용을 트리거해야 한다
    (두 위젯이 동일하게 따르던 시퀀스).

    Args:
        button: 대상 REC 토글 버튼.
        active: True면 녹화 중 스타일, False면 평상시 스타일.
        inactive_text: 평상시 표시할 문구 (언어 키로 이미 해석된 문자열).
        recording_text: 녹화 중 표시할 문구 (기본값 "● REC", 두 위젯 공통).
    """
    if active:
        button.setText(recording_text)
        button.setProperty("state", "recording")
    else:
        button.setText(inactive_text)
        button.setProperty("state", None)
    button.style().unpolish(button)
    button.style().polish(button)


class LogSearchController:
    """
    검색 입력창과 `QSmartListView` 사이의 다음/이전 탐색·실시간 하이라이트
    배선을 캡슐화하는 얇은 컴포지션 헬퍼입니다.

    두 위젯의 `on_..._search_next_clicked` / `on_..._search_prev_clicked` /
    `on_..._search_text_changed` 슬롯 구현이 완전히 동일했던 부분만 모았다.
    상태를 소유하지 않고 주입받은 두 객체(입력창, 로그뷰)에만 위임한다.
    """

    def __init__(self, search_input: QLineEdit, log_list) -> None:
        """
        Args:
            search_input: 검색어를 입력받는 QLineEdit.
            log_list: `set_search_pattern`/`find_next`/`find_prev`를 제공하는
                `QSmartListView` (덕 타이핑 — 타입을 import하지 않아 결합을 늘리지 않음).
        """
        self._search_input = search_input
        self._log_list = log_list

    def search_next(self) -> None:
        """검색창의 텍스트로 다음 항목을 찾습니다."""
        text = self._search_input.text()
        if text:
            # 패턴 설정은 textChanged에서 실시간으로 되지만 안전을 위해 재호출.
            self._log_list.set_search_pattern(text)
            self._log_list.find_next(text)

    def search_prev(self) -> None:
        """검색창의 텍스트로 이전 항목을 찾습니다."""
        text = self._search_input.text()
        if text:
            self._log_list.find_prev(text)

    def on_text_changed(self, text: str) -> None:
        """검색어가 변경되면 하이라이트 패턴을 즉시 업데이트합니다."""
        self._log_list.set_search_pattern(text)
