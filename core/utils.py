"""
핵심 유틸리티 클래스 모듈입니다.

데이터 버퍼링 및 스레드 간 안전한 데이터 전달을 위한
유틸리티 클래스들을 제공합니다.

## WHY
* 고속 데이터 처리를 위해 효율적인 버퍼링이 필요합니다.
* 멀티스레드 환경에서 안전한 데이터 공유가 필요합니다.
"""

import threading
from collections import deque
from typing import Optional, Any
from app_constants import RING_BUFFER_SIZE

class ThreadSafeQueue:
    """
    스레드 안전한(Thread-safe) 큐 래퍼 클래스입니다.
    내부적으로 deque와 Lock을 사용하여 구현되었습니다.
    """

    def __init__(self, maxlen: Optional[int] = None):
        """
        ThreadSafeQueue를 초기화합니다.

        Args:
            maxlen (Optional[int]): 큐의 최대 크기. None이면 무제한.
        """
        self._queue = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def enqueue(self, item: Any) -> bool:
        """
        아이템을 큐에 추가합니다.

        Args:
            item (Any): 추가할 아이템.

        Returns:
            bool: 추가 성공 시 True, 큐가 가득 차서 실패 시 False.
        """
        with self._lock:
            if self._queue.maxlen is not None and len(self._queue) >= self._queue.maxlen:
                return False
            self._queue.append(item)
            return True

    def dequeue(self) -> Optional[Any]:
        """
        큐에서 아이템을 하나 꺼내 반환합니다.

        Returns:
            Optional[Any]: 큐가 비어있지 않으면 아이템, 비어있으면 None.
        """
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def is_empty(self) -> bool:
        """
        큐가 비어있는지 확인합니다.

        Returns:
            bool: 비어있으면 True, 아니면 False.
        """
        with self._lock:
            return len(self._queue) == 0

    def clear(self) -> None:
        """큐의 모든 아이템을 제거합니다."""
        with self._lock:
            self._queue.clear()

    def qsize(self) -> int:
        """
        큐의 현재 크기를 반환합니다.

        Returns:
            int: 아이템 개수.
        """
        with self._lock:
            return len(self._queue)


class RingBuffer:
    """
    고정 크기 링 버퍼(Circular Buffer) 클래스입니다.
    memoryview를 사용하여 제로 카피(Zero-copy)에 가까운 쓰기 성능을 제공합니다.
    """

    def __init__(self, size: int = RING_BUFFER_SIZE):
        """
        RingBuffer를 초기화합니다.

        Args:
            size (int): 버퍼 크기 (바이트 단위). 기본값은 상수로 정의됨.
        """
        self._size = size
        # 실제 데이터 저장소 (bytearray)
        self._buffer = bytearray(size)
        # 슬라이싱 최적화를 위한 memoryview
        self._mv = memoryview(self._buffer)

        self._head = 0  # 쓰기 포인터
        self._tail = 0  # 읽기 포인터 (이 구현에서는 덮어쓰기 시 tail 이동)
        self._stored_bytes = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        """
        데이터를 버퍼에 씁니다. (memoryview 활용 최적화)

        Args:
            data (bytes): 쓸 데이터.

        Returns:
            int: 쓰여진 바이트 수.
        """
        data_len = len(data)
        if data_len == 0:
            return 0

        with self._lock:
            # 입력 데이터가 버퍼 전체보다 크면 뒷부분만 남김 (슬라이싱 없이 오프셋 계산)
            write_offset = 0
            if data_len > self._size:
                write_offset = data_len - self._size
                data_len = self._size

            # 1. 버퍼 끝까지의 여유 공간
            space_at_end = self._size - self._head

            # 2. 첫 번째 청크 길이 계산
            chunk1_len = min(data_len, space_at_end)

            # 3. 데이터 쓰기 (memoryview 슬라이스 대입 - 복사 발생 최소화)
            # data[write_offset : write_offset + chunk1_len]
            self._mv[self._head : self._head + chunk1_len] = data[write_offset : write_offset + chunk1_len]

            # 4. 랩어라운드(Wrap-around) 처리
            chunk2_len = data_len - chunk1_len
            if chunk2_len > 0:
                # data[write_offset + chunk1_len : write_offset + chunk1_len + chunk2_len]
                self._mv[0 : chunk2_len] = data[write_offset + chunk1_len : write_offset + chunk1_len + chunk2_len]

            # 5. 포인터 업데이트
            self._head = (self._head + data_len) % self._size

            # 6. 저장된 바이트 수 및 Tail 업데이트
            if self._stored_bytes + data_len > self._size:
                # 오버플로우: Tail을 밀어냄
                overlap = (self._stored_bytes + data_len) - self._size
                self._tail = (self._tail + overlap) % self._size
                self._stored_bytes = self._size
            else:
                self._stored_bytes += data_len

            return data_len

    def read(self, count: int) -> bytes:
        """
        버퍼에서 데이터를 읽어옵니다. (bytes 객체로 반환)

        Args:
            count (int): 읽을 바이트 수.

        Returns:
            bytes: 읽은 데이터.
        """
        with self._lock:
            if self._stored_bytes == 0:
                return b""

            read_count = min(count, self._stored_bytes)

            space_at_end = self._size - self._tail
            chunk1_len = min(read_count, space_at_end)

            # memoryview 슬라이싱 후 bytes로 변환 (Consumer를 위해)
            # tobytes()는 복사를 생성하지만 API 호환성을 위해 필요
            if chunk1_len == read_count:
                result = self._mv[self._tail : self._tail + chunk1_len].tobytes()
            else:
                chunk2_len = read_count - chunk1_len
                result = (self._mv[self._tail : self._tail + chunk1_len].tobytes() +
                          self._mv[0 : chunk2_len].tobytes())

            self._tail = (self._tail + read_count) % self._size
            self._stored_bytes -= read_count

            return result

    def clear(self) -> None:
        """버퍼를 비웁니다."""
        with self._lock:
            self._head = 0
            self._tail = 0
            self._stored_bytes = 0
