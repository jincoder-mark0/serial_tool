"""
애플리케이션 종료 시퀀스 조정 모듈.

백그라운드 작업 종료, transient runtime 상태 정리, 상태 저장, 연결 종료, logger drain
순서를 관리합니다. S-059의 데이터 보존 순서(connection close -> processEvents -> logger stop)를
보존합니다.
"""
from typing import Callable, Optional

from PyQt5.QtCore import QCoreApplication, QEventLoop

from common.constants import (
    BACKGROUND_WORKER_STOP_TIMEOUT_MS,
    SHUTDOWN_FLUSH_POLL_MS,
)
from core.data_logger import DataLoggerManager
from core.logger import logger
from core.settings_manager import SettingsManager
from model.connection_controller import ConnectionController
from model.file_transfer_manager import FileTransferManager
from model.macro_runner import MacroRunner
from model.macro_script_manager import MacroScriptManager
from model.port_scan_manager import PortScanManager
from model.transaction_manager import TransactionManager
from presenter.data_handler import DataTrafficHandler
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.shutdown_state_collector import ShutdownStateCollector
from presenter.status_coordinator import StatusCoordinator
from view.main_window import MainWindow
from view.managers.language_manager import language_manager


class ShutdownCoordinator:
    """앱 종료 시 반드시 지켜야 하는 순서와 상태 저장을 한 곳에서 관리합니다."""

    def __init__(
        self,
        view: MainWindow,
        settings_manager: SettingsManager,
        connection_controller: ConnectionController,
        file_transfer_manager: FileTransferManager,
        macro_runner: MacroRunner,
        macro_script_manager: MacroScriptManager,
        port_scan_manager: PortScanManager,
        manual_control_presenter: ManualControlPresenter,
        packet_presenter: PacketPresenter,
        data_handler: DataTrafficHandler,
        close_system_log: Callable[[], None],
        status_coordinator: StatusCoordinator,
        data_logger_manager: DataLoggerManager,
        transaction_manager: Optional[TransactionManager] = None,
    ) -> None:
        self._view = view
        self._settings_manager = settings_manager
        self._connection_controller = connection_controller
        self._file_transfer_manager = file_transfer_manager
        self._macro_runner = macro_runner
        self._macro_script_manager = macro_script_manager
        self._port_scan_manager = port_scan_manager
        self._manual_control_presenter = manual_control_presenter
        self._packet_presenter = packet_presenter
        self._data_handler = data_handler
        self._close_system_log = close_system_log
        self._status_coordinator = status_coordinator
        self._data_logger_manager = data_logger_manager
        self._transaction_manager = transaction_manager

    def shutdown(self) -> None:
        """백그라운드 작업, 상태 저장, 연결 및 logger를 안전한 순서로 종료합니다."""
        logger.info("Shutdown initiated...")

        if self._macro_runner.isRunning():
            logger.info("Stopping active macro runner...")
            # 상한은 stop()에 넘겨야 실제로 적용된다. 과거에는 stop() 안에서 이미
            # 무한 wait()을 한 뒤에 wait(1000)을 불러 상한이 아무 역할도 못 했다.
            if not self._macro_runner.stop(
                timeout_ms=BACKGROUND_WORKER_STOP_TIMEOUT_MS
            ):
                logger.warning(
                    "Macro runner did not stop within "
                    f"{BACKGROUND_WORKER_STOP_TIMEOUT_MS} ms; continuing shutdown."
                )

        # ConnectionController 및 USB adapter resource를 닫기 전에 producer 성격의
        # background 작업부터 정리합니다. SPI/I2C session도 별도 lifecycle owner가
        # 있으므로 Serial worker와 독립적으로 여기서 명시적으로 종료합니다.
        self._file_transfer_manager.shutdown()
        if self._transaction_manager is not None:
            self._transaction_manager.shutdown()
        self._macro_script_manager.stop()
        self._port_scan_manager.stop()
        self._data_handler.stop()
        self._packet_presenter.stop()
        self._status_coordinator.stop()

        # Auto Tx 실행 여부는 지속 설정이 아니라 transient runtime 상태입니다.
        # 저장 전에 정지/체크 해제해야 다음 실행에서 UI만 켜진 불일치를 만들지 않습니다.
        self._manual_control_presenter.stop_auto_tx()

        self._close_system_log()
        self._save_ui_state()

        # 앱 종료에서는 비동기 close를 쓰면 안 된다. 프로세스가 사라지면 아직
        # 내보내지 못한 TX 큐가 함께 사라진다 — 기다리지 않는 것이 곧 유실이다.
        # 상한을 두지 않는 것도 같은 이유다.
        if (
            self._connection_controller.has_active_connection
            or self._connection_controller.has_pending_flush()
        ):
            self._connection_controller.close_connection()
            self._wait_for_flush_without_freezing_ui()

        # S-059: Worker가 종료 직전 emit한 queued RX를 main thread에서 먼저 전달합니다.
        QCoreApplication.processEvents()
        self._data_logger_manager.stop_all()
        logger.info("Shutdown completed.")

    def _wait_for_flush_without_freezing_ui(self) -> None:
        """TX 드레인 완료를 기다리되 창이 계속 그려지도록 이벤트를 흘립니다.

        WHY:
            유실을 막으려면 여기서 반드시 기다려야 한다. 그런데 `QThread.wait()`로
            기다리면 이벤트 루프가 멈춰 창이 흰 사각형으로 굳는다 — 사용자에게는
            앱이 죽은 것과 구분되지 않고, 큐가 클수록 오래 굳는다.

            남은 양을 보여주며 기다리면 "멈춘 것"이 아니라 "내보내는 중"임이 보인다.

        HOW:
            `ExcludeUserInputEvents`로 그리기/타이머만 흘리고 마우스·키보드는 버린다.
            사용자 입력까지 흘리면 종료 도중 다시 연결하거나 매크로를 돌리는 재진입이
            생긴다 — 이미 정리한 자원을 다시 쓰게 되는 상태다.

        Note:
            상한을 두지 않는다. 여기서 포기하는 것은 곧 유실이고, 이제 창이 응답하므로
            오래 걸려도 사용자가 무슨 일이 벌어지는지 볼 수 있다. 포트가 물리적으로
            멎어 드레인이 진행되지 않으면 종료가 끝나지 않는데, 그때는 남은 바이트가
            줄지 않는 것이 화면에 그대로 드러난다.
        """
        controller = self._connection_controller
        if not controller.has_pending_flush():
            return

        logger.info("Waiting for queued TX data to flush before exit...")

        while controller.has_pending_flush():
            self._view.show_status_message(
                language_manager.get_text("main_status_msg_flushing").format(
                    controller.pending_flush_bytes()
                )
            )
            QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            controller.wait_for_pending_flush(timeout_ms=SHUTDOWN_FLUSH_POLL_MS)

        logger.info("Queued TX data flushed.")

    def _save_ui_state(self) -> None:
        window_state = self._view.get_window_state()
        manual_state = self._manual_control_presenter.get_state()

        ShutdownStateCollector.collect_and_apply(
            self._settings_manager,
            window_state,
            manual_state,
        )
        self._settings_manager.save_settings()
