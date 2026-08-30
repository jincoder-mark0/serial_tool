"""
MainPresenter 초기화/배선 회귀 테스트.

Production과 동일하게 ApplicationBootstrapper가 View state를 먼저 복원하고 runtime
component를 조립한 뒤 MainPresenter에는 완성된 graph를 명시적으로 주입합니다.
"""
import inspect
from unittest.mock import MagicMock, patch

import pytest

from application_bootstrap import ApplicationBootstrapper
from presenter.main_presenter import MainPresenter
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.packet_panel import PacketPanel
from view.widgets.system_log import SystemLogWidget


@pytest.fixture
def mock_main_window():
    view = MagicMock()
    view.left_section = MagicMock()
    view.right_section = MagicMock()

    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()
    view.left_section.manual_control_panel = MagicMock(spec=ManualControlPanel)
    view.left_section.system_log_widget = MagicMock(spec=SystemLogWidget)
    view.right_section.packet_panel = MagicMock(spec=PacketPanel)

    view.manual_control_view = view.left_section.manual_control_panel
    view.packet_view = view.right_section.packet_panel
    view.macro_view = MagicMock()
    view.port_view = MagicMock()

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
    view.get_port_tabs_count.return_value = 0
    return view


def _build_presenter(view, settings):
    components = ApplicationBootstrapper(view, settings).build()
    return MainPresenter(
        view,
        settings_manager=settings,
        components=components,
    )


class TestMainPresenterInit:
    def test_component_injection(self, mock_main_window, mock_settings_manager):
        presenter = _build_presenter(mock_main_window, mock_settings_manager)

        assert presenter.connection_controller is not None
        assert presenter.macro_runner is not None
        assert presenter.macro_execution_coordinator is not None
        assert presenter.data_handler is not None
        assert presenter.logging_coordinator is not None
        assert presenter.shutdown_coordinator is not None
        assert not hasattr(presenter, "event_router")

        assert presenter.port_presenter is not None
        assert presenter.macro_presenter is not None
        assert presenter.file_presenter is not None
        assert presenter.packet_presenter is not None
        assert presenter.manual_control_presenter is not None
        assert presenter.lifecycle_manager is not None

        # 내부 lifecycle owner를 MainPresenter 서비스 locator처럼 노출하지 않습니다.
        assert not hasattr(presenter, "file_transfer_manager")
        assert not hasattr(presenter, "port_scan_manager")
        assert not hasattr(presenter, "macro_script_manager")
        assert not hasattr(presenter, "traffic_monitor")
        assert not hasattr(presenter, "status_coordinator")

    def test_bootstrapper_restores_view_before_presenter_construction(self):
        source = inspect.getsource(ApplicationBootstrapper.build)

        restore_pos = source.index("lifecycle_manager.initialize_view()")
        port_presenter_pos = source.index("port_presenter = PortPresenter(")
        macro_presenter_pos = source.index("macro_presenter = MacroPresenter(")

        assert restore_pos < port_presenter_pos
        assert restore_pos < macro_presenter_pos
        assert "AppLifecycleManager(" in source

    def test_main_presenter_does_not_create_or_initialize_lifecycle_manager(self):
        source = inspect.getsource(MainPresenter)

        assert "AppLifecycleManager(" not in source
        assert "initialize_view()" not in source
        assert "components.lifecycle_manager" in source

    def test_signal_connections(self, mock_main_window, mock_settings_manager):
        presenter = _build_presenter(mock_main_window, mock_settings_manager)

        mock_main_window.close_requested.connect.assert_called()
        mock_main_window.settings_save_requested.connect.assert_called()
        mock_main_window.theme_change_requested.connect.assert_called()
        mock_main_window.language_change_requested.connect.assert_called()
        mock_main_window.connect_port_tab_changed.assert_called()

        assert presenter.connection_controller.connection_opened is not None
        assert presenter.connection_controller.data_received is not None
        assert presenter.macro_runner.macro_started is not None
        assert presenter.file_presenter.transfer_completed is not None

    def test_data_handler_init(self, mock_main_window, mock_settings_manager):
        with patch("presenter.data_handler.QTimer") as timer_cls:
            presenter = _build_presenter(mock_main_window, mock_settings_manager)

        assert presenter.data_handler.view == mock_main_window
        timer_cls.return_value.start.assert_called()
