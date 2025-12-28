"""
수동 제어 패널 모듈

수동 제어 위젯(ManualControlWidget)을 포함하는 컨테이너 패널입니다.
Presenter와 Widget 사이의 인터페이스(Facade) 역할을 수행하며,
사용자 입력을 DTO로 변환하여 상위로 전달하는 Push 모델을 구현합니다.

## WHY
* UI 계층 구조(Section -> Panel -> Widget) 준수
* 레이아웃 관리 및 확장성 확보
* Presenter가 구체적인 위젯 구현을 알지 못하게 하여 결합도 감소 (LoD 준수)
* 사용자 의도를 DTO로 캡슐화하여 전달 (Data Push)

## WHAT
* ManualControlWidget 배치 및 레이아웃 구성
* 시그널 중계 (Widget -> Panel -> Presenter)
* 하위 위젯의 상태를 조회하거나 설정하는 Facade 메서드 제공
* 전송 요청 시 ManualCommand DTO 생성 및 발송

## HOW
* QVBoxLayout을 사용하여 위젯 배치
* Presenter가 호출할 수 있는 Getter/Setter 메서드 정의
* _on_send_requested에서 위젯 상태를 수집하여 DTO 생성
"""
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal

from view.managers.language_manager import language_manager
from view.widgets.manual_control import ManualControlWidget
from common.dtos import ManualCommand, ManualControlState


class ManualControlPanel(QWidget):
    """
    수동 제어 패널 클래스

    ManualControlWidget을 감싸고 있으며, Presenter와의 통신을 위한
    시그널 및 상태 조회 인터페이스(Facade)를 정의합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 시그널 정의 (Widget -> Presenter 중계)
    # DTO를 실어 보내므로 object 타입 사용
    send_requested = pyqtSignal(object)  # ManualCommand DTO

    broadcast_changed = pyqtSignal(bool)
    dtr_changed = pyqtSignal(bool)
    rts_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        ManualControlPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)

        # UI 컴포넌트
        self.title_lbl: Optional[QLabel] = None
        self._manual_control_widget: Optional[ManualControlWidget] = None

        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 구성 및 레이아웃 설정"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 타이틀
        self.title_lbl = QLabel(language_manager.get_text("manual_panel_title"))
        self.title_lbl.setProperty("class", "section-title")

        # 수동 제어 위젯 생성
        # 내부 변수명에 밑줄(_)을 붙여 외부 직접 접근을 지양함 (캡슐화 의도)
        self._manual_control_widget = ManualControlWidget()

        # 시그널 연결
        # 1. 전송 요청은 Panel이 가로채서 DTO를 확인하거나 로직을 추가할 수 있도록 내부 핸들러 연결
        # (혹은 위젯이 이미 DTO를 보낸다면 바로 중계해도 되지만, 여기서는 Panel이 DTO 생성을 보장)
        self._manual_control_widget.send_requested.connect(self._on_send_requested_relay)

        # 2. 상태 변경 시그널은 바로 중계
        self._manual_control_widget.broadcast_changed.connect(self.broadcast_changed.emit)
        self._manual_control_widget.dtr_changed.connect(self.dtr_changed.emit)
        self._manual_control_widget.rts_changed.connect(self.rts_changed.emit)

        layout.addWidget(self.title_lbl)
        layout.addWidget(self._manual_control_widget)
        layout.addStretch()  # 하단 여백 확보

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 텍스트 업데이트"""
        self.title_lbl.setText(language_manager.get_text("manual_panel_title"))
        # 하위 위젯은 자체적으로 갱신됨

    # -------------------------------------------------------------------------
    # Facade Interfaces (Presenter용 Getter/Setter)
    # -------------------------------------------------------------------------
    def set_controls_enabled(self, enabled: bool) -> None:
        """
        제어 위젯의 전송 버튼 활성화 상태를 변경합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self._manual_control_widget.set_controls_enabled(enabled)

    def set_local_echo_checked(self, checked: bool) -> None:
        """
        로컬 에코 체크박스 상태를 설정합니다.

        Args:
            checked (bool): 체크 여부.
        """
        self._manual_control_widget.set_local_echo_state(checked)

    def get_input_text(self) -> str:
        """
        현재 입력창의 텍스트를 반환합니다.

        Returns:
            str: 입력된 명령어 텍스트.
        """
        return self._manual_control_widget.get_input_text()

    def set_input_text(self, text: str) -> None:
        """
        입력창의 텍스트를 설정합니다.

        Args:
            text (str): 설정할 텍스트.
        """
        self._manual_control_widget.set_input_text(text)

    def is_hex_mode(self) -> bool:
        """HEX 모드 체크 여부를 반환합니다."""
        return self._manual_control_widget.is_hex_mode()

    def is_prefix_enabled(self) -> bool:
        """Prefix 사용 여부를 반환합니다."""
        return self._manual_control_widget.is_prefix_enabled()

    def is_suffix_enabled(self) -> bool:
        """Suffix 사용 여부를 반환합니다."""
        return self._manual_control_widget.is_suffix_enabled()

    def is_rts_enabled(self) -> bool:
        """RTS 체크 여부를 반환합니다."""
        return self._manual_control_widget.is_rts_enabled()

    def is_dtr_enabled(self) -> bool:
        """DTR 체크 여부를 반환합니다."""
        return self._manual_control_widget.is_dtr_enabled()

    def is_local_echo_enabled(self) -> bool:
        """Local Echo 체크 여부를 반환합니다."""
        return self._manual_control_widget.is_local_echo_enabled()

    def is_broadcast_enabled(self) -> bool:
        """Broadcast 체크 여부를 반환합니다."""
        return self._manual_control_widget.is_broadcast_enabled()

    def set_input_focus(self) -> None:
        """입력창에 포커스를 설정합니다."""
        self._manual_control_widget.set_input_focus()

    def _on_send_requested_relay(self, command_dto: ManualCommand) -> None:
        """
        위젯의 전송 요청 시그널을 중계합니다.

        Logic:
            - ManualControlWidget이 이미 ManualCommand DTO를 생성해서 보냅니다.
            - Panel은 이를 받아서 그대로 상위로 emit 합니다.
            - 만약 위젯이 DTO를 안 보냈다면(None), 여기서 생성해서 보낼 수도 있습니다(안전장치).

        Args:
            command_dto (ManualCommand): 전송할 명령어 정보.
        """
        if command_dto and isinstance(command_dto, ManualCommand):
             self.send_requested.emit(command_dto)
        else:
             # 위젯이 DTO를 제대로 안 만들었을 경우를 대비한 Fallback (또는 위젯이 구형일 경우)
             # 현재 구조상 위젯이 DTO를 만들도록 되어 있으므로 이 로직은 방어 코드임
             new_dto = ManualCommand(
                command=self.get_input_text(),
                hex_mode=self.is_hex_mode(),
                prefix_enabled=self.is_prefix_enabled(),
                suffix_enabled=self.is_suffix_enabled(),
                local_echo_enabled=self.is_local_echo_enabled(),
                broadcast_enabled=self.is_broadcast_enabled()
             )
             self.send_requested.emit(new_dto)

        # 편의성: 전송 후 포커스 유지 (Widget 내부에서 처리하기도 하지만 확실히 하기 위함)
        self.set_input_focus()

    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------
    def get_state(self) -> ManualControlState:
        """
        현재 패널의 상태를 DTO로 반환합니다. (저장용)

        Returns:
            ManualControlState: 상태 DTO.
        """
        return self._manual_control_widget.get_state()

    def apply_state(self, state: ManualControlState) -> None:
        """
        상태 DTO를 위젯에 적용합니다. (복원용)

        Args:
            state (ManualControlState): 복원할 상태 DTO.
        """
        if not isinstance(state, ManualControlState):
            return

        self._manual_control_widget.apply_state(state)