"""Production composition root / dependency injection 회귀 테스트."""
import inspect
from dataclasses import fields

import main
from application_bootstrap import ApplicationBootstrapper, ApplicationComponents
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.main_presenter import MainPresenter, MainPresenterDependencies
from presenter.port_presenter import PortPresenter


def test_main_is_thin_entry_point_and_does_not_construct_presenters():
    source = inspect.getsource(main)
    main_source = inspect.getsource(main.main)

    assert "settings_mgr = SettingsManager(resource_path)" in main_source
    assert "ApplicationBootstrapper(window, settings_mgr).build()" in main_source
    assert "MainPresenter" not in source
    assert "dependencies=" not in main_source


def test_bootstrapper_is_the_complete_object_graph_owner():
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
        "MainPresenter(",
    ):
        assert constructor in source
    assert "DataTrafficHandler(self._view, traffic_monitor)" in source
    assert "status_coordinator.start()" in source
    assert "main_presenter=main_presenter" in source


def test_application_components_keeps_strong_references_to_runtime_owners():
    component_names = {field.name for field in fields(ApplicationComponents)}
    assert {
        "lifecycle_manager",
        "packet_parser_manager",
        "connection_session_factory",
        "command_transmission_service",
        "macro_runner",
        "traffic_monitor",
        "port_presenter",
        "macro_presenter",
        "file_presenter",
        "manual_control_presenter",
        "macro_execution_coordinator",
        "logging_coordinator",
        "shutdown_coordinator",
    } <= component_names


def test_bootstrapper_restores_state_in_safe_order():
    source = inspect.getsource(ApplicationBootstrapper.build)
    restore = source.index("lifecycle_manager.initialize_view()")
    manual_presenter = source.index("manual_control_presenter = ManualControlPresenter(")
    manual_apply = source.index("manual_control_presenter.apply_state(")
    control_state = source.index("control_state_coordinator = ControlStateCoordinator(")
    main_presenter = source.index("main_presenter = MainPresenter(")

    assert restore < source.index("port_presenter = PortPresenter(")
    assert restore < source.index("macro_presenter = MacroPresenter(")
    assert restore < manual_presenter < manual_apply < control_state < main_presenter


def test_bootstrapper_owns_fixed_command_routing():
    source = inspect.getsource(ApplicationBootstrapper.build)

    assert "shortcut_connect_requested.connect(" in source
    assert "port_presenter.connect_current_port" in source
    assert "shortcut_disconnect_requested.connect(" in source
    assert "port_presenter.disconnect_current_port" in source
    assert "shortcut_clear_requested.connect(" in source
    assert "port_presenter.clear_log_current_port" in source
    assert "file_transfer_dialog_opened.connect(" in source
    assert "file_presenter.on_file_transfer_dialog_opened" in source


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
        "port_presenter",
        "macro_presenter",
        "packet_presenter",
    ):
        assert f"self.{hidden_policy} =" not in source

    assert "on_shortcut_connect" not in source
    assert "on_shortcut_disconnect" not in source
    assert "on_shortcut_clear" not in source


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
