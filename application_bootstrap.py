"""
SerialTool application composition root.

View 상태 복원부터 MainPresenter 생성까지 전체 runtime object graph를 한 곳에서 조립합니다.
`main.py`는 리소스/Qt 애플리케이션을 준비한 뒤 이 bootstrapper를 호출하는 진입점 역할만
담당합니다.
"""
from dataclasses import dataclass

from core.settings_manager import SettingsManager
from core.transport.transaction.backends.pyftdi_backend import PyFtdiAdapterProvider
from core.transport.transaction.registry import AdapterBackendRegistry
from model.command_transmission_service import CommandTransmissionService
from model.connection_controller import ConnectionController
from model.connection_session_factory import ConnectionSessionFactory
from model.file_transfer_manager import FileTransferManager
from model.macro_runner import MacroRunner
from model.macro_script_manager import MacroScriptManager
from model.packet_annotation_store import PacketAnnotationStore
from model.packet_export_manager import PacketExportManager
from model.packet_parser_manager import PacketParserManager
from model.port_scan_manager import PortScanManager
from model.traffic_monitor import TrafficMonitor
from model.transaction_manager import TransactionManager
from presenter.control_state_coordinator import ControlStateCoordinator
from presenter.data_handler import DataTrafficHandler
from presenter.file_presenter import FilePresenter
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.logging_coordinator import LoggingCoordinator
from presenter.macro_execution_coordinator import MacroExecutionCoordinator
from presenter.macro_presenter import MacroPresenter
from presenter.main_presenter import MainPresenter, MainPresenterDependencies
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from presenter.settings_coordinator import SettingsCoordinator
from presenter.shutdown_coordinator import ShutdownCoordinator
from presenter.status_coordinator import StatusCoordinator
from view.main_window import MainWindow


@dataclass(frozen=True)
class ApplicationComponents:
    """Composition root가 수명을 소유하는 완성된 runtime graph."""

    main_presenter: MainPresenter
    lifecycle_manager: AppLifecycleManager
    packet_parser_manager: PacketParserManager
    packet_annotation_store: PacketAnnotationStore
    packet_export_manager: PacketExportManager
    connection_session_factory: ConnectionSessionFactory
    connection_controller: ConnectionController
    command_transmission_service: CommandTransmissionService
    transaction_manager: TransactionManager
    macro_runner: MacroRunner
    traffic_monitor: TrafficMonitor
    data_handler: DataTrafficHandler
    file_transfer_manager: FileTransferManager
    port_scan_manager: PortScanManager
    macro_script_manager: MacroScriptManager
    port_presenter: PortPresenter
    macro_presenter: MacroPresenter
    file_presenter: FilePresenter
    packet_presenter: PacketPresenter
    manual_control_presenter: ManualControlPresenter
    macro_execution_coordinator: MacroExecutionCoordinator
    logging_coordinator: LoggingCoordinator
    settings_coordinator: SettingsCoordinator
    control_state_coordinator: ControlStateCoordinator
    shutdown_coordinator: ShutdownCoordinator
    status_coordinator: StatusCoordinator


class ApplicationBootstrapper:
    """저장 상태 복원 후 완전한 application runtime graph를 생성합니다."""

    def __init__(self, view: MainWindow, settings_manager: SettingsManager) -> None:
        self._view = view
        self._settings_manager = settings_manager

    def build(self) -> ApplicationComponents:
        """View restore → Model/Service → Presenter state → Coordinator → MainPresenter 순으로 조립합니다."""
        lifecycle_manager = AppLifecycleManager(self._view, self._settings_manager)
        lifecycle_manager.initialize_view()

        packet_parser_manager = PacketParserManager()
        packet_annotation_store = PacketAnnotationStore()
        packet_export_manager = PacketExportManager()
        connection_session_factory = ConnectionSessionFactory()
        connection_controller = ConnectionController(
            packet_parser_manager,
            connection_session_factory,
        )
        command_transmission_service = CommandTransmissionService(
            connection_controller,
            self._settings_manager,
        )

        # SPI/I2C는 Serial stream worker와 분리된 transaction runtime을 사용합니다.
        # PyFtdi package/libusb가 없어도 provider.is_available()만 False가 되며
        # application startup과 Serial 기능은 계속 동작합니다.
        transaction_registry = AdapterBackendRegistry([PyFtdiAdapterProvider()])
        transaction_manager = TransactionManager(transaction_registry)

        file_transfer_manager = FileTransferManager(connection_controller)
        port_scan_manager = PortScanManager()
        macro_runner = MacroRunner()
        macro_script_manager = MacroScriptManager()
        macro_execution_coordinator = MacroExecutionCoordinator(
            macro_runner,
            connection_controller,
            command_transmission_service,
            self._view.port_view,
            self._settings_manager,
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
            packet_annotation_store,
            packet_export_manager,
        )
        manual_control_presenter = ManualControlPresenter(
            self._view.manual_control_view,
            self._view.port_view,
            connection_controller,
            command_transmission_service,
        )

        # 저장된 ManualControl 상태를 먼저 적용한 뒤 enable policy를 계산합니다.
        manual_control_presenter.apply_state(
            lifecycle_manager.create_manual_control_state()
        )

        settings_coordinator = SettingsCoordinator(
            self._view,
            self._settings_manager,
            port_presenter,
            manual_control_presenter,
            packet_presenter,
        )
        control_state_coordinator = ControlStateCoordinator(
            self._view.port_view,
            connection_controller,
            manual_control_presenter,
            macro_presenter,
        )

        # 실행 중 변하지 않는 signal topology는 composition root에서 한 번만 배선합니다.
        connection_controller.data_received.connect(data_handler.on_fast_data_received)
        connection_controller.data_sent.connect(data_handler.on_data_sent)
        connection_controller.data_received.connect(macro_runner.on_data_received)
        manual_control_presenter.local_echo_requested.connect(
            self._view.append_local_echo_data
        )
        macro_execution_coordinator.local_echo_requested.connect(
            self._view.append_local_echo_data
        )
        self._view.shortcut_connect_requested.connect(
            port_presenter.connect_current_port
        )
        self._view.shortcut_disconnect_requested.connect(
            port_presenter.disconnect_current_port
        )
        self._view.shortcut_clear_requested.connect(
            port_presenter.clear_log_current_port
        )
        self._view.file_transfer_dialog_opened.connect(
            file_presenter.on_file_transfer_dialog_opened
        )
        settings_coordinator.info_requested.connect(
            logging_coordinator.info_requested.emit
        )
        port_scan_manager.scan_failed.connect(
            lambda message: logging_coordinator.error_requested.emit(
                f"Port scan failed: {message}"
            )
        )
        settings_coordinator.connect_signals()

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
            transaction_manager=transaction_manager,
        )

        main_presenter = MainPresenter(
            self._view,
            dependencies=MainPresenterDependencies(
                connection_controller=connection_controller,
                macro_runner=macro_runner,
                macro_execution_coordinator=macro_execution_coordinator,
                logging_coordinator=logging_coordinator,
                shutdown_coordinator=shutdown_coordinator,
                file_presenter=file_presenter,
                manual_control_presenter=manual_control_presenter,
            ),
        )

        # 초기 scan은 오류 subscriber까지 완전히 연결된 뒤 시작합니다.
        port_presenter.scan_ports()
        status_coordinator.start()
        lifecycle_manager.log_initialized()

        return ApplicationComponents(
            main_presenter=main_presenter,
            lifecycle_manager=lifecycle_manager,
            packet_parser_manager=packet_parser_manager,
            packet_annotation_store=packet_annotation_store,
            packet_export_manager=packet_export_manager,
            connection_session_factory=connection_session_factory,
            connection_controller=connection_controller,
            command_transmission_service=command_transmission_service,
            transaction_manager=transaction_manager,
            macro_runner=macro_runner,
            traffic_monitor=traffic_monitor,
            data_handler=data_handler,
            file_transfer_manager=file_transfer_manager,
            port_scan_manager=port_scan_manager,
            macro_script_manager=macro_script_manager,
            port_presenter=port_presenter,
            macro_presenter=macro_presenter,
            file_presenter=file_presenter,
            packet_presenter=packet_presenter,
            manual_control_presenter=manual_control_presenter,
            macro_execution_coordinator=macro_execution_coordinator,
            logging_coordinator=logging_coordinator,
            settings_coordinator=settings_coordinator,
            control_state_coordinator=control_state_coordinator,
            shutdown_coordinator=shutdown_coordinator,
            status_coordinator=status_coordinator,
        )
