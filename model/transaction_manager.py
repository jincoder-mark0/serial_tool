"""SPI/I2C transaction runtime manager.

## WHY
* Presenter/View가 AdapterBackendRegistry나 QThread lifecycle을 직접 소유하지 않도록 함
* Session 이름 기준으로 open/execute/cancel/close API를 제공해 상위 계층의 vendor 의존 제거
* 앱 종료 시 모든 SPI/I2C worker를 bounded lifecycle로 정리할 단일 owner 필요

## WHAT
* TransactionSessionWorker 생성 / registry 관리
* request ID 발급 및 transaction 결과 중계
* session duplicate / stale worker cleanup
* 전체 session shutdown

## HOW
* Composition Root에서 ``AdapterBackendRegistry``와 함께 한 번 생성
* 각 session마다 전용 ``TransactionSessionWorker`` 생성
* worker signal을 manager public signal로 중계
* worker 종료 signal을 기준으로 내부 registry에서 strong reference 제거
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger
from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.control import TransactionOptions
from core.transport.transaction.dto import (
    AdapterDescriptor,
    I2cTransactionRequest,
    SpiTransactionRequest,
)
from core.transport.transaction.registry import AdapterBackendRegistry
from model.transaction_session_worker import TransactionSessionWorker


class TransactionManager(QObject):
    """SPI/I2C adapter session과 background transaction worker의 application owner."""

    session_opened = pyqtSignal(str, object)
    session_closed = pyqtSignal(str)
    session_failed = pyqtSignal(str, object)
    transaction_completed = pyqtSignal(str, int, object)
    transaction_failed = pyqtSignal(str, int, object)

    def __init__(self, registry: AdapterBackendRegistry) -> None:
        super().__init__()
        self._registry = registry
        self._workers: dict[str, TransactionSessionWorker] = {}
        self._request_sequence = 0

    @property
    def has_active_session(self) -> bool:
        """하나 이상의 transaction session worker가 살아 있으면 True."""
        return any(worker.isRunning() for worker in self._workers.values())

    def enumerate_adapters(self) -> list[AdapterDescriptor]:
        """현재 사용 가능한 adapter descriptor를 반환합니다.

        이 메서드는 registry의 동기 discovery API를 그대로 노출합니다. UI integration 단계에서는
        USB enumeration이 느린 환경을 고려해 별도 discovery worker/manager를 추가하고 Presenter는
        그 비동기 API만 사용하도록 전환합니다.
        """
        return list(self._registry.enumerate())

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

    def shutdown(self, timeout_ms: int = 2000) -> bool:
        """모든 transaction session을 취소/종료하고 worker reference를 정리합니다."""
        success = True
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

    def _on_worker_terminated(
        self,
        session_name: str,
        worker: TransactionSessionWorker,
    ) -> None:
        """현재 등록된 동일 worker가 종료된 경우에만 registry reference를 제거합니다."""
        if self._workers.get(session_name) is worker:
            self._workers.pop(session_name, None)
