"""
포트 통계 위젯 모듈

현재 연결된 포트의 통신 통계 정보를 표시합니다.

## WHY
* 데이터 송수신량 및 에러 발생 여부 모니터링
* 연결 지속 시간(Uptime) 확인

## WHAT
* RX/TX 바이트 수, 에러 카운트, 가동 시간 표시
* 마지막 수신 시간 표시

## HOW
* QGroupBox 내 그리드 레이아웃으로 라벨 배치
* 외부에서 데이터를 주입받아 텍스트 갱신
"""
from PyQt5.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel
from view.managers.language_manager import language_manager

class PortStatsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_rx_count_lbl: Optional[QLabel] = None
        self.uptime_lbl: Optional[QLabel] = None
        self.error_count_lbl: Optional[QLabel] = None
        self.tx_count_lbl: Optional[QLabel] = None
        self.rx_count_lbl: Optional[QLabel] = None
        self.group_box: Optional[QGroupBox] = None
        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox(language_manager.get_text("port_stats_grp_title"))
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
        self.group_box.setTitle(language_manager.get_text("port_stats_grp_title"))

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
