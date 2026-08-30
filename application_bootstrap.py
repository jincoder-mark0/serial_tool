"""
SerialTool application composition root helper.

이 모듈만 View/Presenter/Model의 구체 클래스를 동시에 알고 런타임 객체 그래프를
조립합니다. MainPresenter는 생성 규칙 대신 조립된 component 사용에 집중합니다.
"""
from dataclasses import dataclass

from core.settings_manager import SettingsManager
from model.command_transmission_service import CommandTransmissionService
from model.connection_controller import ConnectionController
from model.file_transfer_manager import FileTransferManager
from model.macro_runner import MacroRunner
from model.port_scan_manager import PortScanManager
from presenter.data_handler import DataTrafficHandler
from presenter.file_presenter import FilePresenter
from presenter.macro_presenter import MacroPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from view.main_window import MainWindow


@dataclass(frozen=True)
class ApplicationComponents:
    """MainPresenter가 사용하는 구체 runtime component 집합."""

    connection_controller: ConnectionController
    command_transmission_service: CommandTransmissionService
    file_transfer_manager: FileTransferManager
    port_scan_manager: PortScanManager
    macro_runner: MacroRunner
    data_handler: DataTrafficHandler
    port_presenter: PortPresenter
    macro_presenter: MacroPresenter
    file_presenter: FilePresenter
    packet_presenter: PacketPresenter
    manual_control_presenter: ManualControlPresenter


class ApplicationBootstrapper:
    """구체 runtime object graph를 한 곳에서 생성합니다."""

    def __init__(self, view: MainWindow, settings_manager: SettingsManager) -> None:
        self._view = view
        self._settings_manager = settings_manager

    def build(self) -> ApplicationComponents:
        """의존 순서에 따라 Model/Service/Presenter를 생성하고 정적 배선을 구성합니다."""
        connection_controller = ConnectionController()
        command_transmission_service = CommandTransmissionService(
            connection_controller,
            self._settings_manager,
        )
        file_transfer_manager = FileTransferManager(connection_controller)
        port_scan_manager = PortScanManager()
        macro_runner = MacroRunner()
        data_handler = DataTrafficHandler(self._view)

        port_presenter = PortPresenter(
            self._view.port_view,
            connection_controller,
            self._settings_manager,
            port_scan_manager,
        )
        macro_presenter = MacroPresenter(self._view.macro_view, macro_runner)
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

        # View 간 횡단 출력은 Presenter callback 대신 명시적 signal wiring으로 연결합니다.
        manual_control_presenter.local_echo_requested.connect(
            self._view.append_local_echo_data
        )

        return ApplicationComponents(
            connection_controller=connection_controller,
            command_transmission_service=command_transmission_service,
            file_transfer_manager=file_transfer_manager,
            port_scan_manager=port_scan_manager,
            macro_runner=macro_runner,
            data_handler=data_handler,
            port_presenter=port_presenter,
            macro_presenter=macro_presenter,
            file_presenter=file_presenter,
            packet_presenter=packet_presenter,
            manual_control_presenter=manual_control_presenter,
        )
