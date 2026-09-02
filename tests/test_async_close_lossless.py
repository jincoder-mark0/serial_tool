"""포트 종료가 UI를 멈추지 않으면서도 TX를 유실하지 않는지 검증한다.

## WHY
사용자 요구: "데이터 무손실이 중요하다. 다만 UI가 멈추면 안 된다."

두 요구는 사실 상충하지 않는다. 남은 TX 큐를 비우는 것은 **worker thread**가
하는 일이고 호출자의 thread는 필요하지 않다. 그런데 과거 `ConnectionWorker.stop()`은
무조건 `wait()`를 걸었고, `ConnectionController.close_connection()`이 그것을 그대로
호출했다. 그래서 포트를 닫는 UI thread가 드레인이 끝날 때까지 멈췄다 —
TX 큐는 상한이 없고 청크당 write는 최대 `WRITE_TIMEOUT_S`(1초)이므로,
저속 포트에 backlog가 쌓여 있으면 멈추는 시간에 상한이 없다.

요청과 대기를 분리해 **데이터는 그대로 다 내보내면서** UI는 기다리지 않게 했다.

## WHAT
* `close_connection()`이 드레인을 기다리지 않고 즉시 반환하는가
* 그럼에도 큐에 있던 데이터가 **전부** transport까지 도달하는가
* 앱 종료 경로(`close_all_and_wait`)는 반대로 반드시 기다리는가
  — 프로세스가 죽는 경로에서 기다리지 않는 것이 곧 유실이다
* 드레인 중인 포트를 다시 열려는 시도를 막는가

## HOW
`write()`가 붙잡혀 있는 fake transport로 "드레인이 오래 걸리는" 상황을
결정론적으로 만든다. 실제 저속 포트를 흉내 내되 테스트는 빠르게 끝난다.
"""
import time
from threading import Event

import pytest

from common.dtos import PortConfig
from core.transport.base_transport import BaseTransport
from model.connection_controller import ConnectionController
from model.connection_session_factory import ConnectionSessionFactory

PORT = "COM-SLOW"


class _SlowWriteTransport(BaseTransport):
    """각 write()가 release될 때까지 붙잡히는, 느린 포트를 흉내 낸 transport."""

    def __init__(self) -> None:
        self._open = False
        self.written: list[bytes] = []
        self.first_write_started = Event()
        self.release = Event()

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
        self.first_write_started.set()
        self.release.wait(5)
        self.written.append(data)

    @property
    def in_waiting(self) -> int:
        return 0


class _StubFactory(ConnectionSessionFactory):
    def __init__(self, transport: _SlowWriteTransport) -> None:
        self._transport = transport

    def create_worker(self, config: PortConfig):
        from model.connection_worker import ConnectionWorker

        return ConnectionWorker(self._transport, config.port)


@pytest.fixture
def slow_setup(qapp):
    transport = _SlowWriteTransport()
    controller = ConnectionController(session_factory=_StubFactory(transport))
    yield controller, transport
    transport.release.set()
    controller.close_all_and_wait(timeout_ms=3000)


def _open_and_queue(controller, transport, chunks) -> None:
    assert controller.open_connection(PortConfig(port=PORT)) is True
    worker = controller.workers[PORT]
    deadline = time.monotonic() + 2.0
    while not worker.is_running() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert worker.is_running(), "worker가 시작되지 않았다"

    for chunk in chunks:
        assert controller.send_data(PORT, chunk) is True
    assert transport.first_write_started.wait(2), "write가 시작되지 않았다"


def test_close_returns_without_waiting_for_the_flush(slow_setup):
    """
    close_connection()은 드레인을 기다리지 않고 즉시 돌아와야 한다.

    write 하나가 붙잡혀 있는 상태이므로, 과거처럼 `stop()`이 대기했다면 이 호출은
    release 전까지 돌아오지 못한다. 그게 UI가 얼어붙던 이유다.
    """
    controller, transport = slow_setup
    _open_and_queue(controller, transport, [b"A", b"B", b"C"])

    started = time.monotonic()
    controller.close_connection(PORT)
    elapsed = time.monotonic() - started

    assert elapsed < 0.5, (
        f"close_connection()이 {elapsed:.2f}s 동안 블록됐다 — 드레인을 기다리고 있다. "
        f"요청과 대기를 분리해야 UI가 멈추지 않는다."
    )
    # 호출자 입장에서는 즉시 닫힌 것으로 보여야 한다 (신규 송신 거부).
    assert controller.is_connection_open(PORT) is False
    assert controller.has_pending_flush() is True, (
        "드레인이 아직 안 끝났는데 pending으로 보이지 않는다 — UI가 진행 상태를 알 수 없다"
    )


def test_queued_data_is_fully_flushed_after_async_close(slow_setup):
    """UI가 기다리지 않아도 큐에 있던 데이터는 **전부** 나가야 한다."""
    controller, transport = slow_setup
    _open_and_queue(controller, transport, [b"A", b"B", b"C"])

    controller.close_connection(PORT)
    transport.release.set()

    assert controller.wait_for_pending_flush(timeout_ms=5000) is True

    assert transport.written == [b"A", b"B", b"C"], (
        f"비동기 close 후 TX가 유실됐다: {transport.written}. "
        f"대기를 없앤 것이지 드레인 범위를 줄인 것이 아니다."
    )


def test_shutdown_path_waits_for_the_flush(slow_setup):
    """
    앱 종료 경로는 반대로 반드시 기다려야 한다.

    프로세스가 곧 사라지므로, 여기서 기다리지 않는 것이 곧 유실이다.
    """
    controller, transport = slow_setup
    _open_and_queue(controller, transport, [b"X", b"Y"])

    transport.release.set()
    assert controller.close_all_and_wait(timeout_ms=5000) is True

    assert transport.written == [b"X", b"Y"], (
        f"종료 경로가 드레인 완료를 기다리지 않았다: {transport.written}"
    )
    assert controller.has_pending_flush() is False


def test_reopen_waits_briefly_for_a_short_flush_and_succeeds(slow_setup):
    """
    드레인이 곧 끝나는 경우 재연결은 **성공해야** 한다.

    "탭을 닫고 다시 열기"는 정당한 조작이다. 곧바로 거부하면 close에서 없앤 불편이
    open으로 옮겨갈 뿐이다. 보통은 TX 큐가 비어 있어 이 대기는 사실상 0이다.
    """
    controller, transport = slow_setup
    _open_and_queue(controller, transport, [b"A"])

    controller.close_connection(PORT)
    transport.release.set()          # 드레인이 곧 끝나는 상황

    assert controller.open_connection(PortConfig(port=PORT)) is True
    assert controller.is_connection_open(PORT) is True
    assert transport.written == [b"A"], (
        f"재연결 전에 이전 세션의 TX가 다 나가지 않았다: {transport.written}"
    )


def test_reopen_is_rejected_when_the_flush_exceeds_the_wait_limit(slow_setup, monkeypatch):
    """
    상한을 넘기면 무한정 기다리지 않고 알린다.

    드레인 중에는 transport가 아직 열려 있으므로 그대로 새로 열면 같은 물리 포트를
    두 번 여는 시도가 되거나 이전 세션의 남은 TX가 새 세션과 섞인다. 그렇다고
    여기서 무한정 기다리면 close에서 없앤 멈춤이 open으로 옮겨갈 뿐이다.
    """
    # 상한 자체가 검증 대상이 아니라 "상한을 넘기면 알린다"가 검증 대상이므로,
    # 실제 2초를 흘려보내지 않고 짧게 줄여 확인한다.
    monkeypatch.setattr("model.connection_controller.REOPEN_FLUSH_WAIT_MS", 100)

    controller, transport = slow_setup
    _open_and_queue(controller, transport, [b"A", b"B"])

    errors = []
    controller.error_occurred.connect(errors.append)
    controller.close_connection(PORT)   # transport는 계속 붙잡혀 있다

    assert controller.open_connection(PortConfig(port=PORT)) is False
    assert errors, "재연결을 거부하면서 이유를 알리지 않았다"
    assert "flushing" in errors[-1].message.lower()

    # 영구 차단이 아니다 — 드레인이 끝나면 다시 열 수 있어야 한다.
    transport.release.set()
    assert controller.wait_for_pending_flush(timeout_ms=5000) is True
    assert controller.open_connection(PortConfig(port=PORT)) is True
