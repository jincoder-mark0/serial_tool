"""
S-045 커버리지 테스트: RingBuffer / ThreadSafeQueue (core/structures.py)

## WHY
* `tests/test_core_structures.py`는 이름과 달리 `core/structures.py`
  (RingBuffer, ThreadSafeQueue)를 전혀 다루지 않는다 — 실제로는
  DTO/Enum/상수(`common/dtos.py`, `common/enums.py`, `common/constants.py`)를
  검증하는 파일이다. 혼동을 줄이기 위해 기존 파일은 개명하지 않고(다른 문서가
  참조 중일 수 있음), 이 신규 파일에서 `core/structures.py`를 실제로 다룬다.
* `RingBuffer.write()`는 memoryview 슬라이싱으로 랩어라운드/오버플로우
  포인터 산술을 직접 계산하는 코드라, off-by-one 하나만 있어도 조용히 잘못된
  바이트를 반환할 수 있다 — 손으로 계산한 기대값과 정확히 대조해 검증한다.

## WHAT
* RingBuffer: 기본 왕복, 버퍼 경계를 넘는 랩어라운드, 용량 초과 시 가장 오래된
  바이트가 정확히 밀려나는지(FIFO 오버플로우), 단일 쓰기가 버퍼 전체보다 큰
  경우 뒷부분만 남는지, clear()/available() 상태 갱신.
* ThreadSafeQueue: FIFO 순서, maxlen 포화 시 enqueue 실패, is_empty/qsize/clear.

## HOW
* 버퍼 크기를 작게(4~10바이트) 고정하고, 각 write/read 호출 후 기대되는
  포인터 이동과 바이트 내용을 손으로 계산해 assert한다 (표준 라이브러리만 사용,
  하드웨어/스레드 불필요 — 순수 산술 검증).
"""
import pytest

from core.structures import RingBuffer, ThreadSafeQueue


# -----------------------------------------------------------------------------
# RingBuffer — 기본 동작
# -----------------------------------------------------------------------------

def test_ring_buffer_basic_write_read_round_trip():
    """랩어라운드가 없는 단순 쓰기/읽기는 순서와 내용이 그대로 보존된다."""
    rb = RingBuffer(size=16)

    written = rb.write(b"HELLO")
    assert written == 5
    assert rb.available() == 5

    data = rb.read(5)
    assert data == b"HELLO"
    assert rb.available() == 0


def test_ring_buffer_partial_read_leaves_remainder_available():
    """일부만 read()하면 남은 바이트 수가 available()에 정확히 반영된다."""
    rb = RingBuffer(size=16)
    rb.write(b"ABCDEF")

    first = rb.read(2)
    assert first == b"AB"
    assert rb.available() == 4

    rest = rb.read(10)  # 요청량이 남은 것보다 많아도 있는 만큼만 반환
    assert rest == b"CDEF"
    assert rb.available() == 0


def test_ring_buffer_write_zero_length_is_noop():
    """빈 바이트를 write()해도 포인터/저장량이 변하지 않는다."""
    rb = RingBuffer(size=8)
    assert rb.write(b"") == 0
    assert rb.available() == 0


def test_ring_buffer_read_from_empty_returns_empty_bytes():
    """빈 버퍼에서 read()하면 예외 없이 b''를 반환한다."""
    rb = RingBuffer(size=8)
    assert rb.read(10) == b""


# -----------------------------------------------------------------------------
# RingBuffer — 랩어라운드(경계를 넘는 쓰기/읽기)
# -----------------------------------------------------------------------------

def test_ring_buffer_write_wraps_around_buffer_boundary():
    """
    head가 버퍼 끝에 가까울 때 쓰기가 경계를 넘으면 앞부분(offset 0)으로
    이어서 기록되고(wrap-around), read()도 두 조각을 이어붙여 올바른 순서로
    반환해야 한다.
    """
    rb = RingBuffer(size=8)

    rb.write(b"ABCDE")  # head: 0 -> 5 (버퍼: A B C D E _ _ _)
    assert rb.available() == 5

    # 남은 공간(3바이트: index 5,6,7)보다 큰 4바이트를 써서 랩어라운드 유도
    written = rb.write(b"FGHI")  # F,G,H는 index5-7, I는 wrap되어 index0
    assert written == 4

    # 용량(8) 초과분(9-8=1바이트, 즉 가장 오래된 'A')이 밀려나야 함
    assert rb.available() == 8

    data = rb.read(8)
    # 'A'가 밀려나고 남은 것: B C D E F G H I (원래 입력 순서 그대로)
    assert data == b"BCDEFGHI"
    assert rb.available() == 0


def test_ring_buffer_read_wraps_around_buffer_boundary():
    """tail이 버퍼 끝 근처에 있을 때 read()도 랩어라운드하여 올바르게 이어붙인다."""
    rb = RingBuffer(size=6)

    rb.write(b"ABCDEF")  # 버퍼 가득 참, head=0(6%6), tail=0
    assert rb.read(4) == b"ABCD"  # tail: 0 -> 4
    assert rb.available() == 2

    rb.write(b"GH")  # head=0 지점부터 이어쓰기(랩어라운드): index4,5 -> G,H
    assert rb.available() == 4

    # 남은 데이터는 tail=4부터: E,F(인덱스4,5) 그 다음 G,H(인덱스0,1 랩어라운드)
    data = rb.read(4)
    assert data == b"EFGH"


# -----------------------------------------------------------------------------
# RingBuffer — 오버플로우(용량 초과 시 가장 오래된 데이터부터 밀려남)
# -----------------------------------------------------------------------------

def test_ring_buffer_overflow_evicts_oldest_bytes_first():
    """용량을 넘는 누적 쓰기는 가장 오래된 바이트부터 밀어내며 최신 N바이트만 남긴다."""
    rb = RingBuffer(size=5)

    rb.write(b"12345")  # 정확히 가득 참
    rb.write(b"67")  # 누적 7바이트 -> 오버플로우 2바이트("1","2") 밀려남

    assert rb.available() == 5
    assert rb.read(5) == b"34567"


def test_ring_buffer_single_write_larger_than_capacity_keeps_only_tail_portion():
    """단일 write()가 버퍼 전체보다 크면, 슬라이싱 없이 뒷부분(최신 N바이트)만 남는다."""
    rb = RingBuffer(size=4)

    written = rb.write(b"HELLOWORLD")  # 10바이트 입력, 용량 4
    assert written == 4  # 실제로 저장된 바이트 수는 용량만큼
    assert rb.available() == 4

    # "HELLOWORLD"의 마지막 4글자만 남아야 함
    assert rb.read(4) == b"ORLD"


def test_ring_buffer_repeated_overflow_stays_at_capacity():
    """반복적으로 용량을 초과해 써도 available()은 항상 용량을 넘지 않는다."""
    rb = RingBuffer(size=4)

    for chunk in [b"AA", b"BB", b"CC", b"DD", b"EE"]:
        rb.write(chunk)
        assert rb.available() <= 4

    # 마지막 4바이트("D","D","E","E")만 남아야 함
    assert rb.read(4) == b"DDEE"


# -----------------------------------------------------------------------------
# RingBuffer — clear()
# -----------------------------------------------------------------------------

def test_ring_buffer_clear_resets_pointers_and_available():
    """clear() 이후에는 available()이 0이 되고 이전 데이터가 다시 나오지 않는다."""
    rb = RingBuffer(size=8)
    rb.write(b"ABCDEFGH")
    rb.clear()

    assert rb.available() == 0
    assert rb.read(8) == b""

    # clear 이후 재사용 가능해야 함 (포인터가 정상적으로 0에서 재시작)
    rb.write(b"XY")
    assert rb.available() == 2
    assert rb.read(2) == b"XY"


# -----------------------------------------------------------------------------
# ThreadSafeQueue — FIFO 및 maxlen 포화
# -----------------------------------------------------------------------------

def test_thread_safe_queue_fifo_order():
    """enqueue한 순서대로 dequeue된다 (FIFO)."""
    q = ThreadSafeQueue()
    assert q.enqueue("a") is True
    assert q.enqueue("b") is True
    assert q.enqueue("c") is True

    assert q.dequeue() == "a"
    assert q.dequeue() == "b"
    assert q.dequeue() == "c"


def test_thread_safe_queue_dequeue_from_empty_returns_none():
    """빈 큐에서 dequeue()하면 예외 없이 None을 반환한다."""
    q = ThreadSafeQueue()
    assert q.dequeue() is None


def test_thread_safe_queue_maxlen_saturation_rejects_enqueue():
    """maxlen에 도달하면 이후 enqueue()는 False를 반환하고 항목이 추가되지 않는다."""
    q = ThreadSafeQueue(maxlen=2)

    assert q.enqueue(1) is True
    assert q.enqueue(2) is True
    assert q.qsize() == 2

    # 포화 상태 -> 실패해야 하며, 기존 항목을 밀어내지 않아야 함(deque(maxlen)와
    # 달리 자동 폐기가 아니라 명시적 실패를 반환하는 설계를 검증)
    assert q.enqueue(3) is False
    assert q.qsize() == 2
    assert q.dequeue() == 1  # 3이 1을 밀어내지 않았음을 순서로 확인
    assert q.dequeue() == 2


def test_thread_safe_queue_dequeue_frees_room_after_saturation():
    """포화 후 dequeue()로 한 자리가 비면 다시 enqueue()가 성공한다."""
    q = ThreadSafeQueue(maxlen=1)

    assert q.enqueue("x") is True
    assert q.enqueue("y") is False  # 포화

    assert q.dequeue() == "x"
    assert q.enqueue("y") is True
    assert q.dequeue() == "y"


def test_thread_safe_queue_is_empty_and_clear():
    """is_empty()와 clear()가 큐 상태를 정확히 반영한다."""
    q = ThreadSafeQueue()
    assert q.is_empty() is True

    q.enqueue(1)
    q.enqueue(2)
    assert q.is_empty() is False
    assert q.qsize() == 2

    q.clear()
    assert q.is_empty() is True
    assert q.qsize() == 0
    assert q.dequeue() is None


def test_thread_safe_queue_unbounded_when_maxlen_none():
    """maxlen=None(기본값)이면 대량으로 넣어도 실패 없이 계속 받아들인다."""
    q = ThreadSafeQueue()
    for i in range(1000):
        assert q.enqueue(i) is True
    assert q.qsize() == 1000
