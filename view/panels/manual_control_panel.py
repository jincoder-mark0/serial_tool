"""
수동 제어 패널 모듈

ManualControlWidget을 래핑하여 섹션에 통합합니다.

## WHY
* 위젯과 레이아웃 관리의 분리
* 하위 위젯 시그널의 상위 전파(Bubbling)를 통한 캡슐화 유지
* Presenter가 내부 위젯 구조를 알 필요 없도록 추상화

## WHAT
* ManualControlWidget 생성 및 배치
* 하위 위젯의 사용자 입력/제어 시그널 중계
* 상태 저장 및 복원 인터페이스 제공

## HOW
* QVBoxLayout 사용
* Signal Chain 패턴 적용 (Widget -> Panel -> Presenter)
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional

from view.widgets.manual_control import ManualControlWidget
from common.dtos import ManualCommand

class ManualControlPanel(QWidget):
    """
    수동 제어 패널 클래스

    Attributes:
        manual_control_widget (ManualControlWidget): 수동 제어 위젯 인스턴스
    """
    send_requested = pyqtSignal(object)
    rts_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.manual_control_widget: Optional[ManualControlWidget] = None
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""

        self.manual_control_widget = ManualControlWidget()

        # 시그널 연결 (Widget -> Panel)
        self.manual_control_widget.send_requested.connect(self._on_send_requested)
        self.manual_control_widget.rts_changed.connect(self.rts_changed)
        self.manual_control_widget.dtr_changed.connect(self.dtr_changed)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.addWidget(self.manual_control_widget)

        self.setLayout(layout)

    def _on_send_requested(self, command: ManualCommand) -> None:
        """
        수동 전송 요청 핸들러

        Logic:
            - Widget에서 완성된 DTO를 그대로 상위 Presenter로 전달합니다.
            - Panel 계층에서 비즈니스 로직(Broadcast 여부 판단 등)을 수행하지 않습니다.
        """
        self.send_requested.emit(command)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯 활성화/비활성화

        Args:
            enabled (bool): 활성화 여부
        """
        if self.manual_control_widget:
            self.manual_control_widget.set_controls_enabled(enabled)

    def set_local_echo_state(self, checked: bool) -> None:
        """
        Local Echo 체크박스 상태 설정 (Presenter -> View)

        Args:
            checked (bool): 체크 여부
        """
        if self.manual_control_widget:
            self.manual_control_widget.set_local_echo_state(checked)

    def save_state(self) -> dict:
        """
        패널 상태 저장

        Returns:
            dict: 저장된 상태 데이터
        """
        if self.manual_control_widget:
            return {"manual_control_widget": self.manual_control_widget.save_state()}
        return {}

    def load_state(self, state: dict) -> None:
        """
        패널 상태 복원

        Args:
            state (dict): 복원할 상태 데이터
        """
        if not state or not self.manual_control_widget:
            return
        self.manual_control_widget.load_state(state.get("manual_control_widget", {}))
