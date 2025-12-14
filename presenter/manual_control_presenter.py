"""
수동 제어 프레젠터 모듈

사용자의 수동 입력 및 포트 제어 신호를 처리하는 Presenter입니다.

## WHY
* View와 Model 사이의 중재자 역할
* SettingsManager에서 설정값(Prefix/Suffix) 주입
* 하드웨어 제어 신호(RTS, DTR) 처리

## WHAT
* 수동 전송 요청(manual_command_send_requested) 처리
* RTS/DTR 상태 변경 요청 처리
* 설정 적용 및 Local Echo 처리

## HOW
* View 시그널 구독
* CommandProcessor를 통한 데이터 가공
* ConnectionController 메서드 호출 (send_data, set_rts, set_dtr)
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional, Dict, Any
from view.panels.manual_control_panel import ManualControlPanel
from model.connection_controller import ConnectionController
from core.settings_manager import SettingsManager
from core.command_processor import CommandProcessor
from core.logger import logger
from constants import ConfigKeys

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

        # View 시그널 연결 (디미터 법칙 준수)
        self.view.manual_command_send_requested.connect(self.on_manual_command_send_requested)
        self.view.rts_changed.connect(self.on_rts_changed)
        self.view.dtr_changed.connect(self.on_dtr_changed)

    def on_manual_command_send_requested(self, send_data: Dict[str, Any]) -> None:
        """
        수동 명령 전송 요청 처리

        Logic:
            - 연결 열림 확인
            - **SettingsManager에서 Prefix/Suffix 값 획득**
            - CommandProcessor에 값과 함께 전송 요청
            - 데이터 전송 및 Local Echo 처리

        Args:
            send_data (Dict[str, Any]): 전송 관련 설정 딕셔너리
                keys: text, hex_mode, command_prefix, command_suffix, local_echo
        """
        if not self.connection_controller.has_active_connection:
            logger.warning("Manual Send: No active connection")
            return

        # 딕셔너리에서 필요한 값 추출
        text = send_data.get("text", "")
        hex_mode_chk = send_data.get("hex_mode_chk", False)
        prefix_chk = send_data.get("prefix_chk", False)
        suffix_chk = send_data.get("suffix_chk", False)
        local_echo_chk = send_data.get("local_echo_chk", False)

        if not text:
            return
        # SettingsManager에서 값 획득 후 CommandProcessor에 주입
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if prefix_chk else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if suffix_chk else None

        try:
            # 데이터 가공 위임 (CommandProcessor에 Prefix/Suffix 값 직접 전달)
            data = CommandProcessor.process_command(text, hex_mode_chk, prefix=prefix, suffix=suffix)
        except ValueError:
            logger.error(f"Invalid hex string for sending: {text}")
            return

        # 데이터 전송 (Controller)
        self.connection_controller.send_data(data)

        # Local Echo (View에 직접 표시 요청)
        if local_echo and self.local_echo_callback:
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
