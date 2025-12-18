"""
수동 제어 프레젠터 모듈

사용자의 수동 입력 및 포트 제어 신호를 처리하는 Presenter입니다.

## WHY
* View와 Model 사이의 중재자 역할
* 입력 데이터 가공(Prefix/Suffix/Hex) 로직 중앙화

## WHAT
* 수동 전송 요청 처리 및 데이터 가공
* RTS/DTR 상태 변경 요청 처리
* Local Echo 설정 관리

## HOW
* CommandProcessor를 통한 데이터 가공
* ConnectionController 메서드 호출
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional
from view.panels.manual_control_panel import ManualControlPanel
from model.connection_controller import ConnectionController
from common.dtos import ManualCommand, ManualControlState
from core.settings_manager import SettingsManager
from core.command_processor import CommandProcessor
from core.logger import logger
from common.constants import ConfigKeys

class ManualControlPresenter(QObject):
    """
    수동 제어 로직을 담당하는 Presenter 클래스
    """

    def __init__(
        self,
        view: ManualControlPanel,
        connection_controller: ConnectionController,
        local_echo_callback: Optional[Callable[[bytes], None]] = None,
        get_active_port_callback: Optional[Callable[[], Optional[str]]] = None
    ) -> None:
        """
        ManualControlPresenter 초기화

        Args:
            view (ManualControlPanel): 수동 제어 패널 View
            connection_controller (ConnectionController): 연결 제어 Model
            local_echo_callback (Callable): Local Echo 콜백
            get_active_port_callback (Callable): 현재 활성 포트 이름을 반환하는 콜백
        """
        super().__init__()
        self.view = view
        self.connection_controller = connection_controller
        self.local_echo_callback = local_echo_callback
        self.get_active_port = get_active_port_callback
        self.settings_manager = SettingsManager()

        # View 시그널 연결
        self.view.send_requested.connect(self.on_send_requested)
        self.view.rts_changed.connect(self.on_rts_changed)
        self.view.dtr_changed.connect(self.on_dtr_changed)

        self._apply_initial_settings()

    def set_enabled(self, enabled: bool) -> None:
        """
        수동 제어 패널 활성화/비활성화 (MainPresenter에서 호출)

        Args:
            enabled (bool): 활성화 여부
        """
        self.view.set_controls_enabled(enabled)

    def _apply_initial_settings(self) -> None:
        """초기 실행 시 설정값 적용"""
        default_echo = self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False)
        self.update_local_echo_setting(default_echo)

    def update_local_echo_setting(self, enabled: bool) -> None:
        """
        설정 변경 시 Local Echo 상태를 View에 반영합니다.

        Args:
            enabled (bool): Local Echo 활성화 여부
        """
        self.view.set_local_echo_state(enabled)

    def on_send_requested(self, command: ManualCommand) -> None:
        """
        수동 명령 전송 요청 처리

        Logic:
            - 활성 포트 조회
            - 연결 열림 확인
            - SettingsManager에서 Prefix/Suffix 값 획득
            - CommandProcessor에 값과 함께 전송 요청
            - Broadcast 여부에 따라 Controller 메서드 분기 호출
            - 데이터 전송 및 Local Echo 처리

        Args:
            command (ManualCommand): 전송할 Command 및 옵션이 담긴 DTO
        """
        if not self.connection_controller.has_active_connection:
            logger.warning("Manual Send: No active connection")
            return

        # DTO 속성 접근
        if not command.text:
            return

        # SettingsManager에서 값 획득 후 CommandProcessor에 주입
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix else None

        try:
            data = CommandProcessor.process_command(command.text, command.hex_mode, prefix=prefix, suffix=suffix)
        except ValueError:
            logger.error(f"Invalid hex string for sending: {command.text}")
            return

        # Broadcast 여부에 따른 전송 처리
        if command.is_broadcast:
            # 브로드캐스팅 허용된 모든 포트로 전송
            self.connection_controller.send_data_to_broadcasting(data)
            logger.info(f"Manual command broadcasted: {command.text}")
        else:
            # 현재 활성 포트 조회
            active_port = self.get_active_port() if self.get_active_port else None

            if active_port:
                # 명시적으로 포트 이름을 지정하여 전송
                self.connection_controller.send_data(active_port, data)
                logger.info(f"Manual command sent to {active_port}: {command.text}")
            else:
                logger.warning("No active port selected for transmission.")
                return

        # Local Echo (송신 데이터를 화면에 표시)
        if command.local_echo and self.local_echo_callback:
            self.local_echo_callback(data)

    def on_rts_changed(self, state: bool) -> None:
        """
        RTS 상태 변경 처리

        Args:
            state (bool): RTS 상태 (True=ON, False=OFF)
        """
        if self.connection_controller.has_active_connection:
            self.connection_controller.set_rts(state)
            logger.info(f"RTS changed to {state}")

    def on_dtr_changed(self, state: bool) -> None:
        """
        DTR 상태 변경 처리

        Args:
            state (bool): DTR 상태 (True=ON, False=OFF)
        """
        if self.connection_controller.has_active_connection:
            self.connection_controller.set_dtr(state)
            logger.info(f"DTR changed to {state}")

    # -------------------------------------------------------------------------
    # State Management (Persistence)
    # -------------------------------------------------------------------------
    def get_state(self) -> ManualControlState:
        """
        현재 상태(UI 상태)를 DTO로 반환
        """
        # View의 UI 상태 가져오기 (dict)
        # Refactor: save_state -> get_state
        ui_state = self.view.get_state()

        # DTO 생성 (내부 manual_control_widget 키에서 데이터 추출)
        manual_control_widget = ui_state.get("manual_control_widget", {})
        return ManualControlState(
            input_text=manual_control_widget.get("input_text", ""),
            hex_mode=manual_control_widget.get("hex_mode", False),
            prefix_chk=manual_control_widget.get("prefix_chk", False),
            suffix_chk=manual_control_widget.get("suffix_chk", False),
            rts_chk=manual_control_widget.get("rts_chk", False),
            dtr_chk=manual_control_widget.get("dtr_chk", False),
            local_echo_chk=manual_control_widget.get("local_echo_chk", False),
            broadcast_chk=manual_control_widget.get("broadcast_chk", False)
        )

    def load_state(self, state: ManualControlState) -> None:
        """
        저장된 상태 DTO를 복원
        """
        if not state:
            return

        # View 상태 복원 (Dict로 변환하여 전달)
        view_state = {
            "manual_control_widget": {
                "input_text": state.input_text,
                "hex_mode": state.hex_mode,
                "prefix_chk": state.prefix_chk,
                "suffix_chk": state.suffix_chk,
                "rts_chk": state.rts_chk,
                "dtr_chk": state.dtr_chk,
                "local_echo_chk": state.local_echo_chk,
                "broadcast_chk": state.broadcast_chk
            }
        }
        # Refactor: load_state -> apply_state
        self.view.apply_state(view_state)
