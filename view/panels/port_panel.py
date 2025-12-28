"""
포트 패널 모듈

개별 포트 탭의 메인 컨테이너로서, 설정/상태/로그 위젯을 포함합니다.
Presenter와 하위 위젯 사이의 인터페이스(Facade) 역할을 수행합니다.

## WHY
* 포트 단위의 독립적인 UI 컴포넌트 구성 (탭 내부 콘텐츠)
* 하위 위젯들의 레이아웃 및 상호작용 관리
* 다중 포트 지원을 위한 인스턴스화 가능한 구조
* Presenter가 내부 위젯 구조를 몰라도 제어할 수 있도록 캡슐화 (LoD 준수)

## WHAT
* PortSettings, PortStats, DataLog 위젯 배치
* 탭 제목 관리(커스텀 이름) 및 연결 상태 표시
* 하위 위젯 제어를 위한 Facade 메서드 및 시그널 제공
* 외부 트리거(단축키)에 의한 동작 수행 메서드 제공

## HOW
* QVBoxLayout 사용
* 하위 위젯의 시그널을 패널 시그널로 중계(Relay)
* DTO(PortConfig, PortStatistics)를 사용하여 데이터 교환
"""
from typing import Optional, List, Dict, Any

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal

from view.widgets.port_settings import PortSettingsWidget
from view.widgets.data_log import DataLogWidget
from view.widgets.port_stats import PortStatsWidget
from common.dtos import (
    PortConfig,
    PortInfo,
    PortStatistics,
    ColorRule
)

class PortPanel(QWidget):
    """
    개별 시리얼 포트 탭의 메인 위젯 클래스입니다.

    포트 설정(PortSettings), 통신 로그(DataLogWidget), 상태 로그(PortStats) 영역을 포함하며,
    외부에는 통합된 인터페이스만 노출합니다.
    """

    # -------------------------------------------------------------------------
    # Signals (Presenter 통신용)
    # -------------------------------------------------------------------------
    # 탭 관리 시그널
    tab_title_changed = pyqtSignal(str)

    # 설정 위젯 중계 시그널
    connect_requested = pyqtSignal(object)     # PortConfig DTO
    disconnect_requested = pyqtSignal()
    port_scan_requested = pyqtSignal()
    connection_changed = pyqtSignal(bool)      # 연결 상태 변경 알림

    # 로그 위젯 중계 시그널
    tx_broadcast_allowed_changed = pyqtSignal(bool)
    logging_start_requested = pyqtSignal()
    logging_stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # 내부 위젯 (캡슐화)
        self._data_log_widget: Optional[DataLogWidget] = None
        self._port_stats_widget: Optional[PortStatsWidget] = None
        self._port_settings_widget: Optional[PortSettingsWidget] = None

        self.custom_name = "Port"  # 커스텀 이름 (기본값)

        self.init_ui()

        # 내부 로직: 포트 변경 시 탭 제목 자동 업데이트
        # (이는 View 내부적인 UI 갱신 로직이므로 Presenter를 거치지 않아도 무방함)
        if self._port_settings_widget:
            self._port_settings_widget.port_combo.currentTextChanged.connect(self._on_port_changed)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            - 하위 위젯 생성
            - 시그널 중계 연결
            - 레이아웃 배치
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. 컴포넌트 생성
        self._port_settings_widget = PortSettingsWidget()
        self._port_stats_widget = PortStatsWidget()
        self._data_log_widget = DataLogWidget()

        # 2. 시그널 중계 (Widget -> Panel Signal Relay)
        # Port Settings
        self._port_settings_widget.connect_requested.connect(self.connect_requested.emit)
        self._port_settings_widget.disconnect_requested.connect(self.disconnect_requested.emit)
        self._port_settings_widget.port_scan_requested.connect(self.port_scan_requested.emit)
        self._port_settings_widget.port_connection_changed.connect(self.connection_changed.emit)

        # Data Log
        self._data_log_widget.tx_broadcast_allowed_changed.connect(self.tx_broadcast_allowed_changed.emit)
        self._data_log_widget.logging_start_requested.connect(self.logging_start_requested.emit)
        self._data_log_widget.logging_stop_requested.connect(self.logging_stop_requested.emit)

        # 3. 레이아웃 구성
        layout.addWidget(self._port_settings_widget)
        layout.addWidget(self._port_stats_widget)
        layout.addWidget(self._data_log_widget, 1) # 로그 영역이 남은 공간 차지 (Stretch)

        self.setLayout(layout)

    # -------------------------------------------------------------------------
    # Facade Interfaces (Presenter용 Getter/Setter)
    # -------------------------------------------------------------------------

    # --- Port Configuration & Connection ---

    def get_port_config(self) -> PortConfig:
        """
        현재 UI에 설정된 포트 구성 정보를 반환합니다.

        Returns:
            PortConfig: 포트 설정 DTO.
        """
        return self._port_settings_widget.get_current_config()

    def set_port_list(self, ports: List[PortInfo]) -> None:
        """
        콤보박스의 포트 목록을 갱신합니다.

        Args:
            ports (List[PortInfo]): 포트 정보 리스트.
        """
        self._port_settings_widget.set_port_list(ports)

    def set_connected(self, connected: bool) -> None:
        """
        UI의 연결 상태(버튼 스타일 등)를 변경합니다.

        Args:
            connected (bool): 연결 여부.
        """
        self._port_settings_widget.set_connected(connected)

    def toggle_connection(self) -> None:
        """연결 버튼 클릭을 시뮬레이션합니다 (단축키 등)."""
        self._port_settings_widget.toggle_connection()

    def is_connected(self) -> bool:
        """
        현재 연결 상태를 반환합니다.

        Returns:
            bool: 연결되어 있으면 True.
        """
        return self._port_settings_widget.is_connected()

    def get_port_name(self) -> str:
        """
        현재 선택된 포트 이름을 반환합니다.

        Returns:
            str: 포트 이름 (예: "COM1").
        """
        # 하위 위젯의 Getter 호출 (캡슐화 준수)
        return self._port_settings_widget.get_port_name()

    # --- Data Log & Stats ---

    def append_log_data(self, data: bytes) -> None:
        """
        로그 뷰어에 데이터를 추가합니다.

        Args:
            data (bytes): 추가할 데이터.
        """
        self._data_log_widget.append_data(data)

    def clear_data_log(self) -> None:
        """로그 뷰어를 초기화합니다."""
        self._data_log_widget.on_clear_data_log_clicked()

    def set_max_log_lines(self, max_lines: int) -> None:
        """
        최대 로그 라인 수를 설정합니다.

        Args:
            max_lines (int): 라인 수.
        """
        self._data_log_widget.set_max_lines(max_lines)

    def update_statistics(self, stats: PortStatistics) -> None:
        """
        통계 위젯을 업데이트합니다.

        Args:
            stats (PortStatistics): 통계 정보 DTO.
        """
        self._port_stats_widget.update_statistics(stats)

    def set_logging_active(self, active: bool) -> None:
        """
        로깅 활성화 상태를 설정합니다 (UI 업데이트).

        Args:
            active (bool): 활성화 여부.
        """
        self._data_log_widget.set_logging_active(active)

    def show_save_log_dialog(self) -> str:
        """
        로그 저장 파일 대화상자를 표시합니다.

        Returns:
            str: 선택된 파일 경로. (취소 시 빈 문자열)
        """
        return self._data_log_widget.show_save_log_dialog()

    def set_data_log_color_rules(self, rules: List[ColorRule]) -> None:
        """
        로그 뷰어에 색상 규칙을 설정합니다.

        Args:
            rules (List[ColorRule]): 색상 규칙 리스트.
        """
        self._data_log_widget.set_color_rules(rules)

    # --- Tab Management ---

    def get_custom_name(self) -> str:
        """커스텀 탭 이름을 반환합니다."""
        return self.custom_name

    def set_custom_name(self, name: str) -> None:
        """
        커스텀 탭 이름을 설정하고 탭 제목을 갱신합니다.

        Args:
            name (str): 새 커스텀 이름.
        """
        self.custom_name = name
        self.update_tab_title()

    def get_tab_title(self) -> str:
        """
        현재 설정에 맞는 탭 제목을 생성하여 반환합니다.
        형식: "[커스텀명]:포트명"

        Returns:
            str: 탭 제목.
        """
        port_name = self.get_port_name()
        if port_name:
            return f"{self.custom_name}:{port_name}"
        else:
            return self.custom_name

    def update_tab_title(self) -> None:
        """
        탭 제목 변경 시그널을 발생시킵니다.
        상위 컨테이너(PortTabPanel)가 이를 감지하여 실제 탭 텍스트를 변경합니다.
        """
        title = self.get_tab_title()
        # 로그 위젯의 내부 탭 이름 설정 (저장 파일명용)
        self._data_log_widget.set_tab_name(title)
        self.tab_title_changed.emit(title)

    # -------------------------------------------------------------------------
    # Trigger Actions (For Shortcuts)
    # -------------------------------------------------------------------------
    def trigger_connect(self) -> None:
        """
        연결 동작을 트리거합니다. (이미 연결되어 있으면 무시)
        단축키(F2) 등 외부 요청 시 사용됩니다.
        """
        if not self.is_connected():
            self.toggle_connection()

    def trigger_disconnect(self) -> None:
        """
        연결 해제 동작을 트리거합니다. (연결되어 있지 않으면 무시)
        단축키(F3) 등 외부 요청 시 사용됩니다.
        """
        if self.is_connected():
            self.toggle_connection()

    def trigger_log_save(self) -> None:
        """로그 저장 다이얼로그를 엽니다."""
        self._data_log_widget.on_data_log_logging_toggled(True)

    def trigger_clear_log(self) -> None:
        """
        로그 지우기 동작을 트리거합니다.
        단축키(F5) 등 외부 요청 시 사용됩니다.
        """
        self.clear_data_log()

    # -------------------------------------------------------------------------
    # Internal Slots
    # -------------------------------------------------------------------------
    def _on_port_changed(self, _port_name: str) -> None:
        """포트 콤보박스 변경 시 호출되어 탭 제목을 갱신합니다."""
        self.update_tab_title()

    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------
    def get_state(self) -> dict:
        """
        패널의 현재 상태를 딕셔너리로 반환합니다 (저장용).

        Returns:
            dict: 패널 상태 데이터.
        """
        return {
            "custom_name": self.custom_name,
            "port_settings_widget": self._port_settings_widget.get_state(),
            "data_log_widget": self._data_log_widget.get_state()
        }

    def apply_state(self, state: dict) -> None:
        """
        저장된 상태를 패널에 적용합니다 (복원용).

        Args:
            state (dict): 패널 상태 데이터.
        """
        if not state:
            return

        self.custom_name = state.get("custom_name", "Port")

        # 하위 위젯 상태 복원
        self._port_settings_widget.apply_state(state.get("port_settings_widget", {}))
        self._data_log_widget.apply_state(state.get("data_log_widget", {}))

        # 제목 갱신
        self.update_tab_title()