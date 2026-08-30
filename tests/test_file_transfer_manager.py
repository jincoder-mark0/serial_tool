"""FileTransferManager / FilePresenter 구조 회귀 테스트."""
import inspect
from unittest.mock import MagicMock, patch

from common.dtos import FileCompletionEvent, FileProgressState, PortConfig
from model.file_transfer_manager import FileTransferManager
from presenter.file_presenter import FilePresenter


def _controller(opened: bool = True, config: PortConfig | None = None):
    controller = MagicMock()
    controller.is_connection_open.return_value = opened
    controller.get_connection_config.return_value = config or PortConfig(port="COM1")
    return controller


def test_file_presenter_does_not_create_or_schedule_transfer_engine():
    source = inspect.getsource(FilePresenter)

    assert "FileTransferService" not in source
    assert "QThreadPool" not in source
    assert "ConnectionController" not in source
    assert "transfer_manager.start_transfer" in source
    assert "transfer_manager.cancel_transfer" in source


def test_manager_rejects_missing_target_before_service_creation():
    controller = _controller()
    thread_pool = MagicMock()
    manager = FileTransferManager(controller, thread_pool)
    errors = []
    manager.error_occurred.connect(errors.append)

    assert manager.start_transfer("a.bin", "") is False
    assert len(errors) == 1
    assert "target port" in errors[0].message.lower()
    thread_pool.start.assert_not_called()


def test_manager_rejects_disconnected_target():
    controller = _controller(opened=False)
    thread_pool = MagicMock()
    manager = FileTransferManager(controller, thread_pool)
    errors = []
    manager.error_occurred.connect(errors.append)

    assert manager.start_transfer("a.bin", "COM1") is False
    assert len(errors) == 1
    assert "disconnected" in errors[0].message.lower()
    thread_pool.start.assert_not_called()


def test_manager_creates_and_schedules_service_once():
    config = PortConfig(port="COM1")
    controller = _controller(config=config)
    thread_pool = MagicMock()
    manager = FileTransferManager(controller, thread_pool)

    service = MagicMock()
    service.signals.progress_updated = MagicMock()
    service.signals.transfer_completed = MagicMock()
    service.signals.error_occurred = MagicMock()

    with patch(
        "model.file_transfer_manager.FileTransferService",
        return_value=service,
    ) as service_cls:
        assert manager.start_transfer("a.bin", "COM1") is True

    service_cls.assert_called_once_with(controller, "a.bin", config)
    thread_pool.start.assert_called_once_with(service)
    assert manager.is_active is True

    assert manager.start_transfer("b.bin", "COM1") is False
    assert service_cls.call_count == 1


def test_cancel_is_delegated_to_active_service():
    controller = _controller()
    manager = FileTransferManager(controller, MagicMock())
    service = MagicMock()
    manager._active_service = service

    manager.cancel_transfer()

    service.cancel.assert_called_once()


def test_shutdown_cancels_then_waits_for_owned_pool():
    thread_pool = MagicMock()
    manager = FileTransferManager(_controller(), thread_pool)
    service = MagicMock()
    manager._active_service = service
    order = []
    service.cancel.side_effect = lambda: order.append("cancel")
    thread_pool.waitForDone.side_effect = lambda: order.append("wait")

    manager.shutdown()

    assert order == ["cancel", "wait"]
    assert manager.is_active is False


def test_default_manager_owns_a_non_global_thread_pool(qapp):
    manager = FileTransferManager(_controller())

    # 전용 pool이어야 shutdown()이 다른 기능의 QRunnable을 기다리지 않습니다.
    from PyQt5.QtCore import QThreadPool

    assert manager._thread_pool is not QThreadPool.globalInstance()


def test_completion_releases_service_before_reemitting():
    manager = FileTransferManager(_controller(), MagicMock())
    manager._active_service = MagicMock()
    observed = []
    manager.transfer_completed.connect(
        lambda event: observed.append((manager.is_active, event.success))
    )

    manager._on_completed(
        FileCompletionEvent(success=True, message="done", file_path="a.bin")
    )

    assert observed == [(False, True)]


def test_progress_speed_and_eta_are_calculated_by_manager():
    manager = FileTransferManager(_controller(), MagicMock())
    manager._start_monotonic = 10.0
    states = []
    manager.progress_updated.connect(states.append)
    state = FileProgressState(sent_bytes=500, total_bytes=1000)

    with patch("model.file_transfer_manager.time.monotonic", return_value=12.0):
        manager._on_progress(state)

    assert state.speed == 250.0
    assert state.eta == 2.0
    assert states == [state]
