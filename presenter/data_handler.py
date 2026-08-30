"""
RX UI throttling handler.

트래픽 기록/통계는 TrafficMonitor가 소유하고, 이 객체는 고속 RX 데이터를 포트별로
버퍼링해 주기적으로 View에 반영하는 presentation 책임만 담당합니다.
"""
from collections import defaultdict
from typing import Optional

from PyQt5.QtCore import QObject, QTimer

from common.constants import UI_REFRESH_INTERVAL_MS
from common.dtos import LogDataBatch, PortDataEvent
from model.traffic_monitor import TrafficMonitor
from view.main_window import MainWindow


class DataTrafficHandler(QObject):
    """RX 데이터를 UI refresh 주기에 맞춰 배치하는 Presenter helper."""

    def __init__(
        self,
        view: MainWindow,
        traffic_monitor: Optional[TrafficMonitor] = None,
    ) -> None:
        super().__init__()
        self.view = view
        self.traffic_monitor = traffic_monitor or TrafficMonitor()
        self._rx_buffer = defaultdict(bytearray)

        self._ui_refresh_timer = QTimer()
        self._ui_refresh_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self._ui_refresh_timer.timeout.connect(self._flush_rx_buffer_to_ui)
        self._ui_refresh_timer.start()

    @property
    def rx_byte_count(self) -> int:
        """기존 테스트/호출 호환용 통계 alias."""
        return self.traffic_monitor.rx_bytes

    @property
    def tx_byte_count(self) -> int:
        """기존 테스트/호출 호환용 통계 alias."""
        return self.traffic_monitor.tx_bytes

    def on_fast_data_received(self, event: PortDataEvent) -> None:
        """RX 기록/통계를 Monitor에 위임하고 UI buffer에 누적합니다."""
        if not event.data:
            return

        self.traffic_monitor.record_received(event)
        self._rx_buffer[event.port].extend(event.data)

    def on_data_sent(self, event: PortDataEvent) -> None:
        """TX 기록/통계를 TrafficMonitor에 위임합니다."""
        self.traffic_monitor.record_sent(event)

    def _flush_rx_buffer_to_ui(self) -> None:
        """현재 RX buffer를 port별 LogDataBatch로 View에 반영합니다."""
        if not self._rx_buffer:
            return

        pending_ports = list(self._rx_buffer.keys())
        for port_name in pending_ports:
            data = self._rx_buffer[port_name]
            if not data:
                continue

            self.view.append_rx_data(
                LogDataBatch(port=port_name, data=bytes(data))
            )
            del self._rx_buffer[port_name]

    def stop(self) -> None:
        """UI refresh timer를 중지하고 남은 RX buffer를 마지막으로 flush합니다."""
        self._ui_refresh_timer.stop()
        self._flush_rx_buffer_to_ui()

    def reset_counts(self) -> None:
        """기존 호출 호환용 delegate."""
        self.traffic_monitor.reset()
