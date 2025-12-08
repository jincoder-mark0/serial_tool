from PyQt5.QtCore import QObject
from view.main_window import MainWindow
from model.port_controller import PortController
from .port_presenter import PortPresenter

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
        self.view.left_section.manual_control.manual_control_widget.send_command_requested.connect(
            self.on_send_command_requested
        )

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

    def on_send_command_requested(self, text: str, hex_mode: bool, use_prefix: bool, use_suffix: bool) -> None:
        """
        수동 명령 전송 요청을 처리합니다.
        prefix/suffix 설정을 적용하고 최종 데이터를 전송합니다.

        Args:
            text: 사용자가 입력한 원본 텍스트
            hex_mode: HEX 모드 사용 여부
            use_prefix: 접두사 사용 여부
            use_suffix: 접미사 사용 여부
        """
        if not self.port_controller.is_open:
            logger.warning("Port not open")
            return

        from core.settings_manager import SettingsManager
        settings = SettingsManager()

        final_text = text

        # Apply prefix if requested
        if use_prefix:
            prefix = settings.get("command.prefix", "")
            prefix = prefix.replace("\\r", "\r").replace("\\n", "\n")
            final_text = prefix + final_text

        # Apply suffix if requested
        if use_suffix:
            suffix = settings.get("command.suffix", "\\r\\n")
            suffix = suffix.replace("\\r", "\r").replace("\\n", "\n")
            final_text = final_text + suffix

        # Convert to bytes
        if hex_mode:
            try:
                # 16진수 문자열을 실제 바이트로 변환 (예: "01 02 FF" -> b'\x01\x02\xff')
                data = bytes.fromhex(final_text.replace(' ', ''))
            except ValueError:
                # 유효하지 않은 16진수 문자열인 경우 처리 (예: 오류 로깅, 사용자에게 알림)
                logger.error("Invalid hex string for sending.")
                return # 전송 중단
        else:
            data = final_text.encode('utf-8')

        self.port_controller.send_data(data)
