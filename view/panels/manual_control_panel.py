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

class ManualControlPanel(QWidget):
    """
    수동 제어 패널 클래스

    Attributes:
        manual_control_widget (ManualControlWidget): 수동 제어 위젯 인스턴스
    """

    # 하위 위젯 시그널 상위 전달 (Signal Bubbling)
    manual_command_send_requested = pyqtSignal(dict)
    rts_changed = pyqtSignal(bool) # RTS 상태 변경 시그널
    dtr_changed = pyqtSignal(bool) # DTR 상태 변경 시그널

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
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 수동 제어 위젯 생성
        self.manual_control_widget = ManualControlWidget()

        # 위젯 시그널 -> 패널 시그널 연결 (Forwarding)
        self.manual_control_widget.manual_command_send_requested.connect(self.manual_command_send_requested.emit)
        self.manual_control_widget.rts_changed.connect(self.rts_changed.emit)
        self.manual_control_widget.dtr_changed.connect(self.dtr_changed.emit)

        layout.addWidget(self.manual_control_widget)

        self.setLayout(layout)

    def save_state(self) -> dict:
        """
        위젯 상태 저장

        Returns:
            dict: 저장된 상태 데이터
        """
        return self.manual_control_widget.save_state()

    def load_state(self, state: dict) -> None:
        """
        위젯 상태 복원

        Args:
            state (dict): 복원할 상태 데이터
        """
        self.manual_control_widget.load_state(state)

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        연결 상태에 따라 제어 위젯 활성화/비활성화

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
        self.manual_control_widget.set_local_echo_state(checked)
