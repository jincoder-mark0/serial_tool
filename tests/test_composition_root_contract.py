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

    for constructor in (
        "PacketParserManager()",
        "ConnectionSessionFactory()",
        "ConnectionController(",
        "CommandTransmissionService(",
        "FileTransferManager(",
        "PortScanManager()",
        "MacroRunner()",
        "MacroScriptManager()",
        "MacroExecutionCoordinator(",
        "TrafficMonitor()",
        "LoggingCoordinator(",
        "PortPresenter(",
        "MacroPresenter(",
        "FilePresenter(",
        "PacketPresenter(",
        "ManualControlPresenter(",
    ):
        assert constructor in source

    assert "DataTrafficHandler(self._view, traffic_monitor)" in source
    assert "packet_parser_manager," in source
    assert "connection_session_factory," in source
    assert "port_scan_manager," in source
    assert "macro_script_manager," in source


def test_main_presenter_does_not_construct_concrete_runtime_components():
    source = inspect.getsource(MainPresenter)

    for constructor in (
        "ConnectionController(",
        "PacketParserManager(",
        "ConnectionSessionFactory(",
        "CommandTransmissionService(",
        "FileTransferManager(",
        "PortScanManager(",
        "MacroRunner(",
        "MacroScriptManager(",
        "MacroExecutionCoordinator(",
        "TrafficMonitor(",
        "LoggingCoordinator(",
        "PortPresenter(",
        "MacroPresenter(",
        "FilePresenter(",
        "PacketPresenter(",
        "ManualControlPresenter(",
    ):
        assert constructor not in source

    assert "ApplicationBootstrapper(" in source  # 남은 test compatibility fallback
    assert "self._apply_components(runtime)" in source
    assert "self.logging_coordinator = components.logging_coordinator" in source
    assert "self.port_scan_manager = components.port_scan_manager" in source
    assert "self.macro_script_manager = components.macro_script_manager" in source
    assert "self.traffic_monitor = components.traffic_monitor" in source


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
