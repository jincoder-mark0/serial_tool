"""
MainPresenter 초기화/배선 회귀 테스트.

EventRouter 제거 후 핵심 Model/Service/Presenter가 생성되고 View와 직접 signal로
연결되는 composition 계약을 검증합니다.
"""
from unittest.mock import MagicMock, patch

import pytest

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
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.port_tab_added = MagicMock()
    view.get_port_tabs_count.return_value = 0
    return view


class TestMainPresenterInit:
    def test_component_creation(self, mock_main_window, mock_settings_manager):
        presenter = MainPresenter(
            mock_main_window,
            settings_manager=mock_settings_manager,
        )

        assert presenter.connection_controller is not None
        assert presenter.command_transmission_service is not None
        assert presenter.macro_runner is not None
        assert presenter.data_handler is not None
        assert not hasattr(presenter, "event_router")

        assert presenter.port_presenter is not None
        assert presenter.macro_presenter is not None
        assert presenter.file_presenter is not None
        assert presenter.packet_presenter is not None
        assert presenter.manual_control_presenter is not None
        assert presenter.lifecycle_manager is not None
        assert presenter.shutdown_coordinator is not None

    def test_lifecycle_has_no_reverse_main_presenter_orchestration(
        self, mock_main_window, mock_settings_manager
    ):
        with patch("presenter.main_presenter.AppLifecycleManager") as lifecycle_cls:
            lifecycle = lifecycle_cls.return_value
            lifecycle.create_manual_control_state.return_value = MagicMock()
            lifecycle.create_status_timer.return_value = MagicMock()

            MainPresenter(
                mock_main_window,
                settings_manager=mock_settings_manager,
            )

        lifecycle_cls.assert_called_once_with(
            mock_main_window,
            mock_settings_manager,
        )
        lifecycle.initialize_view.assert_called_once()
        lifecycle.create_manual_control_state.assert_called_once()
        lifecycle.create_status_timer.assert_called_once()
        lifecycle.log_initialized.assert_called_once()
        assert not hasattr(lifecycle, "initialize_app") or not lifecycle.initialize_app.called

    def test_signal_connections(self, mock_main_window, mock_settings_manager):
        presenter = MainPresenter(
            mock_main_window,
            settings_manager=mock_settings_manager,
        )

        mock_main_window.close_requested.connect.assert_called()
        mock_main_window.settings_save_requested.connect.assert_called()
        mock_main_window.connect_port_tab_changed.assert_called()

        assert presenter.connection_controller.connection_opened is not None
        assert presenter.connection_controller.data_received is not None
        assert presenter.macro_runner.macro_started is not None
        assert presenter.file_presenter.transfer_completed is not None

    def test_data_handler_init(self, mock_main_window, mock_settings_manager):
        with patch("presenter.data_handler.QTimer") as timer_cls:
            presenter = MainPresenter(
                mock_main_window,
                settings_manager=mock_settings_manager,
            )

        assert presenter.data_handler.view == mock_main_window
        timer_cls.return_value.start.assert_called()
