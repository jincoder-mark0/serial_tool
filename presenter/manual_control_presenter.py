"""
수동 제어 프레젠터 모듈

수동 제어 패널(ManualControlPanel)과 연결 컨트롤러(ConnectionController) 간의 로직을 처리합니다.

## WHY
* 사용자의 직접적인 명령어 입력 및 전송 요청 처리 분리
* 16진수/ASCII 변환 및 접두사/접미사 처리 로직 캡슐화
* RTS/DTR 등의 하드웨어 제어 신호 중계
* 브로드캐스트 상태 변경을 상위 Presenter에 알림 (UI 동기화용)
* Command를 일정 주기로 반복 전송하는 Auto Tx 기능 지원 (S-006)
* 전송 실패(HEX 파싱 오류/브로드캐스트 대상 없음/미연결)를 사용자에게 표면화 (S-042)

## WHAT
* View의 전송 요청(Signal)을 받아 상태를 직접 수집하여 DTO 생성 후 Controller로 전달
* DTR/RTS 제어 요청 처리
* 전송 성공 시 로컬 에코(Local Echo) 처리
* 브로드캐스트 모드 지원 (다중 포트 전송)
* AutoTxScheduler 배선 — 토글 시 시작/정지, 포트 전체 종료 시 자동 정지
* 전송 실패 시 `send_error` 시그널로 MainPresenter에 알려 상태바/다이얼로그로 표면화.
  Auto Tx 반복 실패는 연속 실패 스트릭의 첫 실패에서만 알려 알림 폭주를 방지

## HOW
* View(Panel)가 제공하는 Getter 메서드(Facade)를 통해 상태 조회 (LoD 준수)
* CommandProcessor를 사용하여 입력 데이터 가공
* ConnectionController를 통해 데이터 전송 수행
* Callable 콜백을 통해 MainPresenter(View)에 로컬 에코 데이터 전달
* 수동 전송과 Auto Tx가 동일한 가공/전송 헬퍼(`_process_and_send`)를 공유하여 중복 제거
  (Auto Tx는 `_on_auto_tx_send_requested` 래퍼를 경유해 `is_auto_tx=True`로 구분)
"""
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from view.panels.manual_control_panel import ManualControlPanel
from view.managers.language_manager import language_manager
from model.connection_controller import ConnectionController
from model.auto_tx import AutoTxScheduler
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

    # 전송 실패 알림 (title, message, show_dialog) — MainPresenter가 구독하여
    # 매크로 구조적 에러(`_notify_macro_error`)와 동일한 상태바/다이얼로그 관례로 표면화한다.
    # show_dialog=False인 경우 상태바만 갱신하고 다이얼로그는 띄우지 않는다
    # (Auto Tx 반복 실패의 알림 폭주 방지, S-042).
    send_error = pyqtSignal(str, str, bool)

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

        # Auto Tx(주기적 자동 전송) 스케줄러 (UI 스레드 상주 QTimer, S-006)
        self.auto_tx_scheduler = AutoTxScheduler()
        # 반복 컨텍스트임을 표시하기 위해 래퍼를 경유 (직접 연결 시 수동 전송과 구분 불가)
        self.auto_tx_scheduler.send_requested.connect(self._on_auto_tx_send_requested)
        # Auto Tx 반복 중 연속 실패 여부 (알림 폭주 방지용 edge-trigger 플래그, S-042)
        self._auto_tx_failing = False

        # View -> Presenter 시그널 연결
        # View는 단순한 시그널만 보내고, 데이터 수집은 Presenter가 수행함 (Passive View)
        self.panel.send_requested.connect(self.on_send_requested)
        self.panel.dtr_changed.connect(self.on_dtr_changed)
        self.panel.rts_changed.connect(self.on_rts_changed)

        # View의 브로드캐스트 변경 시그널을 Presenter 시그널로 중계 (Relay)
        if hasattr(self.panel, 'broadcast_changed'):
            self.panel.broadcast_changed.connect(self.broadcast_changed.emit)

        # Auto Tx 토글 시그널 연결
        if hasattr(self.panel, 'auto_tx_toggled'):
            self.panel.auto_tx_toggled.connect(self.on_auto_tx_toggled)

        # 포트가 모두 닫히면 Auto Tx를 자동으로 정지 (확정 설계)
        if hasattr(self.connection_controller, 'connection_closed'):
            self.connection_controller.connection_closed.connect(self._on_connection_closed)

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
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        """
        현재 브로드캐스트 체크박스 상태를 반환합니다.
        (MainPresenter가 버튼 활성화 로직 판단 시 호출)

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        # Panel의 Facade 메서드 사용
        return self.panel.is_broadcast_enabled()

    def on_send_requested(self, _=None) -> None:
        """
        전송 요청 처리 핸들러

        Logic:
            1. View(Panel)의 Getter 메서드를 통해 현재 UI 상태(입력값, 옵션)를 직접 수집
            2. ManualCommand DTO 생성
            3. 공용 가공/전송 헬퍼(`_process_and_send`)에 위임

        Args:
            _ (Any): 시그널에서 전달되는 인자 (사용하지 않음, View가 DTO를 보내지 않도록 가정).
        """
        command = self._build_command_from_panel()
        if command is None:
            return

        self._process_and_send(command)

    def _build_command_from_panel(self) -> Optional[ManualCommand]:
        """
        View(Panel)의 Getter 메서드를 통해 현재 UI 상태를 수집하여 ManualCommand DTO를 만듭니다.

        Logic:
            - Presenter가 View의 내부 위젯 구조를 알 필요 없이 인터페이스만 호출 (LoD 준수)

        Returns:
            Optional[ManualCommand]: 생성된 DTO. Panel Facade 조회 실패 시 None.
        """
        try:
            command_text = self.panel.get_input_text()
            hex_mode = self.panel.is_hex_mode()
            prefix_enabled = self.panel.is_prefix_enabled()
            suffix_enabled = self.panel.is_suffix_enabled()
            broadcast_enabled = self.panel.is_broadcast_enabled()
            # Local Echo는 Presenter가 관리하는 전역 설정 값을 사용하거나 UI 값을 사용
            local_echo_enabled = self.panel.is_local_echo_enabled()
        except AttributeError as e:
            logger.error(f"Failed to gather state from ManualControlPanel: {e}")
            return None

        return ManualCommand(
            command=command_text,
            hex_mode=hex_mode,
            prefix_enabled=prefix_enabled,
            suffix_enabled=suffix_enabled,
            local_echo_enabled=local_echo_enabled,
            broadcast_enabled=broadcast_enabled
        )

    def _process_and_send(self, command: ManualCommand, is_auto_tx: bool = False) -> bool:
        """
        Command DTO를 가공(Prefix/Suffix/HEX)하여 전송하는 공용 헬퍼

        수동 전송(`on_send_requested`)과 Auto Tx(`_on_auto_tx_send_requested`)가
        이 메서드를 공유하여 가공/전송 로직 중복을 제거합니다.

        Logic:
            1. 설정된 Prefix/Suffix 조회 및 데이터 가공
            2. 단일/브로드캐스트 모드에 따라 전송 수행
            3. 성공 시 로컬 에코 출력
            4. 실패 시 `_report_send_error`를 통해 사용자에게 표면화 (S-042)

        Args:
            command (ManualCommand): 전송할 명령어 DTO.
            is_auto_tx (bool): Auto Tx 반복 경로에서의 호출 여부. 실패 알림 방식
                (다이얼로그 vs 상태바만)을 구분하는 데 사용된다.

        Returns:
            bool: 전송 성공 여부.
        """
        # 1. 설정값 조회 (Prefix/Suffix)
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
            self._report_send_error(
                is_auto_tx,
                language_manager.get_text("manual_control_title_send_error"),
                language_manager.get_text("manual_control_msg_invalid_command").format(e)
            )
            return False

        if not data:
            return False

        sent_success = False

        # 3. 전송 수행
        if command.broadcast_enabled:
            # 브로드캐스트 모드: 활성 포트가 하나라도 있는지 확인 (Gatekeeping)
            if self.connection_controller.has_active_broadcast_ports():
                self.connection_controller.send_broadcast_data(data)
                sent_success = True
            else:
                logger.warning("No active ports for broadcast.")
                self._report_send_error(
                    is_auto_tx,
                    language_manager.get_text("manual_control_title_send_error"),
                    language_manager.get_text("manual_control_msg_no_broadcast_target")
                )
        else:
            # 단일 전송 모드
            active_port = self.get_active_port_callback()
            if active_port and self.connection_controller.is_connection_open(active_port):
                self.connection_controller.send_data(active_port, data)
                sent_success = True
            else:
                logger.warning(f"Port '{active_port}' is not open.")
                self._report_send_error(
                    is_auto_tx,
                    language_manager.get_text("manual_control_title_send_error"),
                    language_manager.get_text("manual_control_msg_port_not_connected")
                )

        # 4. 로컬 에코 처리 + Auto Tx 실패 스트릭 해제
        if sent_success:
            if is_auto_tx:
                self._auto_tx_failing = False
            if self.local_echo_enabled:
                self.local_echo_callback(data)

        return sent_success

    def _report_send_error(self, is_auto_tx: bool, title: str, message: str) -> None:
        """
        전송 실패를 사용자에게 표면화합니다 (S-042).

        Logic:
            - 수동 단발 전송(is_auto_tx=False): 사용자의 명시적 클릭 행위이므로
              매번 알림(상태바+다이얼로그)한다 — 매크로의 구조적 에러
              (`MainPresenter._notify_macro_error`)와 동일한 관례.
            - Auto Tx 반복 전송(is_auto_tx=True): 매 tick마다 다이얼로그를 띄우면
              알림 폭주가 발생하므로, 연속 실패 스트릭의 첫 실패에서만(edge-trigger)
              상태바 알림만 발행하고 다이얼로그는 띄우지 않는다. 이미 실패 중이면
              (연속 실패) 침묵하여 폭주를 막는다. 성공 1회로 스트릭이 해제되면
              다음 실패에서 다시 알린다.

        Args:
            is_auto_tx (bool): Auto Tx 반복 경로에서 발생한 실패인지 여부.
            title (str): 다이얼로그 제목 (다이얼로그 표시 시에만 사용됨).
            message (str): 알림 메시지.
        """
        if is_auto_tx:
            if self._auto_tx_failing:
                return
            self._auto_tx_failing = True
            self.send_error.emit(title, message, False)
        else:
            self.send_error.emit(title, message, True)

    def _on_auto_tx_send_requested(self, command: ManualCommand) -> None:
        """
        AutoTxScheduler의 반복 전송 요청 처리 핸들러 (S-006/S-042)

        `_process_and_send`를 `is_auto_tx=True`로 호출하여, 실패 알림 방식을
        수동 단발 전송과 구분한다 (반복 실패 시 다이얼로그 대신 상태바만, 폭주 방지).

        Args:
            command (ManualCommand): 반복 전송할 명령어 DTO.
        """
        self._process_and_send(command, is_auto_tx=True)

    def on_auto_tx_toggled(self, enabled: bool) -> None:
        """
        Auto Tx(주기적 자동 전송) 체크박스 토글 처리 핸들러 (S-006)

        Logic:
            - 활성화: 현재 UI 상태로 ManualCommand를 스냅샷하고, 간격(ms)을 조회하여
              AutoTxScheduler를 시작 (가공 실패 시 체크박스를 다시 해제하여 UI 동기화)
            - 비활성화: AutoTxScheduler 정지

        Args:
            enabled (bool): Auto Tx 활성화 여부.
        """
        if enabled:
            command = self._build_command_from_panel()
            if command is None:
                self.panel.set_auto_tx_checked(False)
                return

            interval_ms = self.panel.get_auto_tx_interval_ms()
            # 새 반복 시작 — 이전 실행의 실패 스트릭 상태를 이어받지 않도록 초기화
            self._auto_tx_failing = False
            self.auto_tx_scheduler.start(command, interval_ms=interval_ms)
        else:
            self.auto_tx_scheduler.stop()

    def _on_connection_closed(self, _event=None) -> None:
        """
        포트 연결 종료 이벤트 처리 핸들러

        활성 연결이 하나도 남지 않으면 Auto Tx를 자동으로 정지하고
        체크박스 상태를 UI에 동기화합니다.

        Args:
            _event (Any): PortConnectionEvent (사용하지 않음).
        """
        if not self.connection_controller.has_active_connection:
            self.auto_tx_scheduler.stop()
            self.panel.set_auto_tx_checked(False)

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
        # UI 상태 동기화 (선택 사항)
        if hasattr(self.panel, 'set_local_echo_checked'):
            self.panel.set_local_echo_checked(enabled)

    def get_state(self) -> ManualControlState:
        """
        현재 UI 상태를 DTO로 반환합니다. (설정 저장용)

        Logic:
            - View Facade를 통해 데이터 조회 후 DTO 조립

        Returns:
            ManualControlState: 현재 상태 DTO.
        """
        if not self.panel:
            return ManualControlState()

        return ManualControlState(
            input_text=self.panel.get_input_text(),
            hex_mode=self.panel.is_hex_mode(),
            prefix_enabled=self.panel.is_prefix_enabled(),
            suffix_enabled=self.panel.is_suffix_enabled(),
            rts_enabled=self.panel.is_rts_enabled(),
            dtr_enabled=self.panel.is_dtr_enabled(),
            local_echo_enabled=self.local_echo_enabled, # 전역 설정 또는 현재 상태 사용
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