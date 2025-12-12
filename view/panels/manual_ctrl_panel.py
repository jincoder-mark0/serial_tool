"""
수동 제어 패널 모듈

ManualCtrlWidget을 래핑하여 섹션에 통합합니다.

## WHY
* 위젯과 레이아웃 관리의 분리
* 하위 위젯 시그널의 상위 전파(Bubbling)

## WHAT
* ManualCtrlWidget 생성 및 배치
* 시그널 중계
* 상태 저장 및 복원 인터페이스

## HOW
* QVBoxLayout 사용
* Signal Chain 패턴 적용
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional
from view.widgets.manual_ctrl import ManualCtrlWidget

class ManualCtrlPanel(QWidget):
    """
    수동 제어 패널 클래스

    Attributes:
        manual_ctrl_widget (ManualCtrlWidget): 수동 제어 위젯 인스턴스
    """

    # 하위 위젯 시그널 상위 전달 (Signal Bubbling)
    manual_cmd_send_requested = pyqtSignal(str, bool, bool, bool, bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualCtrlPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.manual_ctrl_widget = None
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.manual_ctrl_widget = ManualCtrlWidget()

        # 위젯 시그널 -> 패널 시그널 연결
        self.manual_ctrl_widget.manual_cmd_send_requested.connect(self.manual_cmd_send_requested.emit)

        layout.addWidget(self.manual_ctrl_widget)

        self.setLayout(layout)

    def save_state(self) -> dict:
        """
        위젯 상태 저장

        Returns:
            dict: 저장된 상태 데이터
        """
        return self.manual_ctrl_widget.save_state()

    def load_state(self, state: dict) -> None:
        """
        위젯 상태 복원

        Args:
            state (dict): 복원할 상태 데이터
        """
        self.manual_ctrl_widget.load_state(state)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯 활성화 상태 설정

        Args:
            enabled (bool): 활성화 여부
        """
        self.manual_ctrl_widget.set_controls_enabled(enabled)
