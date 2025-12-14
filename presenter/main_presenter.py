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

## HOW
* Signal/Slot 기반 통신
* EventRouter를 통한 전역 이벤트 수신 및 라우팅
* SettingsManager를 통한 설정 동기화 및 View 초기 상태 복원
* QTimer & defaultdict: UI 업데이트 스로틀링 구현
"""
from collections import defaultdict
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
from core.command_processor import CommandProcessor
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager
from view.managers.language_manager import language_manager
from core.logger import logger
from common.constants import ConfigKeys, EventTopics
from common.dtos import ManualCommand, PortDataEvent, PortErrorEvent, PacketEvent, FontConfig

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
            - View 상태 복원 (restore_state 호출)
            - Model 인스턴스 생성
            - 하위 Presenter 초기화 및 의존성 주입
            - EventRouter 및 View 시그널 연결
            - 데이터 수신 직접 연결 및 UI 버퍼링 타이머 설정
            - 상태바 업데이트 타이머 시작

        Args:
            view (MainWindow): 메인 윈도우 뷰 인스턴스
        """
        super().__init__()
        self.view = view

        # --- 0. 설정 로드 및 View 초기화 (MVP) ---
        self.settings_manager = SettingsManager()
        all_settings = self.settings_manager.get_all_settings()

        # View에 설정 주입하여 초기 상태 복원
        self.view.restore_state(all_settings)

        # --- 1. Model 초기화 ---
        self.connection_controller = ConnectionController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()

        # --- 2. Sub-Presenter 초기화 ---

        # 2.1 Port Control (좌측 탭 관리)
        self.port_presenter = PortPresenter(self.view.port_view, self.connection_controller)

        # 2.2 Macro Control (우측 매크로 탭)
        self.macro_presenter = MacroPresenter(self.view.macro_view, self.macro_runner)

        # 2.3 File Transfer (파일 전송)
        self.file_presenter = FilePresenter(self.connection_controller)

        # 2.4 Packet Inspector (우측 패킷 탭)
        self.packet_presenter = PacketPresenter(
            self.view.right_section.packet_panel,
            self.event_router
        )

        # 2.5 Manual Control (좌측 수동 제어)
        self.manual_control_presenter = ManualControlPresenter(
            self.view.left_section.manual_control_panel,
            self.connection_controller,
            self.view.append_local_echo_data,
            self.port_presenter.get_active_port_name
        )

        # --- 3. 데이터 수신 최적화 ---
        # EventBus를 거치지 않고 Controller 시그널을 직접 구독하여 오버헤드 감소
        self.connection_controller.data_received.connect(self._on_fast_data_received)

        # UI 버퍼링: 포트별로 수신 데이터를 모아둠 {port_name: bytearray}
        self._rx_buffer = defaultdict(bytearray)

        # UI 업데이트 타이머 (Throttling): 30ms마다 버퍼 내용을 View에 반영 (약 33fps)
        self._ui_refresh_timer = QTimer()
        self._ui_refresh_timer.setInterval(30)
        self._ui_refresh_timer.timeout.connect(self._flush_rx_buffer_to_ui)
        self._ui_refresh_timer.start()

        # --- 4. EventRouter 시그널 연결 (Model -> Presenter -> View) ---
        # Port Events
        # [Note] data_received는 Fast Path(_on_fast_data_received)에서 처리하므로 여기서 연결하지 않거나, 로직을 비워둠
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)
        self.event_router.data_sent.connect(self.on_data_sent)

        # Macro Events (Global Log/Status)
        self.event_router.macro_started.connect(self.on_macro_started)
        self.event_router.macro_finished.connect(self.on_macro_finished)
        self.event_router.macro_error.connect(self.on_macro_error)

        # File Transfer Events (Global Log/Status)
        self.event_router.file_transfer_completed.connect(self.on_file_transfer_completed)
        self.event_router.file_transfer_error.connect(self.on_file_transfer_error)

        # --- 5. 내부 Model 시그널 연결 ---
        # MacroRunner의 전송 요청 처리
        self.macro_runner.send_requested.connect(self.on_macro_send_requested)

        # --- 6. View 시그널 연결 (View -> Presenter) ---
        # 설정 및 종료
        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.close_requested.connect(self.on_close_requested)
        self.view.preferences_requested.connect(self.on_preferences_requested)

        # 단축키
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

        # 파일 전송 다이얼로그 호출
        self.view.file_transfer_dialog_opened.connect(self.file_presenter.on_file_transfer_dialog_opened)

        # 로깅 및 탭 추가 이벤트 (동적 연결)
        self._connect_logging_signals()
        self.view.port_tab_added.connect(self._on_port_tab_added)

        # --- 7. 초기화 완료 ---
        self.rx_byte_count = 0
        self.tx_byte_count = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000) # 1초 주기 업데이트

        self.view.log_system_message("Application initialized", "INFO")

    # -------------------------------------------------------------------------
    # High-Performance Data Handling
    # -------------------------------------------------------------------------
    def _on_fast_data_received(self, port_name: str, data: bytes) -> None:
        """
        고속 데이터 수신 핸들러 (ConnectionController 직접 연결)

        Logic:
            - [Immediate] 파일 로깅 (DataLogger): 지연 없이 즉시 기록
            - [Immediate] 통계 업데이트: RX 바이트 카운트 즉시 증가
            - [Buffered] UI 업데이트: 버퍼에 추가하고 타이머에 의해 일괄 처리

        Args:
            port_name (str): 포트 이름
            data (bytes): 수신 데이터
        """
        if not data:
            return

        # 1. 파일 로깅 (Critical Path)
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 2. 통계 집계
        self.rx_byte_count += len(data)

        # 3. UI 업데이트 버퍼링 (Throttling)
        # bytearray는 가변 객체이므로 append 대신 extend 사용
        self._rx_buffer[port_name].extend(data)

    def _flush_rx_buffer_to_ui(self) -> None:
        """
        [Timer Slot] 버퍼링된 수신 데이터를 UI에 반영

        Logic:
            - 버퍼에 데이터가 있는 포트만 순회
            - 해당 포트의 View(DataLogWidget)를 찾아 데이터 전달
            - 버퍼 초기화
        """
        if not self._rx_buffer:
            return

        # 현재 뷰의 탭 정보를 가져옴 (최적화: 탭이 많을 경우 매번 전체 검색은 비효율적일 수 있음)
        # 하지만 여기서는 안전하게 전체 탭을 순회하며 매칭
        count = self.view.get_port_tabs_count()

        # 처리할 데이터가 있는 포트 목록 복사 (Iterate 중 수정 방지)
        pending_ports = list(self._rx_buffer.keys())

        for port_name in pending_ports:
            data = self._rx_buffer[port_name]
            if not data:
                continue

            # bytes로 변환하여 전달
            data_bytes = bytes(data)

            # 해당 포트의 탭 찾기
            for i in range(count):
                widget = self.view.get_port_tab_widget(i)
                if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                    if hasattr(widget, 'data_log_widget'):
                        widget.data_log_widget.append_data(data_bytes)
                    break

            # 처리 완료된 버퍼 비우기
            del self._rx_buffer[port_name]

    # -------------------------------------------------------------------------
    # Standard Event Handlers
    # -------------------------------------------------------------------------
    def on_preferences_requested(self):
        """Preferences 다이얼로그 요청 처리"""
        current_settings = self.settings_manager.get_all_settings()
        self.view.open_preferences_dialog(current_settings)

    def on_close_requested(self) -> None:
        """
        애플리케이션 종료 처리

        Logic:
            - 윈도우 상태 수집 (View -> Presenter)
            - 설정 파일 저장 (Presenter -> Model)
            - 열린 포트 닫기 및 리소스 정리
        """
        # 타이머 정지
        self._ui_refresh_timer.stop()
        self.status_timer.stop()

        # 윈도우 상태 가져오기
        state = self.view.get_window_state()

        # 설정 값 업데이트
        self.settings_manager.set(ConfigKeys.WINDOW_WIDTH, state.get(ConfigKeys.WINDOW_WIDTH))
        self.settings_manager.set(ConfigKeys.WINDOW_HEIGHT, state.get(ConfigKeys.WINDOW_HEIGHT))
        self.settings_manager.set(ConfigKeys.WINDOW_X, state.get(ConfigKeys.WINDOW_X))
        self.settings_manager.set(ConfigKeys.WINDOW_Y, state.get(ConfigKeys.WINDOW_Y))
        self.settings_manager.set(ConfigKeys.SPLITTER_STATE, state.get(ConfigKeys.SPLITTER_STATE))
        self.settings_manager.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.get(ConfigKeys.RIGHT_PANEL_VISIBLE))

        # 저장된 패널 너비 저장 (Custom Key 사용)
        if "saved_right_section_width" in state:
             self.settings_manager.set("ui.saved_right_section_width", state["saved_right_section_width"])

        if ConfigKeys.MANUAL_CONTROL_STATE in state:
            self.settings_manager.set(ConfigKeys.MANUAL_CONTROL_STATE, state[ConfigKeys.MANUAL_CONTROL_STATE])
        if ConfigKeys.PORTS_TABS_STATE in state:
            self.settings_manager.set(ConfigKeys.PORTS_TABS_STATE, state[ConfigKeys.PORTS_TABS_STATE])
        if ConfigKeys.MACRO_COMMANDS in state:
            self.settings_manager.set(ConfigKeys.MACRO_COMMANDS, state[ConfigKeys.MACRO_COMMANDS])
        if ConfigKeys.MACRO_CONTROL_STATE in state:
            self.settings_manager.set(ConfigKeys.MACRO_CONTROL_STATE, state[ConfigKeys.MACRO_CONTROL_STATE])

        # 파일 저장
        self.settings_manager.save_settings()

        # 리소스 정리 (포트 닫기)
        if self.connection_controller.has_active_connection:
            self.connection_controller.close_connection()

        logger.info("Application shutdown sequence completed.")

    def on_settings_change_requested(self, new_settings: dict) -> None:
        """
        설정 저장 요청 처리

        Logic:
            - 설정값 매핑 및 타입 변환
            - SettingsManager 업데이트
            - UI 테마/언어 즉시 적용
            - 하위 Presenter(PacketPresenter) 설정 전파

        Args:
            new_settings (dict): 변경할 설정 딕셔너리
        """
        # 설정 키 매핑
        settings_map = {
            'theme': ConfigKeys.THEME,
            'language': ConfigKeys.LANGUAGE,
            'proportional_font_size': ConfigKeys.PROP_FONT_SIZE,
            'max_log_lines': ConfigKeys.RX_MAX_LINES,
            'command_prefix': ConfigKeys.COMMAND_PREFIX,
            'command_suffix': ConfigKeys.COMMAND_SUFFIX,
            'port_baudrate': ConfigKeys.PORT_BAUDRATE,
            'port_newline': ConfigKeys.PORT_NEWLINE,
            'port_local_echo': ConfigKeys.PORT_LOCAL_ECHO,
            'port_scan_interval': ConfigKeys.PORT_SCAN_INTERVAL,
            'log_path': ConfigKeys.LOG_PATH,

            # Packet Settings
            'parser_type': ConfigKeys.PACKET_PARSER_TYPE,
            'delimiters': ConfigKeys.PACKET_DELIMITERS,
            'packet_length': ConfigKeys.PACKET_LENGTH,
            'at_color_ok': ConfigKeys.AT_COLOR_OK,
            'at_color_error': ConfigKeys.AT_COLOR_ERROR,
            'at_color_urc': ConfigKeys.AT_COLOR_URC,
            'at_color_prompt': ConfigKeys.AT_COLOR_PROMPT,

            # Inspector Settings
            'packet_buffer_size': ConfigKeys.PACKET_BUFFER_SIZE,
            'packet_realtime': ConfigKeys.PACKET_REALTIME,
            'packet_autoscroll': ConfigKeys.PACKET_AUTOSCROLL,
        }

        # 데이터 변환 및 저장
        for key, value in new_settings.items():
            final_value = value

            # 데이터 변환 (Data Transformation)
            if key == 'theme':
                final_value = value.lower()
            elif key == 'port_baudrate':
                try:
                    final_value = int(value)
                except ValueError:
                    continue

            setting_path = settings_map.get(key)
            if setting_path:
                self.settings_manager.set(setting_path, final_value)

        # UI 업데이트
        if 'theme' in new_settings:
            self.view.switch_theme(new_settings['theme'].lower())

        if 'language' in new_settings:
            language_manager.set_language(new_settings['language'])

        # max_log_lines 설정 변경 시 모든 DataLogWidget에 적용
        if 'max_log_lines' in new_settings:
            try:
                max_lines_int = int(new_settings['max_log_lines'])
                count = self.view.get_port_tabs_count()
                for i in range(count):
                    widget = self.view.get_port_tab_widget(i)
                    if hasattr(widget, 'data_log_widget'):
                        widget.data_log_widget.set_max_lines(max_lines_int)
            except (ValueError, TypeError):
                logger.warning("Invalid max_log_lines value")

        # Local Echo 설정 변경 반영
        if 'port_local_echo' in new_settings:
            self.manual_control_presenter.update_local_echo_setting(new_settings['port_local_echo'])

        # PacketPresenter 설정 업데이트 요청
        self.packet_presenter.apply_settings()

        # 즉시 저장
        self.settings_manager.save_settings()

        self.view.show_status_message("Settings updated", 2000)
        self.view.log_system_message("Settings updated", "INFO")

    def on_font_settings_changed(self, font_config: FontConfig) -> None:
        """
        폰트 설정 변경 처리

        Args:
            font_config (FontConfig): 폰트 설정 DTO
        """
        self.settings_manager.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        self.settings_manager.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        self.settings_manager.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        self.settings_manager.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)

        self.settings_manager.save_settings()
        logger.info("Font settings saved successfully.")

    def on_data_received_normal(self, port_name: str, data: bytes) -> None:
        """
        데이터 수신 처리

        Logic:
            - 데이터 로깅 (활성화 시)
            - 해당 포트의 View(DataLogWidget)에 데이터 전달
            - RX 카운트 증가

        Args:
            port_name (str): 수신 포트 이름
            data (bytes): 수신 데이터
        """
        # EventRouter에서 DTO로 변환해서 준다고 가정 (나중에 EventRouter 수정 시 반영)
        # 하지만 EventRouter 수정 전까지는 dict일 수도 있으므로 타입 체크
        if isinstance(event, PortDataEvent):
            port_name = event.port
            data = event.data
        else: # Legacy dict support (during refactoring)
            port_name = event.get('port')
            data = event.get('data')

        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 뷰 인터페이스를 통해 데이터 전달 (탭 탐색)
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'data_log_widget'):
                    widget.data_log_widget.append_data(data)
                break

        # RX 카운트 증가
        self.rx_byte_count += len(data)

    def on_data_received(self, event: PortDataEvent) -> None:
        """
        데이터 수신 처리 (EventBus)

        [Note] UI 업데이트 로직은 _on_fast_data_received 및
        _flush_rx_buffer_to_ui로 이관되었습니다.
        여기서는 중복 처리를 방지하기 위해 로직을 비워둡니다.
        추후 플러그인이나 다른 모니터링 기능이 필요할 경우 사용할 수 있습니다.
        """
        pass

    def on_data_sent(self, event: PortDataEvent) -> None:
        """
        데이터 송신 처리

        Logic:
            - 데이터 로깅 (활성화 시)
            - TX 카운트 증가

        Args:
            event (PortDataEvent): 포트 데이터 이벤트
        """
        if isinstance(event, PortDataEvent):
            port_name = event.port
            data = event.data
        else:
            port_name = event.get('port')
            data = event.get('data')

        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)
        self.tx_byte_count += len(data)

    # ---------------------------------------------------------
    # Event Handlers (Port Status)
    # ---------------------------------------------------------
    def on_port_opened(self, port_name: str) -> None:
        """포트 열림 알림"""
        self.view.update_status_bar_port(port_name, True)
        self.view.show_status_message(f"Connected to {port_name}", 3000)

    def on_port_closed(self, port_name: str) -> None:
        """포트 닫힘 알림"""
        self.view.update_status_bar_port(port_name, False)
        self.view.show_status_message(f"Disconnected from {port_name}", 3000)

    def on_port_error(self, event: PortErrorEvent) -> None:
        if isinstance(event, PortErrorEvent):
            port_name = event.port
            error_msg = event.message
        else:
            port_name = event.get('port')
            error_msg = event.get('message')
        self.view.show_status_message(f"Error ({port_name}): {error_msg}", 5000)

    # ---------------------------------------------------------
    # Event Handlers (Macro)
    # ---------------------------------------------------------
    def on_macro_started(self) -> None:
        """매크로 시작 알림"""
        self.view.log_system_message("Macro execution started", "INFO")
        self.view.show_status_message("Macro Running...", 0)

    def on_macro_finished(self) -> None:
        """매크로 종료 알림"""
        self.view.log_system_message("Macro execution finished", "SUCCESS")
        self.view.show_status_message("Macro Finished", 3000)

    def on_macro_error(self, error_msg: str) -> None:
        """매크로 에러 알림"""
        self.view.log_system_message(f"Macro Error: {error_msg}", "ERROR")
        self.view.show_status_message(f"Macro Error: {error_msg}", 5000)

    def on_macro_send_requested(self, command: ManualCommand) -> None:
        """
        매크로 전송 요청 처리

        Logic:
            - 연결 열림 확인
            - CommandProcessor를 사용하여 데이터 가공 (Prefix/Suffix/Hex)
            - 데이터 전송 (ConnectionController)

        Args:
            command (ManualCommand): 매크로 명령어
        """
        active_port = self.port_presenter.get_active_port_name()
        if not active_port or not self.connection_controller.is_connection_open(active_port):
            logger.warning("Macro: No active port open")
            return

        # SettingsManager에서 값 획득 후 CommandProcessor에 주입 (Presenter의 책임)
        prefix = self.settings_manager.get(ConfigKeys.COMMAND_PREFIX) if command.prefix else None
        suffix = self.settings_manager.get(ConfigKeys.COMMAND_SUFFIX) if command.suffix else None

        try:
            # 데이터 가공 위임 (CommandProcessor에 Prefix/Suffix 값 직접 전달)
            data = CommandProcessor.process_command(command.text, command.hex_mode, prefix=prefix, suffix=suffix)
        except ValueError:
            logger.error(f"Invalid hex string for sending: {command.text}")
            return

        # 전송
        self.connection_controller.send_data(active_port, data)

    # ---------------------------------------------------------
    # Event Handlers (File Transfer)
    # ---------------------------------------------------------
    def on_file_transfer_completed(self, success: bool) -> None:
        """파일 전송 완료 알림"""
        status = "Completed" if success else "Failed"
        level = "SUCCESS" if success else "WARN"
        self.view.log_system_message(f"File transfer {status}", level)
        self.view.show_status_message(f"File Transfer {status}", 3000)

    def on_file_transfer_error(self, error_msg: str) -> None:
        """파일 전송 에러 알림"""
        self.view.log_system_message(f"File Transfer Error: {error_msg}", "ERROR")

    # ---------------------------------------------------------
    # UI Updates & Shortcuts
    # ---------------------------------------------------------
    def update_status_bar(self) -> None:
        """상태바 주기적 업데이트 (1초 주기)"""
        # 1. RX/TX 속도 업데이트
        self.view.update_status_bar_stats(self.rx_byte_count, self.tx_byte_count)
        # 카운터 초기화
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # 2. 시간 업데이트
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.view.update_status_bar_time(current_time)

    def on_shortcut_connect(self) -> None:
        """연결 단축키 (F2)"""
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        """연결 해제 단축키 (F3)"""
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """로그 지우기 단축키 (F5)"""
        self.port_presenter.clear_log_current_port()

    # -------------------------------------------------------------------------
    # Data Logging Integration
    # -------------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        """모든 포트 탭의 로깅 시그널 연결"""
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            self._connect_single_port_logging(widget)

    def _on_port_tab_added(self, panel) -> None:
        """새 탭 추가 시 로깅 시그널 연결"""
        self._connect_single_port_logging(panel)

    def _connect_single_port_logging(self, panel) -> None:
        """
        단일 포트 로깅 시그널 연결

        Args:
            panel: 포트 패널 위젯
        """
        if hasattr(panel, 'data_log_widget'):
            rx_widget = panel.data_log_widget
            # 중복 연결 방지를 위해 disconnect 시도
            try:
                rx_widget.data_logging_started.disconnect(self._on_data_logging_started)
                rx_widget.data_logging_stopped.disconnect(self._on_data_logging_stopped)
            except TypeError:
                pass

            rx_widget.data_logging_started.connect(self._on_data_logging_started)
            rx_widget.data_logging_stopped.connect(self._on_data_logging_stopped)

    def _get_port_panel_from_sender(self):
        """시그널 발신 패널 찾기"""
        sender = self.sender()
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            if hasattr(widget, 'data_log_widget') and widget.data_log_widget == sender:
                return widget
        return None

    def _on_data_logging_started(self, filepath: str) -> None:
        """
        로깅 시작 처리

        Args:
            filepath: 로깅 파일 경로
        """
        panel = self._get_port_panel_from_sender()
        if not panel:
            return

        port_name = panel.get_port_name()

        if not port_name:
            logger.warning("Cannot start logging: No port opened")
            return

        if data_logger_manager.start_logging(port_name, filepath):
            logger.info(f"Logging started: {port_name} -> {filepath}")
        else:
            logger.error(f"Failed to start logging: {filepath}")

    def _on_data_logging_stopped(self) -> None:
        """로깅 중단 핸들러"""
        panel = self._get_port_panel_from_sender()
        if not panel:
            return

        port_name = panel.get_port_name()
        if port_name and data_logger_manager.is_logging(port_name):
            data_logger_manager.stop_logging(port_name)
            logger.info(f"Logging stopped: {port_name}")
