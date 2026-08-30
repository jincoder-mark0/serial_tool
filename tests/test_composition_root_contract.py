"""Production composition root / dependency injection 회귀 테스트."""
import inspect

import main
from application_bootstrap import ApplicationBootstrapper
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.main_presenter import MainPresenter, MainPresenterDependencies
from presenter.port_presenter import PortPresenter


def test_main_builds_and_injects_presenter_dependency_contract():
    source = inspect.getsource(main.main)
    assert "settings_mgr = SettingsManager(resource_path)" in source
    assert "ApplicationBootstrapper(window, settings_mgr).build()" in source
    assert "dependencies=components.main_presenter_dependencies" in source
    assert "settings_manager=settings_mgr" not in source


def test_bootstrapper_is_the_concrete_object_graph_owner():
    source = inspect.getsource(ApplicationBootstrapper.build)
    for constructor in (
        "AppLifecycleManager(",
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
        "SettingsCoordinator(",
        "ControlStateCoordinator(",
        "StatusCoordinator(",
        "ShutdownCoordinator(",
        "PortPresenter(",
        "MacroPresenter(",
        "FilePresenter(",
        "PacketPresenter(",
        "ManualControlPresenter(",
        "MainPresenterDependencies(",
    ):
        assert constructor in source
    assert "DataTrafficHandler(self._view, traffic_monitor)" in source
    assert "status_coordinator.start()" in source


def test_bootstrapper_restores_state_in_safe_order():
    source = inspect.getsource(ApplicationBootstrapper.build)
    restore = source.index("lifecycle_manager.initialize_view()")
    manual_presenter = source.index("manual_control_presenter = ManualControlPresenter(")
    manual_apply = source.index("manual_control_presenter.apply_state(")
    control_state = source.index("control_state_coordinator = ControlStateCoordinator(")

    assert restore < source.index("port_presenter = PortPresenter(")
    assert restore < source.index("macro_presenter = MacroPresenter(")
    assert restore < manual_presenter < manual_apply < control_state


def test_main_presenter_owns_only_minimal_display_dependencies():
    source = inspect.getsource(MainPresenter)
    signature = inspect.signature(MainPresenter.__init__)
    assert "ApplicationBootstrapper" not in source
    assert "ApplicationComponents" not in source
    assert "SettingsManager" not in source
    assert "AppLifecycleManager" not in source
    assert set(signature.parameters) == {"self", "view", "dependencies"}
    assert inspect.isclass(MainPresenterDependencies)


def test_main_presenter_does_not_construct_or_own_policy_components():
    source = inspect.getsource(MainPresenter)
    for constructor in (
        "AppLifecycleManager(",
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
        "SettingsCoordinator(",
        "ControlStateCoordinator(",
        "StatusCoordinator(",
        "ShutdownCoordinator(",
        "PortPresenter(",
        "MacroPresenter(",
        "FilePresenter(",
        "PacketPresenter(",
        "ManualControlPresenter(",
    ):
        assert constructor not in source

    assert "self._apply_dependencies(dependencies)" in source
    for hidden_policy in (
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
        assert f"self.{hidden_policy} =" not in source


def test_lifecycle_does_not_own_or_call_main_presenter():
    source = inspect.getsource(AppLifecycleManager)
    assert "main_presenter" not in source
    assert "self.mp" not in source
    assert "_init_core_systems" not in source
    assert "_init_sub_presenters" not in source
    assert "_connect_signals" not in source
    assert "QTimer" not in source
    assert "create_status_timer" not in source


def test_port_presenter_uses_only_injected_runtime_dependencies():
    source = inspect.getsource(PortPresenter)
    signature = inspect.signature(PortPresenter.__init__)
    assert "SettingsManager()" not in source
    assert "PortScanManager()" not in source
    assert signature.parameters["settings_manager"].default is inspect.Parameter.empty
    assert signature.parameters["port_scan_manager"].default is inspect.Parameter.empty
