"""
수동 제어 프레젠터 모듈

사용자의 수동 입력 및 포트 제어 신호를 처리하는 Presenter입니다.

## WHY
* View와 Model 사이의 중재자 역할
* 수동 입력 데이터 가공(Prefix, Suffix, Hex) 로직의 분리
* 하드웨어 제어 신호(RTS, DTR) 처리

## WHAT
* 수동 전송 요청(manual_cmd_send_requested) 처리
* RTS/DTR 상태 변경 요청 처리
* 설정 적용 및 Local Echo 처리

## HOW
* View 시그널 구독 (ManualCtrlPanel -> Widget)
* CmdProcessor를 통한 데이터 가공
* PortController 메서드 호출 (send_data, set_rts, set_dtr)
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional
from view.panels.manual_ctrl_panel import ManualCtrlPanel
from model.port_controller import PortController
from core.settings_manager import SettingsManager
from core.cmd_processor import CmdProcessor
from core.logger import logger
from constants import ConfigKeys

class ManualCtrlPresenter(QObject):
    """
    수동 제어 로직을 담당하는 Presenter 클래스
    """

    def __init__(
        self,
        view: ManualCtrlPanel,
        port_controller: PortController,
        local_echo_callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """
        ManualCtrlPresenter 초기화

        Args:
            view (ManualCtrlPanel): 수동 제어 패널 View
            port_controller (PortController): 포트 제어 Model
            local_echo_callback (Callable): Local Echo 콜백 (선택)
        """
        super().__init__()
        self.view = view
        self.port_controller = port_controller
        self.local_echo_callback = local_echo_callback
        self.settings_manager = SettingsManager()

        # View 시그널 연결 (디미터 법칙 준수)
        self.view.manual_cmd_send_requested.connect(self.on_manual_cmd_send_requested)
        self.view.rts_changed.connect(self.on_rts_changed)
        self.view.dtr_changed.connect(self.on_dtr_changed)

        # 초기 상태 설정 (전역 설정 반영)
        self._apply_initial_settings()

    def _apply_initial_settings(self) -> None:
        """설정 파일에서 Local Echo 기본값을 읽어 View에 적용"""
        default_echo = self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False)
        self.view.set_local_echo_state(default_echo)

    def on_manual_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool, local_echo: bool) -> None:
        """
        수동 명령 전송 요청 처리

        Logic:
            - 포트 열림 확인
            - CmdProcessor를 사용하여 데이터 변환
            - 데이터 전송 및 Local Echo 처리

        Args:
            text (str): 전송할 텍스트
            hex_mode (bool): Hex 모드 여부
            cmd_prefix (bool): 접두사 사용 여부
            cmd_suffix (bool): 접미사 사용 여부
            local_echo (bool): 로컬 에코 사용 여부
        """
        if not self.port_controller.is_open:
            logger.warning("Manual Send: Port not open")
            return

        try:
            # 데이터 가공 위임
            data = CmdProcessor.process_cmd(text, hex_mode, cmd_prefix, cmd_suffix)
        except ValueError:
            logger.error(f"Invalid hex string for sending: {text}")
            return

        # 데이터 전송
        self.port_controller.send_data(data)

        # Local Echo (View에 직접 표시 요청)
        if local_echo and self.local_echo_callback:
            self.local_echo_callback(data)

    def on_rts_changed(self, state: bool) -> None:
        """
        RTS 상태 변경 처리

        Args:
            state (bool): RTS 상태 (True=ON, False=OFF)
        """
        if self.port_controller.is_open:
            self.port_controller.set_rts(state)
            logger.info(f"RTS changed to {state}")

    def on_dtr_changed(self, state: bool) -> None:
        """
        DTR 상태 변경 처리

        Args:
            state (bool): DTR 상태 (True=ON, False=OFF)
        """
        if self.port_controller.is_open:
            self.port_controller.set_dtr(state)
            logger.info(f"DTR changed to {state}")
