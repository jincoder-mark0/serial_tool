"""
RX/TX 트래픽 기록 및 통계 서비스.

UI throttling과 무관한 DataLogger 기록과 바이트 통계를 Presenter에서 분리합니다.
"""
from common.dtos import PortDataEvent, PortStatistics
from core.data_logger import data_logger_manager


class TrafficMonitor:
    """PortDataEvent의 기록/통계를 UI 비의존적으로 관리합니다."""

    def __init__(self) -> None:
        self._rx_bytes = 0
        self._tx_bytes = 0

    def record_received(self, event: PortDataEvent) -> None:
        """RX 데이터를 활성 로그에 기록하고 통계를 누적합니다."""
        if not event.data:
            return
        self._write_if_logging(event)
        self._rx_bytes += len(event.data)

    def record_sent(self, event: PortDataEvent) -> None:
        """TX 데이터를 활성 로그에 기록하고 통계를 누적합니다."""
        if not event.data:
            return
        self._write_if_logging(event)
        self._tx_bytes += len(event.data)

    def take_statistics(self) -> PortStatistics:
        """현재 interval 통계를 DTO로 반환하고 카운터를 원자적으로 초기화합니다."""
        stats = PortStatistics(
            rx_bytes=self._rx_bytes,
            tx_bytes=self._tx_bytes,
            bps=0,
        )
        self._rx_bytes = 0
        self._tx_bytes = 0
        return stats

    @staticmethod
    def _write_if_logging(event: PortDataEvent) -> None:
        if data_logger_manager.is_logging(event.port):
            data_logger_manager.write(event.port, event.data)
