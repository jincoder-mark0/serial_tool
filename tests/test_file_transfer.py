"""FileTransferService 엔진 자체의 direct-signal 동작을 검증합니다."""
import time

import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialFlowControl, SerialParity, SerialStopBits
from model.connection_controller import ConnectionController
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
    def __init__(self, queue_size: int = 0, send_succeeds: bool = True):
        self.queue_size = queue_size
        self.send_succeeds = send_succeeds
        self.sent_chunks = []
        self.registered = []
        self.unregistered = []
        self.queue_size_query_count = 0

    def register_file_transfer(self, port_name, service):
        self.registered.append(port_name)

    def unregister_file_transfer(self, port_name):
        self.unregistered.append(port_name)

    def get_write_queue_size(self, port_name) -> int:
        self.queue_size_query_count += 1
        return self.queue_size

    def send_data_to_connection(self, port_name, chunk) -> bool:
        if not self.send_succeeds:
            return False
        self.sent_chunks.append(chunk)
        return True


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
        controller.close_connection()


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
    assert "SOME_PORT" not in controller._active_file_transfers


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


def test_backpressure_loop_waits_while_queue_exceeds_threshold(qapp, tmp_path, monkeypatch):
    content = b"B" * 100
    file_path = tmp_path / "backpressure.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("FAKE_PORT")
    controller = _FakeConnectionController(queue_size=60)
    sleep_calls = []

    def _fake_sleep(seconds):
        sleep_calls.append(seconds)
        controller.queue_size = max(0, controller.queue_size - 20)

    monkeypatch.setattr("model.file_transfer_service.time.sleep", _fake_sleep)

    service = FileTransferService(controller, str(file_path), config)
    completed = []
    service.signals.transfer_completed.connect(completed.append)
    service.run()

    assert sleep_calls
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
