from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional

from view.widgets.port_settings import PortSettingsWidget
from view.widgets.rx_log import RxLogWidget
# from view.widgets.system_log import SystemLogWidget
from view.widgets.port_stats import PortStatsWidget

class PortPanel(QWidget):
    """
    개별 시리얼 포트 탭의 메인 위젯 클래스입니다.
    포트 설정(PortSettings), 수신 로그(ReceivedArea), 상태 로그(StatusArea) 영역을 포함합니다.
    """

    # 시그널 정의
    tab_title_changed = pyqtSignal(str)  # 탭 제목 변경 시그널

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        # self.system_log_widget = None
        self.received_area_widget = None
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
        self.received_area_widget = RxLogWidget()
        # self.system_log_widget = SystemLogWidget() # Global로 이동

        # 레이아웃 구성
        # 상단: 설정 (Top: Settings)
        layout.addWidget(self.port_settings_widget)

        # 상태 패널 (Status Panel)
        layout.addWidget(self.port_stats_widget)

        # 중간: 로그 (Middle: Log)
        layout.addWidget(self.received_area_widget, 1) # Stretch 1

        # 하단: 상태 로그 영역 (Bottom: Status Log Area)
        # layout.addWidget(self.system_log_widget) # Global로 이동

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

        Returns:
            str: 포트 이름.
        """
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
        self.received_area_widget.set_tab_name(title)
        self.tab_title_changed.emit(title)

    def save_state(self) -> dict:
        """
        패널 상태를 저장합니다.

        Returns:
            dict: 패널 상태 데이터.
        """
        return {
            "custom_name": self.custom_name,
            "port_settings_widget": self.port_settings_widget.save_state(),
            "received_area_widget": self.received_area_widget.save_state()
        }

    def load_state(self, state: dict) -> None:
        """
        패널 상태를 복원합니다.

        Args:
            state (dict): 패널 상태 데이터.
        """
        if not state:
            return
        self.custom_name = state.get("custom_name", "Port")
        self.port_settings_widget.load_state(state.get("port_settings_widget", {}))
        self.received_area_widget.load_state(state.get("received_area_widget", {}))
        self.update_tab_title()

