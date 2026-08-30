"""LoggingCoordinator 구조/생명주기 회귀 테스트."""
import inspect
from unittest.mock import MagicMock, patch

from common.enums import LogFormat
from presenter.logging_coordinator import LoggingCoordinator
from presenter.main_presenter import MainPresenter


def _make_coordinator():
    port_view = MagicMock()
    port_view.get_port_panels.return_value = []
    log_info = MagicMock()
    log_error = MagicMock()
    coordinator = LoggingCoordinator(port_view, log_info, log_error)
    return coordinator, port_view, log_info, log_error


def test_main_presenter_delegates_logging_implementation():
    source = inspect.getsource(MainPresenter)

    assert "LoggingCoordinator(" in source
    assert "data_logger_manager" not in source
    assert "TextLogWriter" not in source
    assert "LoggingFormatResolver" not in source
    assert "self.logging_coordinator.on_port_logging_start_requested" in source
    assert "self.logging_coordinator.close_system_log" in source


def test_connect_port_panel_does_not_disconnect_other_listeners():
    coordinator, _, _, _ = _make_coordinator()
    panel = MagicMock()

    coordinator.connect_port_panel(panel)
    coordinator.connect_port_panel(panel)

    # coordinator 중복 연결만 자체 추적으로 막고 signal 전체 disconnect는 호출하지 않는다.
    panel.logging_start_requested.disconnect.assert_not_called()
    panel.logging_stop_requested.disconnect.assert_not_called()
    panel.logging_start_requested.connect.assert_called_once()
    panel.logging_stop_requested.connect.assert_called_once()


def test_port_logging_start_and_stop_use_data_logger_manager():
    coordinator, _, log_info, _ = _make_coordinator()
    panel = MagicMock()
    panel.show_save_log_dialog.return_value = "capture.bin"
    panel.get_port_name.return_value = "COM1"

    with patch(
        "presenter.logging_coordinator.LoggingFormatResolver.resolve",
        return_value=LogFormat.BIN,
    ), patch(
        "presenter.logging_coordinator.data_logger_manager.start_logging",
        return_value=True,
    ) as start, patch(
        "presenter.logging_coordinator.data_logger_manager.stop_logging"
    ) as stop:
        coordinator.on_port_logging_start_requested(panel)
        coordinator.on_port_logging_stop_requested(panel)

    start.assert_called_once_with("COM1", "capture.bin", LogFormat.BIN)
    stop.assert_called_once_with("COM1")
    panel.set_logging_active.assert_any_call(True)
    panel.set_logging_active.assert_any_call(False)
    assert log_info.call_count == 2


def test_system_log_writer_lifecycle_uses_real_file(tmp_path):
    coordinator, port_view, log_info, _ = _make_coordinator()
    file_path = tmp_path / "system.log"
    port_view.show_save_log_dialog.return_value = str(file_path)

    coordinator.on_system_logging_start_requested()
    assert coordinator._system_log_writer is not None
    assert coordinator._system_log_writer.is_open is True

    coordinator.on_system_log_line_appended("line one")
    coordinator.on_system_logging_stop_requested()

    assert coordinator._system_log_writer is None
    assert file_path.read_text(encoding="utf-8") == "line one\n"
    port_view.set_logging_active.assert_any_call(True)
    port_view.set_logging_active.assert_any_call(False)
    assert log_info.call_count == 2


def test_system_log_write_failure_closes_writer_before_reporting(tmp_path):
    coordinator, port_view, _, log_error = _make_coordinator()
    file_path = tmp_path / "system.log"
    port_view.show_save_log_dialog.return_value = str(file_path)
    coordinator.on_system_logging_start_requested()

    writer = coordinator._system_log_writer
    assert writer is not None

    with patch.object(writer, "write_line", side_effect=OSError("disk full")):
        coordinator.on_system_log_line_appended("lost")

    assert coordinator._system_log_writer is None
    port_view.set_logging_active.assert_called_with(False)
    log_error.assert_called_once()
