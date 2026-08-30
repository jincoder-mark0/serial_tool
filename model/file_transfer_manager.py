"""
파일 전송 애플리케이션 매니저.

FileTransferService 생성, 전용 QThreadPool scheduling, 취소, progress metric 계산과
현재 전송 세션의 생명주기를 소유합니다. Presenter는 Dialog 표시만 담당합니다.
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
        # global pool을 공유하지 않습니다. 종료 시 이 manager가 제출한 작업만
        # 기다릴 수 있도록 전용 pool을 소유합니다.
        self._thread_pool = thread_pool or QThreadPool(self)
        self._active_service: Optional[FileTransferService] = None
        self._start_monotonic = 0.0

    @property
    def is_active(self) -> bool:
        """현재 관리 중인 전송 세션이 있는지 반환합니다."""
        return self._active_service is not None

    def start_transfer(self, file_path: str, target_port: str) -> bool:
        """대상 포트를 검증하고 FileTransferService를 worker pool에 제출합니다."""
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
            self._start_monotonic = time.monotonic()
            self._thread_pool.start(service)
            logger.info(f"File transfer started: {file_path} -> {target_port}")
            return True
        except Exception as exc:
            self._active_service = None
            self._emit_start_error(file_path, f"Failed to start file transfer: {exc}")
            return False

    def cancel_transfer(self) -> None:
        """활성 전송 세션이 있으면 취소를 요청합니다."""
        service = self._active_service
        if service is None:
            return
        logger.info("Cancelling file transfer...")
        service.cancel()

    def shutdown(self) -> None:
        """
        활성 전송을 취소하고 이 manager가 소유한 worker가 끝날 때까지 기다립니다.

        FileTransferService는 cancel flag를 각 chunk/backpressure 루프에서 확인하므로
        종료 중 새 데이터를 계속 큐에 넣지 않습니다. 전용 thread pool을 사용하므로
        waitForDone()이 다른 기능의 QRunnable까지 기다리는 부작용도 없습니다.
        """
        self.cancel_transfer()
        self._thread_pool.waitForDone()
        self._active_service = None

    def _on_progress(self, state: FileProgressState) -> None:
        """전송량으로 평균 속도와 ETA를 계산한 뒤 상위 계층에 전달합니다."""
        elapsed = time.monotonic() - self._start_monotonic
        if elapsed > 0:
            state.speed = state.sent_bytes / elapsed
        if state.speed > 0:
            state.eta = max(0, state.total_bytes - state.sent_bytes) / state.speed
        self.progress_updated.emit(state)

    def _on_completed(self, event: FileCompletionEvent) -> None:
        """세션 소유권을 해제한 뒤 완료 이벤트를 전달합니다."""
        self._active_service = None
        if event.success:
            logger.info(f"File transfer completed: {event.file_path}")
        else:
            logger.warning(f"File transfer failed/cancelled: {event.message}")
        self.transfer_completed.emit(event)

    def _on_error(self, event: FileErrorEvent) -> None:
        """service 오류를 상위 계층에 전달합니다."""
        logger.error(f"File Transfer Error: {event.message}")
        self.error_occurred.emit(event)

    def _emit_start_error(self, file_path: str, message: str) -> None:
        """service 생성 전 실패도 service 오류와 동일한 DTO 계약으로 표면화합니다."""
        logger.error(message)
        self.error_occurred.emit(
            FileErrorEvent(message=message, file_path=file_path)
        )
