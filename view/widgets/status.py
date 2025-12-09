from PyQt5.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel
from view.lang_manager import lang_manager

class StatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_rx_label = None
        self.uptime_label = None
        self.errors_label = None
        self.tx_label = None
        self.rx_label = None
        self.group_box = None
        self.init_ui()
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox(lang_manager.get_text("status_grp_title"))
        gb_layout = QGridLayout()

        self.rx_label = QLabel("RX: 0 B")
        self.tx_label = QLabel("TX: 0 B")
        self.errors_label = QLabel("Errors: 0")
        self.uptime_label = QLabel("Uptime: 00:00:00")
        self.last_rx_label = QLabel("Last RX: [--:--:--.---]")

        gb_layout.addWidget(self.rx_label, 0, 0)
        gb_layout.addWidget(self.tx_label, 0, 1)
        gb_layout.addWidget(self.errors_label, 1, 0)
        gb_layout.addWidget(self.uptime_label, 1, 1)
        gb_layout.addWidget(self.last_rx_label, 2, 0, 1, 2)

        self.group_box.setLayout(gb_layout)
        layout.addWidget(self.group_box, 0, 0)
        self.setLayout(layout)

    def retranslate_ui(self):
        self.group_box.setTitle(lang_manager.get_text("status_grp_title"))

    def update_rx(self, bytes_count: int):
        self.rx_label.setText(f"RX: {self.format_bytes(bytes_count)}")

    def update_tx(self, bytes_count: int):
        self.tx_label.setText(f"TX: {self.format_bytes(bytes_count)}")

    def update_errors(self, count: int):
        self.errors_label.setText(f"Errors: {count}")

    def update_uptime(self, seconds: int):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        self.uptime_label.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

    def update_last_rx(self, timestamp: str):
        self.last_rx_label.setText(f"Last RX: [{timestamp}]")

    @staticmethod
    def format_bytes(size: int) -> str:
        power = 2**10
        n = 0
        power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"
