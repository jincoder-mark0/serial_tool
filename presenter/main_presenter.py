"""
메인 프레젠터 모듈

애플리케이션의 최상위 Presenter입니다.
View와 Model을 연결하고 전역 상태를 관리합니다.
구체적인 View 구현체 대신 인터페이스(Protocol)에 의존하여 결합도를 최소화합니다.

## WHY
* MVP 패턴 준수 (비즈니스 로직 분리) 및 View 구현체 교체 용이성 확보 (DIP)
* 하위 Presenter 조율 및 생명주기 관리
* 전역 이벤트(EventBus) 및 설정(Settings) 중앙 제어

## WHAT
* 하위 Presenter 생성 및 연결 (Interface 기반)
* 설정 로드/저장 및 초기화 로직 (LifecycleManager 위임)
* Fast Path 데이터 수신 처리 및 UI Throttling
* 애플리케이션 종료 처리 및 상태 저장
* 매크로 실행 중 예외 상황 방어 및 브로드캐스트 상태 동기화

## HOW
* EventRouter 및 Signal/Slot 기반 통신
* IMainView 인터페이스를 통한 상태 조회 및 명령 (LoD 준수)
* DTO를 활용한 데이터 교환 (Type Safety)
* SettingsManager 주입 및 관리
"""
import os
from typing import Optional, cast

from PyQt5.QtCore import QObject, QTimer, QDateTime, Qt

from view.interfaces import IMainView, IPortView
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

from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager

from view.managers.language_manager import language_manager
from view.managers.color_manager import color_manager
from core.logger import logger
from common.constants import ConfigKeys, EventTopics
from common.enums import LogFormat
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
    SystemLogEvent
)


class MainPresenter(QObject):
    """
    메인 프레젠터 클래스

    애플리케이션의 전체적인 흐름을 제어하고 하위 Presenter를 관리합니다.
    View의 내부 구조를 알지 못해도 인터페이스(IMainView)를 통해 제어할 수 있도록 설계되었습니다.
    """

    def __init__(self, view: IMainView) -> None:
        """
        MainPresenter 생성 및 초기화

        Logic:
            - LifecycleManager를 통한 초기화 시퀀스 실행
            - View의 추상화된 시그널 연결 (UI 상태 동기화)

        Args:
            view (IMainView): 메인 윈도우 뷰 인터페이스.
        """
        super().__init__()
        self.view = view
        self.settings_manager = SettingsManager()
        self.status_timer: Optional[QTimer] = None

        # LifecycleManager를 통해 초기화 위임
        self.lifecycle_manager = AppLifecycleManager(self)
        self.lifecycle_manager.initialize_app()

        # 탭 변경 시 UI 상태 동기화를 위해 시그널 연결 (Interface 사용)
        self.view.connect_port_tab_changed(self._on_port_tab_changed)

    def _init_core_systems(self) -> None:
        """
        Model 및 Core 시스템 초기화 (LifecycleManager에서 호출).
        """
        self.connection_controller = ConnectionController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()
        # DataHandler는 MainWindow(View 구현체)를 필요로 할 수 있으므로 cast 사용 가능하지만,
        # DataHandler 내부도 추후 인터페이스 의존적으로 리팩토링 권장.
        # 현재 단계에서는 view를 그대로 전달.
        self.data_handler = DataTrafficHandler(self.view)

    def _init_sub_presenters(self) -> None:
        """
        하위 Presenter 인스턴스 생성 (LifecycleManager에서 호출).
        View Interface의 Property를 사용하여 하위 View에 접근합니다.
        """
        # Port Control
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
            - View Interface의 사용자 입력 이벤트를 핸들러 연결
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
        self.macro_runner.send_requested.connect(self.on_macro_send_requested)

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
            - SettingsManager에서 현재 설정을 조회
            - PreferencesState DTO 생성 및 View에 전달
        """
        settings = self.settings_manager
        state = PreferencesState(
            theme=settings.get(ConfigKeys.THEME, "Dark").capitalize(),
            language=settings.get(ConfigKeys.LANGUAGE, "en"),
            font_size=settings.get(ConfigKeys.PROP_FONT_SIZE, 10),
            max_log_lines=settings.get(ConfigKeys.RX_MAX_LINES, 2000),
            baudrate=settings.get(ConfigKeys.PORT_BAUDRATE, 115200),
            newline=str(settings.get(ConfigKeys.PORT_NEWLINE, "\n")),
            local_echo_enabled=settings.get(ConfigKeys.PORT_LOCAL_ECHO, False),
            scan_interval_ms=settings.get(ConfigKeys.PORT_SCAN_INTERVAL, 1000),
            command_prefix=settings.get(ConfigKeys.COMMAND_PREFIX, ""),
            command_suffix=settings.get(ConfigKeys.COMMAND_SUFFIX, ""),
            log_dir=settings.get(ConfigKeys.LOG_PATH, ""),
            parser_type=settings.get(ConfigKeys.PACKET_PARSER_TYPE, 0),
            delimiters=settings.get(ConfigKeys.PACKET_DELIMITERS, ["\\r\\n"]),
            packet_length=settings.get(ConfigKeys.PACKET_LENGTH, 64),
            at_color_ok=settings.get(ConfigKeys.AT_COLOR_OK, True),
            at_color_error=settings.get(ConfigKeys.AT_COLOR_ERROR, True),
            at_color_urc=settings.get(ConfigKeys.AT_COLOR_URC, True),
            at_color_prompt=settings.get(ConfigKeys.AT_COLOR_PROMPT, True),
            packet_buffer_size=settings.get(ConfigKeys.PACKET_BUFFER_SIZE, 100),
            packet_realtime=settings.get(ConfigKeys.PACKET_REALTIME, True),
            packet_autoscroll=settings.get(ConfigKeys.PACKET_AUTOSCROLL, True)
        )
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
        """
        logger.info("Shutdown initiated...")

        # [안전 종료] 매크로 러너가 실행 중이라면 강제 종료 및 대기
        if self.macro_runner.isRunning():
            logger.info("Stopping active macro runner...")
            self.macro_runner.stop()
            self.macro_runner.wait(1000)

        self.data_handler.stop()
        if self.status_timer:
            self.status_timer.stop()

        # View 상태 수집 (Facade Method 사용)
        state = self.view.get_window_state()

        # ManualControlPresenter를 통해 상태 DTO 획득
        manual_state_dto = self.manual_control_presenter.get_state()

        # DTO -> Dict 변환하여 상태 병합 (설정 저장용)
        # Note: 이 부분은 향후 MainPresenter가 직접 DTO를 조립하거나,
        # SettingsManager가 DTO를 직접 받도록 개선할 수 있음.
        state.left_section_state["manual_control"] = {
            "manual_control_widget": {
                "input_text": manual_state_dto.input_text,
                "hex_mode": manual_state_dto.hex_mode,
                "prefix_enabled": manual_state_dto.prefix_enabled,
                "suffix_enabled": manual_state_dto.suffix_enabled,
                "rts_enabled": manual_state_dto.rts_enabled,
                "dtr_enabled": manual_state_dto.dtr_enabled,
                "local_echo_enabled": manual_state_dto.local_echo_enabled,
                "broadcast_enabled": manual_state_dto.broadcast_enabled
            }
        }

        # SettingsManager에 값 설정
        settings = self.settings_manager
        settings.set(ConfigKeys.WINDOW_WIDTH, state.width)
        settings.set(ConfigKeys.WINDOW_HEIGHT, state.height)
        settings.set(ConfigKeys.WINDOW_X, state.x)
        settings.set(ConfigKeys.WINDOW_Y, state.y)
        settings.set(ConfigKeys.SPLITTER_STATE, state.splitter_state)
        settings.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.right_panel_visible)

        if state.right_section_width is not None:
            settings.set(ConfigKeys.SAVED_RIGHT_WIDTH, state.right_section_width)

        # 하위 위젯 상태 저장
        if ConfigKeys.MANUAL_CONTROL_STATE in state.left_section_state:
            settings.set(ConfigKeys.MANUAL_CONTROL_STATE, state.left_section_state[ConfigKeys.MANUAL_CONTROL_STATE])
        if ConfigKeys.PORTS_TABS_STATE in state.left_section_state:
            settings.set(ConfigKeys.PORTS_TABS_STATE, state.left_section_state[ConfigKeys.PORTS_TABS_STATE])
        if ConfigKeys.MACRO_COMMANDS in state.right_section_state:
            settings.set(ConfigKeys.MACRO_COMMANDS, state.right_section_state[ConfigKeys.MACRO_COMMANDS])
        if ConfigKeys.MACRO_CONTROL_STATE in state.right_section_state:
            settings.set(ConfigKeys.MACRO_CONTROL_STATE, state.right_section_state[ConfigKeys.MACRO_CONTROL_STATE])

        settings.save_settings()

        if self.connection_controller.has_active_connection:
            self.connection_controller.close_connection()

        logger.info("Shutdown completed.")

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        """
        설정 변경 요청 처리

        Args:
            new_state (PreferencesState): 변경된 설정 상태 DTO.
        """
        settings = self.settings_manager
        # 설정 저장 로직 ... (기존과 동일)
        settings.set(ConfigKeys.THEME, new_state.theme.lower())
        settings.set(ConfigKeys.LANGUAGE, new_state.language)
        settings.set(ConfigKeys.PROP_FONT_SIZE, new_state.font_size)
        settings.set(ConfigKeys.RX_MAX_LINES, new_state.max_log_lines)
        settings.set(ConfigKeys.PORT_BAUDRATE, new_state.baudrate)
        settings.set(ConfigKeys.PORT_NEWLINE, new_state.newline)
        settings.set(ConfigKeys.PORT_LOCAL_ECHO, new_state.local_echo_enabled)
        settings.set(ConfigKeys.PORT_SCAN_INTERVAL, new_state.scan_interval_ms)
        settings.set(ConfigKeys.COMMAND_PREFIX, new_state.command_prefix)
        settings.set(ConfigKeys.COMMAND_SUFFIX, new_state.command_suffix)
        settings.set(ConfigKeys.LOG_PATH, new_state.log_dir)

        # Packet Settings
        settings.set(ConfigKeys.PACKET_PARSER_TYPE, new_state.parser_type)
        settings.set(ConfigKeys.PACKET_DELIMITERS, new_state.delimiters)
        settings.set(ConfigKeys.PACKET_LENGTH, new_state.packet_length)
        settings.set(ConfigKeys.AT_COLOR_OK, new_state.at_color_ok)
        settings.set(ConfigKeys.AT_COLOR_ERROR, new_state.at_color_error)
        settings.set(ConfigKeys.AT_COLOR_URC, new_state.at_color_urc)
        settings.set(ConfigKeys.AT_COLOR_PROMPT, new_state.at_color_prompt)
        settings.set(ConfigKeys.PACKET_BUFFER_SIZE, new_state.packet_buffer_size)
        settings.set(ConfigKeys.PACKET_REALTIME, new_state.packet_realtime)
        settings.set(ConfigKeys.PACKET_AUTOSCROLL, new_state.packet_autoscroll)

        settings.save_settings()

        # UI 즉시 반영
        # Note: View 구현체가 IMainView 인터페이스에 없는 메서드를 가질 경우 cast 필요할 수 있으나,
        # switch_theme 등은 글로벌 매니저를 통해 동작하므로 View 의존성 낮음.
        # MainWindow(View) 자체 메서드는 인터페이스에 없으면 안 되므로 확인 필요.
        # 여기서는 View 내부 로직에 위임하는 방식이 좋음 (예: view.apply_preferences(new_state))
        # 현재는 Manager에 직접 접근하는 기존 로직 유지 (ViewHelper 패턴)
        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)

        # 모든 포트 탭 업데이트 (Interface 사용)
        count = self.view.get_port_tabs_count()
        for i in range(count):
            # get_port_tab_widget은 IPortView를 반환한다고 가정
            port_view = self.view.get_port_tab_widget(i)
            # Protocol 체크 (Runtime 안전성)
            if port_view and hasattr(port_view, 'set_max_log_lines'):
                port_view.set_max_log_lines(new_state.max_log_lines)

        self.manual_control_presenter.update_local_echo_setting(new_state.local_echo_enabled)

        # EventBus로 변경 전파
        from core.event_bus import event_bus
        event_bus.publish(EventTopics.SETTINGS_CHANGED, new_state)

        self.view.show_status_message("Settings updated", 2000)
        self._log_info("Settings updated")

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
        # 1. View Interface를 통해 현재 탭 연결 상태 조회
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
        self.view.show_status_message("Macro Running...", 0)

    def on_macro_finished(self) -> None:
        """매크로 종료 알림"""
        self._log_success("Macro finished")
        self.view.show_status_message("Macro Finished", 3000)

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

    def on_macro_send_requested(self, manual_command: ManualCommand) -> None:
        """
        매크로 전송 요청 처리 (Runner -> Controller)

        Logic:
            - Prefix/Suffix 등 설정 조회 및 데이터 가공
            - 전송 대상 포트의 유효성 검사
            - Broadcast 여부에 따른 전송 분기
            - 전송 성공 시 Local Echo 출력

        Args:
            manual_command (ManualCommand): 전송할 명령어 DTO.
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
            self._notify_macro_error(f"Command processing error: {e}")
            return

        # 3. 전송 (Broadcast vs Single)
        sent_success = False

        if manual_command.broadcast_enabled:
            # 브로드캐스트 가능한 활성 포트가 하나도 없는 경우 중단
            if not self.connection_controller.has_active_broadcast_ports():
                self._notify_macro_error("No active ports available for broadcast.")
                return

            self.connection_controller.send_broadcast_data(data)
            sent_success = True
        else:
            # 단일 포트 전송
            active_port = self.port_presenter.get_active_port_name()

            if not active_port:
                self._notify_macro_error("No port selected.")
                return

            if not self.connection_controller.is_connection_open(active_port):
                self._notify_macro_error(f"Port '{active_port}' is disconnected.")
                return

            self.connection_controller.send_data(active_port, data)
            sent_success = True

        # 4. Local Echo 처리
        if sent_success:
            local_echo_enabled = self.settings_manager.get(ConfigKeys.PORT_LOCAL_ECHO, False)
            if local_echo_enabled:
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
        self.view.show_status_message(f"Macro Stopped: {message}", 5000)
        self.view.show_alert_message("Macro Error", message)

    # -------------------------------------------------------------------------
    # File Transfer Handlers
    # -------------------------------------------------------------------------
    def on_file_transfer_completed(self, event: FileCompletionEvent) -> None:
        """
        파일 전송 완료 처리

        Args:
            event (FileCompletionEvent): 완료 이벤트 DTO.
        """
        status = "Completed" if event.success else "Failed"
        msg = f"File transfer {status}: {event.message}"

        if event.success:
            self._log_success(msg)
        else:
            self._log_error(msg)

        self.view.show_status_message(f"File Transfer {status}", 3000)

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
        """연결 단축키(F2) 처리: View에게 Trigger 요청"""
        # [Trigger 방식] 로직을 직접 수행하지 않고 View에게 위임
        self.view.port_view.trigger_current_port_connect()

    def on_shortcut_disconnect(self) -> None:
        """연결 해제 단축키(F3) 처리: View에게 Trigger 요청"""
        self.view.port_view.trigger_current_port_disconnect()

    def on_shortcut_clear(self) -> None:
        """로그 초기화 단축키(F5) 처리: View에게 Trigger 요청"""
        self.view.port_view.trigger_current_port_clear_log()

    # -------------------------------------------------------------------------
    # Logging Connections
    # -------------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        """기존 모든 포트 탭에 로깅 시그널을 연결합니다."""
        count = self.view.get_port_tabs_count()
        for i in range(count):
            # View Interface를 통해 뷰 가져오기
            port_view = self.view.get_port_tab_widget(i)
            # IPortView 인터페이스인지 확인 후 연결
            if port_view:
                self._connect_single_port_logging(port_view)

    def _on_port_tab_added(self, port_view: IPortView) -> None:
        """
        포트 탭 추가 시 로깅 시그널 연결 핸들러

        Args:
            port_view (IPortView): 추가된 포트 뷰 인터페이스.
        """
        self._connect_single_port_logging(port_view)
        # 새 탭에 색상 규칙 주입 (LoD: Interface Facade 메서드 사용)
        if hasattr(port_view, 'set_data_log_color_rules'):
             port_view.set_data_log_color_rules(color_manager.rules)

    def _connect_single_port_logging(self, port_view: IPortView) -> None:
        """
        단일 포트 뷰의 로깅 시그널 연결

        Logic:
            - Interface의 시그널을 사용하여 핸들러 연결
            - 람다를 통해 컨텍스트(뷰 인스턴스) 전달

        Args:
            port_view (IPortView): 포트 뷰 인터페이스.
        """
        # [LoD 준수] Interface가 제공하는 시그널 사용
        # Protocol은 hasattr 검사가 어려우므로 try-except 사용
        try:
            port_view.logging_start_requested.disconnect()
            port_view.logging_stop_requested.disconnect()
        except TypeError:
            pass
        except AttributeError:
            # Protocol에 정의되어 있으나 구현체에 없을 경우 (방어)
            return

        # Lambda로 패널 컨텍스트 전달
        port_view.logging_start_requested.connect(lambda: self._on_logging_start_requested(port_view))
        port_view.logging_stop_requested.connect(lambda: self._on_logging_stop_requested(port_view))

    def _on_logging_start_requested(self, port_view: IPortView) -> None:
        """
        로깅 시작 요청 처리

        Logic:
            - Panel을 통해 파일 다이얼로그 표시
            - 확장자 기반 포맷 결정 (BIN/HEX/PCAP)
            - DataLoggerManager에 시작 요청
            - Panel을 통해 로깅 활성화 UI 상태 업데이트

        Args:
            port_view (IPortView): 요청한 포트 뷰.
        """
        format_map = {
            '.pcap': LogFormat.PCAP,
            '.txt': LogFormat.HEX,
        }

        # [LoD 준수] Interface Facade 메서드 사용
        file_path = port_view.show_save_log_dialog()
        if not file_path:
            port_view.set_logging_active(False)
            return

        port = port_view.get_port_name()
        if not port:
            port_view.set_logging_active(False)
            return

        _, ext = os.path.splitext(file_path)
        lower_ext = ext.lower()
        log_format = format_map.get(lower_ext, LogFormat.BIN)

        # 포맷 전달 및 시작
        if data_logger_manager.start_logging(port, file_path, log_format):
            port_view.set_logging_active(True)
            self._log_info(f"[{port}] Logging started ({log_format.value}): {file_path}")
        else:
            port_view.set_logging_active(False)
            self._log_error(f"[{port}] Failed to start logging")

    def _on_logging_stop_requested(self, port_view: IPortView) -> None:
        """
        로깅 중지 요청 처리

        Args:
            port_view (IPortView): 요청한 포트 뷰.
        """
        port = port_view.get_port_name()
        if port:
            data_logger_manager.stop_logging(port)

        # Interface Facade 메서드 사용
        port_view.set_logging_active(False)
        self._log_info(f"[{port}] Logging stopped")