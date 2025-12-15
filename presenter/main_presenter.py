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
* DTO를 활용한 데이터 교환 (View 로직 제거)
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
from common.dtos import (
    ManualCommand, PortDataEvent, PortErrorEvent, PacketEvent, FontConfig,
    MainWindowState, PreferencesState, ManualControlState
)

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
            - DTO 변환 및 View 상태 복원 (apply_state 호출)
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

        # 설정 로드 및 DTO 변환
        all_settings = self.settings_manager.get_all_settings()
        window_state, font_config = self._create_initial_states(all_settings)

        # View에 설정 주입하여 초기 상태 복원 (DTO 전달)
        self.view.apply_state(window_state, font_config)

        # 테마 적용 (초기화 후 별도 적용)
        theme = self.settings_manager.get(ConfigKeys.THEME, 'dark')
        self.view.switch_theme(theme)

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

        # ManualControl 상태 복원 (View 복원 후 추출된 상태 주입)
        # WindowState 내의 딕셔너리에서 데이터 추출
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
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)
        self.event_router.data_sent.connect(self.on_data_sent)

        # Macro Events
        self.event_router.macro_started.connect(self.on_macro_started)
        self.event_router.macro_finished.connect(self.on_macro_finished)
        self.event_router.macro_error.connect(self.on_macro_error)

        # File Transfer Events
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

    def _create_initial_states(self, settings: dict) -> tuple[MainWindowState, FontConfig]:
        """
        설정 딕셔너리를 DTO로 변환하는 헬퍼 메서드

        Args:
            settings (dict): SettingsManager에서 로드한 Raw 설정

        Returns:
            tuple[MainWindowState, FontConfig]: 생성된 DTO 튜플
        """
        # Helper to safely get nested keys
        def get_val(path, default=None):
            keys = path.split('.')
            val = settings
            try:
                for k in keys:
                    val = val.get(k, {})
                return val if val != {} else default
            except AttributeError:
                return default

        # MainWindowState 생성
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

    # -------------------------------------------------------------------------
    # [Fast Path] High-Performance Data Handling
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

        # 1. 파일 로깅
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 2. 통계 집계
        self.rx_byte_count += len(data)

        # 3. UI 업데이트 버퍼링
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
        """Preferences 다이얼로그 요청 처리 (DTO 생성)"""
        settings = self.settings_manager

        # PreferencesState DTO 생성
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

        Logic:
            - 윈도우 상태 수집 (View -> Presenter)
            - 설정 파일 저장 (Presenter -> Model)
            - 열린 포트 닫기 및 리소스 정리
        """
        # 타이머 정지
        self._ui_refresh_timer.stop()
        self.status_timer.stop()

        # View 상태 가져오기
        state = self.view.get_window_state()

        # ManualControl 상태는 Presenter에서 최신 데이터(History 포함) 가져오기
        manual_state_dto = self.manual_control_presenter.get_state()

        # DTO -> Dict 변환 (설정 파일 포맷 호환성 유지)
        manual_state_dict = {
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

        # State 객체의 left_section_state 업데이트
        state.left_section_state["manual_control"] = manual_state_dict

        # SettingsManager 업데이트
        self.settings_manager.set(ConfigKeys.WINDOW_WIDTH, state.width)
        self.settings_manager.set(ConfigKeys.WINDOW_HEIGHT, state.height)
        self.settings_manager.set(ConfigKeys.WINDOW_X, state.x)
        self.settings_manager.set(ConfigKeys.WINDOW_Y, state.y)
        self.settings_manager.set(ConfigKeys.SPLITTER_STATE, state.splitter_state)
        self.settings_manager.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.right_panel_visible)

        # 저장된 패널 너비 저장 (Custom Key 사용)
        if state.saved_right_width is not None:
             self.settings_manager.set(ConfigKeys.SAVED_RIGHT_WIDTH, state.saved_right_width)
        if ConfigKeys.MANUAL_CONTROL_STATE in state.left_section_state:
            self.settings_manager.set(ConfigKeys.MANUAL_CONTROL_STATE, state.left_section_state[ConfigKeys.MANUAL_CONTROL_STATE])
        if ConfigKeys.PORTS_TABS_STATE in state.left_section_state:
            self.settings_manager.set(ConfigKeys.PORTS_TABS_STATE, state.left_section_state[ConfigKeys.PORTS_TABS_STATE])
        if ConfigKeys.MACRO_COMMANDS in state.right_section_state:
            self.settings_manager.set(ConfigKeys.MACRO_COMMANDS, state.right_section_state[ConfigKeys.MACRO_COMMANDS])
        if ConfigKeys.MACRO_CONTROL_STATE in state.right_section_state:
            self.settings_manager.set(ConfigKeys.MACRO_CONTROL_STATE, state.right_section_state[ConfigKeys.MACRO_CONTROL_STATE])

        # 파일 저장
        self.settings_manager.save_settings()

        # 리소스 정리 (포트 닫기)
        if self.connection_controller.has_active_connection:
            self.connection_controller.close_connection()

        logger.info("Application shutdown sequence completed.")

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        """
        설정 저장 요청 처리

        Logic:
            - 설정값 매핑 및 타입 변환
            - SettingsManager 업데이트
            - UI 테마/언어 즉시 적용
            - 하위 Presenter(PacketPresenter) 설정 전파

        Args:
            new_state (PreferenceState) : 변경할 설정
        """
        # 1. SettingsManager 업데이트
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

        # 2. UI 및 로직 즉시 반영
        self.view.switch_theme(new_state.theme.lower())
        language_manager.set_language(new_state.language)

        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            if hasattr(widget, 'data_log_widget'):
                widget.data_log_widget.set_max_lines(new_state.max_log_lines)

        self.manual_control_presenter.update_local_echo_setting(new_state.local_echo)

        # PacketPresenter 직접 호출 제거 -> EventBus 발행
        # 설정 변경 이벤트 발행 (확장성)
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
        Fast Path 사용으로 인해 이곳은 비워둡니다.

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
            command (ManualCommand): 매크로 Command
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
                rx_widget.logging_start_requested.disconnect()
                rx_widget.logging_stop_requested.disconnect()
            except TypeError:
                pass

            # 시그널 연결 (인자 없이 호출되므로 lambda로 panel 전달)
            rx_widget.logging_start_requested.connect(lambda: self._on_logging_start_requested(panel))
            rx_widget.logging_stop_requested.connect(lambda: self._on_logging_stop_requested(panel))

    def _on_logging_start_requested(self, panel) -> None:
        """
        로깅 시작 요청 처리

        Logic:
            1. View의 다이얼로그 호출 메서드 사용 (파일명 획득)
            2. Model(DataLoggerManager) 호출
            3. 성공 시 View 상태 업데이트
        """
        # 1. 파일 경로 획득 (View Helper)
        filepath = panel.data_log_widget.show_save_log_dialog()
        if not filepath:
            panel.data_log_widget.set_logging_active(False)
            return

        port_name = panel.get_port_name()
        if not port_name:
            logger.warning("Cannot start logging: No port opened")
            panel.data_log_widget.set_logging_active(False)
            return

        # 2. Model 호출
        if data_logger_manager.start_logging(port_name, filepath):
            logger.info(f"Logging started: {port_name} -> {filepath}")
            # 3. View 업데이트
            panel.data_log_widget.set_logging_active(True)
        else:
            logger.error(f"Failed to start logging: {filepath}")
            panel.data_log_widget.set_logging_active(False)

    def _on_logging_stop_requested(self, panel) -> None:
        """로깅 중단 요청 처리"""
        port_name = panel.get_port_name()
        if port_name and data_logger_manager.is_logging(port_name):
            data_logger_manager.stop_logging(port_name)
            logger.info(f"Logging stopped: {port_name}")

        # View 상태 업데이트
        panel.data_log_widget.set_logging_active(False)
