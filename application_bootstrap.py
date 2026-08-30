"""
SerialTool application composition root helper.

View 상태 복원과 구체 runtime object graph 생성을 한 곳에서 순서대로 수행합니다.
Port/Macro Presenter가 View collection을 관찰하기 전에 저장된 탭/패널 상태가 먼저
복원되어야 하므로 `AppLifecycleManager.initialize_view()`를 build의 첫 단계로 둡니다.
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
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from view.main_window import MainWindow


@dataclass(frozen=True)
class ApplicationComponents:
    """MainPresenter가 사용하는 완성된 runtime component 집합."""

    lifecycle_manager: AppLifecycleManager
    connection_controller: ConnectionController
    command_transmission_service: CommandTransmissionService
    file_transfer_manager: FileTransferManager
    port_scan_manager: PortScanManager
    macro_runner: MacroRunner
    macro_script_manager: MacroScriptManager
    macro_execution_coordinator: MacroExecutionCoordinator
    traffic_monitor: TrafficMonitor
    data_handler: DataTrafficHandler
    logging_coordinator: LoggingCoordinator
    port_presenter: PortPresenter
    macro_presenter: MacroPresenter
    file_presenter: FilePresenter
    packet_presenter: PacketPresenter
    manual_control_presenter: ManualControlPresenter


class ApplicationBootstrapper:
    """저장 상태 복원 후 구체 runtime object graph를 생성합니다."""

    def __init__(self, view: MainWindow, settings_manager: SettingsManager) -> None:
        self._view = view
        self._settings_manager = settings_manager

    def build(self) -> ApplicationComponents:
        """View restore → Model/Service → Presenter 순으로 application graph를 조립합니다."""
        # 1. View collection을 소비하는 Presenter보다 상태 복원이 반드시 먼저입니다.
        lifecycle_manager = AppLifecycleManager(
            self._view,
            self._settings_manager,
        )
        lifecycle_manager.initialize_view()

        # 2. Model / application services
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

        # 3. Presenter — 복원 완료된 View를 기준으로 초기 collection을 연결합니다.
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

        manual_control_presenter.local_echo_requested.connect(
            self._view.append_local_echo_data
        )

        return ApplicationComponents(
            lifecycle_manager=lifecycle_manager,
            connection_controller=connection_controller,
            command_transmission_service=command_transmission_service,
            file_transfer_manager=file_transfer_manager,
            port_scan_manager=port_scan_manager,
            macro_runner=macro_runner,
            macro_script_manager=macro_script_manager,
            macro_execution_coordinator=macro_execution_coordinator,
            traffic_monitor=traffic_monitor,
            data_handler=data_handler,
            logging_coordinator=logging_coordinator,
            port_presenter=port_presenter,
            macro_presenter=macro_presenter,
            file_presenter=file_presenter,
            packet_presenter=packet_presenter,
            manual_control_presenter=manual_control_presenter,
        )
