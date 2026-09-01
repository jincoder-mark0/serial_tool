"""TransactionManager / TransactionSessionWorker runtime lifecycle tests."""
from __future__ import annotations

import time
from dataclasses import dataclass
from queue import Queue
from threading import Event

import pytest
from PyQt5.QtCore import QCoreApplication

from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.contracts import (
    AdapterHandle,
    AdapterProvider,
    I2cController,
    SpiController,
)
from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.dto import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterIdentity,
    I2cCapabilities,
    I2cConfig,
    I2cTransactionRequest,
    I2cTransactionResult,
    SpiCapabilities,
    SpiConfig,
    SpiTransactionRequest,
    SpiTransactionResult,
    TransactionProtocol,
)
from core.transport.transaction.errors import TransactionCancelledError
from core.transport.transaction.registry import AdapterBackendRegistry
from model.transaction_manager import TransactionManager
from model.transaction_session_worker import TransactionSessionWorker


def _wait_until(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return bool(predicate())


class _FakeSpiController(SpiController):
    def __init__(self, block: bool = False) -> None:
        self.closed = False
        self.block = block
        self.started = Event()

    def transact(
        self,
        request: SpiTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> SpiTransactionResult:
        self.started.set()
        if self.block:
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if cancellation is not None and cancellation.is_cancelled:
                    raise TransactionCancelledError("cancelled")
                time.sleep(0.005)
        return SpiTransactionResult(
            rx_data=request.tx_data or bytes(request.rx_length),
            actual_frequency_hz=1_000_000,
        )

    def close(self) -> None:
        self.closed = True


class _FakeI2cController(I2cController):
    def __init__(self) -> None:
        self.closed = False

    def transact(
        self,
        request: I2cTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> I2cTransactionResult:
        return I2cTransactionResult(
            read_data=bytes([0xA5] * request.read_length),
            actual_frequency_hz=100_000,
        )

    def close(self) -> None:
        self.closed = True


class _FakeHandle(AdapterHandle):
    def __init__(self, descriptor: AdapterDescriptor, spi: _FakeSpiController) -> None:
        self._descriptor = descriptor
        self.spi = spi
        self.i2c = _FakeI2cController()
        self.closed = False

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def open_spi(self, config: SpiConfig) -> SpiController:
        return self.spi

    def open_i2c(self, config: I2cConfig) -> I2cController:
        return self.i2c

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakeProvider(AdapterProvider):
    descriptor: AdapterDescriptor
    spi: _FakeSpiController

    @property
    def backend_id(self) -> str:
        return "fake"

    def is_available(self) -> bool:
        return True

    def enumerate(self):
        return [self.descriptor]

    def open(self, identity: AdapterIdentity) -> AdapterHandle:
        assert identity == self.descriptor.identity
        return _FakeHandle(self.descriptor, self.spi)


def _descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        identity=AdapterIdentity("fake", "adapter-1"),
        device_family="FakeAdapter",
        display_name="Fake Adapter",
        capabilities=AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI, TransactionProtocol.I2C}),
            spi=SpiCapabilities(
                min_frequency_hz=1_000,
                max_frequency_hz=10_000_000,
            ),
            i2c=I2cCapabilities(
                min_frequency_hz=10_000,
                max_frequency_hz=400_000,
            ),
        ),
    )


def _spi_config() -> TransactionConnectionConfig:
    return TransactionConnectionConfig(
        name="fixture-spi",
        protocol=TransactionProtocol.SPI,
        adapter=AdapterIdentity("fake", "adapter-1"),
        spi=SpiConfig(frequency_hz=1_000_000),
    )


@pytest.fixture
def app():
    instance = QCoreApplication.instance()
    return instance or QCoreApplication([])


def test_async_discovery_emits_vendor_neutral_descriptors(app):
    descriptor = _descriptor()
    manager = TransactionManager(
        AdapterBackendRegistry([_FakeProvider(descriptor, _FakeSpiController())])
    )
    found = []
    manager.adapters_found.connect(lambda descriptors: found.extend(descriptors))

    assert manager.request_discovery() is True
    assert _wait_until(lambda: found == [descriptor])
    assert _wait_until(lambda: not manager.is_discovering)
    assert manager.shutdown() is True


def test_manager_executes_spi_transaction_and_emits_result(app):
    spi = _FakeSpiController()
    manager = TransactionManager(
        AdapterBackendRegistry([_FakeProvider(_descriptor(), spi)])
    )
    opened = []
    completed = []
    manager.session_opened.connect(lambda name, desc: opened.append((name, desc)))
    manager.transaction_completed.connect(
        lambda name, request_id, result: completed.append((name, request_id, result))
    )

    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: len(opened) == 1)

    request_id = manager.execute(
        "fixture-spi",
        SpiTransactionRequest(tx_data=b"\x9f"),
    )

    assert request_id == 1
    assert _wait_until(lambda: len(completed) == 1)
    assert completed[0][0] == "fixture-spi"
    assert completed[0][1] == request_id
    assert completed[0][2].rx_data == b"\x9f"
    assert manager.shutdown() is True


def test_manager_rejects_protocol_mismatched_request(app):
    manager = TransactionManager(
        AdapterBackendRegistry([_FakeProvider(_descriptor(), _FakeSpiController())])
    )
    opened = []
    manager.session_opened.connect(lambda name, desc: opened.append(name))

    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: opened == ["fixture-spi"])

    request_id = manager.execute(
        "fixture-spi",
        I2cTransactionRequest(read_length=1),
    )

    assert request_id is None
    assert manager.shutdown() is True


def test_cancel_active_transaction_is_thread_safe(app):
    spi = _FakeSpiController(block=True)
    manager = TransactionManager(
        AdapterBackendRegistry([_FakeProvider(_descriptor(), spi)])
    )
    opened = []
    failed = []
    manager.session_opened.connect(lambda name, desc: opened.append(name))
    manager.transaction_failed.connect(
        lambda name, request_id, error: failed.append((name, request_id, error))
    )

    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: opened == ["fixture-spi"])
    request_id = manager.execute(
        "fixture-spi",
        SpiTransactionRequest(tx_data=b"\x01"),
    )
    assert request_id == 1
    assert spi.started.wait(0.5)

    assert manager.cancel_active("fixture-spi") is True
    assert _wait_until(lambda: len(failed) == 1)
    assert isinstance(failed[0][2], TransactionCancelledError)
    assert manager.shutdown() is True


def test_duplicate_session_name_is_rejected_until_close(app):
    manager = TransactionManager(
        AdapterBackendRegistry([_FakeProvider(_descriptor(), _FakeSpiController())])
    )
    opened = []
    manager.session_opened.connect(lambda name, desc: opened.append(name))

    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: opened == ["fixture-spi"])
    assert manager.open_session(_spi_config()) is False

    assert manager.close_session("fixture-spi") is True
    assert _wait_until(lambda: not manager.is_session_active("fixture-spi"))


def test_queued_transactions_are_answered_when_session_closes(app):
    """
    큐에 남은 transaction도 결과를 받아야 한다 (S-084).

    ## WHY
    `execute()`는 호출자에게 request ID를 돌려준다 — 결과를 신호로 받겠다는 약속이다.
    그런데 세션이 닫히면 **실행 중이던 1건만** `transaction_failed`를 받고, 큐에
    남아 있던 나머지는 완료도 실패도 없이 사라졌다.

    실측: request ID 4건을 발급하고 세션을 닫으면 1번만 응답하고 2·3·4번은 2초를
    기다려도 아무 신호가 없었다. 그 뒤 오는 것은 request ID가 없는
    `session_closed`/`worker_terminated`뿐이라 어느 요청이 버려졌는지 알 수 없다.

    결과를 기다리는 호출자는 영원히 기다리고, 사용자에게는 오류 표시조차 뜨지 않는다 —
    보내지 못한 명령이 조용히 사라진다. `MacroSendResult`(S-080)가 매크로에서 없앤 것과
    같은 종류의 침묵이다.
    """
    spi = _FakeSpiController(block=True)
    manager = TransactionManager(
        registry=AdapterBackendRegistry([_FakeProvider(_descriptor(), spi)]),
    )
    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: manager.is_session_active("fixture-spi"))

    answered: list[int] = []
    manager.transaction_completed.connect(lambda _n, rid, _r: answered.append(rid))
    manager.transaction_failed.connect(lambda _n, rid, _e: answered.append(rid))

    issued = [
        manager.execute("fixture-spi", SpiTransactionRequest(tx_data=b"\x01", rx_length=1))
        for _ in range(4)
    ]
    assert all(rid is not None for rid in issued)
    assert spi.started.wait(1.0)

    manager.close_session("fixture-spi", timeout_ms=1000)
    _wait_until(lambda: set(issued) <= set(answered), timeout=2.0)

    assert set(issued) <= set(answered), (
        f"응답 없이 사라진 request ID: {sorted(set(issued) - set(answered))}"
    )
    manager.shutdown()


def test_pending_failures_are_reported_before_session_closed(app):
    """
    개별 실패 통지가 `session_closed`보다 먼저 와야 한다.

    순서가 뒤집히면 소비자는 세션이 끝난 줄 알고 정리를 마친 뒤에 결과를 받는다 —
    "이 요청은 실패"와 "세션이 끝남"을 구분해 처리할 수 없다.
    """
    spi = _FakeSpiController(block=True)
    manager = TransactionManager(
        registry=AdapterBackendRegistry([_FakeProvider(_descriptor(), spi)]),
    )
    assert manager.open_session(_spi_config()) is True
    assert _wait_until(lambda: manager.is_session_active("fixture-spi"))

    order: list[str] = []
    worker = manager._workers["fixture-spi"]
    worker.transaction_failed.connect(lambda *_: order.append("failed"))
    worker.session_closed.connect(lambda *_: order.append("closed"))

    for _ in range(3):
        manager.execute("fixture-spi", SpiTransactionRequest(tx_data=b"\x01", rx_length=1))
    assert spi.started.wait(1.0)

    manager.close_session("fixture-spi", timeout_ms=1000)
    _wait_until(lambda: "closed" in order, timeout=2.0)

    assert "closed" in order, f"세션 종료 신호가 오지 않았다: {order}"
    assert order.index("closed") == len(order) - 1, (
        f"session_closed 뒤에 개별 실패가 왔다: {order}"
    )
    manager.shutdown()


class _StopOnFirstGetQueue(Queue):
    """첫 `get()`이 command를 돌려준 **직후**에 stop()이 도착하는 큐.

    Worker는 `_commands.get()`으로 command를 꺼낸 뒤에야 state lock을 잡고
    `_stop_requested`를 확인한다. 그 사이는 실제로 열려 있는 창이고, 여기서
    stop()이 들어오면 이미 꺼내진 command가 어디에도 속하지 않게 된다.
    운에 맡기면 재현이 들쭉날쭉하므로 그 인터리빙을 고정한다.
    """

    def __init__(self) -> None:
        super().__init__()
        self.worker: TransactionSessionWorker | None = None
        self.armed = False

    def get(self, *args, **kwargs):
        item = super().get(*args, **kwargs)
        if self.armed and self.worker is not None:
            self.armed = False
            self.worker.stop()
        return item


def test_dequeued_transaction_is_answered_when_stop_arrives_mid_loop(app):
    """
    큐에서 꺼낸 직후 stop()이 와도 그 transaction은 통지를 받아야 한다 (S-085).

    ## WHY
    S-084는 **큐에 남은** request를 통지하도록 고쳤지만, 창이 하나 더 있었다.
    worker는 `get()`으로 command를 꺼낸 다음 lock을 잡고 `_stop_requested`를
    확인해 `break` 한다. 그 command는 이미 큐 밖이라 종료 시 큐를 비우는
    `_fail_pending_transactions()`도 잡지 못한다.

    실측: 이 인터리빙을 고정하면 발급한 ID 3건 중 1번이 완료도 실패도 없이
    사라졌다(`answered: [2, 3]`). S-084가 없앤 것과 같은 침묵이 경로 하나에
    남아 있던 것이다.
    """
    spi = _FakeSpiController()
    registry = AdapterBackendRegistry([_FakeProvider(_descriptor(), spi)])
    worker = TransactionSessionWorker(registry, _spi_config())

    # start() 전에 갈아끼워야 worker thread가 옛 큐에서 대기하는 일이 없다.
    hooked = _StopOnFirstGetQueue()
    hooked.worker = worker
    worker._commands = hooked

    answered: list[int] = []
    worker.transaction_completed.connect(lambda _n, rid, _r: answered.append(rid))
    worker.transaction_failed.connect(lambda _n, rid, _e: answered.append(rid))

    opened: list[str] = []
    worker.session_opened.connect(lambda name, _d: opened.append(name))
    worker.start()
    assert _wait_until(lambda: bool(opened)), "세션이 열리지 않았다"

    hooked.armed = True
    issued = [rid for rid in (1, 2, 3)
              if worker.enqueue_transaction(rid, SpiTransactionRequest(tx_data=b"", rx_length=1))]
    assert issued == [1, 2, 3]

    assert worker.wait(2000), "worker가 종료되지 않았다"
    _wait_until(lambda: set(issued) <= set(answered), timeout=2.0)

    assert set(issued) <= set(answered), (
        f"응답 없이 사라진 request ID: {sorted(set(issued) - set(answered))} "
        f"(큐에서 꺼낸 뒤 stop()이 오면 그 건은 큐 드레인도 놓친다)"
    )
