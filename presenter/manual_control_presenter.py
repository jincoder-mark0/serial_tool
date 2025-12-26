"""
수동 제어 프레젠터 모듈

수동 제어 패널(ManualControlPanel)과 연결 컨트롤러(ConnectionController) 간의 로직을 처리합니다.

## WHY
* 사용자의 직접적인 명령어 입력 및 전송 요청 처리 분리
* 16진수/ASCII 변환 및 접두사/접미사 처리 로직 캡슐화
* RTS/DTR 등의 하드웨어 제어 신호 중계
* 브로드캐스트 상태 변경을 상위 Presenter에 알림 (UI 동기화용)

## WHAT
* View의 전송 요청(Signal)을 받아 데이터 가공 후 Controller로 전달
* DTR/RTS 제어 요청 처리
* 전송 성공 시 로컬 에코(Local Echo) 처리
* 브로드캐스트 모드 지원 (다중 포트 전송)

## HOW
* CommandProcessor를 사용하여 입력 데이터 가공
* ConnectionController를 통해 데이터 전송 수행
* Callable 콜백을 통해 MainPresenter(View)에 로컬 에코 데이터 전달
"""
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from view.panels.manual_control_panel import ManualControlPanel
from model.connection_controller import ConnectionController
from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.logger import logger
from common.constants import ConfigKeys
from common.dtos import ManualCommand, ManualControlState


class ManualControlPresenter(QObject):
    """
    수동 제어 프레젠터 클래스

    사용자의 명령어 입력, DTR/RTS 제어, 브로드캐스트 설정을 관리하고
    데이터 전송 로직을 수행합니다.
    """

    # 브로드캐스트 상태 변경 알림 (MainPresenter가 구독하여 전송 버튼 활성화 여부 판단)
    broadcast_changed = pyqtSignal(bool)

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
            panel (ManualControlPanel): 수동 제어 뷰 패널.
            connection_controller (ConnectionController): 연결 제어 모델.
            local_echo_callback (Callable): 로컬 에코 출력을 위한 콜백 함수.
            get_active_port_callback (Callable): 현재 활성 탭의 포트 이름을 조회하는 콜백.
        """
        super().__init__()
        self.panel = panel
        self.connection_controller = connection_controller
        self.local_echo_callback = local_echo_callback
        self.get_active_port_callback = get_active_port_callback
        self.settings_manager = SettingsManager()

        # View -> Presenter 시그널 연결
        self.panel.send_requested.connect(self.on_send_requested)
        self.panel.dtr_changed.connect(self.on_dtr_changed)
        self.panel.rts_changed.connect(self.on_rts_changed)

        # View의 브로드캐스트 변경 시그널을 Presenter 시그널로 중계 (Relay)
        if hasattr(self.panel, 'broadcast_changed'):
            self.panel.broadcast_changed.connect(self.broadcast_changed.emit)

        # 초기 설정 로드
        self._load_initial_settings()

    def _load_initial_settings(self) -> None:
        """초기 설정을 로드하여 내부 상태에 반영합니다."""
        self.local_echo_enabled = self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False)

    def set_enabled(self, enabled: bool) -> None:
        """
        패널의 활성화 상태를 제어합니다. (MainPresenter에서 호출)

        Args:
            enabled (bool): 활성화 여부.
        """
        self.panel.set_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        """
        현재 브로드캐스트 체크박스 상태를 반환합니다.
        (MainPresenter가 버튼 활성화 로직 판단 시 호출)

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        # Panel -> Widget -> Checkbox 접근 (캡슐화를 위해 Panel에 getter가 있으면 더 좋음)
        if hasattr(self.panel, 'manual_control_widget'):
            return self.panel.manual_control_widget.broadcast_chk.isChecked()
        return False

    def on_send_requested(self, command: ManualCommand) -> None:
        """
        전송 요청 처리 핸들러

        Logic:
            1. 설정된 Prefix/Suffix 조회
            2. 데이터 가공 (Hex/ASCII 변환, 접두사/접미사 붙임)
            3. 단일/브로드캐스트 모드에 따라 전송 수행
            4. 성공 시 로컬 에코 출력

        Args:
            command (ManualCommand): 전송할 명령어 DTO.
        """
        # 1. 설정값 조회
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix_enabled else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix_enabled else None

        # 2. 데이터 가공
        try:
            data = CommandProcessor.process_command(
                command.command,
                command.hex_mode,
                prefix=prefix,
                suffix=suffix
            )
        except ValueError as e:
            logger.error(f"Command processing error: {e}")
            # View에 에러 알림 필요 시 추가 구현 (현재는 로그만)
            return

        if not data:
            return

        sent_success = False

        # 3. 전송 수행
        if command.broadcast_enabled:
            # 브로드캐스트 모드
            if self.connection_controller.has_active_broadcast_ports():
                self.connection_controller.send_broadcast_data(data)
                sent_success = True
            else:
                logger.warning("No active ports for broadcast.")
        else:
            # 단일 전송 모드
            active_port = self.get_active_port_callback()
            if active_port and self.connection_controller.is_connection_open(active_port):
                self.connection_controller.send_data(active_port, data)
                sent_success = True
            else:
                logger.warning(f"Port '{active_port}' is not open.")

        # 4. Local Echo 처리
        if sent_success and self.local_echo_enabled:
            self.local_echo_callback(data)

    def on_dtr_changed(self, state: bool) -> None:
        """
        DTR 상태 변경 요청 처리

        Args:
            state (bool): DTR 상태 (On/Off).
        """
        # 현재는 모든 활성 포트에 일괄 적용 (요구사항에 따라 변경 가능)
        self.connection_controller.set_dtr(state)
        logger.info(f"DTR set to {state}")

    def on_rts_changed(self, state: bool) -> None:
        """
        RTS 상태 변경 요청 처리

        Args:
            state (bool): RTS 상태 (On/Off).
        """
        self.connection_controller.set_rts(state)
        logger.info(f"RTS set to {state}")

    def update_local_echo_setting(self, enabled: bool) -> None:
        """
        로컬 에코 설정 변경 시 호출됨 (MainPresenter -> this)

        Args:
            enabled (bool): 활성화 여부.
        """
        self.local_echo_enabled = enabled

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
