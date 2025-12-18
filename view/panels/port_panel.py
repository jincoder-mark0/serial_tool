"""
포트 패널 모듈

개별 포트 탭의 메인 컨테이너로서, 설정/상태/로그 위젯을 포함합니다.

## WHY
* 포트 단위의 독립적인 UI 컴포넌트 구성 (탭 내부 콘텐츠)
* 하위 위젯들의 레이아웃 및 상호작용 관리
* 다중 포트 지원을 위한 인스턴스화 가능한 구조

## WHAT
* PortSettings, PortStats, DataLog 위젯 배치
* 탭 제목 관리(커스텀 이름) 및 연결 상태 표시
* 데이터 로그 추가 인터페이스

## HOW
* QVBoxLayout 사용
* 하위 위젯의 시그널을 집계하여 Presenter로 전달하거나 내부 처리
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional

from view.widgets.port_settings import PortSettingsWidget
from view.widgets.data_log import DataLogWidget
from view.widgets.port_stats import PortStatsWidget

class PortPanel(QWidget):
    """
    개별 시리얼 포트 탭의 메인 위젯 클래스입니다.
    포트 설정(PortSettings), 통신 로그(DataLogWidget), 상태 로그(PortStats) 영역을 포함합니다.
    """

    # 시그널 정의
    tab_title_changed = pyqtSignal(str)  # 탭 제목 변경 시그널
    broadcast_allow_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.data_log_widget = None
        self.port_stats_widget = None
        self.port_settings_widget = None
        self.custom_name = "Port"  # 커스텀 이름 (기본값)
        self.init_ui()

        # 포트 변경 시 탭 제목 업데이트
        self.port_settings_widget.port_combo.currentTextChanged.connect(self._on_port_changed)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 컴포넌트 생성
        self.port_settings_widget = PortSettingsWidget()
        self.port_stats_widget = PortStatsWidget()
        self.data_log_widget = DataLogWidget()

        self.data_log_widget.tx_broadcast_allow_changed.connect(self.broadcast_allow_changed.emit)

        # 레이아웃 구성
        # 상단: 설정 (Top: Settings)
        layout.addWidget(self.port_settings_widget)

        # 상태 패널 (Status Panel)
        layout.addWidget(self.port_stats_widget)

        # 중간: 로그 (Middle: Log)
        layout.addWidget(self.data_log_widget, 1) # Stretch 1

        self.setLayout(layout)

    def toggle_connection(self) -> None:
        """연결 상태를 토글합니다."""
        self.port_settings_widget.toggle_connection()

    def is_connected(self) -> bool:
        """현재 연결 상태를 반환합니다."""
        return self.port_settings_widget.is_connected()

    def _on_port_changed(self, port_name: str) -> None:
        """포트 변경 시 탭 제목을 업데이트합니다."""
        self.update_tab_title()

    def set_custom_name(self, name: str) -> None:
        """
        커스텀 이름을 설정합니다.

        Args:
            name (str): 커스텀 이름.
        """
        self.custom_name = name
        self.update_tab_title()

    def get_custom_name(self) -> str:
        """
        커스텀 이름을 반환합니다.

        Returns:
            str: 커스텀 이름.
        """
        return self.custom_name

    def get_port_name(self) -> str:
        """
        현재 선택된 포트 이름을 반환합니다.

        Logic:
            - 콤보박스의 텍스트(예: "COM1 (Serial Port)") 대신
            - 내부 데이터(예: "COM1")를 우선적으로 반환하여 설명 문자열을 제외합니다.

        Returns:
            str: 포트 이름.
        """
        # [Fix] Use itemData (clean port name) instead of currentText (display text with description)
        port_data = self.port_settings_widget.port_combo.currentData()
        if port_data:
            return str(port_data)
        return self.port_settings_widget.port_combo.currentText()

    def get_tab_title(self) -> str:
        """
        탭 제목을 생성합니다 ("[커스텀명]:포트명" 형식).

        Returns:
            str: 탭 제목.
        """
        port_name = self.get_port_name()
        if port_name:
            return f"{self.custom_name}:{port_name}"
        else:
            return self.custom_name

    def update_tab_title(self) -> None:
        """탭 제목 변경 시그널을 발생시킵니다."""
        title = self.get_tab_title()
        self.data_log_widget.set_tab_name(title)
        self.tab_title_changed.emit(title)

    def get_state(self) -> dict:
        """
        패널 상태 반환

        Returns:
            dict: 패널 상태 데이터.
        """
        return {
            "custom_name": self.custom_name,
            "port_settings_widget": self.port_settings_widget.get_state(),
            "data_log_widget": self.data_log_widget.get_state() # DataLogWidget은 내부적으로 get_state 유지
        }

    def apply_state(self, state: dict) -> None:
        """
        패널 상태 적용

        Args:
            state (dict): 패널 상태 데이터.
        """
        if not state:
            return
        self.custom_name = state.get("custom_name", "Port")
        self.port_settings_widget.apply_state(state.get("port_settings_widget", {}))
        self.data_log_widget.apply_state(state.get("data_log_widget", {})) # DataLogWidget은 내부적으로 apply_state 유지
        self.update_tab_title()
