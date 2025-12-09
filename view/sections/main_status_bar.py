from PyQt5.QtWidgets import QStatusBar, QLabel, QProgressBar
from PyQt5.QtCore import Qt
from view.tools.lang_manager import lang_manager

class MainStatusBar(QStatusBar):
    """
    메인 윈도우의 상태바를 관리하는 클래스입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        """상태바 초기화"""
        self.showMessage(lang_manager.get_text("main_status_msg_ready"))
        self.init_widgets()

    def init_widgets(self):
        # 1. Port Label
        self.port_label = QLabel("Port: -- ○")
        self.addPermanentWidget(self.port_label)

        # 2. RX Speed
        self.rx_label = QLabel("RX: 0 KB/s")
        self.addPermanentWidget(self.rx_label)

        # 3. TX Speed
        self.tx_label = QLabel("TX: 0 KB/s")
        self.addPermanentWidget(self.tx_label)

        # 4. BPS
        self.bps_label = QLabel("BPS: 0")
        self.addPermanentWidget(self.bps_label)

        # 5. Buffer Bar
        self.buffer_bar = QProgressBar()
        self.buffer_bar.setMaximum(100)
        self.buffer_bar.setMaximumWidth(100)
        self.buffer_bar.setFormat("Buffer: %p%")
        self.buffer_bar.setAlignment(Qt.AlignCenter)
        self.addPermanentWidget(self.buffer_bar)

        # 6. Time Label
        self.time_label = QLabel("00:00:00")
        self.addPermanentWidget(self.time_label)

    def update_port_status(self, port: str, connected: bool):
        status_symbol = "●" if connected else "○"
        color = "green" if connected else "gray"
        self.port_label.setText(f"Port: {port} <span style='color:{color}'>{status_symbol}</span>")

    def update_rx_speed(self, bytes_per_sec: int):
        speed = bytes_per_sec / 1024
        self.rx_label.setText(f"RX: {speed:.1f} KB/s")

    def update_tx_speed(self, bytes_per_sec: int):
        speed = bytes_per_sec / 1024
        self.tx_label.setText(f"TX: {speed:.1f} KB/s")

    def update_buffer(self, percent: int):
        self.buffer_bar.setValue(percent)
        if percent >= 80:
            self.buffer_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
            self.buffer_bar.setStyleSheet("")

    def update_time(self, time_str: str):
        self.time_label.setText(time_str)

    def show_message(self, message: str, timeout: int = 0) -> None:
        """
        상태바에 메시지를 표시합니다.

        Args:
            message (str): 표시할 메시지
            timeout (int): 메시지 표시 시간 (ms). 0이면 계속 표시.
        """
        self.showMessage(message, timeout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 상태바 텍스트를 업데이트합니다."""
        # (임시 메시지가 떠있는 경우는 그대로 둠)
        current_msg = self.currentMessage()
        if not current_msg or lang_manager.text_matches_key(current_msg, "main_status_msg_ready"):
            self.showMessage(lang_manager.get_text("main_status_msg_ready"))
