"""PortScanManager의 QThread 생명주기와 Presenter 위임 계약을 검증합니다."""
import inspect
import time
from threading import Event
from unittest.mock import MagicMock, patch

from model.port_scan_manager import PortScanManager
from presenter.port_presenter import PortPresenter


def test_manager_waits_for_running_scan_without_leaking_worker(qapp):
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


def test_manager_interrupts_scan_even_when_os_query_is_blocked(qapp):
    release = Event()

    with patch(
        "model.port_scanner.serial.tools.list_ports.comports",
        side_effect=lambda: (release.wait(5) or []),
    ):
        manager = PortScanManager()
        assert manager.request_scan() is True
        started_at = time.monotonic()
        assert manager.stop() is True
        elapsed = time.monotonic() - started_at
        release.set()

    assert elapsed < 0.5
    assert manager._worker is None


def test_scan_failure_is_distinct_from_loopback_fallback(qapp, qtbot):
    manager = PortScanManager()
    failures = []
    found = []
    manager.scan_failed.connect(failures.append)
    manager.ports_found.connect(found.append)

    with patch(
        "model.port_scanner.serial.tools.list_ports.comports",
        side_effect=OSError("registry unavailable"),
    ):
        assert manager.request_scan() is True
        qtbot.waitUntil(lambda: bool(failures) and bool(found), timeout=2000)

    assert failures == ["registry unavailable"]
    assert [port.device for port in found[0]] == ["LOOPBACK"]
    manager.stop()


def test_port_presenter_does_not_own_construct_or_stop_scan_worker():
    source = inspect.getsource(PortPresenter)

    assert "PortScanWorker" not in source
    assert "_scan_worker" not in source
    assert "PortScanManager()" not in source
    assert "stop_pending_scan" not in source
    assert "self.port_scan_manager.request_scan()" in source


def test_port_presenter_scan_request_delegates_to_injected_manager(qapp):
    left_section = MagicMock()
    left_section.get_port_panels.return_value = []
    connection_controller = MagicMock()
    settings_manager = MagicMock()
    settings_manager.get.return_value = 2000
    port_scan_manager = MagicMock()
    presenter = PortPresenter(
        left_section,
        connection_controller,
        settings_manager,
        port_scan_manager,
    )
    port_scan_manager.request_scan.reset_mock()

    presenter.scan_ports()

    port_scan_manager.request_scan.assert_called_once()
