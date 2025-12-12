"""
메인 프레젠터 모듈

애플리케이션의 최상위 Presenter
모든 하위 Presenter와 Model을 조율

## WHY
* MVP 패턴의 중심 조율자 역할
* 전역 상태 및 설정 관리
* 하위 Presenter 간 통신 중재
* 애플리케이션 생명주기 관리

## WHAT
* 하위 Presenter 초기화 및 관리 (Port, Macro, File)
* 전역 이벤트 라우팅 (EventRouter 활용)
* 설정 저장/로드 처리
* 상태바 업데이트 및 시스템 로그 관리
* 단축키 처리
* 로깅 기능 통합

## HOW
* PortPresenter, MacroPresenter, FilePresenter 생성 및 조율
* EventRouter로 Model 이벤트를 중앙 집중식으로 처리
* SettingsManager로 설정 영속화
* QTimer로 주기적 상태 업데이트
* PyQt Signal/Slot으로 View와 통신
"""
from PyQt5.QtCore import QObject, QTimer, QDateTime
from view.main_window import MainWindow
from model.port_controller import PortController
from model.macro_runner import MacroRunner
from .port_presenter import PortPresenter
from .macro_presenter import MacroPresenter
from .file_presenter import FilePresenter
from .event_router import EventRouter
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager
from view.managers.lang_manager import lang_manager
from core.logger import logger
from constants import ConfigKeys

class MainPresenter(QObject):
    """
    애플리케이션을 조율하는 메인 Presenter 클래스입니다.
    하위 Presenter들을 초기화하고 전역 상태를 관리합니다.
    """
    def __init__(self, view: MainWindow) -> None:
        """
        MainPresenter를 초기화합니다.

        Args:
            view (MainWindow): 메인 윈도우 인스턴스.
        """
        super().__init__()
        self.view = view

        # 모델 초기화 (Initialize Models)
        self.port_controller = PortController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()

        # 하위 Presenter 초기화 (Initialize Sub-Presenters)
        self.port_presenter = PortPresenter(self.view.left_section, self.port_controller)
        self.macro_presenter = MacroPresenter(self.view.right_section.macro_panel, self.macro_runner)
        self.file_presenter = FilePresenter(self.port_controller)

        # EventRouter 시그널 연결 (Model -> EventBus -> Presenter)
        self.event_router.data_received.connect(self.on_data_received)
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)

        # data_sent, EventRouter를 통해 수신
        self.event_router.data_sent.connect(self.on_data_sent)

        # MacroRunner 전송 요청 연결 (4개 인자: text, hex, prefix, suffix)
        self.macro_runner.send_requested.connect(self.on_macro_cmd_send_requested)

        # 수동 전송 시그널 연결
        self.view.left_section.manual_ctrl.manual_ctrl_widget.manual_cmd_send_requested.connect(
            self.on_manual_cmd_send_requested
        )

        # 설정 저장 요청 시그널 연결
        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)

        # 종료 요청 시그널 연결
        self.view.close_requested.connect(self.on_close_requested)

        # 상태바 업데이트를 위한 변수 및 타이머
        self.rx_byte_count = 0
        self.tx_byte_count = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000)

        # 단축키 시그널 연결
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

        # 파일 전송 다이얼로그 연결
        self.view.file_transfer_dialog_opened.connect(self.file_presenter.on_file_transfer_dialog_opened)

        # 상태바 참조 저장 (반복적인 hasattr 확인 방지)
        self.global_status_bar = self.view.global_status_bar

        # 로깅 시그널 연결 (DataLogger 통합)
        self._connect_logging_signals()

        # 탭 추가 시그널 연결 (새 탭의 로깅 시그널 연결용)
        self.view.left_section.port_tabs.tab_added.connect(self._on_port_tab_added)

        # 시스템 로그 참조
        self.system_log = self.view.left_section.system_log_widget
        self.log_system_message("Application initialized", "INFO")

    def log_system_message(self, message: str, level: str = "INFO") -> None:
        """시스템 로그에 메시지를 기록합니다."""
        if self.system_log:
            self.system_log.log(message, level)

    def on_close_requested(self) -> None:
        """
        애플리케이션 종료 요청을 처리합니다.
        윈도우 상태를 저장하고 리소스를 정리합니다.
        """
        # 1. 윈도우 상태 가져오기
        state = self.view.get_window_state()
        settings_manager = SettingsManager()

        # 2. 설정 저장
        # 2.1 윈도우 기본 설정
        settings_manager.set(ConfigKeys.WINDOW_WIDTH, state.get(ConfigKeys.WINDOW_WIDTH))
        settings_manager.set(ConfigKeys.WINDOW_HEIGHT, state.get(ConfigKeys.WINDOW_HEIGHT))
        settings_manager.set(ConfigKeys.WINDOW_X, state.get(ConfigKeys.WINDOW_X))
        settings_manager.set(ConfigKeys.WINDOW_Y, state.get(ConfigKeys.WINDOW_Y))
        settings_manager.set(ConfigKeys.SPLITTER_STATE, state.get(ConfigKeys.SPLITTER_STATE))
        settings_manager.set(ConfigKeys.RIGHT_PANEL_VISIBLE, state.get(ConfigKeys.RIGHT_PANEL_VISIBLE))

        # 2.2 Left Section 상태
        if ConfigKeys.MANUAL_CTRL_STATE in state:
            settings_manager.set(ConfigKeys.MANUAL_CTRL_STATE, state[ConfigKeys.MANUAL_CTRL_STATE])
        if ConfigKeys.PORTS_TABS_STATE in state:
            settings_manager.set(ConfigKeys.PORTS_TABS_STATE, state[ConfigKeys.PORTS_TABS_STATE])

        # 2.3 Right Section 상태
        if ConfigKeys.MACRO_COMMANDS in state:
            settings_manager.set(ConfigKeys.MACRO_COMMANDS, state[ConfigKeys.MACRO_COMMANDS])
        if ConfigKeys.MACRO_CONTROL_STATE in state:
            settings_manager.set(ConfigKeys.MACRO_CONTROL_STATE, state[ConfigKeys.MACRO_CONTROL_STATE])

        # 3. 파일 쓰기
        settings_manager.save_settings()

        # 4. 리소스 정리 (포트 닫기)
        if self.port_controller.is_open:
            self.port_controller.close_port()

        logger.info("Application shutdown sequence completed.")
        # 종료 시점이라 UI 업데이트가 의미 없을 수 있지만, 로그 파일에는 남음 (만약 파일 로깅 연동 시)

    def on_data_received(self, port_name: str, data: bytes) -> None:
        """
        수신된 시리얼 데이터를 처리합니다.
        포트 이름을 기반으로 해당 포트 패널의 ReceivedArea로 데이터를 전달합니다.

        Args:
            port_name (str): 데이터를 수신한 포트 이름
            data (bytes): 수신된 바이트 데이터.
        """
        # 로깅 중이면 DataLogger에 먼저 기록 (데이터 누락 방지)
        # 해당 포트가 로깅 중인지 확인
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 포트 이름으로 해당 탭 찾기
        for i in range(self.view.left_section.port_tabs.count()):
            widget = self.view.left_section.port_tabs.widget(i)
            # PortPanel인지 확인하고 포트 이름 비교
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'received_area_widget'):
                    widget.received_area_widget.append_data(data)
                break

        # RX 카운트 증가 (전체 합계)
        self.rx_byte_count += len(data)

    def on_manual_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool, local_echo: bool) -> None:
        """
        수동 명령 전송 요청을 처리합니다.
        prefix/suffix 설정을 적용하고 최종 데이터를 전송합니다.

        Args:
            text: 사용자가 입력한 원본 텍스트
            hex_mode: HEX 모드 사용 여부
            cmd_prefix: 접두사 사용 여부
            cmd_suffix: 접미사 사용 여부
            local_echo: 로컬 에코 사용 여부
        """
        if not self.port_controller.is_open:
            logger.warning("Port not open")
            return

        settings = SettingsManager()

        final_text = text

        # Apply prefix if requested
        if cmd_prefix:
            prefix = settings.get(ConfigKeys.CMD_PREFIX, "")
            final_text = prefix + final_text

        # Apply suffix if requested
        if cmd_suffix:
            suffix = settings.get(ConfigKeys.CMD_SUFFIX, "")
            final_text = final_text + suffix

        # Convert to bytes
        if hex_mode:
            try:
                # 16진수 문자열을 실제 바이트로 변환 (예: "01 02 FF" -> b'\x01\x02\xff')
                data = bytes.fromhex(final_text.replace(' ', ''))
            except ValueError:
                # 유효하지 않은 16진수 문자열인 경우 처리 (예: 오류 로깅, 사용자에게 알림)
                logger.error(f"Invalid hex string for sending:{final_text}")

                # Note: 향후 MainWindow의 status_bar를 통해 에러 메시지 표시 예정
                return # 전송 중단
        else:
            data = final_text.encode('utf-8')

        # Send data
        self.port_controller.send_data(data)

        # Local Echo
        if local_echo:
            # 현재 활성 포트 패널을 가져와서 ReceivedArea로 데이터 전달
            index = self.view.left_section.port_tabs.currentIndex()
            if index >= 0:
                widget = self.view.left_section.port_tabs.widget(index)
                if hasattr(widget, 'received_area_widget'):
                    # 로컬 에코는 수신 데이터처럼 처리하되, 구분할 필요가 있다면 별도 메서드 사용 가능
                    # 여기서는 단순히 append_data 호출 (수신된 것처럼 표시)
                    # 실제 수신 데이터와 구분하려면 색상이나 태그를 달리 할 수 있음
                    # 하지만 RxLogWidget은 bytes를 받으므로 data를 그대로 전달
                    widget.received_area_widget.append_data(data)

    def on_macro_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool) -> None:
        """
        매크로에서 전송 요청을 처리합니다.
        local_echo는 False로 처리합니다.
        """
        self.on_manual_cmd_send_requested(text, hex_mode, cmd_prefix, cmd_suffix, False)

    def on_settings_change_requested(self, new_settings: dict) -> None:
        """
        설정 저장 요청을 처리합니다.
        데이터 검증 및 변환 후 설정을 업데이트합니다.

        Args:
            new_settings (dict): View에서 전달된 원본 설정 데이터.
        """
        settings_manager = SettingsManager()

        # 설정 키 매핑
        settings_map = {
            'theme': ConfigKeys.THEME,
            'language': ConfigKeys.LANGUAGE,
            'proportional_font_size': ConfigKeys.PROP_FONT_SIZE,
            'max_log_lines': ConfigKeys.RX_MAX_LINES,
            'cmd_prefix': ConfigKeys.CMD_PREFIX,
            'cmd_suffix': ConfigKeys.CMD_SUFFIX,
            'port_baudrate': ConfigKeys.PORT_BAUDRATE,
            'port_newline': ConfigKeys.PORT_NEWLINE,
            'port_localecho': ConfigKeys.PORT_LOCALECHO,
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
            'inspector_buffer_size': ConfigKeys.INSPECTOR_BUFFER_SIZE,
            'inspector_realtime': ConfigKeys.INSPECTOR_REALTIME,
            'inspector_autoscroll': ConfigKeys.INSPECTOR_AUTOSCROLL,
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
                    continue # 유효하지 않은 보레이트 무시

            setting_path = settings_map.get(key)
            if setting_path:
                settings_manager.set(setting_path, final_value)

        # UI 업데이트 (View Update)
        if 'theme' in new_settings:
            self.view.switch_theme(new_settings['theme'].lower())

        if 'language' in new_settings:
            lang_manager.set_language(new_settings['language'])

        # max_log_lines 설정 변경 시 모든 RxLogWidget에 적용
        if 'max_log_lines' in new_settings:
            max_lines = new_settings['max_log_lines']
            try:
                max_lines_int = int(max_lines)
                # 모든 포트 패널의 RxLogWidget에 적용
                for i in range(self.view.left_section.port_tabs.count()):
                    widget = self.view.left_section.port_tabs.widget(i)
                    if hasattr(widget, 'received_area_widget'):
                        widget.received_area_widget.set_max_lines(max_lines_int)
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_log_lines value: {max_lines}")

        # 상태 메시지 표시
        self.global_status_bar.show_message("Settings updated", 2000)
        self.log_system_message("Settings updated", "INFO")

    def on_font_settings_changed(self, font_settings: dict) -> None:
        """
        폰트 설정 변경 요청을 처리하고 저장합니다.

        Args:
            font_settings (dict): ThemeManager에서 전달된 폰트 설정 값들.
        """
        settings_manager = SettingsManager()

        # ThemeManager 키와 ConfigKeys 상수 매핑
        key_map = {
            "proportional_font_family": ConfigKeys.PROP_FONT_FAMILY,
            "proportional_font_size": ConfigKeys.PROP_FONT_SIZE,
            "fixed_font_family": ConfigKeys.FIXED_FONT_FAMILY,
            "fixed_font_size": ConfigKeys.FIXED_FONT_SIZE
        }

        for tm_key, value in font_settings.items():
            if tm_key in key_map:
                config_key = key_map[tm_key]
                settings_manager.set(config_key, value)
            else:
                # 알 수 없는 키에 대한 경고 (유지보수성 확보)
                logger.warning(f"Unknown font setting key received: {tm_key}")

        settings_manager.save_settings()
        logger.info("Font settings saved successfully.")

    def on_data_sent(self, port_name: str, data: bytes) -> None:
        """
        데이터 전송 시 TX 카운트 증가
        로깅 중이면 데이터 기록
        EventRouter를 통해 호출
        """
        # 로깅 중이면 DataLogger에 기록
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        self.tx_byte_count += len(data)

    def on_port_opened(self, port_name: str) -> None:
        """포트 열림 시 상태바 업데이트"""
        self.global_status_bar.update_port_status(port_name, True)
        self.global_status_bar.show_message(f"Connected to {port_name}", 3000)

    def on_port_closed(self, port_name: str) -> None:
        """포트 닫힘 시 상태바 업데이트"""
        self.global_status_bar.update_port_status(port_name, False)
        self.global_status_bar.show_message(f"Disconnected from {port_name}", 3000)

    def on_port_error(self, port_name: str, error_msg: str) -> None:
        """포트 에러 시 상태바 업데이트"""
        self.global_status_bar.show_message(f"Error ({port_name}): {error_msg}", 5000)

    def update_status_bar(self) -> None:
        """1초마다 호출되어 상태바 정보를 갱신합니다."""
        # 1. RX/TX 속도 업데이트
        self.global_status_bar.update_rx_speed(self.rx_byte_count)
        self.global_status_bar.update_tx_speed(self.tx_byte_count)

        # 카운터 초기화
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # 2. 시간 업데이트
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.global_status_bar.update_time(current_time)

    def on_shortcut_connect(self) -> None:
        """F2 단축키: 현재 포트 연결"""
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        """F3 단축키: 현재 포트 연결 해제"""
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """F5 단축키: 로그 지우기"""
        self.port_presenter.clear_log_current_port()

    # -------------------------------------------------------------------------
    # 데이터 로깅 (Log Logging)
    # -------------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        """모든 포트 패널의 로깅 시그널을 연결합니다."""
        for i in range(self.view.left_section.port_tabs.count()):
            widget = self.view.left_section.port_tabs.widget(i)
            self._connect_single_port_logging(widget)

    def _on_port_tab_added(self, panel) -> None:
        """새 탭이 추가되었을 때 로깅 시그널을 연결합니다."""
        self._connect_single_port_logging(panel)

    def _connect_single_port_logging(self, panel) -> None:
        """단일 포트 패널의 로깅 시그널을 연결합니다."""
        if hasattr(panel, 'received_area_widget'):
            rx_widget = panel.received_area_widget
            # 중복 연결 방지를 위해 disconnect 시도 (실패해도 무방)
            try:
                rx_widget.data_logging_started.disconnect(self._on_data_logging_started)
                rx_widget.data_logging_stopped.disconnect(self._on_data_logging_stopped)
            except TypeError:
                pass

            rx_widget.data_logging_started.connect(self._on_data_logging_started)
            rx_widget.data_logging_stopped.connect(self._on_data_logging_stopped)

    def _get_port_panel_from_sender(self):
        """시그널을 보낸 RxLogWidget이 속한 PortPanel을 찾습니다."""
        sender = self.sender()
        for i in range(self.view.left_section.port_tabs.count()):
            widget = self.view.left_section.port_tabs.widget(i)
            if hasattr(widget, 'received_area_widget') and widget.received_area_widget == sender:
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
        """로깅 중단 처리"""
        panel = self._get_port_panel_from_sender()
        if not panel:
            return

        port_name = panel.get_port_name()
        if port_name and data_logger_manager.is_logging(port_name):
            data_logger_manager.stop_logging(port_name)
            logger.info(f"Logging stopped: {port_name}")
