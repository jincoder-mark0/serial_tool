"""
S-037 회귀 테스트: 연결 직후 send 침묵 실패 레이스

## WHY
* `ConnectionController.is_connection_open()`은 `QThread.isRunning()`을 본다 —
  이 값은 `worker.start()` 호출 직후(OS 스레드가 실제로 `run()`에 진입하기 전에도)
  즉시 True가 된다.
* 반면 (수정 전) `ConnectionWorker.send_data()`의 가드는 `transport.is_open()`을
  보았다 — OS 스레드가 `run()`에 진입해 `transport.open()`을 마쳐야 True.
* 그 틈에 들어온 send는 (수정 전) `False`를 반환하며 조용히 큐잉에 실패했다
  (에러 시그널/로그 없음, 데이터 유실). LOOPBACK처럼 open이 즉시 끝나는 transport에서
  재현 창이 특히 잘 드러난다.

## WHAT
* 단위: `ConnectionWorker.send_data()`가 스레드를 시작하기도 전(transport가
  열리기 전)에도 큐잉에 성공하는지 확인 (수정된 가드 자체의 결정론적 검증).
* 통합: `ConnectionController.open_connection(LOOPBACK)` 직후, `worker.is_running()`
  (transport open 완료 플래그) 대기 없이 바로 `send_data()`를 호출해도 데이터가
  결국 에코로 돌아오는지 확인 (실제 run() 루프를 통한 종단 간 검증).

## HOW
* 단위 테스트는 스레드를 시작(`start()`)하지 않은 채 `ConnectionWorker.send_data()`를
  직접 호출해 큐 상태만 확인한다 (타이밍에 의존하지 않는 결정론적 테스트).
* 통합 테스트는 `qtbot.waitSignal`로 비동기 run() 루프의 최종 결과(에코 수신)만
  대기한다 — "open 완료" 자체를 기다리는 코드는 의도적으로 넣지 않는다.

## 파일 선택 근거
`tests/test_loopback_transport.py`는 Task 지시에 따라 회귀 테스트 추가 대상에서
제외(그 파일이 아닌 신규/기존 통합 테스트 파일에 추가 허용)되어, 레이스 시나리오
전용 신규 파일로 분리했다. 기존 통합 테스트 파일(`test_integration_refactored.py`)에
추가하는 대신 별도 파일로 만든 이유는: 이 레이스는 LOOPBACK 특유의 즉시-open
특성에 의존하는 반면, `test_integration_refactored.py`는 Mock Serial 기반
COM 포트 흐름에 집중하고 있어 관심사가 다르기 때문이다.
"""
import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.transport.loopback_transport import LoopbackTransport
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


# -----------------------------------------------------------------------------
# 단위 테스트: 가드 자체의 결정론적 검증 (스레드 미시작, 타이밍 의존 없음)
# -----------------------------------------------------------------------------

def test_send_data_queues_before_transport_is_open_and_before_thread_start():
    """
    ConnectionWorker.send_data()는 스레드를 시작하지 않아 transport가 아직
    닫혀 있는 상태에서도 큐잉에 성공해야 한다 (수정 전에는 transport.is_open()이
    False라서 즉시 실패했다).
    """
    transport = LoopbackTransport()
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    assert transport.is_open() is False  # 아직 open() 호출 전
    assert worker.isRunning() is False   # 스레드 시작 전

    assert worker.send_data(b"PRE_OPEN") is True
    assert worker.get_write_queue_size() == 1


def test_send_data_rejected_after_stop_requested():
    """
    stop()으로 종료가 요청된 뒤에는(transport open 여부와 무관하게) 큐잉이
    거부되어야 한다 — 완화된 가드가 "무조건 허용"이 아니라 "종료 요청 전까지만
    허용"임을 확인한다.
    """
    transport = LoopbackTransport()
    worker = ConnectionWorker(transport, LOOPBACK_PORT_NAME)

    worker._stop_requested = True  # stop()과 동일한 상태만 재현 (스레드는 미시작)

    assert worker.send_data(b"AFTER_STOP") is False
    assert worker.get_write_queue_size() == 0


# -----------------------------------------------------------------------------
# 통합 테스트: 실제 run() 루프를 통한 종단 간 검증 (LOOPBACK, 대기 없이 send)
# -----------------------------------------------------------------------------

def test_send_immediately_after_open_is_not_lost(qapp, qtbot, loopback_config):
    """
    open_connection() 직후, worker.is_running()(transport open 완료 플래그)을
    기다리지 않고 곧바로 send_data()를 호출해도 데이터가 유실되지 않고 결국
    에코로 돌아온다.

    수정 전에는 이 타이밍에서 worker.send_data()가 조용히 False를 반환하며
    데이터가 유실되었다 (재현 조건: LOOPBACK은 open()이 즉시 끝나 레이스 창이
    실제 하드웨어보다 크게 보이지만, 레이스 자체는 SerialTransport에도 동일).
    """
    controller = ConnectionController()
    try:
        assert controller.open_connection(loopback_config) is True

        # 의도적으로 wait_until/waitUntil(worker.is_running()) 없이 즉시 전송.
        with qtbot.waitSignal(controller.data_received, timeout=2000) as blocker:
            controller.send_data(LOOPBACK_PORT_NAME, b"RACE_PING")

        event = blocker.args[0]
        assert event.port == LOOPBACK_PORT_NAME
        assert event.data == b"RACE_PING"
    finally:
        controller.close_connection()


def test_multiple_sends_immediately_after_open_preserve_order(qapp, qtbot, loopback_config):
    """
    open 직후 대기 없이 여러 번 연속 send해도 순서가 보존된 채 모두 전달된다
    (run() 루프가 open 완료 후 TX 큐를 순서대로 드레인하기 때문).
    """
    controller = ConnectionController()
    received = []

    def _collect(event):
        received.append(event.data)

    controller.data_received.connect(_collect)

    try:
        assert controller.open_connection(loopback_config) is True

        controller.send_data(LOOPBACK_PORT_NAME, b"A")
        controller.send_data(LOOPBACK_PORT_NAME, b"B")
        controller.send_data(LOOPBACK_PORT_NAME, b"C")

        qtbot.waitUntil(lambda: b"".join(received) == b"ABC", timeout=2000)
    finally:
        controller.close_connection()
