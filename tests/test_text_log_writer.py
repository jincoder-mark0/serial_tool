"""
TextLogWriter, SystemLogWidget, LoggingCoordinator의 실제 시스템 로그 파일 기록을 검증합니다.

시스템 로그 저장 구현은 MainPresenter가 아니라 LoggingCoordinator가 소유하므로 테스트도
해당 public API를 직접 사용합니다. 앱 종료 시 writer close 연동만 MainPresenter의 실제
shutdown 경로를 통해 확인합니다.
"""
from unittest.mock import MagicMock, patch

import pytest

from application_bootstrap import ApplicationBootstrapper
from common.dtos import MainWindowState, SystemLogEvent
from core.text_log_writer import TextLogWriter
from presenter.main_presenter import MainPresenter
from view.widgets.system_log import SystemLogWidget


class TestTextLogWriter:
    def test_write_line_appends_to_real_file(self, tmp_path):
        file_path = tmp_path / "syslog.txt"
        writer = TextLogWriter()
        writer.open(str(file_path))
        writer.write_line("first line")
        writer.write_line("second line")
        writer.close()
        assert file_path.read_text(encoding="utf-8") == "first line\nsecond line\n"

    def test_write_line_appends_across_open_sessions(self, tmp_path):
        file_path = tmp_path / "syslog.txt"
        writer = TextLogWriter()
        writer.open(str(file_path))
        writer.write_line("session 1")
        writer.close()
        writer2 = TextLogWriter()
        writer2.open(str(file_path))
        writer2.write_line("session 2")
        writer2.close()
        assert file_path.read_text(encoding="utf-8") == "session 1\nsession 2\n"

    def test_write_line_before_open_raises_oserror(self):
        with pytest.raises(OSError):
            TextLogWriter().write_line("should fail")

    def test_open_creates_missing_parent_directory(self, tmp_path):
        file_path = tmp_path / "nested" / "dir" / "syslog.txt"
        writer = TextLogWriter()
        writer.open(str(file_path))
        writer.write_line("line")
        writer.close()
        assert file_path.read_text(encoding="utf-8") == "line\n"

    def test_is_open_reflects_state(self, tmp_path):
        writer = TextLogWriter()
        assert writer.is_open is False
        writer.open(str(tmp_path / "syslog.txt"))
        assert writer.is_open is True
        writer.close()
        assert writer.is_open is False

    def test_close_is_idempotent(self, tmp_path):
        writer = TextLogWriter()
        writer.open(str(tmp_path / "syslog.txt"))
        writer.close()
        writer.close()

    def test_reopen_closes_previous_file_handle(self, tmp_path):
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        writer = TextLogWriter()
        writer.open(str(file_a))
        writer.write_line("in a")
        writer.open(str(file_b))
        writer.write_line("in b")
        writer.close()
        assert file_a.read_text(encoding="utf-8") == "in a\n"
        assert file_b.read_text(encoding="utf-8") == "in b\n"
        assert writer.file_path == ""


class TestSystemLogWidgetLineAppendedSignal:
    def test_append_log_emits_plain_text_without_html(self, qapp, qtbot):
        widget = SystemLogWidget()
        widget.set_color_rules([])
        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True) as blocker:
            widget.append_log(SystemLogEvent(message="hello world", level="INFO"))
        emitted_text = blocker.args[0]
        assert "[INFO] hello world" in emitted_text
        assert "<" not in emitted_text

    def test_filter_disabled_emits_every_line(self, qapp, qtbot):
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("NOMATCH")
        widget.filter_enabled = False
        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True):
            widget.append_log(SystemLogEvent(message="does not contain the word", level="INFO"))

    def test_filter_enabled_blocks_non_matching_line(self, qapp):
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("TARGET")
        widget.filter_enabled = True
        received = []
        widget.system_log_line_appended.connect(received.append)
        widget.append_log(SystemLogEvent(message="no match here", level="INFO"))
        qapp.processEvents()
        assert received == []

    def test_filter_enabled_allows_matching_line(self, qapp, qtbot):
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("TARGET")
        widget.filter_enabled = True
        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True) as blocker:
            widget.append_log(SystemLogEvent(message="this has TARGET inside", level="INFO"))
        assert "TARGET" in blocker.args[0]


@pytest.fixture
def mock_main_window():
    view = MagicMock()
    view.left_section = MagicMock()
    view.right_section = MagicMock()
    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()
    view.left_section.manual_control_panel = MagicMock()
    view.left_section.system_log_widget = MagicMock()
    view.right_section.packet_panel = MagicMock()
    view.macro_view = MagicMock()
    view.port_view = MagicMock()
    view.manual_control_view = MagicMock()
    view.manual_control_view.get_input_text.return_value = ""
    view.manual_control_view.is_hex_mode.return_value = False
    view.manual_control_view.is_prefix_enabled.return_value = False
    view.manual_control_view.is_suffix_enabled.return_value = False
    view.manual_control_view.is_rts_enabled.return_value = False
    view.manual_control_view.is_dtr_enabled.return_value = False
    view.manual_control_view.is_broadcast_enabled.return_value = False
    view.settings_save_requested = MagicMock()
    view.font_settings_changed = MagicMock()
    view.theme_change_requested = MagicMock()
    view.language_change_requested = MagicMock()
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.get_window_state.return_value = MainWindowState(left_section_state={}, right_section_state={})
    return view


@pytest.fixture
def presenter_and_components(mock_main_window, mock_settings_manager):
    components = ApplicationBootstrapper(mock_main_window, mock_settings_manager).build()
    presenter = MainPresenter(
        mock_main_window,
        settings_manager=mock_settings_manager,
        dependencies=components.main_presenter_dependencies,
    )
    yield presenter, components
    components.status_coordinator.stop()
    components.file_transfer_manager.shutdown()
    components.macro_script_manager.stop()
    components.port_scan_manager.stop()
    components.connection_controller.close_connection()


class TestSystemLogPersistenceIntegration:
    @staticmethod
    def _coordinator(components):
        return components.main_presenter_dependencies.logging_coordinator

    def test_start_line_stop_writes_and_closes_real_file(self, presenter_and_components, tmp_path):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)
        coordinator.on_system_logging_start_requested()
        assert coordinator.system_log_writer is not None and coordinator.system_log_writer.is_open
        coordinator.on_system_log_line_appended("[12:00:00] [INFO] hello")
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] hello\n"
        coordinator.on_system_logging_stop_requested()
        assert coordinator.system_log_writer is None
        coordinator.on_system_log_line_appended("[12:00:01] [INFO] should not be written")
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] hello\n"

    def test_open_failure_surfaces_error_and_leaves_recording_off(self, presenter_and_components, tmp_path):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        blocking_file = tmp_path / "not_a_dir"
        blocking_file.write_text("x", encoding="utf-8")
        presenter.view.port_view.show_save_log_dialog.return_value = str(blocking_file / "system_log.txt")
        coordinator.on_system_logging_start_requested()
        assert coordinator.system_log_writer is None
        presenter.view.port_view.set_logging_active.assert_any_call(False)
        assert any(call.args[0].level == "ERROR" for call in presenter.view.log_system_message.call_args_list)

    def test_write_failure_stops_recording_and_surfaces_error(self, presenter_and_components, tmp_path):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)
        coordinator.on_system_logging_start_requested()
        writer = coordinator.system_log_writer
        assert writer is not None
        with patch.object(writer, "write_line", side_effect=OSError("disk full")):
            coordinator.on_system_log_line_appended("[12:00:00] [INFO] boom")
        assert coordinator.system_log_writer is None
        presenter.view.port_view.set_logging_active.assert_called_with(False)
        assert any(call.args[0].level == "ERROR" for call in presenter.view.log_system_message.call_args_list)

    def test_cancel_dialog_does_not_create_writer(self, presenter_and_components):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        presenter.view.port_view.show_save_log_dialog.return_value = ""
        coordinator.on_system_logging_start_requested()
        assert coordinator.system_log_writer is None

    def test_app_shutdown_closes_open_writer_without_data_loss(self, presenter_and_components, tmp_path):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)
        coordinator.on_system_logging_start_requested()
        coordinator.on_system_log_line_appended("[12:00:00] [INFO] before shutdown")
        writer = coordinator.system_log_writer
        assert writer is not None and writer.is_open
        presenter.on_close_requested()
        assert coordinator.system_log_writer is None
        assert writer.is_open is False
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] before shutdown\n"

    def test_app_shutdown_without_active_recording_does_not_raise(self, presenter_and_components):
        presenter, components = presenter_and_components
        coordinator = self._coordinator(components)
        assert coordinator.system_log_writer is None
        presenter.on_close_requested()
        assert coordinator.system_log_writer is None
