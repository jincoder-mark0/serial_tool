"""
파일 프레젠터 모듈

FileTransferDialog와 FileTransferService 사이를 중재하고 진행 상태를 View에 반영합니다.
완료/에러는 상위 조정자가 직접 구독할 수 있도록 Presenter signal로 재발행합니다.
"""
from typing import Optional

from PyQt5.QtCore import QDateTime, QObject, QThreadPool, pyqtSignal

from common.dtos import FileCompletionEvent, FileErrorEvent, FileProgressState
from core.logger import logger
from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService
from view.dialogs.file_transfer_dialog import FileTransferDialog


class FilePresenter(QObject):
    """파일 전송 View/Service 생명주기를 중재합니다."""

    transfer_completed = pyqtSignal(object)
    transfer_error = pyqtSignal(object)

    def __init__(self, connection_controller: ConnectionController) -> None:
        super().__init__()
        self.connection_controller = connection_controller
        self.file_transfer_service: Optional[FileTransferService] = None
        self.file_transfer_dialog: Optional[FileTransferDialog] = None
        self.target_port: Optional[str] = None
        self._start_time = 0

    def on_file_transfer_dialog_opened(
        self,
        dialog: FileTransferDialog,
        target_port: str,
    ) -> None:
        self.file_transfer_dialog = dialog
        self.target_port = target_port

        if not self.target_port:
            logger.warning("File Transfer Dialog opened without active port context.")

        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)
        dialog.finished.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        self.file_transfer_dialog = None
        self.target_port = None

    def start_transfer(self, file_path: str) -> None:
        if not self.target_port:
            logger.error("File Transfer: No target port specified.")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, "No target port selected.")
            return

        if not self.connection_controller.is_connection_open(self.target_port):
            logger.error(f"File Transfer: Target port {self.target_port} is not open.")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, "Port disconnected.")
            return

        port_config = self.connection_controller.get_connection_config(self.target_port)
        if not port_config:
            logger.error(f"Configuration not found for port {self.target_port}")
            return

        try:
            service = FileTransferService(
                self.connection_controller,
                file_path,
                port_config,
            )
            self.file_transfer_service = service
            service.signals.progress_updated.connect(self._on_progress)
            service.signals.transfer_completed.connect(self._on_completed)
            service.signals.error_occurred.connect(self._on_error)

            self._start_time = QDateTime.currentMSecsSinceEpoch()
            QThreadPool.globalInstance().start(service)
            logger.info(f"File transfer started: {file_path} -> {self.target_port}")
        except Exception as exc:
            logger.error(f"Failed to start file transfer: {exc}")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, str(exc))

    def cancel_transfer(self) -> None:
        if self.file_transfer_service:
            logger.info("Cancelling file transfer...")
            self.file_transfer_service.cancel()

    def _on_progress(self, state: FileProgressState) -> None:
        if not self.file_transfer_dialog:
            return

        elapsed_total_sec = (
            QDateTime.currentMSecsSinceEpoch() - self._start_time
        ) / 1000.0
        if elapsed_total_sec > 0:
            state.speed = state.sent_bytes / elapsed_total_sec
        if state.speed > 0:
            state.eta = (state.total_bytes - state.sent_bytes) / state.speed

        self.file_transfer_dialog.update_progress(state)

    def _on_completed(self, event: FileCompletionEvent) -> None:
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(event.success, event.message)

        self.file_transfer_service = None

        if event.success:
            logger.info(f"File transfer completed: {event.file_path}")
        else:
            logger.warning(f"File transfer failed/cancelled: {event.message}")

        self.transfer_completed.emit(event)

    def _on_error(self, event: FileErrorEvent) -> None:
        logger.error(f"File Transfer Error: {event.message}")
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(False, event.message)
        self.transfer_error.emit(event)
