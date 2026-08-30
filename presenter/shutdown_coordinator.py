"""
애플리케이션 종료 시퀀스 조정 모듈

MainPresenter에서 백그라운드 작업 종료, 상태 저장, 연결 종료, logger drain 순서를 분리합니다.
S-059의 데이터 보존 순서(connection close -> processEvents -> logger stop)를 보존합니다.
"""
from typing import Callable, Optional

from PyQt5.QtCore import QCoreApplication, QTimer

from core.data_logger import data_logger_manager
from core.logger import logger
from core.settings_manager import SettingsManager
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from presenter.data_handler import DataTrafficHandler
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.shutdown_state_collector import ShutdownStateCollector
from view.main_window import MainWindow


class ShutdownCoordinator:
    """앱 종료 시 반드시 지켜야 하는 순서와 상태 저장을 한 곳에서 관리합니다."""

    def __init__(
        self,
        view: MainWindow,
        settings_manager: SettingsManager,
        connection_controller: ConnectionController,
        macro_runner: MacroRunner,
        port_presenter: PortPresenter,
        manual_control_presenter: ManualControlPresenter,
        packet_presenter: PacketPresenter,
        data_handler: DataTrafficHandler,
        close_system_log: Callable[[], None],
        status_timer: Optional[QTimer] = None,
    ) -> None:
        self._view = view
        self._settings_manager = settings_manager
        self._connection_controller = connection_controller
        self._macro_runner = macro_runner
        self._port_presenter = port_presenter
        self._manual_control_presenter = manual_control_presenter
        self._packet_presenter = packet_presenter
        self._data_handler = data_handler
        self._close_system_log = close_system_log
        self._status_timer = status_timer

    def shutdown(self) -> None:
        """백그라운드 작업, 상태 저장, 연결 및 logger를 안전한 순서로 종료합니다."""
        logger.info("Shutdown initiated...")

        if self._macro_runner.isRunning():
            logger.info("Stopping active macro runner...")
            self._macro_runner.stop()
            self._macro_runner.wait(1000)

        self._port_presenter.stop_pending_scan()
        self._data_handler.stop()
        self._packet_presenter.stop()

        if self._status_timer:
            self._status_timer.stop()

        self._close_system_log()
        self._save_ui_state()

        if self._connection_controller.has_active_connection:
            self._connection_controller.close_connection()

        # S-059: Worker가 종료 직전 emit한 queued RX를 main thread에서 먼저 전달한다.
        QCoreApplication.processEvents()
        data_logger_manager.stop_all()
        logger.info("Shutdown completed.")

    def _save_ui_state(self) -> None:
        window_state = self._view.get_window_state()
        manual_state = self._manual_control_presenter.get_state()

        ShutdownStateCollector.collect_and_apply(
            self._settings_manager,
            window_state,
            manual_state,
        )
        self._settings_manager.save_settings()
