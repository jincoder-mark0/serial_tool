from PyQt5.QtCore import QObject, QTimer, QDateTime
from view.main_window import MainWindow
from model.port_controller import PortController
from .port_presenter import PortPresenter
from core.settings_manager import SettingsManager
from view.managers.lang_manager import lang_manager
from core.logger import logger

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

        # 하위 Presenter 초기화 (Initialize Sub-Presenters)
        self.port_presenter = PortPresenter(self.view.left_section, self.port_controller)

        # 데이터 수신 시그널을 로그 뷰에 연결
        self.port_controller.data_received.connect(self.on_data_received)

        # 수동 전송 시그널 연결
        self.view.left_section.manual_ctrl.manual_ctrl_widget.manual_cmd_send_requested.connect(
            self.on_manual_cmd_send_requested
        )

        # 설정 저장 요청 시그널 연결
        self.view.settings_save_requested.connect(self.on_settings_change_requested)

        # 종료 요청 시그널 연결
        self.view.close_requested.connect(self.on_close_requested)

        # 상태바 업데이트를 위한 변수 및 타이머
        self.rx_byte_count = 0
        self.tx_byte_count = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000)

        # 포트 컨트롤러 시그널 연결
        self.port_controller.data_sent.connect(self.on_data_sent)
        self.port_controller.port_opened.connect(self.on_port_opened)
        self.port_controller.port_closed.connect(self.on_port_closed)
        self.port_controller.error_occurred.connect(self.on_port_error)

        # 단축키 시그널 연결
        self.view.shortcut_connect_requested.connect(self.on_shortcut_connect)
        self.view.shortcut_disconnect_requested.connect(self.on_shortcut_disconnect)
        self.view.shortcut_clear_requested.connect(self.on_shortcut_clear)

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
        settings_manager.set('ui.window_width', state.get('ui.window_width'))
        settings_manager.set('ui.window_height', state.get('ui.window_height'))
        settings_manager.set('ui.window_x', state.get('ui.window_x'))
        settings_manager.set('ui.window_y', state.get('ui.window_y'))
        settings_manager.set('ui.splitter_state', state.get('ui.splitter_state'))
        settings_manager.set('settings.right_panel_visible', state.get('settings.right_panel_visible'))

        # 2.2 Left Section 상태
        if 'manual_ctrl' in state:
            settings_manager.set('manual_ctrl', state['manual_ctrl'])
        if 'ports.tabs' in state:
            settings_manager.set('ports.tabs', state['ports.tabs'])

        # 2.3 Right Section 상태
        if 'macro_list.commands' in state:
            settings_manager.set('macro_list.commands', state['macro_list.commands'])
        if 'macro_list.control_state' in state:
            settings_manager.set('macro_list.control_state', state['macro_list.control_state'])

        # 3. 파일 쓰기
        settings_manager.save_settings()

        # 4. 리소스 정리 (포트 닫기)
        if self.port_controller.is_open:
            self.port_controller.close_port()

        logger.info("Application shutdown sequence completed.")

    def on_data_received(self, data: bytes) -> None:
        """
        수신된 시리얼 데이터를 처리합니다.
        현재 활성 포트 패널의 ReceivedArea로 데이터를 전달합니다.

        Args:
            data (bytes): 수신된 바이트 데이터.
        """
        # 현재 활성 포트 패널을 가져와서 ReceivedArea로 데이터 전달
        index = self.view.left_section.port_tabs.currentIndex()
        if index >= 0:
            widget = self.view.left_section.port_tabs.widget(index)
            if hasattr(widget, 'received_area_widget'):
                widget.received_area_widget.append_data(data)

        # RX 카운트 증가
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
            prefix = settings.get("settings.cmd_prefix", "")
            final_text = prefix + final_text

        # Apply suffix if requested
        if cmd_suffix:
            suffix = settings.get("settings.cmd_suffix", "")
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
            'theme': 'settings.theme',
            'language': 'settings.language',
            'proportional_font_size': 'settings.proportional_font_size',
            'max_log_lines': 'settings.rx_max_lines',
            'cmd_prefix': 'settings.cmd_prefix',
            'cmd_suffix': 'settings.cmd_suffix',
            'port_baudrate': 'settings.port_baudrate',
            'port_scan_interval': 'settings.port_scan_interval',
            'log_path': 'logging.path',
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
        if hasattr(self.view, 'global_status_bar'):
            self.view.global_status_bar.show_message("Settings updated", 2000)

    def on_data_sent(self, data: bytes) -> None:
        """데이터 전송 시 TX 카운트를 증가시킵니다."""
        self.tx_byte_count += len(data)

    def on_port_opened(self, port_name: str) -> None:
        """포트 열림 시 상태바 업데이트"""
        if hasattr(self.view, 'global_status_bar'):
            self.view.global_status_bar.update_port_status(port_name, True)
            self.view.global_status_bar.show_message(f"Connected to {port_name}", 3000)

    def on_port_closed(self, port_name: str) -> None:
        """포트 닫힘 시 상태바 업데이트"""
        if hasattr(self.view, 'global_status_bar'):
            self.view.global_status_bar.update_port_status(port_name, False)
            self.view.global_status_bar.show_message(f"Disconnected from {port_name}", 3000)

    def on_port_error(self, error_msg: str) -> None:
        """포트 에러 시 상태바 업데이트"""
        if hasattr(self.view, 'global_status_bar'):
            self.view.global_status_bar.show_message(f"Error: {error_msg}", 5000)

    def update_status_bar(self) -> None:
        """1초마다 호출되어 상태바 정보를 갱신합니다."""
        if not hasattr(self.view, 'global_status_bar'):
            return

        # 1. RX/TX 속도 업데이트
        self.view.global_status_bar.update_rx_speed(self.rx_byte_count)
        self.view.global_status_bar.update_tx_speed(self.tx_byte_count)

        # 카운터 초기화
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # 2. 시간 업데이트
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.view.global_status_bar.update_time(current_time)

        # 3. 버퍼 상태 (임시: 실제 버퍼 크기를 알 수 있다면 연동)
        # self.view.global_status_bar.update_buffer(buffer_percent)

    def on_shortcut_connect(self) -> None:
        """F2 단축키: 현재 포트 연결"""
        self.port_presenter.connect_current_port()

    def on_shortcut_disconnect(self) -> None:
        """F3 단축키: 현재 포트 연결 해제"""
        self.port_presenter.disconnect_current_port()

    def on_shortcut_clear(self) -> None:
        """F5 단축키: 로그 지우기"""
        self.port_presenter.clear_log_current_port()

