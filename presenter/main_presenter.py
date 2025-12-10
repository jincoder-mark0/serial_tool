from PyQt5.QtCore import QObject
from view.main_window import MainWindow
from model.port_controller import PortController
from .port_presenter import PortPresenter
from core.settings_manager import SettingsManager
from view.tools.lang_manager import lang_manager
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
        self.view.setting_save_requested.connect(self.on_settings_change_requested)

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
            if hasattr(widget, 'received_area'):
                widget.received_area.append_data(data)

    def on_manual_cmd_send_requested(self, text: str, hex_mode: bool, cmd_prefix: bool, cmd_suffix: bool) -> None:
        """
        수동 명령 전송 요청을 처리합니다.
        prefix/suffix 설정을 적용하고 최종 데이터를 전송합니다.

        Args:
            text: 사용자가 입력한 원본 텍스트
            hex_mode: HEX 모드 사용 여부
            cmd_prefix: 접두사 사용 여부
            cmd_suffix: 접미사 사용 여부
        """
        if not self.port_controller.is_open:
            logger.warning("Port not open")
            return

        settings = SettingsManager()

        final_text = text

        # Apply prefix if requested
        if cmd_prefix:
            prefix = settings.get("settings.cmd_prefix", "")
            prefix = prefix.replace("\\r", "\r").replace("\\n", "\n")
            final_text = prefix + final_text

        # Apply suffix if requested
        if cmd_suffix:
            suffix = settings.get("settings.cmd_suffix", "\\r\\n")
            suffix = suffix.replace("\\r", "\r").replace("\\n", "\n")
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

        self.port_controller.send_data(data)

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
            'max_log_lines': 'settings.recv_max_lines',
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

        # max_log_lines 설정 변경 시 모든 ReceivedAreaWidget에 적용
        if 'max_log_lines' in new_settings:
            max_lines = new_settings['max_log_lines']
            try:
                max_lines_int = int(max_lines)
                # 모든 포트 패널의 ReceivedAreaWidget에 적용
                for i in range(self.view.left_section.port_tabs.count()):
                    widget = self.view.left_section.port_tabs.widget(i)
                    if hasattr(widget, 'received_area'):
                        widget.received_area.set_max_lines(max_lines_int)
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_log_lines value: {max_lines}")

        # 상태 메시지 표시
        if hasattr(self.view, 'global_status_bar'):
            self.view.global_status_bar.show_message("Settings updated", 2000)

