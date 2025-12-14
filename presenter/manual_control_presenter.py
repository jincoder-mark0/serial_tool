"""
수동 제어 프레젠터 모듈

사용자의 수동 입력 및 포트 제어 신호를 처리하는 Presenter입니다.

## WHY
* View와 Model 사이의 중재자 역할
* SettingsManager에서 설정값(Prefix/Suffix) 주입
* 하드웨어 제어 신호(RTS, DTR) 처리

## WHAT
* 수동 전송 요청(send_requested) 처리
* RTS/DTR 상태 변경 요청 처리
* 설정 적용 및 Local Echo 처리

## HOW
* View 시그널 구독
* CommandProcessor를 통한 데이터 가공
* ConnectionController 메서드 호출 (send_data, set_rts, set_dtr)
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional
from view.panels.manual_control_panel import ManualControlPanel
from model.connection_controller import ConnectionController
from common.dtos import ManualCommand
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
        local_echo_callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """
        ManualControlPresenter 초기화

        Args:
            view (ManualControlPanel): 수동 제어 패널 View
            connection_controller (ConnectionController): 연결 제어 Model
            local_echo_callback (Callable): Local Echo 콜백 (선택)
        """
        super().__init__()
        self.view = view
        self.connection_controller = connection_controller
        self.local_echo_callback = local_echo_callback
        self.settings_manager = SettingsManager()

        # View 시그널 연결
        self.view.send_requested.connect(self.on_send_requested)
        self.view.rts_changed.connect(self.on_rts_changed)
        self.view.dtr_changed.connect(self.on_dtr_changed)

        self._apply_initial_settings()

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
            - 연결 열림 확인
            - SettingsManager에서 Prefix/Suffix 값 획득
            - CommandProcessor에 값과 함께 전송 요청
            - 데이터 전송 및 Local Echo 처리

        Args:
            command (ManualCommand): 전송할 명령어 및 옵션이 담긴 DTO
        """
        if not self.connection_controller.has_active_connection:
            logger.warning("Manual Send: No active connection")
            return

        # DTO 속성 접근 (오타 방지 및 타입 힌트 지원)
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

        # Controller에 DTO의 브로드캐스트 플래그 전달
        self.connection_controller.send_data_to_broadcasting(data)

        mode_str = "Broadcast" if command.is_broadcast else "Unicast"
        logger.info(f"Manual command sent ({mode_str}): {command.text}")

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
