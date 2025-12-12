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
* PortController 메서드 호출 (send_data, set_rts, set_dtr)
* SettingsManager 설정값 조회
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional
from view.panels.manual_ctrl_panel import ManualCtrlPanel
from model.port_controller import PortController
from core.settings_manager import SettingsManager
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

        # 패널 내부의 실제 위젯 접근
        widget = self.view.manual_ctrl_widget

        # 시그널 연결
        widget.manual_cmd_send_requested.connect(self.on_manual_cmd_send_requested)
        widget.rts_changed.connect(self.on_rts_changed)
        widget.dtr_changed.connect(self.on_dtr_changed)

    def on_manual_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool, local_echo: bool) -> None:
        """
        수동 명령 전송 요청 처리

        Logic:
            - 포트 열림 확인
            - Prefix/Suffix 적용
            - Hex 모드 변환 및 유효성 검사
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

        final_text = text

        # Prefix 적용
        if cmd_prefix:
            prefix = self.settings_manager.get(ConfigKeys.CMD_PREFIX, "")
            final_text = prefix + final_text

        # Suffix 적용
        if cmd_suffix:
            suffix = self.settings_manager.get(ConfigKeys.CMD_SUFFIX, "")
            final_text = final_text + suffix

        # 데이터 변환 (Hex vs Text)
        data: bytes
        if hex_mode:
            try:
                # 공백 제거 후 Hex 변환
                data = bytes.fromhex(final_text.replace(' ', ''))
            except ValueError:
                logger.error(f"Invalid hex string for sending: {final_text}")
                # TODO: View에 에러 알림 표시 (향후 개선 사항)
                return
        else:
            data = final_text.encode('utf-8')

        # 데이터 전송
        self.port_controller.send_data(data)

        # Local Echo 처리
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
