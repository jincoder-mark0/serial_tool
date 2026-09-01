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
from core.transport.transaction.errors import TransactionCancelledError
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
                    stopping = self._stop_requested
                    if not stopping:
                        self._active_token = token

                if stopping:
                    # 이 command는 이미 큐에서 꺼낸 뒤다 — 여기서 통지하지 않으면
                    # `_fail_pending_transactions()`의 큐 드레인도 놓친다 (S-085).
                    self._fail_transaction(
                        command.request_id,
                        "Session closed before the transaction started.",
                    )
                    break

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
            # 큐에 남은 request에도 결과를 돌려준 뒤에 세션을 닫는다 (S-084).
            # 순서가 중요하다 — session_closed보다 먼저 보내야 소비자가
            # "이 요청은 실패"와 "세션이 끝남"을 구분해 처리할 수 있다.
            self._fail_pending_transactions()
            self._close_runtime(controller, handle)
            self.session_closed.emit(self.session_name)
            self.worker_terminated.emit(self.session_name)

    def _fail_pending_transactions(self) -> None:
        """큐에 남은 transaction에 실패를 통지하고 큐를 비웁니다 (S-084).

        Why:
            `execute()`는 호출자에게 request ID를 돌려준다 — 결과를 신호로 받겠다는
            약속이다. 그런데 세션이 닫히면 실행 중이던 1건만 `transaction_failed`를
            받고, **큐에 남아 있던 나머지는 완료도 실패도 없이 사라졌다.**
            실측: request ID 4건을 발급하고 세션을 닫으면 1번만 응답하고 2·3·4번은
            2초를 기다려도 아무 신호가 없었다. 그 뒤에 오는 것은 request ID가 없는
            `session_closed`/`worker_terminated`뿐이라 어느 요청이 버려졌는지 알 수 없다.

            결과를 기다리는 호출자는 영원히 기다리게 되고, 사용자에게는 오류 표시조차
            뜨지 않는다 — 보내지 못한 명령이 조용히 사라지는 것이다.

        Note:
            비우는 동안 큐가 다시 늘지 않도록 먼저 신규 request를 차단한다.
            `stop()`을 거치지 않고 interruption만 걸린 경로에서도 안전해야 한다.
        """
        with self._state_lock:
            self._stop_requested = True

        while True:
            try:
                command = self._commands.get_nowait()
            except Empty:
                break

            self._fail_transaction(
                command.request_id,
                "Session closed before the transaction started.",
            )

    def _fail_transaction(self, request_id: int, message: str) -> None:
        """실행되지 못한 transaction에 취소 실패를 통지합니다."""
        self.transaction_failed.emit(
            self.session_name,
            request_id,
            TransactionCancelledError(message),
        )

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
            except Exception:
                pass

        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
