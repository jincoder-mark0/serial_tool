"""리팩토링으로 확립한 상태 소유권/수평 의존 경계를 고정합니다."""
import inspect

from application_bootstrap import ApplicationBootstrapper
from presenter.main_presenter import MainPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.port_presenter import PortPresenter
from presenter.shutdown_coordinator import ShutdownCoordinator
from view.sections.main_left_section import MainLeftSection


def test_manual_control_enabled_policy_is_not_owned_by_view():
    view_source = inspect.getsource(MainLeftSection)
    presenter_source = inspect.getsource(
        MainPresenter._update_controls_state_for_current_tab
    )

    assert "_sync_manual_control_state" not in view_source
    assert "set_controls_enabled(" not in view_source
    assert "manual_control_presenter.set_enabled" in presenter_source
    assert "macro_presenter.set_enabled" in presenter_source
    assert "has_any_connection" in presenter_source


def test_macro_port_lookup_does_not_depend_on_port_presenter():
    started_source = inspect.getsource(MainPresenter.on_macro_started)
    single_source = inspect.getsource(MainPresenter.on_macro_send_requested)

    for source in (started_source, single_source):
        assert "port_presenter.get_active_port_name" not in source
        assert "view.port_view.get_current_port_name" in source


def test_manual_presenter_has_no_cross_presenter_or_view_callbacks():
    source = inspect.getsource(ManualControlPresenter)

    assert "local_echo_callback" not in source
    assert "get_active_port_callback" not in source
    assert "local_echo_requested = pyqtSignal(bytes)" in source
    assert "self.port_view.get_current_port_name()" in source


def test_bootstrapper_wires_local_echo_signal_explicitly():
    source = inspect.getsource(ApplicationBootstrapper.build)

    assert "manual_control_presenter.local_echo_requested.connect" in source
    assert "self._view.append_local_echo_data" in source


def test_shutdown_coordinator_does_not_depend_on_port_presenter():
    source = inspect.getsource(ShutdownCoordinator)

    assert "PortPresenter" not in source
    assert "port_presenter" not in source
    assert "port_scan_manager" in source
    assert "self._port_scan_manager.stop()" in source


def test_port_presenter_does_not_own_qthread_scan_worker():
    source = inspect.getsource(PortPresenter)

    assert "PortScanWorker" not in source
    assert "_scan_worker" not in source
    assert "port_scan_manager.request_scan()" in source
