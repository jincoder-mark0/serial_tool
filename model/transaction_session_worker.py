"""SPI/I2C transaction session worker.

## WHY
* Serial ``ConnectionWorker``는 stream polling / TX queue 모델이며 SPI/I2C transaction과
  실행 의미가 다름
* Adapter handle / protocol controller를 하나의 전용 thread에서 열고 닫아 vendor-native
  resource lifecycle을 명확하게 유지
* UI thread에서는 blocking USB transaction을 직접 실행하지 않음

## WHAT
* 하나의 ``TransactionConnectionConfig``에 대한 AdapterHandle / Controller lifecycle 소유
* Queue 기반 transaction request 직렬 실행
* thread-safe cooperative cancellation
* open / result / error / close signal 발행

## HOW
* ``QThread.run()`` 내부에서 adapter와 protocol controller를 생성
* Python ``Queue``로 request를 받아 순서대로 실행
* 현재 transaction의 ``CancellationToken``은 Lock으로 보호하여 다른 thread에서 즉시 cancel
* 종료 시 controller -> adapter handle 순서로 idempotent close
"""
from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.contracts import AdapterHandle, I2cController, SpiController
from core.transport.transaction.dto import (
    I2cTransactionRequest,
    SpiTransactionRequest,
    TransactionProtocol,
)
from core.transport.transaction.errors import TransactionAdapterError
from core.transport.transaction.registry import AdapterBackendRegistry


@dataclass(frozen=True)
class _TransactionCommand:
    """Worker queue에 전달되는 immutable transaction command."""

    request_id: int
    request: SpiTransactionRequest | I2cTransactionRequest
    options: TransactionOptions


class TransactionSessionWorker(QThread):
    """하나의 SPI/I2C adapter session을 전용 thread에서 실행합니다."""

    session_opened = pyqtSignal(str, object)
    transaction_completed = pyqtSignal(str, int, object)
    transaction_failed = pyqtSignal(str, int, object)
    session_failed = pyqtSignal(str, object)
    session_closed = pyqtSignal(str)
    worker_terminated = pyqtSignal(str)

    _QUEUE_WAIT_MS = 50

    def __init__(
        self,
        registry: AdapterBackendRegistry,
        config: TransactionConnectionConfig,
    ) -> None:
        super().__init__()
        self._registry = registry
        self._config = config
        self._commands: Queue[_TransactionCommand] = Queue()
        self._state_lock = Lock()
        self._stop_requested = False
        self._active_token: Optional[CancellationToken] = None

    @property
    def session_name(self) -> str:
        return self._config.name

    def enqueue_transaction(
        self,
        request_id: int,
        request: SpiTransactionRequest | I2cTransactionRequest,
        options: Optional[TransactionOptions] = None,
    ) -> bool:
        """Transaction을 worker queue에 추가합니다.

        Worker가 종료 요청을 받은 뒤에는 신규 request를 받지 않습니다. Request type은
        session protocol과 즉시 비교하여 잘못된 호출이 vendor backend까지 도달하지 않게 합니다.
        """
        if not self._request_matches_protocol(request):
            return False

        with self._state_lock:
            if self._stop_requested:
                return False

        self._commands.put(
            _TransactionCommand(
                request_id=request_id,
                request=request,
                options=options or TransactionOptions(),
            )
        )
        return True

    def cancel_active_transaction(self) -> bool:
        """현재 실행 중인 transaction에 cooperative cancellation을 요청합니다."""
        with self._state_lock:
            token = self._active_token
        if token is None:
            return False
        token.cancel()
        return True

    def stop(self) -> None:
        """신규 request를 차단하고 현재 transaction을 취소한 뒤 thread 종료를 요청합니다."""
        with self._state_lock:
            self._stop_requested = True
            token = self._active_token
        if token is not None:
            token.cancel()
        self.requestInterruption()

    def run(self) -> None:
        """Adapter/controller를 열고 queued transaction을 직렬 처리합니다."""
        handle: Optional[AdapterHandle] = None
        controller: Optional[SpiController | I2cController] = None

        try:
            descriptor = self._registry.resolve(self._config.adapter)
            handle = self._registry.open(self._config.adapter)
            controller = self._open_controller(handle)
            self.session_opened.emit(self.session_name, descriptor)

            while not self.isInterruptionRequested():
                try:
                    command = self._commands.get(timeout=self._QUEUE_WAIT_MS / 1000.0)
                except Empty:
                    continue

                token = CancellationToken()
                with self._state_lock:
                    if self._stop_requested:
                        break
                    self._active_token = token

                try:
                    result = controller.transact(
                        command.request,
                        options=command.options,
                        cancellation=token,
                    )
                    self.transaction_completed.emit(
                        self.session_name,
                        command.request_id,
                        result,
                    )
                except Exception as exc:
                    self.transaction_failed.emit(
                        self.session_name,
                        command.request_id,
                        exc,
                    )
                finally:
                    with self._state_lock:
                        if self._active_token is token:
                            self._active_token = None

        except Exception as exc:
            self.session_failed.emit(self.session_name, exc)
        finally:
            self._close_runtime(controller, handle)
            self.session_closed.emit(self.session_name)
            self.worker_terminated.emit(self.session_name)

    def _open_controller(
        self,
        handle: AdapterHandle,
    ) -> SpiController | I2cController:
        if self._config.protocol is TransactionProtocol.SPI:
            if self._config.spi is None:
                raise ValueError("SPI transaction session requires SpiConfig")
            return handle.open_spi(self._config.spi)

        if self._config.protocol is TransactionProtocol.I2C:
            if self._config.i2c is None:
                raise ValueError("I2C transaction session requires I2cConfig")
            return handle.open_i2c(self._config.i2c)

        raise ValueError(f"Unsupported transaction protocol: {self._config.protocol}")

    def _request_matches_protocol(
        self,
        request: SpiTransactionRequest | I2cTransactionRequest,
    ) -> bool:
        if self._config.protocol is TransactionProtocol.SPI:
            return isinstance(request, SpiTransactionRequest)
        if self._config.protocol is TransactionProtocol.I2C:
            return isinstance(request, I2cTransactionRequest)
        return False

    @staticmethod
    def _close_runtime(
        controller: Optional[SpiController | I2cController],
        handle: Optional[AdapterHandle],
    ) -> None:
        """부분 open 실패를 포함해 protocol controller와 adapter handle을 안전하게 정리합니다."""
        if controller is not None:
            try:
                controller.close()
            except TransactionAdapterError:
                pass
            except Exception:
                pass

        if handle is not None:
            try:
                handle.close()
            except TransactionAdapterError:
                pass
            except Exception:
                pass
