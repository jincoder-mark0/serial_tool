"""
메인 프레젠터 모듈

애플리케이션의 최상위 Presenter입니다.
View와 Model을 연결하고 전역 상태를 관리합니다.

## WHY
* MVP 패턴 준수 (비즈니스 로직 분리)
* 하위 Presenter 조율 및 생명주기 관리
* 전역 이벤트(EventBus) 및 설정(Settings) 중앙 제어

## WHAT
* 하위 Presenter (Port, Macro, File, Packet, Manual) 생성 및 연결
* View 이벤트 처리 (시그널 구독)
* Model 상태 변화에 따른 View 업데이트 (EventRouter 활용)
* 설정 저장/로드 및 애플리케이션 종료 처리
* Fast Path: 고속 데이터 수신 처리를 위한 직접 연결 및 버퍼링
* SettingsManager 주입 (DI)

## HOW
* Signal/Slot 기반 통신
* EventRouter를 통한 전역 이벤트 수신 및 라우팅
* SettingsManager를 통한 설정 동기화 및 View 초기 상태 복원
* DTO를 활용한 데이터 교환 (View 로직 제거)
"""
from PyQt5.QtCore import QObject, QTimer, QDateTime
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
from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager
from view.managers.language_manager import language_manager
from core.logger import logger
from common.constants import ConfigKeys, EventTopics
from common.dtos import (
    ManualCommand, PortDataEvent, PortErrorEvent, PacketEvent, FontConfig,
    MainWindowState, PreferencesState, ManualControlState
)
from view.dialogs.file_transfer_dialog import FileTransferDialog
from view.managers.color_manager import color_manager

class MainPresenter(QObject):
    """
    메인 프레젠터 클래스

    애플리케이션의 전체적인 흐름을 제어하고 하위 Presenter를 관리합니다.
    """

    def __init__(self, view: MainWindow) -> None:
        """
        MainPresenter 생성 및 초기화

        Logic:
            - SettingsManager를 통해 설정 로드
            - 설정 초기화 여부 확인 및 경고 표시
            - initialize_view_from_settings 메서드로 초기화 로직 분리
            - Model 인스턴스 생성
            - 하위 Presenter 초기화 및 의존성 주입
            - ManualControl 상태 복원
            - EventRouter 및 View 시그널 연결
            - 데이터 수신 직접 연결(Fast Path) 및 UI 버퍼링 타이머 설정
            - 상태바 업데이트 타이머 시작

        Args:
            view (MainWindow): 메인 윈도우 뷰 인스턴스
        """
        super().__init__()
        self.view = view

        # --- 0. 설정 로드 및 View 초기화 (MVP) ---
        self.settings_manager = SettingsManager()

        # 설정 초기화 알림 체크
        if self.settings_manager.config_was_reset:
            reason = self.settings_manager.reset_reason
            self.view.show_alert_message(
                "Settings Reset",
                f"Configuration file corrupted or invalid.\nDefaults restored.\n\nReason: {reason}"
            )

        # [Refactor] View 초기화 로직 분리
        self.initialize_view_from_settings()

        # --- 1. Model 및 Handler 초기화 ---
        self.connection_controller = ConnectionController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()
        self.data_handler = DataTrafficHandler(self.view)

        # --- 2. Sub-Presenter 초기화 ---
        # 2.1 Port Control
        self.port_presenter = PortPresenter(self.view.port_view, self.connection_controller)

        # 2.2 Macro Control
        self.macro_presenter = MacroPresenter(self.view.macro_view, self.macro_runner)

        # 2.3 File Transfer
        self.file_presenter = FilePresenter(self.connection_controller)

        # 2.4 Packet Inspector
        self.packet_presenter = PacketPresenter(
            self.view.right_section.packet_panel,
            self.event_router,
            self.settings_manager
        )

        # 2.5 Manual Control
        self.manual_control_presenter = ManualControlPresenter(
            self.view.left_section.manual_control_panel,
            self.connection_controller,
            self.view.append_local_echo_data,
            self.port_presenter.get_active_port_name
        )

        # ManualControl 상태 복원 (이것도 별도 메서드로 분리 가능하나 일단 유지)
        # Note: initialize_view_from_settings가 호출된 시점에서는 아직 하위 위젯들의 상태가 완전히 복원되지 않았을 수 있음
        # (MainWindow.apply_state에서 복원하지만, ManualControl의 개별 상태는 여기서 추가 복원)
        all_settings = self.settings_manager.get_all_settings()
        window_state, _ = self._create_initial_states(all_settings)

        manual_settings_dict = window_state.left_section_state.get("manual_control", {}).get("manual_control_widget", {})
        manual_state_dto = ManualControlState(
            input_text=manual_settings_dict.get("input_text", ""),
            hex_mode=manual_settings_dict.get("hex_mode", False),
            prefix_chk=manual_settings_dict.get("prefix_chk", False),
            suffix_chk=manual_settings_dict.get("suffix_chk", False),
            rts_chk=manual_settings_dict.get("rts_chk", False),
            dtr_chk=manual_settings_dict.get("dtr_chk", False),
            local_echo_chk=manual_settings_dict.get("local_echo_chk", False),
            broadcast_chk=manual_settings_dict.get("broadcast_chk", False)
        )
        self.manual_control_presenter.load_state(manual_state_dto)

        # --- 3. 데이터 수신 최적화 (Fast Path) ---
        # DataHandler로 위임
        self.connection_controller.data_received.connect(self.data_handler.on_fast_data_received)

        # --- 4. EventRouter 시그널 연결 ---
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

        # --- 5. 내부 Model 시그널 연결 ---
        self.macro_runner.send_requested.connect(self.on_macro_send_requested)

        # --- 6. View 시그널 연결 ---
        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.close_requested.connect(self.on_close_requested)
        self.view.preferences_requested.connect(self.on_preferences_requested)

        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

        self.view.file_transfer_dialog_opened.connect(self.file_presenter.on_file_transfer_dialog_opened)

        self._connect_logging_signals()
        self.view.port_tab_added.connect(self._on_port_tab_added)

        # --- 7. 초기화 완료 ---
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000)

        self.view.log_system_message("Application initialized", "INFO")

    def initialize_view_from_settings(self) -> None:
        """
        설정 파일에서 값을 읽어 View의 초기 상태를 구성합니다.
        """
        all_settings = self.settings_manager.get_all_settings()
        window_state, font_config = self._create_initial_states(all_settings)

        # View에 설정 주입하여 초기 상태 복원
        self.view.apply_state(window_state, font_config)

        # 테마 적용
        theme = self.settings_manager.get(ConfigKeys.THEME, 'dark')
        self.view.switch_theme(theme)

        self.view.left_section.system_log_widget.set_color_rules(color_manager.rules)

    def _create_initial_states(self, settings: dict) -> tuple[MainWindowState, FontConfig]:
        """
        설정 딕셔너리를 DTO로 변환하는 헬퍼 메서드

        Args:
            settings (dict): 설정 딕셔너리

        Returns:
            tuple[MainWindowState, FontConfig]: MainWindowState와 FontConfig DTO
        """
        def get_val(path, default=None):
            """
            설정 딕셔너리에서 값을 가져오는 헬퍼 메서드

            Args:
                path (str): 설정 키 경로 (점으로 구분된 문자열)
                default (any, optional): 기본값. Defaults to None.

            Returns:
                any: 설정 값 또는 기본값
            """
            keys = path.split('.')
            val = settings
            try:
                for k in keys: val = val.get(k, {})
                return val if val != {} else default
            except AttributeError: return default

        window_state = MainWindowState(
            width=get_val(ConfigKeys.WINDOW_WIDTH, 1400),
            height=get_val(ConfigKeys.WINDOW_HEIGHT, 900),
            x=get_val(ConfigKeys.WINDOW_X),
            y=get_val(ConfigKeys.WINDOW_Y),
            splitter_state=get_val(ConfigKeys.SPLITTER_STATE),
            right_panel_visible=get_val(ConfigKeys.RIGHT_PANEL_VISIBLE, True),
            saved_right_width=get_val(ConfigKeys.SAVED_RIGHT_WIDTH),
            left_section_state={
                "manual_control": get_val(ConfigKeys.MANUAL_CONTROL_STATE, {}),
                "ports": get_val(ConfigKeys.PORTS_TABS_STATE, [])
            },
            right_section_state={
                "macro_panel": {
                    "commands": get_val(ConfigKeys.MACRO_COMMANDS, []),
                    "control_state": get_val(ConfigKeys.MACRO_CONTROL_STATE, {})
                }
            }
        )

        # FontConfig 생성
        font_config = FontConfig(
            prop_family=get_val(ConfigKeys.PROP_FONT_FAMILY, "Segoe UI"),
            prop_size=get_val(ConfigKeys.PROP_FONT_SIZE, 9),
            fixed_family=get_val(ConfigKeys.FIXED_FONT_FAMILY, "Consolas"),
            fixed_size=get_val(ConfigKeys.FIXED_FONT_SIZE, 9)
        )

        return window_state, font_config

    def on_preferences_requested(self) -> None:
        """
        설정을 변경할 수 있는 PreferencesDialog를 표시합니다.

        Returns:
            PreferencesState: 변경된 설정 DTO
        """
        settings = self.settings_manager
        state = PreferencesState(
            theme=settings.get(ConfigKeys.THEME, "Dark").capitalize(),
            language=settings.get(ConfigKeys.LANGUAGE, "en"),
            font_size=settings.get(ConfigKeys.PROP_FONT_SIZE, 10),
            max_log_lines=settings.get(ConfigKeys.RX_MAX_LINES, 2000),
            baudrate=settings.get(ConfigKeys.PORT_BAUDRATE, 115200),
            newline=str(settings.get(ConfigKeys.PORT_NEWLINE, "\n")),
            local_echo=settings.get(ConfigKeys.PORT_LOCAL_ECHO, False),
            scan_interval=settings.get(ConfigKeys.PORT_SCAN_INTERVAL, 1000),
            cmd_prefix=settings.get(ConfigKeys.COMMAND_PREFIX, ""),
            cmd_suffix=settings.get(ConfigKeys.COMMAND_SUFFIX, ""),
            log_path=settings.get(ConfigKeys.LOG_PATH, ""),
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
        애플리케이션 종료 처리
        """
        self.data_handler.stop()
        self.status_timer.stop()

        state = self.view.get_window_state()
        manual_state_dto = self.manual_control_presenter.get_state()
        state.left_section_state["manual_control"] = {
            "manual_control_widget": {
                "input_text": manual_state_dto.input_text,
                "hex_mode": manual_state_dto.hex_mode,
                "prefix_chk": manual_state_dto.prefix_chk,
                "suffix_chk": manual_state_dto.suffix_chk,
                "rts_chk": manual_state_dto.rts_chk,
                "dtr_chk": manual_state_dto.dtr_chk,
                "local_echo_chk": manual_state_dto.local_echo_chk,
                "broadcast_chk": manual_state_dto.broadcast_chk
            }
        }

        settings = self.settings_manager
        settings.set(ConfigKeys.WINDOW_WIDTH, state.width)
        settings.set(ConfigKeys.WINDOW_HEIGHT, state.height)
        settings.set(ConfigKeys.WINDOW_X, state.x)
        settings.set(ConfigKeys.WINDOW_Y, state.y)
        settings.set(ConfigKeys.SPLITTER_STATE, state.splitter_state)
        settings.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.right_panel_visible)

        if state.saved_right_width is not None:
             settings.set(ConfigKeys.SAVED_RIGHT_WIDTH, state.saved_right_width)

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
        설정 저장 요청 처리

        Logic:
            - 설정값 매핑 및 타입 변환
            - SettingsManager 업데이트
            - UI 테마/언어 즉시 적용
            - 하위 Presenter 설정 전파

        Args:
            new_state (PreferenceState) : 변경할 설정
        """
        settings = self.settings_manager
        settings.set(ConfigKeys.THEME, new_state.theme.lower())
        settings.set(ConfigKeys.LANGUAGE, new_state.language)
        settings.set(ConfigKeys.PROP_FONT_SIZE, new_state.font_size)
        settings.set(ConfigKeys.RX_MAX_LINES, new_state.max_log_lines)
        settings.set(ConfigKeys.PORT_BAUDRATE, new_state.baudrate)
        settings.set(ConfigKeys.PORT_NEWLINE, new_state.newline)
        settings.set(ConfigKeys.PORT_LOCAL_ECHO, new_state.local_echo)
        settings.set(ConfigKeys.PORT_SCAN_INTERVAL, new_state.scan_interval)
        settings.set(ConfigKeys.COMMAND_PREFIX, new_state.cmd_prefix)
        settings.set(ConfigKeys.COMMAND_SUFFIX, new_state.cmd_suffix)
        settings.set(ConfigKeys.LOG_PATH, new_state.log_path)

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

        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)

        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            if hasattr(widget, 'data_log_widget'):
                widget.data_log_widget.set_max_lines(new_state.max_log_lines)

        self.manual_control_presenter.update_local_echo_setting(new_state.local_echo)

        from core.event_bus import event_bus
        event_bus.publish(EventTopics.SETTINGS_CHANGED, new_state)

        self.view.show_status_message("Settings updated", 2000)
        self.view.log_system_message("Settings updated", "INFO")

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        """
        폰트 설정 변경 처리

        Args:
            font_config (FontConfig): 폰트 설정 DTO
        """
        settings = self.settings_manager
        settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        settings.save_settings()
        logger.info("Font settings saved successfully.")

    def _on_data_sent_router(self, event: PortDataEvent) -> None:
        """
        데이터 송신 이벤트 (라우터 -> 핸들러)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트
        """
        # EventRouter가 이미 DTO로 변환하여 전달함
        self.data_handler.on_data_sent(event.port, event.data)

    def on_port_opened(self, port_name: str) -> None:
        """
        포트 열림 알림

        Args:
            port_name (str): 열린 포트 이름
        """
        self.view.update_status_bar_port(port_name, True)
        self.view.show_status_message(f"Connected to {port_name}", 3000)

    def on_port_closed(self, port_name: str) -> None:
        """
        포트 닫힘 알림

        Args:
            port_name (str): 닫힌 포트 이름
        """
        self.view.update_status_bar_port(port_name, False)
        self.view.show_status_message(f"Disconnected from {port_name}", 3000)

    def on_port_error(self, event: PortErrorEvent) -> None:
        """
        포트 오류 알림

        Args:
            event (PortErrorEvent): 포트 오류 이벤트
        """
        self.view.show_status_message(f"Error ({event.port}): {event.message}", 5000)

    def on_macro_started(self) -> None:
        """
        매크로 시작 알림
        """
        self.view.log_system_message("Macro started", "INFO")
        self.view.show_status_message("Macro Running...", 0)

    def on_macro_finished(self) -> None:
        """
        매크로 종료 알림
        """
        self.view.log_system_message("Macro finished", "SUCCESS")
        self.view.show_status_message("Macro Finished", 3000)

    def on_macro_error(self, error_msg: str) -> None:
        """
        매크로 오류 알림

        Args:
            error_msg (str): 오류 메시지
        """
        self.view.log_system_message(f"Macro Error: {error_msg}", "ERROR")
        self.view.show_status_message(f"Macro Error: {error_msg}", 5000)

    def on_macro_send_requested(self, command: ManualCommand) -> None:
        """
        매크로 전송 요청 처리

        Args:
            command (ManualCommand): 매크로 명령어
        """
        if command.is_broadcast:
            prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix else None
            suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix else None
            try:
                data = CommandProcessor.process_command(command.text, command.hex_mode, prefix=prefix, suffix=suffix)
                self.connection_controller.send_data_to_broadcasting(data)
            except ValueError as e:
                logger.error(f"Broadcast error: {e}")
            return

        active_port = self.port_presenter.get_active_port_name()
        if not active_port or not self.connection_controller.is_connection_open(active_port):
            logger.warning("No active port")
            return

        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix else None
        try:
            data = CommandProcessor.process_command(command.text, command.hex_mode, prefix=prefix, suffix=suffix)
            self.connection_controller.send_data(active_port, data)
        except ValueError as e:
            logger.error(f"Send error: {e}")

    def on_file_transfer_completed(self, success: bool) -> None:
        """
        파일 전송 완료 처리

        Args:
            success (bool): 성공 여부
        """
        status = "Completed" if success else "Failed"
        self.view.log_system_message(f"File transfer {status}", "SUCCESS" if success else "WARN")
        self.view.show_status_message(f"File Transfer {status}", 3000)

    def on_file_transfer_error(self, msg: str) -> None:
        """
        파일 전송 오류 처리

        Args:
            msg (str): 오류 메시지
        """
        self.view.log_system_message(f"File Transfer Error: {msg}", "ERROR")

    def update_status_bar(self) -> None:
        """
        상태 표시줄 업데이트
        """
        self.view.update_status_bar_stats(self.data_handler.rx_byte_count, self.data_handler.tx_byte_count)
        self.data_handler.reset_counts()
        self.view.update_status_bar_time(QDateTime.currentDateTime().toString("HH:mm:ss"))

    def on_shortcut_connect(self)-> None:
        """
        연결 단축키 처리
        """
        self.port_presenter.connect_current_port()
    def on_shortcut_disconnect(self)-> None:
        """
        연결 해제 단축키 처리
        """
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """
        로그 초기화 단축키 처리
        """
        self.port_presenter.clear_log_current_port()

    def _connect_logging_signals(self) -> None:
        """
        포트 탭 로깅 시그널 연결
        """
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            self._connect_single_port_logging(widget)

    def _on_port_tab_added(self, panel) -> None:
        """
        포트 탭 추가 시 로깅 시그널 연결

        Args:
            panel (PortPanel): 추가된 포트 패널
        """
        self._connect_single_port_logging(panel)

        # Inject Color Rules into new DataLogWidget
        if hasattr(panel, 'data_log_widget'):
            panel.data_log_widget.set_color_rules(color_manager.rules)

    def _connect_single_port_logging(self, panel) -> None:
        """
        포트 패널 로깅 시그널 연결

        Args:
            panel (PortPanel): 포트 패널
        """
        if hasattr(panel, 'data_log_widget'):
            data_log_widget = panel.data_log_widget
            try:
                data_log_widget.logging_start_requested.disconnect()
                data_log_widget.logging_stop_requested.disconnect()
            except TypeError: pass
            data_log_widget.logging_start_requested.connect(lambda: self._on_logging_start_requested(panel))
            data_log_widget.logging_stop_requested.connect(lambda: self._on_logging_stop_requested(panel))

    def _on_logging_start_requested(self, panel) -> None:
        """
        로깅 시작 요청 처리

        Args:
            panel (PortPanel): 포트 패널
        """
        filepath = panel.data_log_widget.show_save_log_dialog()
        if not filepath:
            panel.data_log_widget.set_logging_active(False)
            return
        port = panel.get_port_name()
        if not port:
            panel.data_log_widget.set_logging_active(False)
            return
        if data_logger_manager.start_logging(port, filepath):
            panel.data_log_widget.set_logging_active(True)
        else:
            panel.data_log_widget.set_logging_active(False)

    def _on_logging_stop_requested(self, panel):
        """
        로깅 중지 요청 처리

        Args:
            panel (PortPanel): 포트 패널
        """
        port = panel.get_port_name()
        if port: data_logger_manager.stop_logging(port)
        panel.data_log_widget.set_logging_active(False)
