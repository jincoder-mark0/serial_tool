"""
S-045 커버리지 테스트: FileTransferService (model/file_transfer_service.py)

## WHY
* `FileTransferService`는 기존 테스트가 0건이었다. Backpressure 루프, 취소,
  완료/에러 이벤트 발행처럼 상태에 따라 분기하는 로직은 코드 정독만으로는
  경로 누락(예: 취소 시 최종 드레인 대기를 건너뛰는지)을 확신할 수 없다.
* S-044가 `common/enums.py` 정리를 진행 중이므로, 이 태스크에서는
  `model/file_transfer_service.py`의 **코드는 수정하지 않고 테스트만 추가**한다.

## WHAT
* 실제 LOOPBACK 포트 + 임시 파일로 종단 간(end-to-end) 전송 왕복을 검증
  (전송된 바이트가 순서대로 transport까지 도달하는지, 완료 이벤트/시그널).
* 파일 없음 → 에러/실패 완료 이벤트 발행.
* 취소(cancel) → 남은 청크를 보내지 않고 즉시 실패 완료 이벤트로 종료.
* Backpressure 루프 → 큐가 임계값(50)을 초과하면 대기하다가 임계값 아래로
  내려가야 다음 청크를 전송하는지 (Fake 컨트롤러로 큐 크기를 결정론적으로 제어).
* 전송 실패(`send_data_to_connection` 실패) → 예외 경로의 에러/완료 이벤트 발행.

## HOW
* `FileTransferService`는 `QRunnable`이지만 `run()`은 평범한 메서드이므로,
  `QThreadPool`을 거치지 않고 테스트 스레드에서 직접 `run()`을 호출해
  결정론적으로 검증한다 (동일 스레드이므로 PyQt 시그널은 Direct Connection으로
  동기 처리됨).
* Backpressure/취소/에러 테스트는 실제 하드웨어 큐 타이밍에 의존하지 않도록
  `ConnectionController`를 흉내 낸 가벼운 Fake 더블을 사용한다
  (`register_file_transfer`/`unregister_file_transfer`/`get_write_queue_size`/
  `send_data_to_connection`만 덕타이핑으로 제공하면 충분하다).
* 실제 왕복 검증(성공 케이스)은 `tests/test_tx_flush.py`와 동일하게
  진짜 `ConnectionController` + `LoopbackTransport`를 사용한다.
"""
import time

import pytest

from common.constants import EventTopics, LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.event_bus import event_bus
from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def loopback_config() -> PortConfig:
    """LOOPBACK 포트용 PortConfig. flowctrl=None (Speed Control 경로 사용)."""
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


def _rts_cts_config(port: str, baudrate: int = 115200) -> PortConfig:
    """
    Speed Control(time.sleep(wait_time)) 경로를 건너뛰기 위해
    flowctrl="RTS/CTS"로 설정한 PortConfig (하드웨어 핸드셰이킹을 신뢰하는
    분기라 코드상 sleep이 발생하지 않는다 - 테스트 결정성/속도 확보 목적).
    """
    return PortConfig(
        port=port,
        baudrate=baudrate,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl="RTS/CTS",
    )


class _FakeConnectionController:
    """
    ConnectionController를 흉내 낸 최소 Fake 더블.

    FileTransferService.run()이 실제로 호출하는 4개 메서드만 덕타이핑으로
    제공한다. Backpressure/취소/에러 경로를 실제 스레드 타이밍 없이
    결정론적으로 재현하기 위해 사용한다.
    """

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


# -----------------------------------------------------------------------------
# 1. 실제 LOOPBACK 왕복 (End-to-End)
# -----------------------------------------------------------------------------

def test_successful_transfer_over_loopback_delivers_bytes_in_order(qapp, tmp_path):
    """
    LOOPBACK + 임시 파일로 실제 전송 왕복을 검증한다: 파일 내용이 청크 단위로
    분할되어 순서대로 transport.write()까지 도달하고, 성공 완료 이벤트/시그널이
    발행되는지 확인한다.
    """
    content = bytes((i % 256) for i in range(5000))  # 여러 청크(1024B)로 분할됨
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config(LOOPBACK_PORT_NAME)
    controller = ConnectionController()

    completed = []
    errors = []
    progresses = []
    bus_completed = []
    event_bus.subscribe(EventTopics.FILE_COMPLETED, bus_completed.append)

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

        service.run()  # QThreadPool 없이 직접 호출 (동기 실행)

        # 워커가 큐를 실제로 write()까지 드레인할 시간을 짧게 대기
        deadline = time.monotonic() + 2.0
        while b"".join(written) != content and time.monotonic() < deadline:
            time.sleep(0.01)

        assert errors == []
        assert len(completed) == 1
        assert completed[0].success is True
        assert completed[0].file_path == str(file_path)

        assert b"".join(written) == content

        assert len(progresses) >= 1
        assert progresses[-1].sent_bytes == len(content)
        assert progresses[-1].total_bytes == len(content)

        assert len(bus_completed) == 1
        assert bus_completed[0].success is True
    finally:
        controller.close_connection()


# -----------------------------------------------------------------------------
# 2. 파일 없음 → 에러 + 실패 완료
# -----------------------------------------------------------------------------

def test_missing_file_emits_error_and_failed_completion(qapp, tmp_path):
    """존재하지 않는 파일 경로로 전송을 시도하면 error_occurred + 실패 완료가 발행된다."""
    missing_path = str(tmp_path / "does_not_exist.bin")
    config = _rts_cts_config("SOME_PORT")
    controller = ConnectionController()  # 포트를 열지 않아도 register/unregister는 동작함

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

    # register/unregister 쌍이 정상적으로 호출되어 레지스트리에 남지 않음
    assert "SOME_PORT" not in controller._active_file_transfers


# -----------------------------------------------------------------------------
# 3. 취소 → 남은 청크 미전송 + 실패 완료
# -----------------------------------------------------------------------------

def test_cancel_stops_before_remaining_chunks_and_emits_failed_completion(qapp, tmp_path):
    """
    첫 청크 전송 직후(progress_updated 콜백에서) cancel()을 호출하면,
    남은 청크는 전송되지 않고 곧바로 실패("cancelled") 완료 이벤트가 발행된다.
    """
    chunk_size = 1024  # baudrate<=115200 -> FileTransferService의 청크 크기
    content = b"A" * (chunk_size * 3)  # 3개 청크 분량
    file_path = tmp_path / "cancel_me.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("FAKE_PORT")
    fake_controller = _FakeConnectionController(queue_size=0, send_succeeds=True)

    service = FileTransferService(fake_controller, str(file_path), config)

    completed = []
    errors = []
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)

    def _cancel_after_first_progress(_state):
        service.cancel()

    service.signals.progress_updated.connect(_cancel_after_first_progress)

    service.run()

    # 취소 시점에 이미 큐에 들어간(=전송 시도된) 첫 청크 외에는 전송되지 않아야 함
    assert len(fake_controller.sent_chunks) == 1
    assert fake_controller.sent_chunks[0] == content[:chunk_size]

    assert len(errors) == 1
    assert "cancel" in errors[0].message.lower()

    assert len(completed) == 1
    assert completed[0].success is False
    assert "cancel" in completed[0].message.lower()


# -----------------------------------------------------------------------------
# 4. Backpressure 루프 — 큐가 임계값을 넘으면 대기 후 재시도
# -----------------------------------------------------------------------------

def test_backpressure_loop_waits_while_queue_exceeds_threshold(qapp, tmp_path, monkeypatch):
    """
    큐 크기가 임계값(50)을 초과하는 동안은 청크를 전송하지 않고 대기(sleep)하다가,
    임계값 아래로 내려간 뒤에야 send_data_to_connection이 호출되는지 확인한다.
    실제 시간 대기 없이 검증하기 위해 time.sleep을 가로채 큐 크기를 감소시킨다.
    """
    content = b"B" * 100  # 단일 청크 (chunk_size=1024보다 작음)
    file_path = tmp_path / "backpressure.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("FAKE_PORT")
    # 임계값(50) 초과 상태로 시작 -> Backpressure 대기 루프 진입 강제
    fake_controller = _FakeConnectionController(queue_size=60, send_succeeds=True)

    sleep_calls = []

    def _fake_sleep(seconds):
        sleep_calls.append(seconds)
        # 매 sleep 호출마다 큐가 줄어드는 것처럼 시뮬레이션 (실시간 대기 없음)
        fake_controller.queue_size = max(0, fake_controller.queue_size - 20)

    monkeypatch.setattr("model.file_transfer_service.time.sleep", _fake_sleep)

    service = FileTransferService(fake_controller, str(file_path), config)
    completed = []
    service.signals.transfer_completed.connect(completed.append)

    service.run()

    # Backpressure 대기가 실제로 발생했어야 함 (60 -> 40 하려면 최소 1회 sleep)
    assert len(sleep_calls) >= 1
    # 대기 후에는 정상적으로 청크가 전송됨
    assert fake_controller.sent_chunks == [content]
    # 최종적으로 큐가 완전히 빠질 때까지 기다린 뒤 성공 완료
    assert fake_controller.queue_size == 0
    assert len(completed) == 1
    assert completed[0].success is True


# -----------------------------------------------------------------------------
# 5. 전송 실패(send_data_to_connection == False) → 예외 경로
# -----------------------------------------------------------------------------

def test_send_failure_raises_and_emits_error_and_failed_completion(qapp, tmp_path):
    """
    `send_data_to_connection`이 실패(False)를 반환하면 포트 미오픈 예외로
    처리되어 error_occurred + 실패 완료 이벤트가 발행된다.
    """
    content = b"X" * 10
    file_path = tmp_path / "fail.bin"
    file_path.write_bytes(content)

    config = _rts_cts_config("DEAD_PORT")
    fake_controller = _FakeConnectionController(queue_size=0, send_succeeds=False)

    service = FileTransferService(fake_controller, str(file_path), config)
    completed = []
    errors = []
    service.signals.transfer_completed.connect(completed.append)
    service.signals.error_occurred.connect(errors.append)

    service.run()

    assert fake_controller.sent_chunks == []
    assert len(errors) == 1
    assert "DEAD_PORT" in errors[0].message
    assert len(completed) == 1
    assert completed[0].success is False
