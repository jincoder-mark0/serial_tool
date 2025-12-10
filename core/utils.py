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
from core.constants import RING_BUFFER_SIZE

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
    바이트 데이터를 효율적으로 저장하고 읽어오며, 오버플로우 시 오래된 데이터를 덮어씁니다.
    """

    def __init__(self, size: int = RING_BUFFER_SIZE):
        """
        RingBuffer를 초기화합니다.

        Args:
            size (int): 버퍼 크기 (바이트 단위). 기본값은 상수로 정의됨.
        """
        self._size = size
        self._buffer = bytearray(size)
        self._head = 0  # 쓰기 포인터
        self._tail = 0  # 읽기 포인터
        self._stored_bytes = 0 # 현재 데이터 양
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        """
        데이터를 버퍼에 씁니다. 버퍼가 가득 차면 오래된 데이터를 덮어씁니다.

        Args:
            data (bytes): 쓸 데이터.

        Returns:
            int: 쓰여진 바이트 수.
        """
        data_len = len(data)
        if data_len == 0:
            return 0

        with self._lock:
            # 데이터가 버퍼 크기보다 크면 뒷부분만 남김
            if data_len > self._size:
                data = data[-self._size:]
                data_len = self._size

            # 1. 버퍼 끝까지의 여유 공간 계산
            space_at_end = self._size - self._head

            # 2. 복사할 데이터 길이 계산
            chunk1_len = min(data_len, space_at_end)
            chunk2_len = data_len - chunk1_len

            # 3. 데이터 복사 (chunk1)
            self._buffer[self._head : self._head + chunk1_len] = data[:chunk1_len]

            # 4. 데이터 복사 (chunk2 - 랩어라운드)
            if chunk2_len > 0:
                self._buffer[0 : chunk2_len] = data[chunk1_len:]

            # 5. 포인터 업데이트
            self._head = (self._head + data_len) % self._size

            # 6. Count 및 Tail 업데이트 (덮어쓰기 감지)
            if self._stored_bytes + data_len > self._size:
                # 오버플로우 발생: Tail을 Head 뒤로 이동
                overlap = (self._stored_bytes + data_len) - self._size
                self._tail = (self._tail + overlap) % self._size
                self._stored_bytes = self._size
            else:
                self._stored_bytes += data_len

            return data_len

    def read(self, count: int) -> bytes:
        """
        버퍼에서 데이터를 읽어옵니다 (소비합니다).

        Args:
            count (int): 읽을 바이트 수.

        Returns:
            bytes: 읽은 데이터.
        """
        with self._lock:
            if self._stored_bytes == 0:
                return b""

            read_stored_bytes = min(count, self._stored_bytes)

            # 1. 버퍼 끝까지 읽을 수 있는 양
            space_at_end = self._size - self._tail
            chunk1_len = min(read_stored_bytes, space_at_end)
            chunk2_len = read_stored_bytes - chunk1_len

            # 2. 데이터 읽기
            result = self._buffer[self._tail : self._tail + chunk1_len]
            if chunk2_len > 0:
                result += self._buffer[0 : chunk2_len]

            # 3. 포인터 업데이트
            self._tail = (self._tail + read_stored_bytes) % self._size
            self._stored_bytes -= read_stored_bytes

            return bytes(result)

    def clear(self) -> None:
        """버퍼를 비웁니다."""
        with self._lock:
            self._head = 0
            self._tail = 0
            self._stored_bytes = 0
