"""FileTransferService 엔진 자체의 direct-signal 동작을 검증합니다."""
import time

import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialFlowControl, SerialParity, SerialStopBits
from core.transport.base_transport import BaseTransport
from model.connection_controller import ConnectionController
from model.connection_worker import ConnectionWorker
from model.file_transfer_service import FileTransferService


@pytest.fixture
def loopback_config() -> PortConfig:
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


def _rts_cts_config(port: str, baudrate: int = 115200) -> PortConfig:
    return PortConfig(
        port=port,
        baudrate=baudrate,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.RTS_CTS.value,
    )


class _FakeConnectionController:
    """FileTransferService가 실제로 사용하는 queue/send 계약만 구현합니다."""

    def __init__(self, queue_size: int = 0, send_succeeds: bool = True):
        self.queue_size = queue_size
        self.send_succeeds = send_succeeds
        self.sent_chunks = []
        self.queue_size_query_count = 0
        self.write_idle = True
        self.write_error = None

    def get_write_queue_size(self, port_name) -> int:
        self.queue_size_query_count += 1
        return self.queue_size

    def is_write_idle(self, port_name) -> bool:
        return self.write_idle and self.queue_size == 0

    def is_connection_open(self, port_name) -> bool:
        return True

    def get_write_error(self, port_name):
        return self.write_error

    def send_data_to_connection(self, port_name, chunk) -> bool:
        if not self.send_succeeds:
            return False
        self.sent_chunks.append(chunk)
        return True


class _DelayedIdleController(_FakeConnectionController):
    def __init__(self):
        super().__init__()
        self.idle_query_count = 0

    def is_write_idle(self, port_name) -> bool:
        self.idle_query_count += 1
        return self.idle_query_count >= 3


class _FailingWriteTransport(BaseTransport):
    def __init__(self):
        self._open = False

    def open(self) -> bool:
        self._open = True
        return True

    def close(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def read(self, size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        raise OSError("simulated device write failure")

    @property
    def in_waiting(self) -> int:
        return 0

def test_successful_transfer_over_loopback_delivers_bytes_in_order(qapp, tmp_path):
    content = bytes((index % 256) for index in range(5000))
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config(LOOPBACK_PORT_NAME)
    controller = ConnectionController()
    completed = []
    errors = []
    progresses = []

    try:
        assert controller.open_connection(config) is True
        worker = controller.workers[LOOPBACK_PORT_NAME]
        written = []
        original_write = worker.transport.write

        def _spy_write(data: bytes) -> None:
            written.append(data)
            original_write(data)

        worker.transport.write = _spy_write

        service = FileTransferService(controller, str(file_path), config)
        service.signals.transfer_completed.connect(completed.append)
        service.signals.error_occurred.connect(errors.append)
        service.signals.progress_updated.connect(progresses.append)
        service.run()

        deadline = time.monotonic() + 2.0
        while b"".join(written) != content and time.monotonic() < deadline:
            time.sleep(0.01)

        assert errors == []
        assert len(completed) == 1
        assert completed[0].success is True
        assert b"".join(written) == content
        assert progresses[-1].sent_bytes == len(content)
        assert progresses[-1].total_bytes == len(content)
    finally:
        controller.close_all_and_wait()


def test_missing_file_emits_error_and_failed_completion(qapp, tmp_path):
    missing_path = str(tmp_path / "does_not_exist.bin")
    config = _rts_cts_config("SOME_PORT")
    controller = ConnectionController()
    completed = []
    errors = []

    service = FileTransferService(controller, missing_path, config)
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)
    service.run()

    assert len(errors) == 1
    assert "not found" in errors[0].message.lower()
    assert len(completed) == 1
    assert completed[0].success is False


def test_completion_waits_for_in_flight_transport_write(qapp, tmp_path):
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(b"PAYLOAD")
    controller = _DelayedIdleController()
    config = _rts_cts_config("COM1")
    service = FileTransferService(controller, str(file_path), config)
    completed = []
    service.signals.transfer_completed.connect(completed.append)

    service.run()

    assert controller.idle_query_count == 3
    assert completed[-1].success is True


def test_transport_write_failure_cannot_report_success(qapp, tmp_path):
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(b"PAYLOAD")
    controller = _FakeConnectionController()
    controller.write_error = "simulated timeout"
    config = _rts_cts_config("COM1")
    service = FileTransferService(controller, str(file_path), config)
    completed = []
    errors = []
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)

    service.run()

    assert errors
    assert "simulated timeout" in errors[-1].message
    assert completed[-1].success is False


def test_real_worker_write_failure_reaches_file_transfer_completion(qapp, tmp_path):
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(b"PAYLOAD")
    config = _rts_cts_config("COM_FAIL")
    controller = ConnectionController()
    worker = ConnectionWorker(_FailingWriteTransport(), config.port)
    controller.session_factory.create_worker = lambda _config: worker
    completed = []
    errors = []

    try:
        assert controller.open_connection(config) is True
        service = FileTransferService(controller, str(file_path), config)
        service.signals.transfer_completed.connect(completed.append)
        service.signals.error_occurred.connect(errors.append)

        service.run()

        assert errors
        assert "simulated device write failure" in errors[-1].message
        assert completed[-1].success is False
    finally:
        controller.close_all_and_wait()


def test_cancel_stops_before_remaining_chunks_and_emits_failed_completion(qapp, tmp_path):
    chunk_size = 1024
    content = b"A" * (chunk_size * 3)
    file_path = tmp_path / "cancel_me.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("FAKE_PORT")
    controller = _FakeConnectionController()
    service = FileTransferService(controller, str(file_path), config)
    completed = []
    errors = []
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)
    service.signals.progress_updated.connect(lambda _state: service.cancel())

    service.run()

    assert len(controller.sent_chunks) == 1
    assert controller.sent_chunks[0] == content[:chunk_size]
    assert len(errors) == 1
    assert "cancel" in errors[0].message.lower()
    assert len(completed) == 1
    assert completed[0].success is False


def test_cancel_interrupts_long_baudrate_wait_immediately(tmp_path):
    file_path = tmp_path / "slow.bin"
    file_path.write_bytes(b"A")
    service = FileTransferService(
        _FakeConnectionController(),
        str(file_path),
        PortConfig(port="SLOW", baudrate=50),
    )

    service.cancel()
    started = time.monotonic()
    was_cancelled = service._wait_or_cancel(60.0)
    elapsed = time.monotonic() - started

    assert was_cancelled is True
    assert elapsed < 0.1


def test_backpressure_loop_waits_while_queue_exceeds_threshold(qapp, tmp_path, monkeypatch):
    content = b"B" * 100
    file_path = tmp_path / "backpressure.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("FAKE_PORT")
    controller = _FakeConnectionController(queue_size=60)
    wait_calls = []
    service = FileTransferService(controller, str(file_path), config)

    def _fake_wait(seconds):
        wait_calls.append(seconds)
        controller.queue_size = max(0, controller.queue_size - 20)
        return False

    monkeypatch.setattr(service, "_wait_or_cancel", _fake_wait)

    completed = []
    service.signals.transfer_completed.connect(completed.append)
    service.run()

    assert wait_calls
    assert controller.sent_chunks == [content]
    assert controller.queue_size == 0
    assert len(completed) == 1
    assert completed[0].success is True


def test_send_failure_emits_error_and_failed_completion(qapp, tmp_path):
    file_path = tmp_path / "fail.bin"
    file_path.write_bytes(b"X" * 10)

    config = _rts_cts_config("DEAD_PORT")
    controller = _FakeConnectionController(send_succeeds=False)
    service = FileTransferService(controller, str(file_path), config)
    completed = []
    errors = []
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)

    service.run()

    assert controller.sent_chunks == []
    assert len(errors) == 1
    assert "DEAD_PORT" in errors[0].message
    assert len(completed) == 1
    assert completed[0].success is False
