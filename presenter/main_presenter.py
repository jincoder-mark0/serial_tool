"""
메인 프레젠터 모듈

애플리케이션의 최상위 Presenter입니다.
View와 Model을 연결하고 전역 상태를 관리합니다.

## WHY
* MVP 패턴 준수 (비즈니스 로직 분리)
* 하위 Presenter 조율 및 생명주기 관리
* 전역 이벤트(EventBus) 및 설정(Settings) 중앙 제어

## WHAT
* 하위 Presenter 생성 및 연결
* 설정 로드/저장 및 초기화 로직 (LifecycleManager 위임)
* Fast Path 데이터 수신 처리 및 UI Throttling
* 애플리케이션 종료 처리 및 상태 저장
* 매크로 실행 중 예외 상황(포트 끊김, 종료 등) 방어 로직
* 브로드캐스트 모드에 따른 UI 활성화 상태 동기화

## HOW
* EventRouter 및 Signal/Slot 기반 통신
* View의 Facade 메서드를 통한 상태 조회 (LoD 준수)
* DTO를 활용한 데이터 교환 (Type Safety)
* SettingsManager 주입 및 관리
"""
from typing import Optional
from PyQt5.QtCore import QObject, QTimer, QDateTime, QCoreApplication

from view.main_window import MainWindow
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner

from .port_presenter import PortPresenter
from .macro_presenter import MacroPresenter
from .file_presenter import FilePresenter
from .packet_presenter import PacketPresenter
from .manual_control_presenter import ManualControlPresenter
from .event_router import EventRouter
from .data_handler import DataTrafficHandler
from .lifecycle_manager import AppLifecycleManager
from .logging_format_resolver import LoggingFormatResolver
from .preferences_coordinator import PreferencesCoordinator
from .shutdown_state_collector import ShutdownStateCollector

from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager
from core.text_log_writer import TextLogWriter

from view.panels.port_panel import PortPanel

from view.managers.language_manager import language_manager
from view.managers.color_manager import color_manager
from core.logger import logger
from common.constants import ConfigKeys, EventTopics
from common.dtos import (
    ManualCommand,
    PortDataEvent,
    PortErrorEvent,
    PortStatistics,
    PreferencesState,
    FontConfig,
    PortConnectionEvent,
    MacroErrorEvent,
    FileErrorEvent,
    FileCompletionEvent,
    SystemLogEvent,
    MacroSendResult
)

class MainPresenter(QObject):
    """
    메인 프레젠터 클래스

    애플리케이션의 전체적인 흐름을 제어하고 하위 Presenter를 관리합니다.
    View의 내부 구조를 알지 못해도 인터페이스를 통해 제어할 수 있도록 설계되었습니다.
    """

    def __init__(self, view: MainWindow) -> None:
        """
        MainPresenter 생성 및 초기화

        Logic:
            - LifecycleManager를 통한 초기화 시퀀스 실행
            - View의 추상화된 시그널 연결 (UI 상태 동기화)

        Args:
            view (MainWindow): 메인 윈도우 뷰 인스턴스.
        """
        super().__init__()
        self.view = view
        self.settings_manager = SettingsManager()
        self.status_timer: Optional[QTimer] = None
        # 시스템 로그 REC 토글의 실제 파일 기록 라이터 (S-055). None이면 미기록 상태.
        self._sys_log_writer: Optional[TextLogWriter] = None

        # LifecycleManager를 통해 초기화 위임
        self.lifecycle_manager = AppLifecycleManager(self)
        self.lifecycle_manager.initialize_app()

        # 탭 변경 시 UI 상태 동기화를 위해 시그널 연결
        self.view.connect_port_tab_changed(self._on_port_tab_changed)

    def _init_core_systems(self) -> None:
        """
        Model 및 Core 시스템 초기화 (LifecycleManager에서 호출).
        """
        self.connection_controller = ConnectionController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()
        self.data_handler = DataTrafficHandler(self.view)

    def _init_sub_presenters(self) -> None:
        """
        하위 Presenter 인스턴스 생성 (LifecycleManager에서 호출).
        """
        # Port Control
        # View Facade Property 사용 (LoD 준수)
        self.port_presenter = PortPresenter(self.view.port_view, self.connection_controller)

        # Macro Control
        self.macro_presenter = MacroPresenter(self.view.macro_view, self.macro_runner)

        # File Transfer
        self.file_presenter = FilePresenter(self.connection_controller)

        # Packet Inspector
        self.packet_presenter = PacketPresenter(
            self.view.packet_view,
            self.event_router,
            self.settings_manager
        )

        # Manual Control
        self.manual_control_presenter = ManualControlPresenter(
            self.view.manual_control_view,
            self.connection_controller,
            self.view.append_local_echo_data,
            self.port_presenter.get_active_port_name
        )

    def _connect_signals(self) -> None:
        """
        EventRouter, Model, View 간의 시그널 연결.

        Logic:
            - EventRouter를 통해 비동기 이벤트를 수신하여 핸들러 연결
            - View의 사용자 입력 이벤트를 핸들러 연결
            - Model의 직접적인 시그널 연결
            - 하위 Presenter의 브로드캐스트 변경 감지 연결
        """
        # EventRouter 연결 (Model -> UI Thread)
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)

        # Data 송신 로그 처리를 위해 Handler로 라우팅
        self.event_router.data_sent.connect(self._on_data_sent_router)

        self.event_router.macro_started.connect(self.on_macro_started)
        self.event_router.macro_finished.connect(self.on_macro_finished)
        self.event_router.macro_error.connect(self.on_macro_error)

        self.event_router.file_transfer_completed.connect(self.on_file_transfer_completed)
        self.event_router.file_transfer_error.connect(self.on_file_transfer_error)

        self.event_router.settings_changed.connect(self.on_settings_change_requested)

        # 내부 Model 연결
        # 단발 전송(send_single_command)은 시그널 경로 그대로 — 메인 스레드에서 온다.
        self.macro_runner.send_requested.connect(self.on_macro_send_requested)

        # 매크로 실행 루프는 **결과가 필요한** 동기 경로를 쓴다 (S-080).
        # 시그널은 반환값이 없어, 전송 실패를 스텝 판정에 반영할 수 없었다.
        self.macro_runner.set_send_handler(self.deliver_macro_command)

        # View 연결 (Facade Signal 사용)
        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.close_requested.connect(self.on_close_requested)
        self.view.preferences_requested.connect(self.on_preferences_requested)

        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

        self.view.file_transfer_dialog_opened.connect(self.file_presenter.on_file_transfer_dialog_opened)

        # 포트 탭 추가 시 로깅 시그널 등 재연결을 위해 View 시그널 사용
        self.view.port_tab_added.connect(self._on_port_tab_added)

        # 로깅 시그널 연결 (각 탭별)
        self._connect_logging_signals()

        # 하위 Presenter의 브로드캐스트 설정 변경 감지
        # 사용자가 'Broadcast' 체크박스를 누를 때마다 활성화 상태를 재계산해야 함
        self.manual_control_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )
        # 수동 전송(Auto Tx 포함) 실패를 매크로 에러와 동일한 관례로 표면화 (S-042)
        self.manual_control_presenter.send_error.connect(self._on_manual_send_error)
        self.macro_presenter.broadcast_changed.connect(
            lambda _: self._update_controls_state_for_current_tab()
        )

    # -------------------------------------------------------------------------
    # Helper Methods for Logging
    # -------------------------------------------------------------------------
    def _log_info(self, message: str) -> None:
        """INFO 레벨 시스템 로그 기록."""
        # View Facade 메서드 사용 (내부 위젯 구조 몰라도 됨)
        self.view.log_system_message(SystemLogEvent(message=message, level="INFO"))

    def _log_error(self, message: str) -> None:
        """ERROR 레벨 시스템 로그 기록."""
        self.view.log_system_message(SystemLogEvent(message=message, level="ERROR"))

    def _log_success(self, message: str) -> None:
        """SUCCESS 레벨 시스템 로그 기록."""
        self.view.log_system_message(SystemLogEvent(message=message, level="SUCCESS"))

    # -------------------------------------------------------------------------
    # Settings & Lifecycle Handlers
    # -------------------------------------------------------------------------
    def on_preferences_requested(self) -> None:
        """
        설정을 변경할 수 있는 PreferencesDialog를 표시합니다.

        Logic:
            - PreferencesCoordinator를 통해 현재 설정으로부터 DTO 조립 (S-058)
            - View에 전달
        """
        state = PreferencesCoordinator.build_state(self.settings_manager)
        self.view.open_preferences_dialog(state)

    def on_close_requested(self) -> None:
        """
        애플리케이션 종료 처리 핸들러

        Logic:
            - 매크로 러너 안전 종료 (Wait)
            - 데이터 핸들러 및 타이머 정지
            - View에서 현재 윈도우 및 위젯 상태(DTO) 수집 (Facade)
            - SettingsManager를 통해 설정 저장
            - 활성 연결 종료
            - RX 데이터 로거 정리 (연결 종료 이후, S-059)
            - 종료 로그 기록
        """
        logger.info("Shutdown initiated...")

        # [안전 종료] 매크로 러너가 실행 중이라면 강제 종료 및 대기
        if self.macro_runner.isRunning():
            logger.info("Stopping active macro runner...")
            self.macro_runner.stop()
            self.macro_runner.wait(1000)  # 최대 1초 대기

        # [안전 종료] 진행 중인 포트 스캔 스레드 정리 (S-062).
        # 데이터 유실과 무관한 온디맨드 스레드라 RX 로거의 "연결 종료 ->
        # processEvents -> 로거 정리" 순서(S-059, 아래)와는 별개로, 같은
        # "백그라운드 스레드 정리" 단계로 매크로 러너 옆에 둔다.
        self.port_presenter.stop_pending_scan()

        self.data_handler.stop()
        # 패킷 뷰 버퍼(S-061)에 남은 잔여를 조용히 버리지 않고 flush한다.
        self.packet_presenter.stop()
        if self.status_timer:
            self.status_timer.stop()

        # 시스템 로그 REC 중이었다면 파일을 닫아 유실을 방지한다 (S-055).
        # AppLifecycleManager는 초기화 시퀀스만 담당하고 별도 종료 시퀀스가 없어
        # (initialize_app()만 존재), 실제 종료 처리는 이 메서드가 유일한 지점이다.
        self._close_sys_log_writer()

        # View 상태 수집 (Facade Method 사용)
        state = self.view.get_window_state()

        # ManualControlPresenter를 통해 상태 DTO 획득
        manual_state_dto = self.manual_control_presenter.get_state()

        # DTO -> Dict 변환·병합 및 SettingsManager 반영은 ShutdownStateCollector로
        # 통합 (S-058) — 저장 키·조건·순서는 기존과 완전히 동일하다.
        settings = self.settings_manager
        ShutdownStateCollector.collect_and_apply(settings, state, manual_state_dto)

        settings.save_settings()

        if self.connection_controller.has_active_connection:
            self.connection_controller.close_connection()

        # [S-059] RX 데이터 로거 정리: 반드시 연결 종료 "이후"에 수행한다.
        # 근거: ConnectionWorker.run()은 종료 직전 finally에서 배치 버퍼에 남은
        # 마지막 RX 조각을 data_received로 flush한다(worker 스레드 emit, Fast Path로
        # data_logger_manager.write()까지 전달). close_connection() -> worker.stop()은
        # QThread.wait()로 블로킹 대기하므로, 그 사이 발생한 교차 스레드 큐잉 시그널은
        # 메인 이벤트 루프가 아직 처리하지 못한 상태로 남는다. 로거를 먼저 닫으면
        # 이 마지막 조각이 아직 파일에 반영되기 전에 파일이 닫혀 유실된다.
        # 따라서 (1) 연결 종료 -> (2) processEvents()로 큐잉된 마지막 Fast Path
        # 시그널 배송 -> (3) 로거 정리 순서로만 유실 없이 닫을 수 있다.
        QCoreApplication.processEvents()
        data_logger_manager.stop_all()

        logger.info("Shutdown completed.")

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        """
        설정 변경 요청 처리

        Args:
            new_state (PreferencesState): 변경된 설정 상태 DTO.
        """
        settings = self.settings_manager
        # 설정 저장 로직: DTO<->키 매핑은 PreferencesCoordinator로 통합 (S-058)
        PreferencesCoordinator.apply_state(settings, new_state)

        settings.save_settings()

        # UI 즉시 반영
        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)

        # 모든 포트 탭 업데이트 (Facade 사용)
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            # PortPanel인지 확인하고 설정 (View 내부 로직 의존 최소화)
            if hasattr(widget, 'set_max_log_lines'):
                widget.set_max_log_lines(new_state.max_log_lines)

        self.manual_control_presenter.update_local_echo_setting(new_state.local_echo_enabled)

        # EventBus로 변경 전파
        from core.event_bus import event_bus
        event_bus.publish(EventTopics.SETTINGS_CHANGED, new_state)

        settings_updated_msg = language_manager.get_text("main_status_msg_settings_updated")
        self.view.show_status_message(settings_updated_msg, 2000)
        self._log_info(settings_updated_msg)

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        """
        폰트 설정 변경 처리

        Args:
            font_config (FontConfig): 폰트 설정 DTO.
        """
        settings = self.settings_manager
        settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        settings.save_settings()
        logger.info("Font settings saved successfully.")

    # -------------------------------------------------------------------------
    # Port & Data Handlers
    # -------------------------------------------------------------------------
    def _on_data_sent_router(self, event: PortDataEvent) -> None:
        """
        데이터 송신 이벤트 (EventRouter -> DataHandler)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트 DTO.
        """
        self.data_handler.on_data_sent(event)

    def on_port_opened(self, event: PortConnectionEvent) -> None:
        """
        포트 열림 알림

        Logic:
            - 상태바 업데이트
            - 컨트롤 패널(수동/매크로) 활성화 동기화

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        self.view.update_status_bar_port(event.port, True)
        self.view.show_status_message(f"Connected to {event.port}", 3000)

        self._update_controls_state_for_current_tab()

    def on_port_closed(self, event: PortConnectionEvent) -> None:
        """
        포트 닫힘 알림

        Logic:
            - 매크로 실행 중 포트가 닫히면 매크로 중단
            - 상태바 업데이트
            - 컨트롤 패널 비활성화 동기화

        Args:
            event (PortConnectionEvent): 포트 연결 이벤트 DTO.
        """
        port_name = event.port

        # 매크로 실행 중 포트가 닫히면 매크로 중단 (Ghost Run 방지)
        if self.macro_runner.isRunning():
            # 1. 단일 전송 모드인데 타겟 포트가 닫힌 경우
            target_port = self.port_presenter.get_active_port_name()
            if not self.macro_runner.broadcast_enabled and target_port == port_name:
                self._notify_macro_error(f"Target port '{port_name}' closed. Macro stopped.")

            # 2. 브로드캐스트 모드인데 남은 활성 포트가 없는 경우
            elif self.macro_runner.broadcast_enabled:
                if not self.connection_controller.has_active_broadcast_ports():
                    self._notify_macro_error("No active ports left. Macro stopped.")

        self.view.update_status_bar_port(event.port, False)
        self.view.show_status_message(f"Disconnected from {event.port}", 3000)

        self._update_controls_state_for_current_tab()

    def on_port_error(self, event: PortErrorEvent) -> None:
        """
        포트 오류 알림

        Args:
            event (PortErrorEvent): 포트 오류 이벤트 DTO.
        """
        self.view.show_status_message(f"Error ({event.port}): {event.message}", 5000)

    def _on_port_tab_changed(self, index: int) -> None:
        """
        포트 탭 변경 시 호출됨
        새로운 탭의 연결 상태에 따라 전역 컨트롤(매크로, 수동 제어) 활성화 상태 동기화

        Args:
            index (int): 변경된 탭 인덱스.
        """
        self._update_controls_state_for_current_tab()

    def _update_controls_state_for_current_tab(self) -> None:
        """
        컨트롤 패널(Manual/Macro)의 활성화 상태 동기화

        Logic:
            - View의 Facade 메서드를 통해 현재 탭의 연결 상태 확인
            - 규칙: (현재 탭 연결됨) OR (브로드캐스트 켜짐 AND 활성 포트 있음)
        """
        # 1. View를 통해 현재 탭 연결 상태 조회 (Facade Method)
        is_current_connected = self.view.is_current_port_connected()

        # 2. 전체 시스템의 활성 포트 존재 여부 확인
        has_any_connection = self.connection_controller.has_active_connection

        # 3. Manual Control 활성화 로직
        if self.manual_control_presenter:
            is_broadcast = self.manual_control_presenter.is_broadcast_enabled()
            # (현재 연결됨) OR (브로드캐스트 켜짐 AND 활성 포트 있음)
            should_enable = is_current_connected or (is_broadcast and has_any_connection)
            self.manual_control_presenter.set_enabled(should_enable)

        # 4. Macro Control 활성화 로직
        if self.macro_presenter:
            is_broadcast = self.macro_presenter.is_broadcast_enabled()
            should_enable = is_current_connected or (is_broadcast and has_any_connection)
            self.macro_presenter.set_enabled(should_enable)

    # -------------------------------------------------------------------------
    # Macro Handlers
    # -------------------------------------------------------------------------
    def on_macro_started(self) -> None:
        """매크로 시작 알림"""
        self._log_info("Macro started")
        self.view.show_status_message(language_manager.get_text("main_status_msg_macro_running"), 0)

    def on_macro_finished(self) -> None:
        """매크로 종료 알림"""
        self._log_success("Macro finished")
        self.view.show_status_message(language_manager.get_text("main_status_msg_macro_finished"), 3000)

    def on_macro_error(self, event: MacroErrorEvent) -> None:
        """
        매크로 오류 알림

        Args:
            event (MacroErrorEvent): 매크로 에러 이벤트 DTO.
        """
        row_info = f"(Row {event.row_index})" if event.row_index >= 0 else ""
        msg = f"Macro Error {row_info}: {event.message}"
        self._log_error(msg)
        self.view.show_status_message(msg, 5000)

    def deliver_macro_command(self, manual_command: ManualCommand) -> MacroSendResult:
        """
        매크로 명령을 실제로 전송하고 **결과를 돌려줍니다** (S-080).

        Logic:
            1. Prefix/Suffix 조회 및 데이터 가공
            2. 전송 대상 유효성 검사
            3. Broadcast 여부에 따라 전송하고 수락 여부를 받는다
            4. Local Echo는 여기서 하지 않는다 — 위젯 접근이기 때문이다

        Threading:
            **매크로 스레드에서 직접 호출된다.** 그래서 이 메서드는 위젯을 만지지
            않고, 스레드 안전한 것만 쓴다(SettingsManager 조회, 뮤텍스로 보호된
            워커 큐). Local Echo처럼 UI를 건드리는 일은 호출자가 시그널로
            메인 스레드에 넘긴다.

            결과를 시그널로 되받는 방식(BlockingQueuedConnection)은 쓸 수 없다 —
            `MacroRunner.stop()`이 메인 스레드에서 `wait()`로 매크로 스레드를
            기다리므로, 매크로 스레드가 메인 스레드를 기다리면 교착한다.

        Args:
            manual_command (ManualCommand): 전송할 명령어 DTO.

        Returns:
            MacroSendResult: 성공 여부, 실패 사유, 전송된 바이트.
        """
        # 1. 설정값 조회 (Prefix/Suffix)
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if manual_command.prefix_enabled else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if manual_command.suffix_enabled else None

        # 2. 데이터 가공
        try:
            data = CommandProcessor.process_command(
                manual_command.command,
                manual_command.hex_mode,
                prefix=prefix,
                suffix=suffix
            )
        except ValueError as e:
            return MacroSendResult(False, f"Command processing error: {e}")

        # 3. 전송 (Broadcast vs Single)
        if manual_command.broadcast_enabled:
            # 브로드캐스트 가능한 활성 포트가 하나도 없는 경우 중단
            if not self.connection_controller.has_active_broadcast_ports():
                return MacroSendResult(False, "No active ports available for broadcast.")

            if not self.connection_controller.send_broadcast_data(data):
                return MacroSendResult(False, "Broadcast send failed on one or more ports.")
            return MacroSendResult(True, "", data)

        # 단일 포트 전송
        active_port = self.port_presenter.get_active_port_name()

        if not active_port:
            return MacroSendResult(False, "No port selected.")

        if not self.connection_controller.is_connection_open(active_port):
            return MacroSendResult(False, f"Port '{active_port}' is disconnected.")

        if not self.connection_controller.send_data(active_port, data):
            return MacroSendResult(False, f"Send failed on port '{active_port}'.")

        return MacroSendResult(True, "", data)

    def on_macro_send_requested(self, manual_command: ManualCommand) -> None:
        """
        매크로 단발 전송 요청 처리 (Runner -> Controller, 메인 스레드 슬롯)

        Logic:
            - 실제 전송은 `deliver_macro_command`가 한다
            - 여기서는 실패 알림과 Local Echo 등 **UI 쪽 뒷일**만 맡는다

        Args:
            manual_command (ManualCommand): 전송할 명령어 DTO.
        """
        result = self.deliver_macro_command(manual_command)

        if not result.success:
            self._notify_macro_error(result.message)
            return

        self.show_local_echo(result.data)

    def show_local_echo(self, data: bytes) -> None:
        """
        설정이 켜져 있으면 송신 데이터를 수신창에 표시합니다 (메인 스레드 전용).

        Args:
            data (bytes): 방금 보낸 바이트.
        """
        if not data:
            return
        if self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False):
            self.view.append_local_echo_data(data)

    def _notify_macro_error(self, message: str) -> None:
        """
        매크로 실행 중 에러 발생 시 처리 (Helper)

        Logic:
            - 로그 기록
            - 매크로 강제 중단(stop) 요청
            - 사용자 알림

        Args:
            message (str): 에러 메시지.
        """
        logger.error(f"Macro stopped: {message}")
        self.macro_runner.stop()
        self.view.show_status_message(language_manager.get_text("main_status_msg_macro_stopped").format(message), 5000)
        self.view.show_alert_message(language_manager.get_text("main_title_macro_error"), message)

    def _on_manual_send_error(self, title: str, message: str, show_dialog: bool) -> None:
        """
        수동 전송(Auto Tx 포함) 실패 알림 처리 (S-042)

        `_notify_macro_error`와 동일한 상태바+다이얼로그 관례를 재사용한다.
        `show_dialog`는 ManualControlPresenter가 판단해서 넘긴다 — 사용자의
        단발 Send 클릭 실패는 True(다이얼로그 포함), Auto Tx 반복 실패는
        연속 실패의 첫 회에서만 False(상태바만)로 전달되어 알림 폭주를 막는다.

        Args:
            title (str): 다이얼로그 제목 (show_dialog=True일 때만 사용).
            message (str): 알림 메시지.
            show_dialog (bool): 모달 다이얼로그 표시 여부.
        """
        self._log_error(f"Manual send failed: {message}")
        self.view.show_status_message(message, 5000)
        if show_dialog:
            self.view.show_alert_message(title, message)

    # -------------------------------------------------------------------------
    # File Transfer Handlers
    # -------------------------------------------------------------------------
    def on_file_transfer_completed(self, event: FileCompletionEvent) -> None:
        """
        파일 전송 완료 처리

        Args:
            event (FileCompletionEvent): 완료 이벤트 DTO.
        """
        status_key = "file_prog_lbl_status_completed" if event.success else "file_prog_lbl_status_failed"
        status_text = language_manager.get_text(status_key)
        msg = language_manager.get_text("main_msg_file_transfer_result").format(status_text, event.message)

        if event.success:
            self._log_success(msg)
        else:
            self._log_error(msg)

        self.view.show_status_message(
            language_manager.get_text("main_status_msg_file_transfer_result").format(status_text), 3000
        )

    def on_file_transfer_error(self, event: FileErrorEvent) -> None:
        """
        파일 전송 오류 처리

        Args:
            event (FileErrorEvent): 에러 이벤트 DTO.
        """
        self._log_error(f"File Transfer Error: {event.message}")

    # -------------------------------------------------------------------------
    # UI Updates & Shortcuts
    # -------------------------------------------------------------------------
    def update_status_bar(self) -> None:
        """
        상태 표시줄 업데이트 (Timer Slot).
        DataHandler의 통계를 바탕으로 UI 갱신.
        """
        stats = PortStatistics(
            rx_bytes=self.data_handler.rx_byte_count,
            tx_bytes=self.data_handler.tx_byte_count,
            bps=0
        )

        self.view.update_status_bar_stats(stats)

        # 카운터 초기화 (Interval 단위 속도 계산용)
        self.data_handler.reset_counts()
        self.view.update_status_bar_time(QDateTime.currentDateTime().toString("HH:mm:ss"))

    def on_shortcut_connect(self) -> None:
        """연결 단축키(F2) 처리."""
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        """연결 해제 단축키(F3) 처리."""
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """로그 초기화 단축키(F5) 처리."""
        self.port_presenter.clear_log_current_port()

    # -------------------------------------------------------------------------
    # Logging Connections
    # -------------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        """기존 모든 포트 탭 + 시스템 로그의 로깅 시그널을 연결합니다."""
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            self._connect_single_port_logging(widget)

        # 시스템 로그는 포트 탭과 달리 앱 생명주기 동안 단일 인스턴스이므로 1회만 연결 (S-052)
        self._connect_system_logging_signals()

    def _connect_system_logging_signals(self) -> None:
        """
        시스템 로그(SystemLogWidget)의 로깅 요청 시그널을 연결합니다.

        Logic:
            - S-052: SystemLogWidget도 DataLogWidget과 동일한 Presenter 권위
              제어 흐름을 쓰므로, DataLog와 대칭인 요청 시그널을 동일하게 연결한다.
            - View Facade(port_view = MainLeftSection)의 시그널만 사용 (LoD 준수).
        """
        left_view = self.view.port_view
        left_view.sys_logging_start_requested.connect(self._on_sys_logging_start_requested)
        left_view.sys_logging_stop_requested.connect(self._on_sys_logging_stop_requested)
        # 화면에 실제로 추가되는 시스템 로그 한 줄 한 줄을 라이터에도 전달 (S-055)
        left_view.system_log_line_appended.connect(self._on_system_log_line_appended)

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        """
        포트 탭 추가 시 로깅 시그널 연결 핸들러

        Args:
            panel (PortPanel): 추가된 포트 패널.
        """
        self._connect_single_port_logging(panel)
        # 새 탭에 색상 규칙 주입 (LoD: Panel의 Facade 메서드 사용)
        panel.set_data_log_color_rules(color_manager.rules)

    def _connect_single_port_logging(self, panel: PortPanel) -> None:
        """
        단일 포트 패널의 로깅 시그널 연결

        Logic:
            - Panel의 로깅 요청 시그널을 핸들러에 연결
            - DataLogWidget 직접 접근 대신 Panel의 시그널 사용 (Facade)

        Args:
            panel (PortPanel): 포트 패널.
        """
        # LoD 준수: Panel의 시그널 사용
        if hasattr(panel, 'logging_start_requested'):
            try:
                panel.logging_start_requested.disconnect()
                panel.logging_stop_requested.disconnect()
            except TypeError:
                pass

            # Lambda로 패널 컨텍스트 전달
            panel.logging_start_requested.connect(lambda: self._on_logging_start_requested(panel))
            panel.logging_stop_requested.connect(lambda: self._on_logging_stop_requested(panel))

    def _start_log_capture_dialog(self, widget) -> Optional[str]:
        """
        로깅 시작 요청의 공통부: 파일 저장 다이얼로그 표시 + 취소 처리.

        DataLog(PortPanel)/SystemLog(MainLeftSection) 양쪽이 동일하게 필요로 하는
        "다이얼로그를 띄우고, 취소되면 위젯을 비활성 상태로 되돌린다" 절차만 묶는다
        (S-052 — 로그 종류별 차이인 파일 확장자 기본값·대상 위젯은 호출부가 담당).

        Args:
            widget: `show_save_log_dialog()`/`set_logging_active()`를 제공하는
                View Facade(PortPanel 또는 MainLeftSection).

        Returns:
            Optional[str]: 선택된 파일 경로. 취소 시 None(위젯은 비활성 상태로 복귀됨).
        """
        file_path = widget.show_save_log_dialog()
        if not file_path:
            widget.set_logging_active(False)
            return None
        return file_path

    def _on_logging_start_requested(self, panel: PortPanel) -> None:
        """
        로깅 시작 요청 처리

        Logic:
            - Panel을 통해 파일 다이얼로그 표시
            - 확장자 기반 포맷 결정 (BIN/HEX/PCAP)
            - DataLoggerManager에 시작 요청
            - Panel을 통해 로깅 활성화 UI 상태 업데이트

        Args:
            panel (PortPanel): 요청한 패널.
        """
        file_path = self._start_log_capture_dialog(panel)
        if file_path is None:
            return

        port = panel.get_port_name()
        if not port:
            panel.set_logging_active(False)
            return

        # 확장자 기반 포맷 결정 (순수 로직은 LoggingFormatResolver로 분리 — S-058)
        log_format = LoggingFormatResolver.resolve(file_path)

        # 포맷 전달 및 시작
        if data_logger_manager.start_logging(port, file_path, log_format):
            panel.set_logging_active(True)
            self._log_info(f"[{port}] Logging started ({log_format.value}): {file_path}")
        else:
            panel.set_logging_active(False)
            self._log_error(f"[{port}] Failed to start logging")

    def _on_logging_stop_requested(self, panel: PortPanel) -> None:
        """
        로깅 중지 요청 처리

        Args:
            panel (PortPanel): 요청한 패널.
        """
        port = panel.get_port_name()
        if port:
            data_logger_manager.stop_logging(port)

        # Panel Facade 사용
        panel.set_logging_active(False)
        self._log_info(f"[{port}] Logging stopped")

    def _on_sys_logging_start_requested(self) -> None:
        """
        시스템 로그 REC 시작 요청 처리 (S-052 제어 흐름, S-055 실제 파일 기록).

        Logic:
            - View Facade(MainLeftSection)를 통해 파일 다이얼로그 표시
            - DataLog와 달리 포트에 종속되지 않는 단일 로그이므로 DataLoggerManager
              대신 전용 TextLogWriter(core/text_log_writer.py)를 사용한다
              (시스템 로그는 줄 단위 텍스트, DataLogger는 바이트 스트림 전용).
            - 파일 열기 실패는 조용히 삼키지 않는다(S-039/S-045 원칙) — REC UI를
              켜지 않고 ERROR로 표면화한다.
        """
        left_view = self.view.port_view
        file_path = self._start_log_capture_dialog(left_view)
        if file_path is None:
            return

        writer = TextLogWriter()
        try:
            writer.open(file_path)
        except OSError as e:
            left_view.set_logging_active(False)
            self._log_error(f"Failed to start system log recording ({file_path}): {e}")
            return

        self._sys_log_writer = writer
        left_view.set_logging_active(True)
        self._log_info(f"System log recording enabled: {file_path}")

    def _on_sys_logging_stop_requested(self) -> None:
        """시스템 로그 REC 중지 요청 처리 (S-052 제어 흐름, S-055 실제 파일 닫기)."""
        left_view = self.view.port_view
        self._close_sys_log_writer()
        left_view.set_logging_active(False)
        self._log_info("System log recording stopped")

    def _close_sys_log_writer(self) -> None:
        """
        시스템 로그 라이터가 열려 있으면 닫습니다 (S-055).

        REC 중지 요청 처리와 앱 종료 처리(`on_close_requested`) 양쪽에서
        공유하는 정리 로직 — 앱 종료 시에도 REC 중이었다면 파일이 유실 없이
        닫혀야 한다.
        """
        if self._sys_log_writer is not None:
            self._sys_log_writer.close()
            self._sys_log_writer = None

    def _on_system_log_line_appended(self, text: str) -> None:
        """
        화면에 실제로 추가된 시스템 로그 한 줄을 파일에도 기록합니다 (S-055).

        Logic:
            - 현재 REC 중이 아니면(writer가 None) 아무 것도 하지 않는다.
            - 쓰기 실패 시 조용히 삼키지 않는다 — writer를 먼저 닫아 REC 상태를
              끈 뒤(재귀적으로 이 메서드가 다시 불려도 즉시 반환되도록) ERROR로
              표면화한다. writer를 먼저 정리하지 않으면 `_log_error()`가 다시
              이 메서드를 재호출할 때 동일한 쓰기 실패가 반복될 수 있다.

        Args:
            text: 화면에 추가된 것과 동일한(필터 적용 후) 한 줄.
        """
        if self._sys_log_writer is None:
            return

        writer = self._sys_log_writer
        try:
            writer.write_line(text)
        except OSError as e:
            self._sys_log_writer = None
            writer.close()
            self.view.port_view.set_logging_active(False)
            self._log_error(f"System log write failed, recording stopped: {e}")