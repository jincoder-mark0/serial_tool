"""
수동 제어 프레젠터 모듈

수동 제어 패널(View)과 연결 컨트롤러(Model) 사이의 로직을 처리합니다.
구체적인 UI 구현체 대신 인터페이스(Protocol)에 의존하여 결합도를 낮춥니다.
데이터 흐름을 View에서 전달받은 DTO를 사용하는 'Push' 방식으로 구현합니다.

## WHY
* 사용자의 직접적인 명령어 입력 및 전송 요청 처리 분리
* View의 내부 상태(체크박스 등)를 Presenter가 알 필요 없이, 전달받은 데이터(DTO)만 처리 (Decoupling)
* 16진수/ASCII 변환 및 접두사/접미사 처리 로직 캡슐화
* RTS/DTR 등의 하드웨어 제어 신호 중계

## WHAT
* View의 전송 요청(Signal)에 포함된 DTO를 사용하여 데이터 전송 로직 수행
* DTR/RTS 제어 요청 처리
* 전송 성공 시 로컬 에코(Local Echo) 처리
* 브로드캐스트 모드 지원 (다중 포트 전송)

## HOW
* IManualControlView 인터페이스를 통해 UI 제어 (Dependency Inversion)
* 시그널 인자로 전달된 ManualCommand DTO 사용 (Push Model)
* CommandProcessor를 사용하여 입력 데이터 가공
* ConnectionController를 통해 데이터 전송 수행
"""
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from view.interfaces import IManualControlView
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
        view: IManualControlView,
        connection_controller: ConnectionController,
        local_echo_callback: Callable[[bytes], None],
        get_active_port_callback: Callable[[], Optional[str]]
    ) -> None:
        """
        ManualControlPresenter 초기화

        Args:
            view (IManualControlView): 수동 제어 뷰 인터페이스.
            connection_controller (ConnectionController): 연결 제어 모델.
            local_echo_callback (Callable): 로컬 에코 출력을 위한 콜백 함수.
            get_active_port_callback (Callable): 현재 활성 탭의 포트 이름을 조회하는 콜백.
        """
        super().__init__()
        self.view = view
        self.connection_controller = connection_controller
        self.local_echo_callback = local_echo_callback
        self.get_active_port_callback = get_active_port_callback
        self.settings_manager = SettingsManager()

        # View -> Presenter 시그널 연결
        # View는 사용자 의도가 담긴 DTO를 직접 전달함 (Push Model)
        self.view.send_requested.connect(self.on_send_requested)
        self.view.dtr_changed.connect(self.on_dtr_changed)
        self.view.rts_changed.connect(self.on_rts_changed)

        # View의 브로드캐스트 변경 시그널을 Presenter 시그널로 중계 (Relay)
        # Protocol에는 hasattr 검사가 어렵으므로 try-except 사용
        try:
            self.view.broadcast_changed.connect(self.broadcast_changed.emit)
        except AttributeError:
            pass

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
        self.view.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        """
        현재 브로드캐스트 체크박스 상태를 반환합니다.
        (MainPresenter가 버튼 활성화 로직 판단 시 호출)

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        # View Interface 메서드 사용
        return self.view.is_broadcast_enabled()

    def on_send_requested(self, command_dto: ManualCommand) -> None:
        """
        전송 요청 처리 핸들러 (Push 방식)

        Logic:
            1. 시그널 인자로 전달된 `command_dto`를 확인 (View 조회 제거)
            2. 설정된 Prefix/Suffix 조회 및 데이터 가공
            3. 단일/브로드캐스트 모드에 따라 전송 수행
            4. 성공 시 로컬 에코 출력

        Args:
            command_dto (ManualCommand): View에서 생성하여 전달한 명령어 DTO.
        """
        # 1. DTO 유효성 검사 (View가 데이터를 줌)
        if not command_dto or not isinstance(command_dto, ManualCommand):
            logger.error("Invalid command DTO received from View.")
            return

        # 2. 설정값 조회 (Prefix/Suffix 문자열은 Global Setting이므로 Manager에서 조회)
        # DTO에는 '활성화 여부'만 있고 실제 문자열은 설정에 있음
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command_dto.prefix_enabled else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command_dto.suffix_enabled else None

        # 3. 데이터 가공 (CommandProcessor)
        try:
            data = CommandProcessor.process_command(
                command_dto.command,
                command_dto.hex_mode,
                prefix=prefix,
                suffix=suffix
            )
        except ValueError as e:
            logger.error(f"Command processing error: {e}")
            # 필요 시 View에 에러 알림 표시 로직 추가 가능
            return

        if not data:
            return

        sent_success = False

        # 4. 전송 수행 (DTO의 플래그 사용)
        if command_dto.broadcast_enabled:
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
        # (Local Echo 옵션도 DTO에 포함되어 있거나 전역 설정을 따름. 여기선 DTO 우선 혹은 전역 설정과 OR 연산 가능)
        # 현재 로직: View DTO의 체크박스 상태와 전역 설정 중 하나라도 True면 표시하거나,
        # 기획에 따라 View의 체크박스 상태(DTO)를 우선시함.
        if sent_success:
            if command_dto.local_echo_enabled:
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
        # UI 상태 동기화
        self.view.set_local_echo_checked(enabled)

    def get_state(self) -> ManualControlState:
        """
        현재 UI 상태를 DTO로 반환합니다. (설정 저장용)

        Logic:
            - View Interface를 통해 상태 DTO를 직접 받아옴

        Returns:
            ManualControlState: 현재 상태 DTO.
        """
        if not self.view:
            return ManualControlState()

        # View가 스스로 상태를 DTO로 만들어 반환함 (Facade Interface 활용)
        return self.view.get_state()

    def apply_state(self, state: ManualControlState) -> None:
        """
        저장된 상태를 패널에 적용합니다.
        (애플리케이션 시작 시 복원용)

        Args:
            state (ManualControlState): 복원할 상태 DTO.
        """
        # DTO를 View로 전달 (View 내부 구현은 캡슐화됨)
        self.view.apply_state(state)