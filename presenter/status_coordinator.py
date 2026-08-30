"""
상태바 갱신 생명주기 조정자.

TrafficMonitor의 interval 통계를 소비하고 현재 시각과 함께 MainWindow 상태바에
반영합니다. QTimer 생성/시작/중지는 이 객체가 소유합니다.
"""
from PyQt5.QtCore import QDateTime, QObject, QTimer

from common.constants import STATUS_BAR_UPDATE_INTERVAL_MS
from model.traffic_monitor import TrafficMonitor
from view.main_window import MainWindow


class StatusCoordinator(QObject):
    """주기적 상태바 갱신과 timer 생명주기를 관리합니다."""

    def __init__(self, view: MainWindow, traffic_monitor: TrafficMonitor) -> None:
        super().__init__()
        self._view = view
        self._traffic_monitor = traffic_monitor
        self._timer = QTimer(self)
        self._timer.setInterval(STATUS_BAR_UPDATE_INTERVAL_MS)
        self._timer.timeout.connect(self.update)

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        """상태바 주기 갱신을 시작합니다."""
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """상태바 주기 갱신을 중지합니다."""
        self._timer.stop()

    def update(self) -> None:
        """현재 interval 통계와 시간을 상태바에 반영합니다."""
        self._view.update_status_bar_stats(self._traffic_monitor.take_statistics())
        self._view.update_status_bar_time(
            QDateTime.currentDateTime().toString("HH:mm:ss")
        )
