"""SPI/I2C transaction runtime manager.

## WHY
* Presenter/View가 AdapterBackendRegistry나 QThread lifecycle을 직접 소유하지 않도록 함
* Session 이름 기준으로 open/execute/cancel/close API를 제공해 상위 계층의 vendor 의존 제거
* 앱 종료 시 모든 SPI/I2C worker를 bounded lifecycle로 정리할 단일 owner 필요
* USB/libusb enumeration을 UI thread에서 실행하지 않도록 discovery lifecycle도 Model에서 소유

## WHAT
* TransactionSessionWorker 생성 / registry 관리
* TransactionDiscoveryWorker 생성 / 중복 discovery 방지
* request ID 발급 및 transaction 결과 중계
* session duplicate / stale worker cleanup
* 전체 session/discovery shutdown

## HOW
* Composition Root에서 ``AdapterBackendRegistry``와 함께 한 번 생성
* 각 session마다 전용 ``TransactionSessionWorker`` 생성
* discovery는 one-shot ``TransactionDiscoveryWorker`` 사용
* worker signal을 manager public signal로 중계
* worker 종료 signal을 기준으로 내부 strong reference 제거
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger
from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.control import TransactionOptions
from core.transport.transaction.dto import (
    I2cTransactionRequest,
    SpiTransactionRequest,
)
from core.transport.transaction.registry import AdapterBackendRegistry
from model.transaction_discovery_worker import TransactionDiscoveryWorker
from model.transaction_session_worker import TransactionSessionWorker


class TransactionManager(QObject):
    """SPI/I2C adapter discovery/session/background worker의 application owner."""

    adapters_found = pyqtSignal(object)
    discovery_failed = pyqtSignal(object)
    session_opened = pyqtSignal(str, object)
    session_closed = pyqtSignal(str)
    session_failed = pyqtSignal(str, object)
    transaction_completed = pyqtSignal(str, int, object)
    transaction_failed = pyqtSignal(str, int, object)

    def __init__(self, registry: AdapterBackendRegistry) -> None:
        super().__init__()
        self._registry = registry
        self._workers: dict[str, TransactionSessionWorker] = {}
        self._discovery_worker: Optional[TransactionDiscoveryWorker] = None
        self._request_sequence = 0

    @property
    def has_active_session(self) -> bool:
        """하나 이상의 transaction session worker가 살아 있으면 True."""
        return any(worker.isRunning() for worker in self._workers.values())

    @property
    def is_discovering(self) -> bool:
        """Adapter discovery worker가 현재 실행 중인지 반환합니다."""
        worker = self._discovery_worker
        return worker is not None and worker.isRunning()

    def request_discovery(self) -> bool:
        """Background adapter discovery를 요청합니다.

        동일 시점에는 하나의 discovery만 허용합니다. 결과는 ``adapters_found`` 또는
        ``discovery_failed`` signal로 전달합니다.
        """
        if self.is_discovering:
            logger.debug("Transaction adapter discovery already in progress.")
            return False

        worker = TransactionDiscoveryWorker(self._registry)
        worker.adapters_found.connect(self.adapters_found.emit)
        worker.discovery_failed.connect(self.discovery_failed.emit)
        worker.finished.connect(lambda current=worker: self._on_discovery_finished(current))
        self._discovery_worker = worker
        worker.start()
        return True

    def open_session(self, config: TransactionConnectionConfig) -> bool:
        """새 SPI/I2C session worker를 생성하고 비동기로 open합니다."""
        existing = self._workers.get(config.name)
        if existing is not None:
            if existing.isRunning():
                logger.warning(f"Transaction session already active: {config.name}")
                return False
            self._workers.pop(config.name, None)

        worker = TransactionSessionWorker(self._registry, config)
        worker.session_opened.connect(self.session_opened.emit)
        worker.session_closed.connect(self.session_closed.emit)
        worker.session_failed.connect(self.session_failed.emit)
        worker.transaction_completed.connect(self.transaction_completed.emit)
        worker.transaction_failed.connect(self.transaction_failed.emit)
        worker.worker_terminated.connect(
            lambda name, current=worker: self._on_worker_terminated(name, current)
        )

        self._workers[config.name] = worker
        worker.start()
        return True

    def execute(
        self,
        session_name: str,
        request: SpiTransactionRequest | I2cTransactionRequest,
        *,
        options: Optional[TransactionOptions] = None,
    ) -> Optional[int]:
        """Session worker에 transaction을 queue하고 request ID를 반환합니다."""
        worker = self._workers.get(session_name)
        if worker is None or not worker.isRunning():
            return None

        request_id = self._next_request_id()
        if not worker.enqueue_transaction(request_id, request, options):
            return None
        return request_id

    def cancel_active(self, session_name: str) -> bool:
        """해당 session에서 현재 실행 중인 transaction에 취소를 요청합니다."""
        worker = self._workers.get(session_name)
        if worker is None:
            return False
        return worker.cancel_active_transaction()

    def close_session(self, session_name: str, timeout_ms: int = 2000) -> bool:
        """Session 종료를 요청하고 bounded wait 후 결과를 반환합니다."""
        worker = self._workers.get(session_name)
        if worker is None:
            return True

        worker.stop()
        if worker.isRunning():
            worker.wait(timeout_ms)

        if worker.isRunning():
            logger.warning(
                f"Transaction session did not stop within {timeout_ms} ms: {session_name}"
            )
            return False

        self._workers.pop(session_name, None)
        return True

    def stop_discovery(self, timeout_ms: int = 2000) -> bool:
        """실행 중인 adapter discovery 종료를 bounded wait합니다."""
        worker = self._discovery_worker
        if worker is None:
            return True

        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(timeout_ms)

        if worker.isRunning():
            logger.warning(
                f"Transaction adapter discovery did not stop within {timeout_ms} ms."
            )
            return False

        self._discovery_worker = None
        return True

    def shutdown(self, timeout_ms: int = 2000) -> bool:
        """Discovery와 모든 transaction session을 취소/종료하고 reference를 정리합니다."""
        success = self.stop_discovery(timeout_ms=timeout_ms)
        for session_name in tuple(self._workers):
            if not self.close_session(session_name, timeout_ms=timeout_ms):
                success = False
        return success

    def is_session_active(self, session_name: str) -> bool:
        """지정 session worker가 현재 실행 중인지 반환합니다."""
        worker = self._workers.get(session_name)
        return worker is not None and worker.isRunning()

    def _next_request_id(self) -> int:
        self._request_sequence += 1
        return self._request_sequence

    def _on_discovery_finished(self, worker: TransactionDiscoveryWorker) -> None:
        """현재 등록된 동일 discovery worker 종료 시에만 strong reference를 제거합니다."""
        if self._discovery_worker is worker:
            self._discovery_worker = None

    def _on_worker_terminated(
        self,
        session_name: str,
        worker: TransactionSessionWorker,
    ) -> None:
        """현재 등록된 동일 worker가 종료된 경우에만 registry reference를 제거합니다."""
        if self._workers.get(session_name) is worker:
            self._workers.pop(session_name, None)
