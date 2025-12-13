"""
유틸리티 클래스 단위 테스트

- RingBuffer: 순환 버퍼 쓰기/읽기, 랩어라운드, 오버라이트 검증
- ThreadSafeQueue: 스레드 안전 큐 동작 검증

pytest tests/test_core_utils.py -v
"""
import sys
import os
import pytest
from threading import Thread
import time

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import RingBuffer, ThreadSafeQueue

# --- RingBuffer Tests ---

def test_ringbuffer_basic_io():
    """기본 읽기/쓰기 동작 테스트"""
    rb = RingBuffer(size=10)

    # Write
    data = b"12345"
    written = rb.write(data)
    assert written == 5

    # Read
    read_data = rb.read(5)
    assert read_data == b"12345"
    assert rb.read(1) == b"" # Empty

def test_ringbuffer_wrap_around():
    """버퍼 끝에서 랩어라운드(Wrap-around) 동작 테스트"""
    rb = RingBuffer(size=10)

    # 1. 8바이트 채움 (Head: 8)
    rb.write(b"12345678")
    # 2. 5바이트 읽음 (Tail: 5) -> 남은 데이터: "678"
    rb.read(5)

    # 3. 5바이트 추가 쓰기 (Head: 8 -> 10 -> 3)
    # 공간은 충분함 (Size 10, Stored 3, Available 7)
    # "ABCDE"를 쓰면 "678" 뒤에 "AB", 그리고 앞에 "CDE"가 써져야 함
    rb.write(b"ABCDE")

    # 현재 버퍼 상태(개념적): [C, D, E, _, _, 6, 7, 8, A, B]
    # Tail은 5 ('6'의 위치)

    # 4. 전체 읽기 (8바이트)
    # 예상 순서: 6 -> 7 -> 8 -> A -> B -> C -> D -> E
    result = rb.read(8)
    assert result == b"678ABCDE"

def test_ringbuffer_overwrite():
    """버퍼 가득 찼을 때 덮어쓰기(Overwrite) 테스트"""
    rb = RingBuffer(size=5)

    # 1. 가득 채움
    rb.write(b"12345")

    # 2. 추가 쓰기 (오버플로우 발생) -> 오래된 데이터(1, 2)가 지워져야 함
    rb.write(b"AB")

    # 예상 상태: [A, B, 3, 4, 5] (Head는 2, Tail은 2로 밀림)
    # 읽으면 345AB 순서여야 함
    result = rb.read(5)
    assert result == b"345AB"

def test_ringbuffer_large_write():
    """버퍼 크기보다 큰 데이터 쓰기 테스트"""
    rb = RingBuffer(size=5)

    # 버퍼보다 큰 데이터 -> 뒷부분 5바이트만 남아야 함
    rb.write(b"1234567890")

    result = rb.read(5)
    assert result == b"67890"

# --- ThreadSafeQueue Tests ---

def test_queue_basic():
    """큐 기본 동작 테스트"""
    q = ThreadSafeQueue(maxlen=3)

    assert q.is_empty() is True

    assert q.enqueue(1) is True
    assert q.enqueue(2) is True
    assert q.enqueue(3) is True
    assert q.enqueue(4) is False # Full

    assert q.qsize() == 3

    assert q.dequeue() == 1
    assert q.dequeue() == 2
    assert q.dequeue() == 3
    assert q.dequeue() is None # Empty

def test_queue_threading():
    """멀티스레드 환경에서의 안정성 테스트 (간단 검증)"""
    q = ThreadSafeQueue()
    item_count = 1000

    def producer():
        for i in range(item_count):
            q.enqueue(i)

    def consumer(results):
        while len(results) < item_count:
            item = q.dequeue()
            if item is not None:
                results.append(item)
            else:
                time.sleep(0.001)

    results = []
    t1 = Thread(target=producer)
    t2 = Thread(target=consumer, args=(results,))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    assert len(results) == item_count
    assert results == list(range(item_count))

if __name__ == "__main__":
    pytest.main([__file__])
