"""리팩토링으로 확립한 상태 소유권/수평 의존 경계를 고정합니다."""
import inspect

from application_bootstrap import ApplicationBootstrapper
from presenter.control_state_coordinator import ControlStateCoordinator
from presenter.macro_execution_coordinator import MacroExecutionCoordinator
from presenter.main_presenter import MainPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.port_presenter import PortPresenter
from presenter.settings_coordinator import SettingsCoordinator
from presenter.shutdown_coordinator import ShutdownCoordinator
from view.main_window import MainWindow
from view.sections.main_left_section import MainLeftSection


def test_manual_control_enabled_policy_is_not_owned_by_view_or_main_presenter():
    view_source = inspect.getsource(MainLeftSection)
    main_source = inspect.getsource(MainPresenter)
    coordinator_source = inspect.getsource(ControlStateCoordinator)

    assert "_sync_manual_control_state" not in view_source
    assert "set_controls_enabled(" not in view_source
    assert "_update_controls_state_for_current_tab" not in main_source
    assert "manual_control_presenter.set_enabled" not in main_source
    assert "macro_presenter.set_enabled" not in main_source

    assert "is_current_port_connected()" in coordinator_source
    assert "has_active_connection" in coordinator_source
    assert "_manual_presenter.set_enabled" in coordinator_source
    assert "_macro_presenter.set_enabled" in coordinator_source


def test_macro_transmission_policy_is_not_owned_by_main_presenter():
    source = inspect.getsource(MainPresenter)

    assert "_macro_target_port" not in source
    assert "deliver_macro_command" not in source
    assert "on_macro_send_requested" not in source
    assert "set_send_handler" not in source
    assert "send_requested.connect" not in source


def test_macro_execution_coordinator_owns_target_snapshot_and_send_handler():
    source = inspect.getsource(MacroExecutionCoordinator)

    assert "_target_port" in source
    assert "_port_view.get_current_port_name()" in source
    assert "set_send_handler(self.deliver_repeated_command)" in source
    assert "send_requested.connect(self.on_single_send_requested)" in source
    assert "connection_closed.connect(self.on_connection_closed)" in source


def test_manual_presenter_has_no_cross_presenter_or_view_callbacks():
    source = inspect.getsource(ManualControlPresenter)

    assert "local_echo_callback" not in source
    assert "get_active_port_callback" not in source
    assert "local_echo_requested = pyqtSignal(bytes)" in source
    assert "self.port_view.get_current_port_name()" in source


def test_bootstrapper_wires_local_echo_and_policy_coordinators_explicitly():
    source = inspect.getsource(ApplicationBootstrapper.build)

    assert "manual_control_presenter.local_echo_requested.connect" in source
    assert "macro_execution_coordinator.local_echo_requested.connect" in source
    assert "self._view.append_local_echo_data" in source
    assert "SettingsCoordinator(" in source
    assert "ControlStateCoordinator(" in source


def test_shutdown_coordinator_does_not_depend_on_port_presenter():
    source = inspect.getsource(ShutdownCoordinator)

    assert "PortPresenter" not in source
    assert "port_presenter" not in source
    assert "port_scan_manager" in source
    assert "self._port_scan_manager.stop()" in source


def test_port_presenter_requires_injected_scan_and_settings_dependencies():
    source = inspect.getsource(PortPresenter)
    signature = inspect.signature(PortPresenter.__init__)

    assert "PortScanWorker" not in source
    assert "_scan_worker" not in source
    assert "PortScanManager()" not in source
    assert "SettingsManager()" not in source
    assert signature.parameters["settings_manager"].default is inspect.Parameter.empty
    assert signature.parameters["port_scan_manager"].default is inspect.Parameter.empty


def test_main_window_routes_model_affecting_menu_commands_to_request_signals():
    source = inspect.getsource(MainWindow._connect_menu_signals)

    assert "connect_requested.connect(self.shortcut_connect_requested.emit)" in source
    assert "theme_changed.connect(self.theme_change_requested.emit)" in source
    assert "language_changed.connect(self.language_change_requested.emit)" in source

    assert "left_section.open_current_port" not in source
    assert "theme_changed.connect(self.switch_theme)" not in source
    assert "language_manager.set_language" not in source


def test_settings_coordinator_owns_theme_and_language_persistence():
    main_source = inspect.getsource(MainPresenter)
    theme_source = inspect.getsource(SettingsCoordinator.apply_theme)
    language_source = inspect.getsource(SettingsCoordinator.apply_language)

    assert "ConfigKeys.THEME" not in main_source
    assert "ConfigKeys.LANGUAGE" not in main_source
    assert "SettingsManager" not in main_source

    assert "ConfigKeys.THEME" in theme_source
    assert "_settings.save_settings()" in theme_source
    assert "_view.switch_theme" in theme_source

    assert "ConfigKeys.LANGUAGE" in language_source
    assert "_settings.save_settings()" in language_source
    assert "language_manager.set_language" in language_source
