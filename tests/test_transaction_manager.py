"""TransactionManager / TransactionSessionWorker runtime lifecycle tests."""
from __future__ import annotations

import time
from dataclasses import dataclass
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
