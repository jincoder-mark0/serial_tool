"""PortScanManager의 QThread 생명주기와 Presenter 위임 계약을 검증합니다."""
import inspect
import time
from unittest.mock import MagicMock, patch

from model.port_scan_manager import PortScanManager
from presenter.port_presenter import PortPresenter


def test_manager_waits_for_running_scan_without_leaking_worker(qapp):
    """종료와 스캔이 겹쳐도 worker가 실행 중인 채로 남지 않아야 합니다."""
    manager = PortScanManager()

    def _slow_comports():
        time.sleep(0.2)
        return []

    with patch(
        "model.port_scanner.serial.tools.list_ports.comports",
        side_effect=_slow_comports,
    ):
        assert manager.request_scan() is True
        worker = manager._worker
        assert worker is not None
        assert worker.isRunning() is True

        manager.stop()

    assert worker.isRunning() is False
    assert manager._worker is None


def test_manager_rejects_overlapping_scan_requests(qapp):
    manager = PortScanManager()

    def _slow_comports():
        time.sleep(0.2)
        return []

    with patch(
        "model.port_scanner.serial.tools.list_ports.comports",
        side_effect=_slow_comports,
    ):
        assert manager.request_scan() is True
        assert manager.request_scan() is False
        manager.stop()


def test_manager_stop_without_worker_is_idempotent():
    manager = PortScanManager()
    manager.stop()
    manager.stop()
    assert manager._worker is None


def test_port_presenter_does_not_own_or_construct_scan_worker():
    source = inspect.getsource(PortPresenter)

    assert "PortScanWorker" not in source
    assert "_scan_worker" not in source
    assert "self.port_scan_manager.request_scan()" in source
    assert "self.port_scan_manager.stop()" in source


def test_port_presenter_scan_methods_delegate_to_manager():
    presenter = object.__new__(PortPresenter)
    presenter.port_scan_manager = MagicMock()

    presenter.scan_ports()
    presenter.stop_pending_scan()

    presenter.port_scan_manager.request_scan.assert_called_once()
    presenter.port_scan_manager.stop.assert_called_once()
