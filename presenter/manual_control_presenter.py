"""
수동 제어 프레젠터 모듈

사용자의 수동 입력(텍스트/HEX)을 처리하고 데이터를 전송하는 Presenter입니다.

## WHY
* 사용자의 입력 이벤트와 실제 데이터 전송 로직의 분리 (MVP 패턴)
* 명령어 가공(Prefix/Suffix/Hex 변환) 로직의 캡슐화
* 전송 데이터의 로컬 에코(Local Echo) 및 브로드캐스트 처리

## WHAT
* ManualControlPanel(View)과 ConnectionController(Model) 연결
* Send 버튼 클릭 시 입력값 검증 및 가공 (CommandProcessor)
* 데이터 전송 및 로컬 에코 출력
* UI 상태(입력값, 체크박스 등) 저장 및 복원

## HOW
* View의 시그널(send_requested)을 구독하여 처리
* CommandProcessor를 통해 문자열을 바이트 데이터로 변환
* ConnectionController를 통해 단일 또는 브로드캐스트 전송 수행
* DTO(ManualControlState)를 통해 UI 상태를 주고받음
"""
from typing import Callable, Optional

from PyQt5.QtCore import QObject

from view.panels.manual_control_panel import ManualControlPanel
from model.connection_controller import ConnectionController
from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.logger import logger
from common.constants import ConfigKeys
from common.dtos import ManualCommand, ManualControlState


class ManualControlPresenter(QObject):
    """
    수동 제어 패널 로직을 담당하는 Presenter 클래스

    사용자 입력을 받아 데이터를 가공하고, ConnectionController를 통해 전송합니다.
    """

    def __init__(
        self,
        panel: ManualControlPanel,
        connection_controller: ConnectionController,
        local_echo_callback: Callable[[bytes], None],
        get_active_port_callback: Callable[[], Optional[str]]
    ) -> None:
        """
        ManualControlPresenter 초기화

        Args:
            panel (ManualControlPanel): 수동 제어 뷰 인스턴스.
            connection_controller (ConnectionController): 연결 제어 모델.
            local_echo_callback (Callable[[bytes], None]): 로컬 에코 출력을 위한 콜백 함수 (View 메서드).
            get_active_port_callback (Callable[[], Optional[str]]): 현재 활성화된 포트 이름을 반환하는 콜백 함수.
        """
        super().__init__()
        self.panel = panel
        self.connection_controller = connection_controller
        self.local_echo_callback = local_echo_callback
        self.get_active_port_callback = get_active_port_callback
        self.settings_manager = SettingsManager()

        # View 시그널 연결 (전송 요청)
        self.panel.send_requested.connect(self.on_send_requested)

        # DTR/RTS 제어 시그널 연결
        # (Panel이 해당 시그널을 중계하도록 구현되어 있어야 함)
        if hasattr(self.panel, 'dtr_changed'):
            self.panel.dtr_changed.connect(self.on_dtr_changed)
        if hasattr(self.panel, 'rts_changed'):
            self.panel.rts_changed.connect(self.on_rts_changed)

    def set_enabled(self, enabled: bool) -> None:
        """
        패널의 제어 요소(버튼 등) 활성화 상태를 변경합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.panel.set_controls_enabled(enabled)

    def on_send_requested(self, command_dto: ManualCommand) -> None:
        """
        사용자의 전송 요청을 처리합니다.

        Logic:
            1. 입력된 명령어 유효성 검사 (빈 값 체크)
            2. 글로벌 설정(Prefix/Suffix) 가져오기
            3. CommandProcessor를 통해 바이트 데이터로 변환
            4. 활성 포트 확인 및 데이터 전송 (Broadcast or Single)
            5. 로컬 에코 출력

        Args:
            command_dto (ManualCommand): 전송할 명령어 정보가 담긴 DTO.
        """
        # HEX 모드가 아닐 때 빈 명령어는 무시
        if not command_dto.command and not command_dto.hex_mode:
            return

        # 1. 설정값 조회 (Prefix/Suffix)
        # UI에서 체크되었을 때만 글로벌 설정을 적용
        prefix = ""
        suffix = ""

        if command_dto.prefix_enabled:
            prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX, "")

        if command_dto.suffix_enabled:
            suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX, "")

        # 2. 데이터 가공 (String -> Bytes)
        try:
            data = CommandProcessor.process_command(
                command_dto.command,
                command_dto.hex_mode,
                prefix=prefix,
                suffix=suffix
            )
        except ValueError as e:
            logger.error(f"Command processing error: {e}")
            # 필요 시 View를 통해 에러 메시지 표시 가능
            return

        if not data:
            return

        # 3. 데이터 전송
        sent_success = False

        if command_dto.broadcast_enabled:
            # 브로드캐스트 전송
            self.connection_controller.send_broadcast_data(data)
            sent_success = True
            logger.debug(f"Broadcast sent: {len(data)} bytes")
        else:
            # 단일 포트 전송
            active_port = self.get_active_port_callback()
            if active_port and self.connection_controller.is_connection_open(active_port):
                self.connection_controller.send_data(active_port, data)
                sent_success = True
            else:
                logger.warning("Send failed: No active connection.")

        # 4. 로컬 에코 (전송 성공 시에만)
        if sent_success and command_dto.local_echo_enabled:
            self.local_echo_callback(data)

    def on_dtr_changed(self, state: bool) -> None:
        """
        DTR 체크박스 상태 변경 처리

        Args:
            state (bool): True=ON, False=OFF.
        """
        self.connection_controller.set_dtr(state)

    def on_rts_changed(self, state: bool) -> None:
        """
        RTS 체크박스 상태 변경 처리

        Args:
            state (bool): True=ON, False=OFF.
        """
        self.connection_controller.set_rts(state)

    def update_local_echo_setting(self, enabled: bool) -> None:
        """
        글로벌 설정 변경 시 로컬 에코 상태를 업데이트합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        # View의 메서드를 호출하여 체크박스 상태 등을 동기화
        if hasattr(self.panel, 'set_local_echo_checked'):
            self.panel.set_local_echo_checked(enabled)

    def get_state(self) -> ManualControlState:
        """
        현재 패널의 UI 상태(입력값, 체크박스 등)를 DTO로 반환합니다.
        (애플리케이션 종료 시 저장용)

        Returns:
            ManualControlState: 현재 상태 DTO.
        """
        return self.panel.get_state()

    def apply_state(self, state: ManualControlState) -> None:
        """
        저장된 상태를 패널에 적용합니다.
        (애플리케이션 시작 시 복원용)

        Args:
            state (ManualControlState): 복원할 상태 DTO.
        """
        # DTO를 View로 전달
        self.panel.apply_state(state)