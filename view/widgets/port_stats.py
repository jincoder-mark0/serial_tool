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
* 외부에서 DTO(PortStatistics)를 주입받아 텍스트 갱신
"""
from PyQt5.QtWidgets import QWidget, QGroupBox, QGridLayout, QLabel
from typing import Optional
from view.managers.language_manager import language_manager
from common.dtos import PortStatistics

class PortStatsWidget(QWidget):
    """
    포트 통계 표시 위젯
    """
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

    def update_statistics(self, stats: PortStatistics) -> None:
        """
        통계 정보 업데이트 (DTO 적용)

        Args:
            stats (PortStatistics): 통계 정보 DTO
        """
        self.rx_count_lbl.setText(f"RX: {self.format_bytes(stats.rx_bytes)}")
        self.tx_count_lbl.setText(f"TX: {self.format_bytes(stats.tx_bytes)}")
        self.error_count_lbl.setText(f"Errors: {stats.error_count}")
        # BPS는 MainStatusBar에서 주로 표시하므로 여기선 선택적

    def set_rx_bytes(self, bytes_count: int):
        """
        RX 데이터 크기 업데이트

        Args:
            bytes_count (int): 수신 데이터 크기
        """
        self.rx_count_lbl.setText(f"RX: {self.format_bytes(bytes_count)}")

    def set_tx_bytes(self, bytes_count: int):
        """
        TX 데이터 크기 업데이트

        Args:
            bytes_count (int): 송신 데이터 크기
        """
        self.tx_count_lbl.setText(f"TX: {self.format_bytes(bytes_count)}")

    def set_error_count(self, count: int):
        """
        에러 카운트 업데이트

        Args:
            count (int): 에러 발생 횟수
        """
        self.error_count_lbl.setText(f"Errors: {count}")

    def set_uptime(self, seconds: int):
        """
        가동 시간 업데이트

        Args:
            seconds (int): 가동 시간 (초)
        """
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        self.uptime_lbl.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")

    def set_last_rxtime(self, timestamp: str):
        """
        마지막 수신 시간 업데이트

        Args:
            timestamp (str): 마지막 수신 시간
        """
        self.last_rx_count_lbl.setText(f"Last RX: [{timestamp}]")

    @staticmethod
    def format_bytes(size: int) -> str:
        """
        바이트 크기를 읽기 쉬운 단위로 변환

        Args:
            size (int): 바이트 크기

        Returns:
            str: 변환된 크기 문자열
        """
        power = 2**10
        n = 0
        power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"
