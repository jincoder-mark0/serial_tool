"""
파일 전송 서비스 모듈

QRunnable 기반 파일 전송 엔진입니다. 진행/완료/에러는 FileTransferSignals로 직접 전달합니다.
"""
import os
import time

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

from common.constants import FILE_TRANSFER_BACKPRESSURE_WAIT_S
from common.dtos import FileCompletionEvent, FileErrorEvent, FileProgressState, PortConfig
from common.enums import FileStatus, SerialFlowControl
from model.connection_controller import ConnectionController


class FileTransferSignals(QObject):
    progress_updated = pyqtSignal(object)
    transfer_completed = pyqtSignal(object)
    error_occurred = pyqtSignal(object)


class FileTransferService(QRunnable):
    """파일을 청크 단위로 비동기 전송합니다."""

    def __init__(
        self,
        connection_controller: ConnectionController,
        file_path: str,
        config: PortConfig,
    ) -> None:
        super().__init__()
        self.connection_controller = connection_controller
        self.file_path = file_path
        self.config = config
        self.port_name = config.port
        self.signals = FileTransferSignals()
        self._is_cancelled = False

        self.chunk_size = 4096 if self.config.baudrate > 115200 else 1024
        self.queue_threshold = 50

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            self.connection_controller.register_file_transfer(self.port_name, self)

            if not os.path.exists(self.file_path):
                msg = f"File not found: {self.file_path}"
                self._emit_failure(msg)
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0

            with open(self.file_path, "rb") as file_obj:
                while not self._is_cancelled:
                    while (
                        self.connection_controller.get_write_queue_size(self.port_name)
                        > self.queue_threshold
                    ):
                        time.sleep(FILE_TRANSFER_BACKPRESSURE_WAIT_S)
                        if self._is_cancelled:
                            break

                    if self._is_cancelled:
                        break

                    chunk = file_obj.read(self.chunk_size)
                    if not chunk:
                        break

                    if not self.connection_controller.send_data_to_connection(
                        self.port_name,
                        chunk,
                    ):
                        raise RuntimeError(
                            f"Port {self.port_name} is not open or unavailable."
                        )

                    sent_bytes += len(chunk)
                    self.signals.progress_updated.emit(
                        FileProgressState(
                            file_path=self.file_path,
                            sent_bytes=sent_bytes,
                            total_bytes=total_size,
                            status=FileStatus.SENDING.value,
                        )
                    )

                    if self.config.flowctrl not in (
                        SerialFlowControl.RTS_CTS.value,
                        SerialFlowControl.XON_XOFF.value,
                    ):
                        wait_time = (len(chunk) * 10) / self.config.baudrate
                        time.sleep(wait_time)

            if self._is_cancelled:
                self._emit_failure("Transfer cancelled by user.")
                return

            while self.connection_controller.get_write_queue_size(self.port_name) > 0:
                if self._is_cancelled:
                    self._emit_failure("Transfer cancelled by user.")
                    return
                time.sleep(FILE_TRANSFER_BACKPRESSURE_WAIT_S)

            self.signals.transfer_completed.emit(
                FileCompletionEvent(
                    success=True,
                    message="Transfer successful",
                    file_path=self.file_path,
                )
            )

        except Exception as exc:
            try:
                from core.error_handler import get_error_handler

                handler = get_error_handler()
                if handler:
                    handler.report_error(type(exc), exc, exc.__traceback__)
            except Exception:
                pass

            self._emit_failure(str(exc))
        finally:
            self.connection_controller.unregister_file_transfer(self.port_name)

    def _emit_failure(self, message: str) -> None:
        error_event = FileErrorEvent(message=message, file_path=self.file_path)
        self.signals.error_occurred.emit(error_event)
        self.signals.transfer_completed.emit(
            FileCompletionEvent(
                success=False,
                message=message,
                file_path=self.file_path,
            )
        )
