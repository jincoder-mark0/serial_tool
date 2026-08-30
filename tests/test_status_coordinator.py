"""StatusCoordinator의 timer/통계 표시 책임을 검증합니다."""
from unittest.mock import MagicMock, patch

from common.dtos import PortStatistics
from presenter.status_coordinator import StatusCoordinator


def test_status_coordinator_updates_view_with_interval_statistics(qapp):
    view = MagicMock()
    traffic = MagicMock()
    stats = PortStatistics(rx_bytes=10, tx_bytes=20, bps=0)
    traffic.take_statistics.return_value = stats
    coordinator = StatusCoordinator(view, traffic)

    with patch(
        "presenter.status_coordinator.QDateTime.currentDateTime"
    ) as current_datetime:
        current_datetime.return_value.toString.return_value = "15:30:00"
        coordinator.update()

    traffic.take_statistics.assert_called_once_with()
    view.update_status_bar_stats.assert_called_once_with(stats)
    view.update_status_bar_time.assert_called_once_with("15:30:00")


def test_status_coordinator_owns_timer_lifecycle(qapp):
    coordinator = StatusCoordinator(MagicMock(), MagicMock())

    assert coordinator.is_running is False
    coordinator.start()
    assert coordinator.is_running is True
    coordinator.stop()
    assert coordinator.is_running is False
