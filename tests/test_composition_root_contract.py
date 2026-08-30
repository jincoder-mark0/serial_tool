"""Production composition root / dependency injection 회귀 테스트."""
import inspect

import main
from application_bootstrap import ApplicationBootstrapper
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.main_presenter import MainPresenter
from presenter.port_presenter import PortPresenter


def test_main_builds_and_injects_runtime_components():
    source = inspect.getsource(main.main)

    assert "settings_mgr = SettingsManager(resource_path)" in source
    assert "ApplicationBootstrapper(window, settings_mgr).build()" in source
    assert "settings_manager=settings_mgr" in source
    assert "components=components" in source


def test_bootstrapper_is_the_concrete_object_graph_owner():
    source = inspect.getsource(ApplicationBootstrapper.build)

    assert "ConnectionController()" in source
    assert "CommandTransmissionService(" in source
    assert "FileTransferManager(" in source
    assert "PortScanManager()" in source
    assert "MacroRunner()" in source
    assert "PortPresenter(" in source
    assert "port_scan_manager," in source
    assert "FilePresenter(file_transfer_manager)" in source
    assert "PacketPresenter(" in source
    assert "ManualControlPresenter(" in source


def test_main_presenter_does_not_construct_concrete_model_or_sub_presenter():
    source = inspect.getsource(MainPresenter)

    assert "ConnectionController()" not in source
    assert "CommandTransmissionService(" not in source
    assert "FileTransferManager(" not in source
    assert "PortScanManager()" not in source
    assert "MacroRunner()" not in source
    assert "PortPresenter(" not in source
    assert "FilePresenter(" not in source
    assert "PacketPresenter(" not in source
    assert "ManualControlPresenter(" not in source
    assert "ApplicationBootstrapper(" in source  # compatibility fallback only
    assert "self._apply_components(runtime)" in source
    assert "self.port_scan_manager = components.port_scan_manager" in source


def test_lifecycle_does_not_own_or_call_main_presenter():
    source = inspect.getsource(AppLifecycleManager)
    assert "main_presenter" not in source
    assert "self.mp" not in source
    assert "_init_core_systems" not in source
    assert "_init_sub_presenters" not in source
    assert "_connect_signals" not in source


def test_port_presenter_uses_injected_settings_for_packet_configuration():
    source = inspect.getsource(PortPresenter._apply_packet_parser_settings)
    assert "settings = self.settings_manager" in source
    assert "SettingsManager()" not in source
