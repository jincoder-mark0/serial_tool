"""
SerialTool application composition root helper.

View 상태 복원, 구체 runtime object graph 생성, 변하지 않는 cross-component signal wiring을
한 곳에서 수행합니다. MainPresenter에는 사용자 표시 orchestration에 필요한 최소 dependency
contract만 전달합니다.
"""
from dataclasses import dataclass

from core.settings_manager import SettingsManager
from model.command_transmission_service import CommandTransmissionService
from model.connection_controller import ConnectionController
from model.connection_session_factory import ConnectionSessionFactory
from model.file_transfer_manager import FileTransferManager
from model.macro_runner import MacroRunner
from model.macro_script_manager import MacroScriptManager
from model.packet_parser_manager import PacketParserManager
from model.port_scan_manager import PortScanManager
from model.traffic_monitor import TrafficMonitor
from presenter.data_handler import DataTrafficHandler
from presenter.file_presenter import FilePresenter
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.logging_coordinator import LoggingCoordinator
from presenter.macro_execution_coordinator import MacroExecutionCoordinator
from presenter.macro_presenter import MacroPresenter
from presenter.main_presenter import MainPresenterDependencies
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from presenter.shutdown_coordinator import ShutdownCoordinator
from presenter.status_coordinator import StatusCoordinator
from view.main_window import MainWindow


@dataclass(frozen=True)
class ApplicationComponents:
    """Composition root가 소유하는 전체 runtime graph와 Presenter contract."""

    main_presenter_dependencies: MainPresenterDependencies
    connection_controller: ConnectionController
    file_transfer_manager: FileTransferManager
    port_scan_manager: PortScanManager
    macro_script_manager: MacroScriptManager
    status_coordinator: StatusCoordinator


class ApplicationBootstrapper:
    """저장 상태 복원 후 구체 runtime object graph를 생성합니다."""

    def __init__(self, view: MainWindow, settings_manager: SettingsManager) -> None:
        self._view = view
        self._settings_manager = settings_manager

    def build(self) -> ApplicationComponents:
        """View restore → Model/Service → Presenter/Coordinator → static wiring 순으로 조립합니다."""
        lifecycle_manager = AppLifecycleManager(self._view, self._settings_manager)
        lifecycle_manager.initialize_view()

        packet_parser_manager = PacketParserManager()
        connection_session_factory = ConnectionSessionFactory()
        connection_controller = ConnectionController(
            packet_parser_manager,
            connection_session_factory,
        )
        command_transmission_service = CommandTransmissionService(
            connection_controller,
            self._settings_manager,
        )
        file_transfer_manager = FileTransferManager(connection_controller)
        port_scan_manager = PortScanManager()
        macro_runner = MacroRunner()
        macro_script_manager = MacroScriptManager()
        macro_execution_coordinator = MacroExecutionCoordinator(
            macro_runner,
            connection_controller,
            command_transmission_service,
            self._view.port_view,
        )
        traffic_monitor = TrafficMonitor()
        data_handler = DataTrafficHandler(self._view, traffic_monitor)
        logging_coordinator = LoggingCoordinator(self._view.port_view)
        status_coordinator = StatusCoordinator(self._view, traffic_monitor)

        port_presenter = PortPresenter(
            self._view.port_view,
            connection_controller,
            self._settings_manager,
            port_scan_manager,
        )
        macro_presenter = MacroPresenter(
            self._view.macro_view,
            macro_runner,
            macro_script_manager,
        )
        file_presenter = FilePresenter(file_transfer_manager)
        packet_presenter = PacketPresenter(
            self._view.packet_view,
            connection_controller,
            self._settings_manager,
        )
        manual_control_presenter = ManualControlPresenter(
            self._view.manual_control_view,
            self._view.port_view,
            connection_controller,
            command_transmission_service,
        )

        # 변하지 않는 data path는 composition root에서 한 번만 배선합니다.
        connection_controller.data_received.connect(data_handler.on_fast_data_received)
        connection_controller.data_sent.connect(data_handler.on_data_sent)
        connection_controller.data_received.connect(macro_runner.on_data_received)
        manual_control_presenter.local_echo_requested.connect(
            self._view.append_local_echo_data
        )

        shutdown_coordinator = ShutdownCoordinator(
            view=self._view,
            settings_manager=self._settings_manager,
            connection_controller=connection_controller,
            file_transfer_manager=file_transfer_manager,
            macro_runner=macro_runner,
            macro_script_manager=macro_script_manager,
            port_scan_manager=port_scan_manager,
            manual_control_presenter=manual_control_presenter,
            packet_presenter=packet_presenter,
            data_handler=data_handler,
            close_system_log=logging_coordinator.close_system_log,
            status_coordinator=status_coordinator,
        )

        main_presenter_dependencies = MainPresenterDependencies(
            lifecycle_manager=lifecycle_manager,
            connection_controller=connection_controller,
            macro_runner=macro_runner,
            macro_execution_coordinator=macro_execution_coordinator,
            logging_coordinator=logging_coordinator,
            shutdown_coordinator=shutdown_coordinator,
            port_presenter=port_presenter,
            macro_presenter=macro_presenter,
            file_presenter=file_presenter,
            packet_presenter=packet_presenter,
            manual_control_presenter=manual_control_presenter,
        )

        status_coordinator.start()

        return ApplicationComponents(
            main_presenter_dependencies=main_presenter_dependencies,
            connection_controller=connection_controller,
            file_transfer_manager=file_transfer_manager,
            port_scan_manager=port_scan_manager,
            macro_script_manager=macro_script_manager,
            status_coordinator=status_coordinator,
        )
