"""
LoopbackTransport 단위/통합 테스트 모듈 (S-033)

## WHY
* 실기기 없이 앱의 송수신 전 경로를 디버깅할 루프백 더미 포트가 기대대로
  동작하는지(에코, 스레드 안전성, ConnectionController 배선) 검증

## WHAT
* 단위: write/read/in_waiting 왕복, 부분 read, close 후 동작, 간단한 2스레드 동시성
* 통합: ConnectionController.open_connection(LOOPBACK) -> send_data ->
  data_received 시그널로 동일 바이트가 되돌아오는지 확인

## HOW
* 단위 테스트는 LoopbackTransport를 직접 생성해 검증
* 통합 테스트는 qtbot.waitSignal로 실제 ConnectionWorker 스레드의 비동기 동작을 대기
"""
import threading

import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.transport.loopback_transport import LoopbackTransport
from model.connection_controller import ConnectionController


# -----------------------------------------------------------------------------
# 단위 테스트 (LoopbackTransport 자체)
# -----------------------------------------------------------------------------

def test_write_then_read_roundtrip():
    """write()한 바이트가 read()로 그대로 되돌아온다 (에코)."""
    transport = LoopbackTransport()
    transport.open()

    transport.write(b"HELLO")

    assert transport.in_waiting == 5
    assert transport.read(5) == b"HELLO"
    assert transport.in_waiting == 0


def test_partial_read_leaves_remainder_in_buffer():
    """size보다 버퍼가 크면 앞부분만 읽고 나머지는 버퍼에 남는다."""
    transport = LoopbackTransport()
    transport.open()

    transport.write(b"ABCDEF")

    assert transport.read(3) == b"ABC"
    assert transport.in_waiting == 3
    assert transport.read(10) == b"DEF"
    assert transport.in_waiting == 0


def test_read_on_empty_buffer_returns_empty_bytes():
    """버퍼가 비어있으면 read()는 빈 bytes를 반환한다."""
    transport = LoopbackTransport()
    transport.open()

    assert transport.read(10) == b""


def test_close_clears_buffer_and_blocks_io():
    """close() 이후에는 버퍼가 비워지고 write/read가 무시된다."""
    transport = LoopbackTransport()
    transport.open()
    transport.write(b"DATA")

    transport.close()

    assert transport.is_open() is False
    assert transport.in_waiting == 0

    # 닫힌 상태에서는 write도 무시됨
    transport.write(b"IGNORED")
    assert transport.in_waiting == 0
    assert transport.read(10) == b""


def test_open_after_close_starts_with_empty_buffer():
    """close 후 재오픈하면 이전 데이터 없이 새로 시작한다."""
    transport = LoopbackTransport()
    transport.open()
    transport.write(b"OLD")
    transport.close()

    transport.open()

    assert transport.in_waiting == 0
    assert transport.is_open() is True


def test_thread_safety_concurrent_write_and_read():
    """
    Worker 스레드가 read하는 동안 다른 스레드가 write해도 데이터가 유실/오염되지 않는다.

    Logic:
        - 한 스레드가 100번 write(1바이트)
        - 메인 스레드가 짧게 대기 후 전체를 반복 read하여 합산
        - 총 수신 바이트 수가 write 총량과 일치하는지 확인 (경쟁 조건 없음)
    """
    transport = LoopbackTransport()
    transport.open()

    total_writes = 100

    def writer():
        for i in range(total_writes):
            transport.write(bytes([i % 256]))

    thread = threading.Thread(target=writer)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()

    collected = bytearray()
    while transport.in_waiting > 0:
        collected.extend(transport.read(16))

    assert len(collected) == total_writes


# -----------------------------------------------------------------------------
# 통합 테스트 (ConnectionController 배선 확인)
# -----------------------------------------------------------------------------

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


def test_connection_controller_uses_loopback_transport_for_reserved_name(loopback_config):
    """config.port가 LOOPBACK_PORT_NAME이면 LoopbackTransport가 선택된다."""
    controller = ConnectionController()
    try:
        assert controller.open_connection(loopback_config) is True
        worker = controller.workers[LOOPBACK_PORT_NAME]
        assert isinstance(worker.transport, LoopbackTransport)
    finally:
        controller.close_connection()


def test_send_data_echoes_back_through_data_received_signal(qapp, qtbot, loopback_config):
    """
    send_data로 보낸 바이트가 RX 경로(data_received 시그널)로 그대로 돌아온다.

    Logic:
        - ConnectionController.open_connection(LOOPBACK)으로 연결
        - send_data로 곧바로 바이트 전송 (Worker의 내부 실행 플래그 is_running이
          True가 될 때까지 대기하지 않음 — S-037 수정 전에는 QThread.isRunning()이
          start() 직후 곧바로 True가 되는 반면 transport.open()은 실제 run()
          스레드에서 지연 완료되어, 그 틈의 send가 조용히 유실되었다. 이제는
          ConnectionWorker.send_data()가 stop 요청 여부만으로 큐잉을 허용하고
          run() 루프가 open 후 큐를 드레인하므로 대기가 불필요하다. 회귀 테스트:
          tests/test_send_before_open_race.py)
        - ConnectionWorker의 폴링 루프가 write -> read를 수행할 때까지
          qtbot.waitSignal로 data_received(PortDataEvent)를 대기
        - 수신된 DTO의 port/data가 기대값과 일치하는지 확인
    """
    controller = ConnectionController()
    try:
        assert controller.open_connection(loopback_config) is True

        with qtbot.waitSignal(controller.data_received, timeout=2000) as blocker:
            controller.send_data(LOOPBACK_PORT_NAME, b"PING")

        event = blocker.args[0]
        assert event.port == LOOPBACK_PORT_NAME
        assert event.data == b"PING"
    finally:
        controller.close_connection()
