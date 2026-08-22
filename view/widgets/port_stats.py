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
from common.constants import LAYOUT_MARGIN_NONE, LAYOUT_SPACING_DEFAULT

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

        # 언어 전환(retranslate) 시 최신 값으로 라벨을 재구성하기 위한 상태 캐시
        self._rx_bytes: int = 0
        self._tx_bytes: int = 0
        self._error_count: int = 0
        self._uptime_seconds: int = 0
        self._last_rx_timestamp: Optional[str] = None

        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE,
                                   LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)

        self.group_box = QGroupBox(language_manager.get_text("port_stats_grp_title"))
        gb_layout = QGridLayout()
        # 형제 그리드(macro_control 실행 설정, manual_control 옵션)와 동일한 spacing으로 통일 (S-025)
        gb_layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.rx_count_lbl = QLabel()
        self.tx_count_lbl = QLabel()
        self.error_count_lbl = QLabel()
        self.uptime_lbl = QLabel()
        self.last_rx_count_lbl = QLabel()

        gb_layout.addWidget(self.rx_count_lbl, 0, 0)
        gb_layout.addWidget(self.tx_count_lbl, 0, 1)
        gb_layout.addWidget(self.error_count_lbl, 1, 0)
        gb_layout.addWidget(self.uptime_lbl, 1, 1)
        gb_layout.addWidget(self.last_rx_count_lbl, 2, 0, 1, 2)

        self.group_box.setLayout(gb_layout)
        layout.addWidget(self.group_box, 0, 0)
        self.setLayout(layout)

        # 초기 라벨 텍스트 반영 (캐시된 기본값 기준)
        self._refresh_rx()
        self._refresh_tx()
        self._refresh_errors()
        self._refresh_uptime()
        self._refresh_last_rx()

    def retranslate_ui(self):
        self.group_box.setTitle(language_manager.get_text("port_stats_grp_title"))
        self._refresh_rx()
        self._refresh_tx()
        self._refresh_errors()
        self._refresh_uptime()
        self._refresh_last_rx()

    def _refresh_rx(self) -> None:
        """캐시된 RX 바이트로 라벨을 (재)렌더링합니다."""
        self.rx_count_lbl.setText(language_manager.get_text("port_stats_lbl_rx").format(self.format_bytes(self._rx_bytes)))

    def _refresh_tx(self) -> None:
        """캐시된 TX 바이트로 라벨을 (재)렌더링합니다."""
        self.tx_count_lbl.setText(language_manager.get_text("port_stats_lbl_tx").format(self.format_bytes(self._tx_bytes)))

    def _refresh_errors(self) -> None:
        """캐시된 에러 카운트로 라벨을 (재)렌더링합니다."""
        self.error_count_lbl.setText(language_manager.get_text("port_stats_lbl_errors").format(self._error_count))

    def _refresh_uptime(self) -> None:
        """캐시된 가동 시간으로 라벨을 (재)렌더링합니다."""
        m, s = divmod(self._uptime_seconds, 60)
        h, m = divmod(m, 60)
        self.uptime_lbl.setText(language_manager.get_text("port_stats_lbl_uptime").format(f"{h:02d}:{m:02d}:{s:02d}"))

    def _refresh_last_rx(self) -> None:
        """캐시된 마지막 수신 시각으로 라벨을 (재)렌더링합니다."""
        display = self._last_rx_timestamp if self._last_rx_timestamp is not None else "--:--:--.---"
        self.last_rx_count_lbl.setText(language_manager.get_text("port_stats_lbl_last_rx").format(display))

    def update_statistics(self, stats: PortStatistics) -> None:
        """
        통계 정보 업데이트 (DTO 적용)

        Args:
            stats (PortStatistics): 통계 정보 DTO
        """
        self._rx_bytes = stats.rx_bytes
        self._tx_bytes = stats.tx_bytes
        self._error_count = stats.error_count
        self._refresh_rx()
        self._refresh_tx()
        self._refresh_errors()
        # BPS는 MainStatusBar에서 주로 표시하므로 여기선 선택적

    def set_rx_bytes(self, bytes_count: int):
        """
        RX 데이터 크기 업데이트

        Args:
            bytes_count (int): 수신 데이터 크기
        """
        self._rx_bytes = bytes_count
        self._refresh_rx()

    def set_tx_bytes(self, bytes_count: int):
        """
        TX 데이터 크기 업데이트

        Args:
            bytes_count (int): 송신 데이터 크기
        """
        self._tx_bytes = bytes_count
        self._refresh_tx()

    def set_error_count(self, count: int):
        """
        에러 카운트 업데이트

        Args:
            count (int): 에러 발생 횟수
        """
        self._error_count = count
        self._refresh_errors()

    def set_uptime(self, seconds: int):
        """
        가동 시간 업데이트

        Args:
            seconds (int): 가동 시간 (초)
        """
        self._uptime_seconds = seconds
        self._refresh_uptime()

    def set_last_rxtime(self, timestamp: str):
        """
        마지막 수신 시간 업데이트

        Args:
            timestamp (str): 마지막 수신 시간
        """
        self._last_rx_timestamp = timestamp
        self._refresh_last_rx()

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
