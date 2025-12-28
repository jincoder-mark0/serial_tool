"""
수동 제어 프레젠터 모듈

수동 제어 패널(ManualControlPanel)과 연결 컨트롤러(ConnectionController) 간의 로직을 처리합니다.

## WHY
* 사용자의 직접적인 명령어 입력 및 전송 요청 처리 분리
* 16진수/ASCII 변환 및 접두사/접미사 처리 로직 캡슐화
* RTS/DTR 등의 하드웨어 제어 신호 중계
* 브로드캐스트 상태 변경을 상위 Presenter에 알림 (UI 동기화용)

## WHAT
* View의 전송 요청(Signal)을 받아 상태를 직접 수집하여 DTO 생성 후 Controller로 전달
* DTR/RTS 제어 요청 처리
* 전송 성공 시 로컬 에코(Local Echo) 처리
* 브로드캐스트 모드 지원 (다중 포트 전송)

## HOW
* View(Panel)가 제공하는 Getter 메서드(Facade)를 통해 상태 조회 (Widget 직접 접근 제거)
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
        # View는 단순한 시그널만 보내고, 데이터 수집은 Presenter가 수행함 (Passive View)
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
        return self.panel.is_broadcast_enabled()

    def on_send_requested(self, _=None) -> None:
        """
        전송 요청 처리 핸들러

        Logic:
            1. View(Panel)의 Getter 메서드를 통해 현재 UI 상태(입력값, 옵션)를 직접 수집
            2. ManualCommand DTO 생성
            3. 설정된 Prefix/Suffix 조회 및 데이터 가공
            4. 단일/브로드캐스트 모드에 따라 전송 수행
            5. 성공 시 로컬 에코 출력

        Args:
            _ (Any): 시그널에서 전달되는 인자 (사용하지 않음, View가 DTO를 보내지 않도록 가정).
        """
        # 1. View에서 상태 수집 (Passive View 패턴 강화)
        # Presenter가 View의 내부 위젯 구조를 알 필요 없이 인터페이스만 호출
        try:
            command_text = self.panel.get_input_text()
            hex_mode = self.panel.is_hex_mode()
            prefix_enabled = self.panel.is_prefix_enabled()
            suffix_enabled = self.panel.is_suffix_enabled()
            broadcast_enabled = self.panel.is_broadcast_enabled()
            # Local Echo는 Presenter가 관리하는 전역 설정 값을 사용 (또는 UI 체크박스 값 사용 가능)
            # 여기서는 UI 체크박스 값과 전역 설정 중 UI 값을 우선하거나 동기화된 값을 사용
            # View에 is_local_echo_enabled()가 있다고 가정
            local_echo_enabled = self.panel.is_local_echo_enabled()
        except AttributeError as e:
            logger.error(f"Failed to gather state from ManualControlPanel: {e}")
            return

        # DTO 생성
        command = ManualCommand(
            command=command_text,
            hex_mode=hex_mode,
            prefix_enabled=prefix_enabled,
            suffix_enabled=suffix_enabled,
            local_echo_enabled=local_echo_enabled,
            broadcast_enabled=broadcast_enabled
        )

        # 2. 설정값 조회 (Prefix/Suffix)
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix_enabled else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix_enabled else None

        # 3. 데이터 가공
        try:
            data = CommandProcessor.process_command(
                command.command,
                command.hex_mode,
                prefix=prefix,
                suffix=suffix
            )
        except ValueError as e:
            logger.error(f"Command processing error: {e}")
            # View에 에러 알림 필요 시 추가 구현
            return

        if not data:
            return

        sent_success = False

        # 4. 전송 수행
        if command.broadcast_enabled:
            # 브로드캐스트 모드: 활성 포트가 하나라도 있는지 확인 (Gatekeeping)
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

        # 5. 로컬 에코 처리
        # 전송 성공하고 로컬 에코가 활성화되어 있으면 콜백 호출
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
        현재 UI 상태를 DTO로 반환합니다. (설정 저장용)

        Logic:
            - 데이터를 조합하여 DTO 생성

        Returns:
            ManualControlState: 현재 상태 DTO.
        """
        # View가 아직 초기화되지 않았거나 인터페이스가 없는 경우 방어
        if not self.panel:
            return ManualControlState()

        return ManualControlState(
            input_text=self.panel.get_input_text(),
            hex_mode=self.panel.is_hex_mode(),
            prefix_enabled=self.panel.is_prefix_enabled(),
            suffix_enabled=self.panel.is_suffix_enabled(),
            rts_enabled=self.panel.is_rts_enabled(),
            dtr_enabled=self.panel.is_dtr_enabled(),
            local_echo_enabled=self.local_echo_enabled, # 전역 설정 사용
            broadcast_enabled=self.panel.is_broadcast_enabled()
        )

    def apply_state(self, state: ManualControlState) -> None:
        """
        저장된 상태를 패널에 적용합니다.
        (애플리케이션 시작 시 복원용)

        Args:
            state (ManualControlState): 복원할 상태 DTO.
        """
        # DTO를 View로 전달 (View 내부 구현은 캡슐화됨)
        self.panel.apply_state(state)