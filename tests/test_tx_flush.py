"""
S-039 회귀 테스트: TX 데이터 유실 2건 (close 시 flush 부재 + write_timeout 무효)

## WHY
* `model/connection_worker.py`의 `run()`은 `while self.is_running():` 조건을
  루프 맨 위에서만 확인한다. `msleep(1)`(큐가 빈 상태) 중에 `stop()`이 플래그를
  내리면 TX 큐를 비우는 블록(run() 내부)을 한 번도 통과하지 못하고 `finally`로
  빠지며, 수정 전 `finally`는 RX 배치 버퍼만 flush하고 **TX 큐는 조용히 버렸다**.
  `send_data()`는 큐잉 성공 시점에 이미 `True`를 반환한 뒤라 호출자는 유실을
  알 수 없었다.
* `core/transport/serial_transport.py`의 `write_timeout=0`은 설치된 pyserial 3.5의
  Windows 구현(serialwin32.py)에서 쓰기 완료 확인(GetOverlappedResult)을 생략한
  채 성공을 보고한다 — 과거 주석("write_timeout=0으로 예외 전파, 유실 방지")과
  정반대로 동작한다.

## WHAT
* 단위: `ConnectionWorker._drain_write_queue_on_exit()`가
  (1) transport가 열려있으면 큐를 순서대로 모두 write()하고 에러를 내지 않는지,
  (2) transport가 이미 닫혀있으면 조용히 버리지 않고 `error_occurred`로 개수를
      표면화하는지,
  (3) write() 도중 예외가 발생하면 (실패한 청크 포함) 남은 개수를
      `error_occurred`로 표면화하는지
  를 직접 호출로 결정론적으로 검증한다.
* 통합: LOOPBACK 포트에 `send_data()` 직후 즉시 `close_connection()`을 호출해도
  (드레인 성공이든 표면화든) 데이터가 "조용히" 사라지지 않는지 종단 간으로 확인한다.
* `SerialTransport.open()`이 `write_timeout=0`이 아니라 `WRITE_TIMEOUT_S`
  (완료 확인 분기)로 `serial.Serial`을 생성하는지 확인한다.

## HOW
* 단위 테스트는 스레드를 시작하지 않고 `ConnectionWorker`를 직접 생성/조작한다
  (`tests/test_send_before_open_race.py`와 동일한 결정론적 스타일).
* 통합 테스트는 `qtbot.waitSignal`/`wait()`로 실제 스레드 종료를 동기적으로
  기다린 뒤 결과(전송 여부/에러 시그널)를 확인한다.
* `write_timeout` 테스트는 `conftest.py`의 `mock_serial_port` fixture로
  `serial.Serial` 생성자 호출 인자를 가로챈다.
"""
import pytest

from common.constants import LOOPBACK_PORT_NAME, WRITE_TIMEOUT_S
from common.dtos import PortConfig
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.transport.base_transport import BaseTransport
from core.transport.loopback_transport import LoopbackTransport
from core.transport.serial_transport import SerialTransport
from model.connection_controller import ConnectionController
from model.connection_worker import ConnectionWorker


@pytest.fixture
def loopback_config() -> PortConfig:
    """LOOPBACK 더미 포트용 PortConfig DTO."""
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


class _FlakyTransport(BaseTransport):
    """
    write() 호출 2번째부터 예외를 던지는 테스트 전용 Fake Transport.

    드레인 도중 write()가 실패하는 경로(예: write_timeout에 의한
    SerialTimeoutException)를 결정론적으로 재현하기 위해 사용한다.
    """

    def __init__(self):
        self._open = True
        self.written = []

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
        if len(self.written) >= 1:
            raise RuntimeError("simulated write timeout")
        self.written.append(data)

    @property
    def in_waiting(self) -> int:
        return 0


# -----------------------------------------------------------------------------
# 단위 테스트: _drain_write_queue_on_exit() 결정론적 검증 (스레드 미시작)
# -----------------------------------------------------------------------------

def test_drain_flushes_all_queued_chunks_in_order_when_transport_open():
    """
    transport가 열려있으면 큐에 쌓인 모든 청크를 순서대로 write()하고,
    드레인 후 큐는 비워지며 error_occurred는 발생하지 않는다 (항목 ②: 수량/순서).
    """
    transport = LoopbackTransport()
    transport.open()
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    errors = []
    worker.error_occurred.connect(errors.append)

    assert worker.send_data(b"A") is True
    assert worker.send_data(b"B") is True
    assert worker.send_data(b"C") is True
    assert worker.get_write_queue_size() == 3

    worker._drain_write_queue_on_exit()

    assert worker.get_write_queue_size() == 0
    # LoopbackTransport.write()는 버퍼에 순서대로 append하므로 읽어보면 순서 확인 가능
    assert transport.read(10) == b"ABC"
    assert errors == []  # 침묵 성공: 표면화할 에러가 없어야 함


def test_drain_is_noop_when_queue_already_empty():
    """큐가 비어있으면 drain은 아무 것도 하지 않고 에러도 내지 않는다."""
    transport = LoopbackTransport()
    transport.open()
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    errors = []
    worker.error_occurred.connect(errors.append)

    worker._drain_write_queue_on_exit()

    assert worker.get_write_queue_size() == 0
    assert errors == []


def test_drain_surfaces_error_when_transport_already_closed():
    """
    transport가 이미 닫혀 드레인이 불가능하면, 남은 항목을 조용히 버리지 않고
    개수를 error_occurred로 표면화한 뒤 큐를 비운다 (침묵 금지가 핵심).
    """
    transport = LoopbackTransport()
    # open() 호출 안 함 -> is_open() False
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    errors = []
    worker.error_occurred.connect(errors.append)

    assert worker.send_data(b"LOST1") is True
    assert worker.send_data(b"LOST2") is True
    assert worker.get_write_queue_size() == 2

    worker._drain_write_queue_on_exit()

    assert worker.get_write_queue_size() == 0  # 버려지되
    assert len(errors) == 1                    # 반드시 표면화됨
    assert "2" in errors[0]                    # 몇 건이 버려졌는지 메시지에 포함


def test_drain_surfaces_error_with_full_lost_count_when_write_raises():
    """
    write() 도중 예외가 발생하면(예: write_timeout으로 인한 타임아웃), 이미
    dequeue되어 큐 크기에 잡히지 않는 "실패한 청크 자신"까지 포함해 정확한
    유실 개수를 error_occurred로 표면화한다 (과소 집계 금지).
    """
    transport = _FlakyTransport()
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    errors = []
    worker.error_occurred.connect(errors.append)

    worker.send_data(b"OK")     # 1번째 write는 성공하도록 _FlakyTransport 설계
    worker.send_data(b"FAIL")   # 2번째 write에서 예외 발생
    worker.send_data(b"NEVER")  # 시도조차 못 함 (루프 중단)

    worker._drain_write_queue_on_exit()

    assert worker.get_write_queue_size() == 0
    assert transport.written == [b"OK"]  # 첫 청크만 실제로 나감
    assert len(errors) == 1
    # drained=1(OK), 유실=2("FAIL" 자신 + 아직 큐에 남아있던 "NEVER")
    assert "1 chunk(s) sent" in errors[0]
    assert "2 chunk(s) discarded" in errors[0]


# -----------------------------------------------------------------------------
# 통합 테스트: 실제 run() 스레드를 통한 종단 간 검증 (LOOPBACK, 즉시 종료)
# -----------------------------------------------------------------------------

def test_send_then_immediate_close_never_loses_data_silently(qapp, qtbot, loopback_config):
    """
    send_data() 직후 즉시 close_connection()을 호출해도, 보낸 바이트가
    (a) 실제로 transport.write()까지 도달했거나(드레인 성공)
    (b) 명시적으로 error_occurred가 발생(표면화)해야 한다.
    수정 전에는 msleep(1) 중 stop()이 걸리면 어느 쪽도 없이 조용히 사라졌다.
    """
    controller = ConnectionController()
    errors = []

    try:
        assert controller.open_connection(loopback_config) is True
        worker = controller.workers[LOOPBACK_PORT_NAME]
        worker.error_occurred.connect(errors.append)

        # transport.write()를 감싸서 실제로 도달한 바이트를 기록 (close()가
        # LoopbackTransport 내부 버퍼를 지우므로, close 이후에도 확인 가능하도록
        # 별도 리스트에 기록해 둔다)
        written = []
        original_write = worker.transport.write

        def _spy_write(data: bytes) -> None:
            written.append(data)
            original_write(data)

        worker.transport.write = _spy_write

        controller.send_data(LOOPBACK_PORT_NAME, b"IMMEDIATE_CLOSE")

        # 대기 없이 곧바로 종료 요청 (재현하려는 레이스: msleep(1) 도중 stop())
        controller.close_connection(LOOPBACK_PORT_NAME)

        qtbot.waitUntil(lambda: not controller.has_active_connection, timeout=2000)

        delivered = b"".join(written) == b"IMMEDIATE_CLOSE"
        surfaced = len(errors) > 0

        assert delivered or surfaced, (
            "데이터가 write()로 전달되지도, error_occurred로 표면화되지도 않았다 "
            "(침묵 유실 발생)"
        )
    finally:
        controller.close_connection()


def test_multiple_sends_then_immediate_close_preserve_order_or_surface(qapp, qtbot, loopback_config):
    """
    여러 청크를 큐에 넣고 즉시 종료해도, 실제로 도달한 청크는 순서가 보존되고
    (일부만 도달한 경우 포함), 아무것도 도달하지 못했다면 반드시 에러가
    표면화된다 (항목 ②: 여러 건 + 즉시 종료).
    """
    controller = ConnectionController()
    errors = []

    try:
        assert controller.open_connection(loopback_config) is True
        worker = controller.workers[LOOPBACK_PORT_NAME]
        worker.error_occurred.connect(errors.append)

        written = []
        original_write = worker.transport.write

        def _spy_write(data: bytes) -> None:
            written.append(data)
            original_write(data)

        worker.transport.write = _spy_write

        controller.send_data(LOOPBACK_PORT_NAME, b"1")
        controller.send_data(LOOPBACK_PORT_NAME, b"2")
        controller.send_data(LOOPBACK_PORT_NAME, b"3")

        controller.close_connection(LOOPBACK_PORT_NAME)

        qtbot.waitUntil(lambda: not controller.has_active_connection, timeout=2000)

        joined = b"".join(written)
        # 도달한 것은 항상 접두어 형태로 순서가 보존되어야 한다 (뒤섞임 금지)
        assert b"123".startswith(joined)
        if joined != b"123":
            # 일부만 도달했다면(레이스로 조기 종료) 반드시 표면화되어 있어야 함
            assert len(errors) > 0
    finally:
        controller.close_connection()


# -----------------------------------------------------------------------------
# write_timeout 설정 검증 (S-039 항목 2)
# -----------------------------------------------------------------------------

def test_serial_transport_open_uses_nonzero_write_timeout(sample_port_config):
    """
    SerialTransport.open()이 write_timeout=0(완료 미확인)이 아니라
    WRITE_TIMEOUT_S(완료 확인 분기)로 serial.Serial을 생성하는지 확인한다.
    """
    from unittest.mock import patch

    with patch("core.transport.serial_transport.serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        transport = SerialTransport(sample_port_config)
        transport.open()

        _, kwargs = mock_cls.call_args
        assert kwargs["write_timeout"] == WRITE_TIMEOUT_S
        assert kwargs["write_timeout"] != 0
