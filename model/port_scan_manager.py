"""
포트 스캔 생명주기 매니저.

PortScanWorker(QThread)의 생성/중복 실행 방지/종료 대기를 Model 계층에서 소유합니다.
Presenter는 스캔 요청과 결과를 View에 반영하는 역할만 담당합니다.
"""
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger
from common.constants import BACKGROUND_WORKER_STOP_TIMEOUT_MS
from model.port_scanner import PortScanWorker


class PortScanManager(QObject):
    """한 번에 하나의 PortScanWorker를 관리합니다."""

    ports_found = pyqtSignal(object)
    scan_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker: Optional[PortScanWorker] = None

    @property
    def is_running(self) -> bool:
        """스캔 worker가 실행 중인지 반환합니다."""
        return self._worker is not None and self._worker.isRunning()

    def request_scan(self) -> bool:
        """
        비동기 포트 스캔을 요청합니다.

        Returns:
            bool: 새 worker를 시작했으면 True, 이미 실행 중이면 False.
        """
        if self.is_running:
            logger.debug("Port scan already in progress.")
            return False

        logger.debug("Starting async port scan...")
        worker = PortScanWorker()
        worker.ports_found.connect(self._on_ports_found)
        worker.scan_failed.connect(self.scan_failed.emit)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._worker = worker
        worker.start()
        return True

    def stop(self, timeout_ms: Optional[int] = None) -> bool:
        """
        실행 중인 scan worker 종료를 기다립니다.

        blocking OS 호출은 worker 내부 daemon I/O thread가 담당하고 QThread는
        interruption을 polling하므로 shutdown은 상한 안에 종료됩니다.

        Returns:
            bool: worker가 완전히 종료됐거나 처음부터 없었으면 True.
        """
        worker = self._worker
        if worker is None:
            return True

        if worker.isRunning():
            logger.debug("Stopping pending port scan before shutdown...")
            worker.requestInterruption()
            worker.wait(
                BACKGROUND_WORKER_STOP_TIMEOUT_MS
                if timeout_ms is None
                else timeout_ms
            )

        if worker.isRunning():
            logger.warning("Port scan worker did not finish before the requested timeout.")
            return False

        self._worker = None
        return True

    def _on_ports_found(self, port_list) -> None:
        """worker 결과를 manager public signal로 중계합니다."""
        self.ports_found.emit(port_list)

    def _on_worker_finished(self, worker: PortScanWorker) -> None:
        """명시적으로 전달된 현재 worker가 종료되면 소유 참조를 해제합니다."""
        if worker is self._worker:
            self._worker = None
