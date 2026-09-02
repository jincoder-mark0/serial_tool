"""
파일 전송 서비스 모듈.

QRunnable 기반 파일 전송 엔진입니다. 진행/완료/에러는 FileTransferSignals로 직접
전달하고, backpressure/baudrate 대기는 cancel 요청으로 즉시 깨울 수 있습니다.
세션 생명주기와 connection-close 대응은 FileTransferManager가 소유합니다.
"""
import os
import time
from typing import Optional
from threading import Event

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

from common.constants import (
    FILE_TRANSFER_BACKPRESSURE_WAIT_S,
    FILE_TRANSFER_STALL_TIMEOUT_S,
)
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
        self._cancel_event = Event()

        self.chunk_size = 4096 if self.config.baudrate > 115200 else 1024
        self.queue_threshold = 50

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """전송 취소를 요청하고 현재 대기 중인 wait를 즉시 깨웁니다."""
        self._cancel_event.set()

    def _wait_or_cancel(self, seconds: float) -> bool:
        """지정 시간까지 기다리되 cancel되면 즉시 True를 반환합니다."""
        return self._cancel_event.wait(max(0.0, seconds))

    def run(self) -> None:
        try:
            if not os.path.exists(self.file_path):
                self._emit_failure(f"File not found: {self.file_path}")
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0
            pending_chunk: Optional[bytes] = None
            stalled_since: Optional[float] = None

            with open(self.file_path, "rb") as file_obj:
                while not self.is_cancelled:
                    while (
                        self.connection_controller.get_write_queue_size(self.port_name)
                        > self.queue_threshold
                    ):
                        if self._wait_or_cancel(FILE_TRANSFER_BACKPRESSURE_WAIT_S):
                            break

                    if self.is_cancelled:
                        break

                    # 큐잉에 실패한 청크는 버리지 않고 들고 있다가 재시도한다.
                    # 새로 읽어버리면 그 청크가 조용히 사라진다.
                    if pending_chunk is None:
                        pending_chunk = file_obj.read(self.chunk_size)
                        if not pending_chunk:
                            break

                    if not self.connection_controller.send_data_to_connection(
                        self.port_name,
                        pending_chunk,
                    ):
                        # 실패 이유를 구분해야 한다. 포트가 닫힌 것은 전송 실패지만,
                        # TX 큐가 가득 찬 것은 "지금은 못 받는다"일 뿐이다.
                        # 구분하지 않으면 일시적인 backpressure에 전송을 중단하게 된다.
                        if not self.connection_controller.is_connection_open(
                            self.port_name
                        ):
                            raise RuntimeError(
                                f"Port {self.port_name} is not open or unavailable."
                            )

                        if stalled_since is None:
                            stalled_since = time.monotonic()
                        elif (
                            time.monotonic() - stalled_since
                            > FILE_TRANSFER_STALL_TIMEOUT_S
                        ):
                            raise RuntimeError(
                                f"Port {self.port_name} TX queue stayed full for "
                                f"{FILE_TRANSFER_STALL_TIMEOUT_S:.0f}s; "
                                f"the port is not draining."
                            )

                        if self._wait_or_cancel(FILE_TRANSFER_BACKPRESSURE_WAIT_S):
                            break
                        continue

                    stalled_since = None
                    chunk = pending_chunk
                    pending_chunk = None
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
                        baudrate = max(1, self.config.baudrate)
                        wait_time = (len(chunk) * 10) / baudrate
                        if self._wait_or_cancel(wait_time):
                            break

            if self.is_cancelled:
                self._emit_failure("Transfer cancelled by user.")
                return

            while not self.connection_controller.is_write_idle(self.port_name):
                write_error = self.connection_controller.get_write_error(self.port_name)
                if write_error:
                    self._emit_failure(f"Transport write failed: {write_error}")
                    return
                if not self.connection_controller.is_connection_open(self.port_name):
                    self._emit_failure(
                        f"Port {self.port_name} closed before queued data was written."
                    )
                    return
                if self._wait_or_cancel(FILE_TRANSFER_BACKPRESSURE_WAIT_S):
                    self._emit_failure("Transfer cancelled by user.")
                    return

            write_error = self.connection_controller.get_write_error(self.port_name)
            if write_error:
                self._emit_failure(f"Transport write failed: {write_error}")
                return

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
