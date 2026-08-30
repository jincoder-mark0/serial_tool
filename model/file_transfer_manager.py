"""
파일 전송 애플리케이션 매니저.

FileTransferService 생성, 전용 QThreadPool scheduling, 취소, progress metric 계산과
현재 전송 세션의 생명주기를 소유합니다. ConnectionController는 파일 전송 기능을
모르며, Manager가 connection_closing signal을 구독해 worker stop 전에 자기 세션을 취소합니다.
"""
import time
from typing import Optional

from PyQt5.QtCore import QObject, QThreadPool, pyqtSignal

from common.dtos import FileCompletionEvent, FileErrorEvent, FileProgressState
from core.logger import logger
from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService


class FileTransferManager(QObject):
    """단일 활성 파일 전송 세션과 전용 worker pool을 관리합니다."""

    progress_updated = pyqtSignal(object)
    transfer_completed = pyqtSignal(object)
    error_occurred = pyqtSignal(object)

    def __init__(
        self,
        connection_controller: ConnectionController,
        thread_pool: Optional[QThreadPool] = None,
    ) -> None:
        super().__init__()
        self._connection_controller = connection_controller
        self._thread_pool = thread_pool or QThreadPool(self)
        self._active_service: Optional[FileTransferService] = None
        self._active_port: Optional[str] = None
        self._start_monotonic = 0.0

        self._connection_controller.connection_closing.connect(
            self._on_connection_closing
        )

    @property
    def is_active(self) -> bool:
        return self._active_service is not None

    def start_transfer(self, file_path: str, target_port: str) -> bool:
        if self._active_service is not None:
            self._emit_start_error(file_path, "File transfer is already in progress.")
            return False
        if not target_port:
            self._emit_start_error(file_path, "No target port selected.")
            return False
        if not self._connection_controller.is_connection_open(target_port):
            self._emit_start_error(file_path, f"Port '{target_port}' is disconnected.")
            return False

        port_config = self._connection_controller.get_connection_config(target_port)
        if port_config is None:
            self._emit_start_error(
                file_path,
                f"Configuration not found for port {target_port}.",
            )
            return False

        try:
            service = FileTransferService(
                self._connection_controller,
                file_path,
                port_config,
            )
            service.signals.progress_updated.connect(self._on_progress)
            service.signals.transfer_completed.connect(self._on_completed)
            service.signals.error_occurred.connect(self._on_error)

            self._active_service = service
            self._active_port = target_port
            self._start_monotonic = time.monotonic()
            self._thread_pool.start(service)
            logger.info(f"File transfer started: {file_path} -> {target_port}")
            return True
        except Exception as exc:
            self._clear_active_session()
            self._emit_start_error(file_path, f"Failed to start file transfer: {exc}")
            return False

    def cancel_transfer(self) -> None:
        service = self._active_service
        if service is None:
            return
        logger.info("Cancelling file transfer...")
        service.cancel()

    def shutdown(self) -> None:
        """활성 전송을 취소하고 이 manager의 전용 worker pool을 drain합니다."""
        self.cancel_transfer()
        self._thread_pool.waitForDone()
        self._clear_active_session()

    def _on_connection_closing(self, port_name: str) -> None:
        """전송 대상 포트가 stop되기 전에 해당 전송 세션에 취소를 요청합니다."""
        if self._active_service is None:
            return
        if port_name == self._active_port:
            logger.warning(
                f"File transfer target port {port_name} is closing. Cancelling transfer..."
            )
            self.cancel_transfer()

    def _on_progress(self, state: FileProgressState) -> None:
        elapsed = time.monotonic() - self._start_monotonic
        if elapsed > 0:
            state.speed = state.sent_bytes / elapsed
        if state.speed > 0:
            state.eta = max(0, state.total_bytes - state.sent_bytes) / state.speed
        self.progress_updated.emit(state)

    def _on_completed(self, event: FileCompletionEvent) -> None:
        self._clear_active_session()
        if event.success:
            logger.info(f"File transfer completed: {event.file_path}")
        else:
            logger.warning(f"File transfer failed/cancelled: {event.message}")
        self.transfer_completed.emit(event)

    def _on_error(self, event: FileErrorEvent) -> None:
        logger.error(f"File Transfer Error: {event.message}")
        self.error_occurred.emit(event)

    def _clear_active_session(self) -> None:
        self._active_service = None
        self._active_port = None

    def _emit_start_error(self, file_path: str, message: str) -> None:
        logger.error(message)
        self.error_occurred.emit(
            FileErrorEvent(message=message, file_path=file_path)
        )
