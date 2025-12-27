"""
수동 제어 패널 모듈

수동 제어 위젯(ManualControlWidget)을 포함하는 컨테이너 패널입니다.
Presenter와 Widget 사이의 인터페이스(Facade) 역할을 수행합니다.

## WHY
* UI 계층 구조(Section -> Panel -> Widget) 준수
* 레이아웃 관리 및 확장성 확보
* Presenter가 구체적인 위젯 구현(Checkbox 이름 등)을 알지 못하게 하여 결합도 감소 (LoD 준수)

## WHAT
* ManualControlWidget 배치 및 레이아웃 구성
* 시그널 중계 (Widget -> Panel -> Presenter)
* 하위 위젯의 상태를 조회하거나 설정하는 Facade 메서드 제공
* 상태 복원 메서드(apply_state) 제공

## HOW
* QVBoxLayout을 사용하여 위젯 배치
* Presenter가 호출할 수 있는 Getter/Setter 메서드 정의
* 시그널을 재발행(Re-emit)하여 계층 간 통신
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
    send_requested = pyqtSignal(object)  # ManualCommand DTO (혹은 None)

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

        # 시그널 연결 (Widget -> Panel Signal Relay)
        # 위젯의 시그널을 패널의 시그널로 바로 연결하여 중계
        # self.manual_control_widget.send_requested.connect(self._on_send_requested)
        self._manual_control_widget.send_requested.connect(self.send_requested.emit)

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
        return self._manual_control_widget.hex_chk.isChecked()

    def is_prefix_enabled(self) -> bool:
        """Prefix 사용 여부를 반환합니다."""
        return self._manual_control_widget.prefix_chk.isChecked()

    def is_suffix_enabled(self) -> bool:
        """Suffix 사용 여부를 반환합니다."""
        return self._manual_control_widget.suffix_chk.isChecked()

    def is_rts_enabled(self) -> bool:
        """RTS 체크 여부를 반환합니다."""
        return self._manual_control_widget.rts_chk.isChecked()

    def is_dtr_enabled(self) -> bool:
        """DTR 체크 여부를 반환합니다."""
        return self._manual_control_widget.dtr_chk.isChecked()

    def is_local_echo_enabled(self) -> bool:
        """Local Echo 체크 여부를 반환합니다."""
        return self._manual_control_widget.local_echo_chk.isChecked()

    def is_broadcast_enabled(self) -> bool:
        """Broadcast 체크 여부를 반환합니다."""
        return self._manual_control_widget.broadcast_chk.isChecked()

    def set_input_focus(self) -> None:
        """입력창에 포커스를 설정합니다."""
        self._manual_control_widget.set_input_focus()

    def _on_send_requested(self) -> None:
        """
        위젯의 전송 요청 처리 핸들러

        Logic:
            1. 위젯의 현재 상태(입력값, 체크박스 등)를 조회
            2. ManualCommand DTO 생성
            3. send_requested 시그널을 통해 Presenter로 DTO 전달
        """
        widget = self.manual_control_widget

        # DTO 생성
        command_dto = ManualCommand(
            command=widget.input_edit.text(),
            hex_mode=widget.hex_chk.isChecked(),
            prefix_enabled=widget.prefix_chk.isChecked(),
            suffix_enabled=widget.suffix_chk.isChecked(),
            broadcast_enabled=widget.broadcast_chk.isChecked(),
            local_echo_enabled=True # 로컬 에코는 기본적으로 활성화 (Presenter 설정에 따름)
        )

        # Presenter로 전달
        self.send_requested.emit(command_dto)

        # 편의성: 전송 후 포커스 유지 및 텍스트 선택 (입력 편의성)
        widget.input_edit.selectAll()
        widget.input_edit.setFocus()

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