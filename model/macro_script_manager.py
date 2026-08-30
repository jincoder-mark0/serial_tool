"""
매크로 스크립트 I/O 및 비동기 load 생명주기 매니저.

MacroPresenter가 직접 수행하던 JSON 파일 I/O와 QThread 생성/종료를 Model 계층으로
이동합니다. Presenter는 사용자 요청과 성공/실패 표시만 담당합니다.
"""
from typing import Optional
from queue import Empty, Queue
from threading import Thread

try:
    import commentjson
except ImportError:
    import json as commentjson

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from common.dtos import MacroScriptData
from common.constants import BACKGROUND_IO_POLL_S, BACKGROUND_WORKER_STOP_TIMEOUT_MS
from core.logger import logger


class _MacroScriptLoadWorker(QThread):
    """단일 스크립트 파일을 백그라운드에서 읽고 파싱합니다."""

    load_finished = pyqtSignal(object)
    load_failed = pyqtSignal(str)

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self._file_path = file_path
        self._io_thread: Optional[Thread] = None

    @property
    def has_pending_io(self) -> bool:
        """QThread 종료 후에도 file I/O helper가 남아 있는지 반환합니다."""
        return self._io_thread is not None and self._io_thread.is_alive()

    def run(self) -> None:
        result_queue = Queue()

        def load_file() -> None:
            try:
                with open(self._file_path, "r", encoding="utf-8") as file:
                    data = commentjson.load(file)
                result_queue.put((True, data))
            except Exception as exc:
                result_queue.put((False, exc))

        self._io_thread = Thread(target=load_file, daemon=True)
        self._io_thread.start()

        while not self.isInterruptionRequested():
            try:
                succeeded, payload = result_queue.get(timeout=BACKGROUND_IO_POLL_S)
                break
            except Empty:
                continue
        else:
            return

        if succeeded:
            self.load_finished.emit(
                MacroScriptData.from_dict(self._file_path, payload)
            )
        else:
            self.load_failed.emit(str(payload))


class MacroScriptManager(QObject):
    """매크로 스크립트 저장/로드와 load worker 생명주기를 관리합니다."""

    script_loaded = pyqtSignal(object)
    load_failed = pyqtSignal(str)
    save_succeeded = pyqtSignal(str)
    save_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._load_worker: Optional[_MacroScriptLoadWorker] = None
        self._pending_io_worker: Optional[_MacroScriptLoadWorker] = None

    @property
    def is_loading(self) -> bool:
        return self._load_worker is not None and self._load_worker.isRunning()

    def save_script(self, script_data: MacroScriptData) -> bool:
        """스크립트를 저장하고 결과 signal을 발행합니다."""
        try:
            with open(script_data.file_path, "w", encoding="utf-8") as file:
                commentjson.dump(script_data.data, file, indent=4)
        except Exception as exc:
            message = str(exc)
            logger.error(f"Failed to save macro script: {message}")
            self.save_failed.emit(message)
            return False

        logger.info(f"Macro script saved to: {script_data.file_path}")
        self.save_succeeded.emit(script_data.file_path)
        return True

    def request_load(self, file_path: str) -> bool:
        """중복 load를 막고 새 load worker를 시작합니다."""
        if self.is_loading:
            logger.warning("Script loading already in progress.")
            return False
        if self._pending_io_worker is not None:
            if self._pending_io_worker.has_pending_io:
                logger.warning(
                    "Previous script file I/O is still blocked; retry rejected."
                )
                return False
            self._pending_io_worker = None

        logger.debug(f"Starting async script load: {file_path}")
        worker = _MacroScriptLoadWorker(file_path)
        worker.load_finished.connect(self._on_load_finished)
        worker.load_failed.connect(self._on_load_failed)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._load_worker = worker
        worker.start()
        return True

    def stop(self, timeout_ms: Optional[int] = None) -> bool:
        """진행 중 load QThread에 interruption을 요청하고 bounded wait합니다."""
        worker = self._load_worker
        if worker is None:
            return True

        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(
                BACKGROUND_WORKER_STOP_TIMEOUT_MS
                if timeout_ms is None
                else timeout_ms
            )

        if worker.isRunning():
            logger.warning("Macro script load worker did not finish before timeout.")
            return False

        if worker.has_pending_io:
            self._pending_io_worker = worker
        self._load_worker = None
        return True

    def _on_load_finished(self, script_data: MacroScriptData) -> None:
        logger.info("Macro script loaded successfully.")
        self.script_loaded.emit(script_data)

    def _on_load_failed(self, message: str) -> None:
        logger.error(f"Failed to load macro script: {message}")
        self.load_failed.emit(message)

    def _on_worker_finished(self, worker: _MacroScriptLoadWorker) -> None:
        if worker is self._load_worker:
            self._load_worker = None
