"""
뷰 인터페이스 정의 모듈

View 계층의 구체적인 구현체(Widget, Panel)와 Presenter 사이의 결합도를 낮추기 위해
Python의 `typing.Protocol`을 사용하여 추상 인터페이스를 정의합니다.

## WHY
* **의존성 역전 (DIP)**: Presenter가 구체적인 UI(Qt Widget)가 아닌 추상 인터페이스에 의존하도록 함.
* **테스트 용이성**: UI 없이 Mock 객체나 가짜 객체(Fake Object)를 사용하여 Presenter 로직을 독립적으로 테스트 가능.
* **유연성**: 향후 UI 라이브러리가 변경되거나 구조가 바뀌어도 Presenter 코드를 보호.

## WHAT
* 각 Presenter가 필요로 하는 View의 기능(메서드, 시그널)을 Protocol로 정의.
* IMainView, IPortView, IMacroView, IPacketView, IManualControlView 등.

## HOW
* `typing.Protocol`을 상속받아 구조적 타이핑(Structural Subtyping) 구현.
* DTO(Data Transfer Object)를 활용하여 데이터 교환 포맷 명시.

## SYNTAX NOTE (Python Ellipsis)
* 메서드 본문에 사용된 `...`은 파이썬 내장 객체인 `Ellipsis`입니다.
* `typing.Protocol`이나 추상 클래스 정의 시, **"구현부는 생략하고 타입 시그니처만 정의함"**을 명시하는 표준 문법입니다.
* `pass`와 기능적으로 동일하지만, "인터페이스 정의(Stub)"라는 의미를 시각적으로 더 명확하게 전달합니다.
"""
from typing import Protocol, List, Any, Optional, Dict, Callable
from common.dtos import (
    PortConfig,
    PortInfo,
    PortStatistics,
    ManualCommand,
    ManualControlState,
    MacroEntry,
    MacroScriptData,
    MacroExecutionRequest,
    PacketViewData,
    SystemLogEvent,
    ColorRule,
    LogDataBatch,
    FontConfig,
    MainWindowState,
    PreferencesState
)


class IViewSignal(Protocol):
    """
    View에서 발생하는 시그널(이벤트)을 추상화한 프로토콜입니다.
    PyQt5.QtCore.pyqtSignal과 호환되는 인터페이스를 가집니다.
    """
    def connect(self, slot: Any) -> None:
        """슬롯(핸들러)을 시그널에 연결합니다."""
        ...

    def emit(self, *args: Any) -> None:
        """시그널을 방출합니다."""
        ...


class IManualControlView(Protocol):
    """
    수동 제어 뷰(ManualControlPanel)가 구현해야 할 인터페이스입니다.
    """
    # Signals
    send_requested: IViewSignal       # ManualCommand DTO 전달
    broadcast_changed: IViewSignal    # bool 전달
    dtr_changed: IViewSignal          # bool 전달
    rts_changed: IViewSignal          # bool 전달

    def set_controls_enabled(self, enabled: bool) -> None:
        """제어 위젯 활성화 상태 설정"""
        ...

    def set_local_echo_checked(self, checked: bool) -> None:
        """로컬 에코 체크박스 상태 설정"""
        ...

    def get_input_text(self) -> str:
        """입력창 텍스트 조회"""
        ...

    def set_input_text(self, text: str) -> None:
        """입력창 텍스트 설정"""
        ...

    def is_hex_mode(self) -> bool:
        """HEX 모드 여부 조회"""
        ...

    def is_prefix_enabled(self) -> bool:
        """Prefix 사용 여부 조회"""
        ...

    def is_suffix_enabled(self) -> bool:
        """Suffix 사용 여부 조회"""
        ...

    def is_rts_enabled(self) -> bool:
        """RTS 상태 조회"""
        ...

    def is_dtr_enabled(self) -> bool:
        """DTR 상태 조회"""
        ...

    def is_local_echo_enabled(self) -> bool:
        """Local Echo 상태 조회"""
        ...

    def is_broadcast_enabled(self) -> bool:
        """Broadcast 상태 조회"""
        ...

    def set_input_focus(self) -> None:
        """입력창 포커스 설정"""
        ...

    def get_state(self) -> ManualControlState:
        """현재 상태 DTO 반환"""
        ...

    def apply_state(self, state: ManualControlState) -> None:
        """상태 DTO 적용"""
        ...


class IPortView(Protocol):
    """
    개별 포트 패널(PortPanel)이 구현해야 할 인터페이스입니다.
    """
    # Signals
    connect_requested: IViewSignal      # PortConfig DTO 전달
    disconnect_requested: IViewSignal   # 인자 없음
    port_scan_requested: IViewSignal    # 인자 없음
    connection_changed: IViewSignal     # bool 전달
    tx_broadcast_allowed_changed: IViewSignal # bool 전달
    logging_start_requested: IViewSignal # 인자 없음
    logging_stop_requested: IViewSignal  # 인자 없음

    def get_port_config(self) -> PortConfig:
        """현재 UI 설정된 포트 구성 정보 반환"""
        ...

    def set_port_list(self, ports: List[PortInfo]) -> None:
        """포트 목록 갱신"""
        ...

    def set_connected(self, connected: bool) -> None:
        """연결 상태에 따른 UI 변경"""
        ...

    def is_connected(self) -> bool:
        """현재 연결 상태 반환"""
        ...

    def get_port_name(self) -> str:
        """선택된 포트 이름 반환"""
        ...

    def append_log_data(self, data: bytes) -> None:
        """로그 뷰어에 데이터 추가"""
        ...

    def clear_data_log(self) -> None:
        """로그 뷰어 초기화"""
        ...

    def set_max_log_lines(self, max_lines: int) -> None:
        """최대 로그 라인 수 설정"""
        ...

    def update_statistics(self, stats: PortStatistics) -> None:
        """통계 정보 업데이트"""
        ...

    def set_logging_active(self, active: bool) -> None:
        """로깅 활성화 상태 UI 반영"""
        ...

    def show_save_log_dialog(self) -> str:
        """로그 저장 다이얼로그 표시 및 경로 반환"""
        ...

    def set_data_log_color_rules(self, rules: List[ColorRule]) -> None:
        """로그 뷰어 색상 규칙 설정"""
        ...

    def get_state(self) -> Dict[str, Any]:
        """패널 상태 반환"""
        ...

    def apply_state(self, state: Dict[str, Any]) -> None:
        """패널 상태 적용"""
        ...

    # --- Trigger Actions (For Shortcuts) ---
    def trigger_connect(self) -> None:
        """연결 동작 트리거"""
        ...

    def trigger_disconnect(self) -> None:
        """연결 해제 동작 트리거"""
        ...

    def trigger_clear_log(self) -> None:
        """로그 지우기 동작 트리거"""
        ...


class IPortContainerView(Protocol):
    """
    포트 탭 관리자(MainLeftSection/PortTabPanel)가 구현해야 할 인터페이스입니다.
    """
    # Signals
    port_tab_added: IViewSignal         # IPortView(또는 구현체) 전달
    current_tab_changed: IViewSignal    # int 전달 (인덱스)

    def get_port_tabs_count(self) -> int:
        """현재 탭 개수 반환"""
        ...

    def get_port_panel_at(self, index: int) -> Optional[IPortView]:
        """특정 인덱스의 포트 뷰 반환"""
        ...

    def get_current_port_panel(self) -> Optional[IPortView]:
        """현재 활성화된 포트 뷰 반환"""
        ...

    def get_current_port_name(self) -> str:
        """현재 활성 포트 이름 반환"""
        ...

    def is_current_port_connected(self) -> bool:
        """현재 활성 포트 연결 여부 반환"""
        ...

    def add_new_port_tab(self) -> None:
        """새 탭 추가"""
        ...

    def append_rx_data(self, batch: LogDataBatch) -> None:
        """데이터 수신 처리 (라우팅)"""
        ...

    def log_system_message(self, event: SystemLogEvent) -> None:
        """시스템 로그 출력"""
        ...

    def connect_tab_changed_signal(self, slot: Callable[[int], None]) -> None:
        """탭 변경 시그널 연결"""
        ...

    # --- Trigger Actions (For Shortcuts) ---
    def trigger_current_port_connect(self) -> None:
        """현재 탭의 연결 동작 트리거"""
        ...

    def trigger_current_port_disconnect(self) -> None:
        """현재 탭의 연결 해제 동작 트리거"""
        ...

    def trigger_current_port_clear_log(self) -> None:
        """현재 탭의 로그 지우기 동작 트리거"""
        ...


class IMacroView(Protocol):
    """
    매크로 패널(MacroPanel)이 구현해야 할 인터페이스입니다.
    """
    # Signals
    repeat_start_requested: IViewSignal  # MacroExecutionRequest DTO
    repeat_stop_requested: IViewSignal   # 인자 없음
    repeat_pause_requested: IViewSignal  # 인자 없음
    script_save_requested: IViewSignal   # MacroScriptData DTO
    script_load_requested: IViewSignal   # str (path)
    broadcast_changed: IViewSignal       # bool
    send_row_requested: IViewSignal      # int, MacroEntry

    def set_controls_enabled(self, enabled: bool) -> None:
        """제어 위젯 활성화 상태 설정"""
        ...

    def is_broadcast_enabled(self) -> bool:
        """브로드캐스트 활성화 여부 반환"""
        ...

    def get_macro_entries(self) -> List[MacroEntry]:
        """매크로 목록 데이터 반환"""
        ...

    def set_current_row(self, row: int) -> None:
        """현재 실행 행 하이라이트"""
        ...

    def set_running_state(self, running: bool, is_repeat: bool = False) -> None:
        """실행 상태에 따른 UI 변경"""
        ...

    def update_auto_count(self, current: int, total: int) -> None:
        """반복 횟수 업데이트"""
        ...

    def show_info(self, title: str, message: str) -> None:
        """정보 메시지 박스 표시"""
        ...

    def show_error(self, title: str, message: str) -> None:
        """에러 메시지 박스 표시"""
        ...

    def get_state(self) -> Dict[str, Any]:
        """상태 반환"""
        ...

    def apply_state(self, state: Dict[str, Any]) -> None:
        """상태 적용"""
        ...


class IPacketView(Protocol):
    """
    패킷 패널(PacketPanel)이 구현해야 할 인터페이스입니다.
    """
    # Signals
    clear_requested: IViewSignal
    capture_toggled: IViewSignal  # bool

    def set_buffer_size(self, size: int) -> None:
        """버퍼 크기 설정"""
        ...

    def set_autoscroll(self, enabled: bool) -> None:
        """자동 스크롤 설정"""
        ...

    def set_capture_state(self, enabled: bool) -> None:
        """캡처 상태 UI 반영"""
        ...

    def append_packet(self, data: PacketViewData) -> None:
        """패킷 데이터 추가"""
        ...

    def clear_view(self) -> None:
        """뷰 초기화"""
        ...


class IMainView(Protocol):
    """
    메인 윈도우(MainWindow)가 구현해야 할 인터페이스입니다.
    """
    # Signals
    close_requested: IViewSignal
    settings_save_requested: IViewSignal     # PreferencesState
    preferences_requested: IViewSignal
    font_settings_changed: IViewSignal       # FontConfig
    shortcut_connect_requested: IViewSignal
    shortcut_disconnect_requested: IViewSignal
    shortcut_clear_requested: IViewSignal
    file_transfer_dialog_opened: IViewSignal # dialog object, target_port
    port_tab_added: IViewSignal              # PortPanel Widget

    # Sub-Views Accessors
    @property
    def port_view(self) -> IPortContainerView:
        """포트 컨테이너 뷰 인터페이스 반환"""
        ...

    @property
    def macro_view(self) -> IMacroView:
        """매크로 뷰 인터페이스 반환"""
        ...

    @property
    def packet_view(self) -> IPacketView:
        """패킷 뷰 인터페이스 반환"""
        ...

    @property
    def manual_control_view(self) -> IManualControlView:
        """수동 제어 뷰 인터페이스 반환"""
        ...

    # Methods
    def apply_state(self, state: MainWindowState, font_config: FontConfig) -> None:
        """상태 및 폰트 설정 적용"""
        ...

    def get_window_state(self) -> MainWindowState:
        """현재 윈도우 상태 반환"""
        ...

    def log_system_message(self, event: SystemLogEvent) -> None:
        """시스템 로그 기록"""
        ...

    def update_status_bar_stats(self, stats: PortStatistics) -> None:
        """상태바 통계 업데이트"""
        ...

    def update_status_bar_time(self, time_str: str) -> None:
        """상태바 시간 업데이트"""
        ...

    def update_status_bar_port(self, port_name: str, connected: bool) -> None:
        """상태바 포트 상태 업데이트"""
        ...

    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """상태바 메시지 표시"""
        ...

    def show_alert_message(self, title: str, message: str) -> None:
        """경고 메시지 표시"""
        ...

    def append_local_echo_data(self, data: bytes) -> None:
        """로컬 에코 데이터 추가"""
        ...

    def append_rx_data(self, batch: LogDataBatch) -> None:
        """수신 데이터 추가 (Fast Path)"""
        ...

    def connect_port_tab_changed(self, slot: Callable[[int], None]) -> None:
        """탭 변경 시그널 연결"""
        ...

    def is_current_port_connected(self) -> bool:
        """현재 탭 연결 상태 확인"""
        ...

    def open_preferences_dialog(self, state: PreferencesState) -> None:
        """설정 다이얼로그 표시"""
        ...

    def get_port_tabs_count(self) -> int:
        """현재 열려있는 포트 탭의 개수를 반환합니다."""
        ...

    def get_port_tab_widget(self, index: int) -> Any:
        """
        인덱스에 해당하는 포트 탭 위젯(IPortView 구현체)을 반환합니다.
        (초기화/Wiring 단계에서 사용)
        """
        ...