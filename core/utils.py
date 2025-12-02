import threading
from collections import deque
from typing import Optional, Any

class ThreadSafeQueue:
    """
    스레드 안전한(Thread-safe) 큐 래퍼 클래스입니다.
    내부적으로 deque와 Lock을 사용하여 구현되었습니다.
    """
    def __init__(self):
        """ThreadSafeQueue를 초기화합니다."""
        self._queue = deque()
        self._lock = threading.Lock()

    def enqueue(self, item: Any):
        """
        아이템을 큐에 추가합니다.
        
        Args:
            item (Any): 추가할 아이템.
        """
        with self._lock:
            self._queue.append(item)

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

    def clear(self):
        """큐의 모든 아이템을 제거합니다."""
        with self._lock:
            self._queue.clear()

class RingBuffer:
    """
    고정 크기 링 버퍼(Circular Buffer) 클래스입니다.
    바이트 데이터를 효율적으로 저장하고 읽어옵니다.
    """
    def __init__(self, size: int = 1024):
        """
        RingBuffer를 초기화합니다.
        
        Args:
            size (int): 버퍼 크기 (바이트 단위). 기본값은 1024.
        """
        self._size = size
        self._buffer = bytearray(size)
        self._head = 0
        self._tail = 0
        self._count = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        """
        데이터를 버퍼에 씁니다. 버퍼가 가득 차면 오래된 데이터를 덮어씁니다.
        
        Args:
            data (bytes): 쓸 데이터.
            
        Returns:
            int: 쓰여진 바이트 수.
        """
        with self._lock:
            written = 0
            for byte in data:
                if self._count < self._size:
                    self._buffer[self._head] = byte
                    self._head = (self._head + 1) % self._size
                    self._count += 1
                    written += 1
                else:
                    # 덮어쓰기 모드 (Circular)
                    # 오래된 데이터(tail)를 덮어쓰고 tail을 이동시킴
                    self._buffer[self._head] = byte
                    self._head = (self._head + 1) % self._size
                    self._tail = (self._tail + 1) % self._size # Tail 이동
                    written += 1
            return written

    def read(self, count: int) -> bytes:
        """
        버퍼에서 데이터를 읽어옵니다.
        
        Args:
            count (int): 읽을 바이트 수.
            
        Returns:
            bytes: 읽은 데이터.
        """
        with self._lock:
            if self._count == 0:
                return b""
            
            read_count = min(count, self._count)
            result = bytearray(read_count)
            
            for i in range(read_count):
                result[i] = self._buffer[self._tail]
                self._tail = (self._tail + 1) % self._size
                self._count -= 1
                
            return bytes(result)

    def clear(self):
        """버퍼를 비웁니다."""
        with self._lock:
            self._head = 0
            self._tail = 0
            self._count = 0
