from PyQt5.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel
from view.managers.lang_manager import lang_manager

class PortStatsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_rx_count_lbl = None
        self.uptime_lbl = None
        self.error_count_lbl = None
        self.tx_count_lbl = None
        self.rx_count_lbl = None
        self.group_box = None
        self.init_ui()
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox(lang_manager.get_text("port_stats_grp_title"))
        gb_layout = QGridLayout()

        self.rx_count_lbl = QLabel("RX: 0 B")
        self.tx_count_lbl = QLabel("TX: 0 B")
        self.error_count_lbl = QLabel("Errors: 0")
        self.uptime_lbl = QLabel("Uptime: 00:00:00")
        self.last_rx_count_lbl = QLabel("Last RX: [--:--:--.---]")

        gb_layout.addWidget(self.rx_count_lbl, 0, 0)
        gb_layout.addWidget(self.tx_count_lbl, 0, 1)
        gb_layout.addWidget(self.error_count_lbl, 1, 0)
        gb_layout.addWidget(self.uptime_lbl, 1, 1)
        gb_layout.addWidget(self.last_rx_count_lbl, 2, 0, 1, 2)

        self.group_box.setLayout(gb_layout)
        layout.addWidget(self.group_box, 0, 0)
        self.setLayout(layout)

    def retranslate_ui(self):
        self.group_box.setTitle(lang_manager.get_text("port_stats_grp_title"))

    def set_rx_bytes(self, bytes_count: int):
        self.rx_count_lbl.setText(f"RX: {self.format_bytes(bytes_count)}")

    def set_tx_bytes(self, bytes_count: int):
        self.tx_count_lbl.setText(f"TX: {self.format_bytes(bytes_count)}")

    def set_error_count(self, count: int):
        self.error_count_lbl.setText(f"Errors: {count}")

    def set_uptime(self, seconds: int):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        self.uptime_lbl.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

    def set_last_rxtime(self, timestamp: str):
        self.last_rx_count_lbl.setText(f"Last RX: [{timestamp}]")

    @staticmethod
    def format_bytes(size: int) -> str:
        power = 2**10
        n = 0
        power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"
