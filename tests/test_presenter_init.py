"""MainPresenter 초기화/배선 회귀 테스트."""
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
    return view


def _build_presenter(view, settings):
    components = ApplicationBootstrapper(view, settings).build()
    return MainPresenter(view, dependencies=components.main_presenter_dependencies)


class TestMainPresenterInit:
    def test_component_injection(self, mock_main_window, mock_settings_manager):
        presenter = _build_presenter(mock_main_window, mock_settings_manager)
        for attr in (
            "connection_controller",
            "macro_runner",
            "macro_execution_coordinator",
            "logging_coordinator",
            "shutdown_coordinator",
            "port_presenter",
            "file_presenter",
            "manual_control_presenter",
        ):
            assert getattr(presenter, attr) is not None
        for internal_owner in (
            "event_router",
            "settings_manager",
            "lifecycle_manager",
            "data_handler",
            "file_transfer_manager",
            "port_scan_manager",
            "macro_script_manager",
            "traffic_monitor",
            "status_coordinator",
            "settings_coordinator",
            "control_state_coordinator",
            "macro_presenter",
            "packet_presenter",
        ):
            assert not hasattr(presenter, internal_owner)

    def test_bootstrapper_restores_view_and_manual_state_before_control_policy(self):
        source = inspect.getsource(ApplicationBootstrapper.build)
        restore_pos = source.index("lifecycle_manager.initialize_view()")
        manual_apply_pos = source.index("manual_control_presenter.apply_state(")
        control_pos = source.index("control_state_coordinator = ControlStateCoordinator(")

        assert restore_pos < manual_apply_pos < control_pos
        assert restore_pos < source.index("port_presenter = PortPresenter(")
        assert restore_pos < source.index("macro_presenter = MacroPresenter(")

    def test_main_presenter_owns_only_presenter_dependency_contract(self):
        source = inspect.getsource(MainPresenter)
        signature = inspect.signature(MainPresenter.__init__)
        assert "ApplicationBootstrapper" not in source
        assert "ApplicationComponents" not in source
        assert "SettingsManager" not in source
        assert "AppLifecycleManager" not in source
        assert "MainPresenterDependencies" in source
        assert set(signature.parameters) == {"self", "view", "dependencies"}

    def test_signal_connections(self, mock_main_window, mock_settings_manager):
        presenter = _build_presenter(mock_main_window, mock_settings_manager)
        # Settings/control-state 관련 signal은 전용 coordinator가 연결합니다.
        mock_main_window.settings_save_requested.connect.assert_called()
        mock_main_window.theme_change_requested.connect.assert_called()
        mock_main_window.language_change_requested.connect.assert_called()
        mock_main_window.close_requested.connect.assert_called()
        assert presenter.connection_controller.connection_opened is not None
        assert presenter.macro_runner.macro_started is not None

    def test_bootstrapper_owns_data_handler_and_static_wiring(
        self, mock_main_window, mock_settings_manager
    ):
        with patch("presenter.data_handler.QTimer") as timer_cls:
            ApplicationBootstrapper(mock_main_window, mock_settings_manager).build()
        timer_cls.return_value.start.assert_called()
        source = inspect.getsource(ApplicationBootstrapper.build)
        assert "connection_controller.data_received.connect(data_handler.on_fast_data_received)" in source
        assert "connection_controller.data_sent.connect(data_handler.on_data_sent)" in source
        assert "connection_controller.data_received.connect(macro_runner.on_data_received)" in source
        assert "ControlStateCoordinator(" in source
