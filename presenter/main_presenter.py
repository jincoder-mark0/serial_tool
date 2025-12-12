"""
메인 프레젠터 모듈

애플리케이션의 최상위 Presenter입니다.
View와 Model을 연결하고 전역 상태를 관리합니다.

## WHY
* MVP 패턴 준수 (비즈니스 로직 분리)
* 하위 Presenter 조율
* 전역 이벤트 및 설정 관리

## WHAT
* 하위 Presenter (Port, Macro, File, Packet, Manual) 생성 및 연결
* View 이벤트 처리 (시그널 구독)
* Model 상태 변화에 따른 View 업데이트
* 설정 저장 및 로드 로직

## HOW
* Signal/Slot 기반 통신
* EventRouter를 통한 전역 이벤트 수신
"""
from PyQt5.QtCore import QObject, QTimer, QDateTime
from view.main_window import MainWindow
from model.port_controller import PortController
from model.macro_runner import MacroRunner
from .port_presenter import PortPresenter
from .macro_presenter import MacroPresenter
from .file_presenter import FilePresenter
from .packet_presenter import PacketPresenter
from .manual_ctrl_presenter import ManualCtrlPresenter
from .event_router import EventRouter
from core.settings_manager import SettingsManager
from core.data_logger import data_logger_manager
from view.managers.lang_manager import lang_manager
from core.logger import logger
from constants import ConfigKeys

class MainPresenter(QObject):
    """
    메인 프레젠터 클래스

    애플리케이션의 전체적인 흐름을 제어합니다.
    """

    def __init__(self, view: MainWindow) -> None:
        """
        MainPresenter 생성 및 초기화

        Logic:
            - 모델 인스턴스 생성
            - 하위 Presenter 초기화 및 View 연결
            - 시그널/슬롯 연결 (Model <-> Presenter <-> View)
            - 상태바 타이머 시작

        Args:
            view (MainWindow): 메인 윈도우 뷰 인스턴스
        """
        super().__init__()
        self.view = view

        # --- 1. Model 초기화 ---
        self.port_controller = PortController()
        self.macro_runner = MacroRunner()
        self.event_router = EventRouter()

        # --- 2. Sub-Presenter 초기화 ---
        # MVP: View가 노출한 인터페이스를 통해 하위 View 전달

        # 2.1 Port Control
        self.port_presenter = PortPresenter(self.view.port_view, self.port_controller)

        # 2.2 Macro Control
        self.macro_presenter = MacroPresenter(self.view.macro_view, self.macro_runner)

        # 2.3 File Transfer
        self.file_presenter = FilePresenter(self.port_controller)

        # 2.4 Packet Inspector
        # MainWindow는 packet_inspector_panel에 대한 직접적인 프로퍼티가 없으므로 right_section을 통해 접근하거나
        # MainWindow에 packet_view 프로퍼티를 추가하는 것이 MVP에 더 부합함.
        # 여기서는 right_section을 통해 접근 (기존 macro_view 패턴과 동일하게 MainWindow 수정 필요할 수 있음)
        # MainWindow에 packet_view 프로퍼티를 추가했다고 가정하고 사용 (아래 MainWindow 수정 코드 필요)
        # 하지만 이번 턴의 요구사항 범위 내에서 해결하기 위해 직접 접근 방식 사용 (view.right_section.packet_inspector)
        self.packet_presenter = PacketPresenter(self.view.right_section.packet_inspector, self.event_router)

        # 2.5 Manual Control
        # Local Echo 처리를 위해 view의 append_local_echo_data 메서드를 콜백으로 전달
        self.manual_ctrl_presenter = ManualCtrlPresenter(
            self.view.left_section.manual_ctrl,
            self.port_controller,
            self.view.append_local_echo_data
        )

        # --- 3. EventRouter 시그널 연결 (Model -> Presenter) ---
        # Port Events
        self.event_router.data_received.connect(self.on_data_received)
        self.event_router.port_opened.connect(self.on_port_opened)
        self.event_router.port_closed.connect(self.on_port_closed)
        self.event_router.port_error.connect(self.on_port_error)
        self.event_router.data_sent.connect(self.on_data_sent)
        
        # [New] Macro Events (Global Log/Status)
        self.event_router.macro_started.connect(self.on_macro_started)
        self.event_router.macro_finished.connect(self.on_macro_finished)
        self.event_router.macro_error.connect(self.on_macro_error)

        # [New] File Transfer Events (Global Log/Status)
        self.event_router.file_transfer_completed.connect(self.on_file_transfer_completed)
        self.event_router.file_transfer_error.connect(self.on_file_transfer_error)
        # Progress는 빈도가 높으므로 MainStatusbar가 아닌 FileDialog에서만 처리 (성능 고려)

        # --- 4. 내부 Model 시그널 연결 ---
        # 매크로 러너의 전송 요청은 ManualCtrlPresenter 로직과 유사하므로
        # ManualCtrlPresenter의 메서드를 호출하거나, 별도로 처리.
        # 여기서는 매크로 로직이 독립적이므로 MainPresenter에서 중계하되,
        # 로직 중복을 피하기 위해 ManualCtrlPresenter의 로직을 재사용할 수도 있음.
        # 다만 MacroRunner의 시그널 인자가 다르므로(local_echo 없음), 별도 처리 유지.
        self.macro_runner.send_requested.connect(self.on_macro_cmd_send_requested)

        # --- 5. View 시그널 연결 (View -> Presenter) ---
        # 수동 전송 요청은 이제 ManualCtrlPresenter가 직접 처리하므로
        # MainPresenter에서는 연결하지 않음.
        # self.view.manual_cmd_send_requested.connect(...) -> REMOVED

        # 설정 및 종료
        self.view.settings_save_requested.connect(self.on_settings_change_requested)
        self.view.font_settings_changed.connect(self.on_font_settings_changed)
        self.view.close_requested.connect(self.on_close_requested)

        # 단축키
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

        # 파일 전송
        self.view.file_transfer_dialog_opened.connect(self.file_presenter.on_file_transfer_dialog_opened)

        # 로깅 및 탭 추가
        self._connect_logging_signals()
        self.view.port_tab_added.connect(self._on_port_tab_added)

        # --- 6. 초기화 완료 ---
        self.rx_byte_count = 0
        self.tx_byte_count = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000)

        self.view.log_system_message("Application initialized", "INFO")

    def on_close_requested(self) -> None:
        """
        애플리케이션 종료 처리

        Logic:
            - 윈도우 상태 및 설정 데이터 수집
            - 설정 파일 저장
            - 포트 및 리소스 정리
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
        데이터 수신 처리

        Logic:
            - 데이터 로깅 (활성화 시)
            - 해당 포트의 뷰 위젯에 데이터 전달
            - RX 카운트 증가

        Args:
            port_name (str): 수신 포트 이름
            data (bytes): 수신 데이터
        """
        # 로깅 중이면 DataLogger에 먼저 기록 (데이터 누락 방지)
        # 해당 포트가 로깅 중인지 확인
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 뷰 인터페이스를 통해 데이터 전달
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            if hasattr(widget, 'get_port_name') and widget.get_port_name() == port_name:
                if hasattr(widget, 'received_area_widget'):
                    widget.received_area_widget.append_data(data)
                break

        # RX 카운트 증가 (전체 합계)
        self.rx_byte_count += len(data)

    def on_macro_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool) -> None:
        """
        매크로 전송 요청 처리

        Note: ManualCtrlPresenter와 로직이 유사하므로 추후 공통 로직으로 분리 가능.
        현재는 ManualCtrlPresenter가 View 인스턴스를 가지고 있어 재사용이 어려우므로 별도 처리.

        Logic:
            - 포트 열림 확인
            - Prefix/Suffix 적용
            - Hex 변환 (필요 시)
            - 데이터 전송
            - Local Echo 처리 (View 인터페이스 호출)

        Args:
            text (str): 전송할 텍스트
            hex_mode (bool): Hex 모드 여부
            cmd_prefix (bool): 접두사 사용 여부
            cmd_suffix (bool): 접미사 사용 여부
            local_echo (bool): 로컬 에코 사용 여부
        """
        # ManualCtrlPresenter의 메서드를 직접 호출할 수도 있으나, 인자가 약간 다름 (local_echo)
        # 여기서는 MainPresenter에서 직접 처리 (기존 로직 유지)
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
            self.view.append_local_echo_data(data)
    def on_settings_change_requested(self, new_settings: dict) -> None:
        """
        설정 저장 요청을 처리합니다.
        데이터 검증 및 변환 후 설정을 업데이트합니다.

        Args:
            new_settings (dict): 변경할 설정 딕셔너리
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
                    continue

            setting_path = settings_map.get(key)
            if setting_path:
                settings_manager.set(setting_path, final_value)

        # UI 업데이트
        if 'theme' in new_settings:
            self.view.switch_theme(new_settings['theme'].lower())

        if 'language' in new_settings:
            lang_manager.set_language(new_settings['language'])

        # max_log_lines 설정 변경 시 모든 RxLogWidget에 적용
        if 'max_log_lines' in new_settings:
            try:
                max_lines_int = int(new_settings['max_log_lines'])
                count = self.view.get_port_tabs_count()
                for i in range(count):
                    widget = self.view.get_port_tab_widget(i)
                    if hasattr(widget, 'received_area_widget'):
                        widget.received_area_widget.set_max_lines(max_lines_int)
            except (ValueError, TypeError):
                logger.warning("Invalid max_log_lines value")

        # PacketPresenter 설정 업데이트 요청
        # (설정 저장 후 즉시 반영)
        self.packet_presenter.apply_settings()

        self.view.show_status_message("Settings updated", 2000)
        self.view.log_system_message("Settings updated", "INFO")

    @staticmethod
    def on_font_settings_changed(self, font_settings: dict) -> None:
        """
        폰트 설정 변경 처리

        Args:
            font_settings (dict): 폰트 설정 데이터
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
                settings_manager.set(key_map[tm_key], value)
            else:
                # 알 수 없는 키에 대한 경고 (유지보수성 확보)
                logger.warning(f"Unknown font setting key: {tm_key}")

        settings_manager.save_settings()
        logger.info("Font settings saved successfully.")

    def on_data_sent(self, port_name: str, data: bytes) -> None:
        """
        데이터 전송 시 TX 카운트 증가, 로깅 중이면 데이터 기록
        EventRouter를 통해 호출
        """
        # 로깅 중이면 DataLogger에 기록
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        self.tx_byte_count += len(data)

    def on_port_opened(self, port_name: str) -> None:
        """포트 열림 알림"""
        self.view.update_status_bar_port(port_name, True)
        self.view.show_status_message(f"Connected to {port_name}", 3000)

    def on_port_closed(self, port_name: str) -> None:
        """포트 닫힘 알림"""
        self.view.update_status_bar_port(port_name, False)
        self.view.show_status_message(f"Disconnected from {port_name}", 3000)

    def on_port_error(self, port_name: str, error_msg: str) -> None:
        """포트 에러 알림"""
        self.view.show_status_message(f"Error ({port_name}): {error_msg}", 5000)

    # ---------------------------------------------------------
    # Macro Event Handlers (New)
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

    # ---------------------------------------------------------
    # File Transfer Event Handlers (New)
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

    def update_status_bar(self) -> None:
        """상태바 주기적 업데이트"""
        # 1. RX/TX 속도 업데이트
        self.view.update_status_bar_stats(self.rx_byte_count, self.tx_byte_count)
        # 카운터 초기화
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # 2. 시간 업데이트
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.view.update_status_bar_time(current_time)

    def on_shortcut_connect(self) -> None:
        """연결 단축키"""
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        """연결 해제 단축키"""
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """로그 지우기 단축키"""
        self.port_presenter.clear_log_current_port()

    # -------------------------------------------------------------------------
    # 데이터 로깅 (Log Logging)
    # -------------------------------------------------------------------------
    def _connect_logging_signals(self) -> None:
        """로깅 시그널 연결"""
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
            self._connect_single_port_logging(widget)

    def _on_port_tab_added(self, panel) -> None:
        """탭 추가 시 로깅 연결"""
        self._connect_single_port_logging(panel)

    def _connect_single_port_logging(self, panel) -> None:
        """
        단일 포트 로깅 시그널 연결

        Args:
            panel: 포트 패널 위젯
        """
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
        """시그널 발신 패널 찾기"""
        sender = self.sender()
        count = self.view.get_port_tabs_count()
        for i in range(count):
            widget = self.view.get_port_tab_widget(i)
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
        """로깅 중단 핸들러"""
        panel = self._get_port_panel_from_sender()
        if not panel:
            return

        port_name = panel.get_port_name()
        if port_name and data_logger_manager.is_logging(port_name):
            data_logger_manager.stop_logging(port_name)
            logger.info(f"Logging stopped: {port_name}")
