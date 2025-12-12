"""
수동 제어 프레젠터 모듈

수동 명령어 전송에 관련된 비즈니스 로직을 처리합니다.

## WHY
* MainPresenter의 비대화 방지 (SRP 준수)
* 수동 전송 로직(Prefix/Suffix, Hex 변환)의 캡슐화
* View와 Model 사이의 명확한 역할 분리

## WHAT
* 수동 전송 요청 처리
* 설정(SettingsManager) 기반 데이터 가공
* Local Echo 처리 (콜백 활용)
* PortController를 통한 데이터 전송

## HOW
* View의 시그널(manual_cmd_send_requested) 구독
* SettingsManager 설정값 조회
* Callable 콜백을 통해 외부 UI(RxLog) 업데이트 요청
"""
from PyQt5.QtCore import QObject
from typing import Callable, Optional
from view.panels.manual_ctrl_panel import ManualCtrlPanel
from model.port_controller import PortController
from core.settings_manager import SettingsManager
from core.logger import logger
from constants import ConfigKeys

class ManualControlPresenter(QObject):
    """
    수동 제어 Presenter 클래스

    사용자의 수동 입력 명령을 처리하고 전송합니다.
    """

    def __init__(
        self,
        view: ManualCtrlPanel,
        port_controller: PortController,
        local_echo_callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """
        ManualControlPresenter 초기화

        Args:
            view (ManualCtrlPanel): 수동 제어 뷰 패널
            port_controller (PortController): 포트 제어 모델
            local_echo_callback (Callable): Local Echo 데이터를 처리할 콜백 함수 (선택)
        """
        super().__init__()
        self.view = view
        self.port_controller = port_controller
        self.local_echo_callback = local_echo_callback

        self.settings_manager = SettingsManager()

        # View 시그널 연결
        self.view.manual_cmd_send_requested.connect(self.on_manual_cmd_send_requested)

    def on_manual_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool, local_echo: bool) -> None:
        """
        수동 명령 전송 요청 처리

        Logic:
            - 포트 열림 상태 확인
            - Prefix/Suffix 설정 조회 및 적용
            - HEX 모드에 따른 데이터 변환 및 유효성 검사
            - PortController를 통한 전송
            - Local Echo 활성화 시 콜백 호출

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
