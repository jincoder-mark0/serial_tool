import threading
from collections import deque
from typing import Optional, List

class ThreadSafeQueue:
    """
    스레드 안전한 큐 래퍼 클래스입니다.
    """
    def __init__(self):
        self._queue = deque()
        self._lock = threading.Lock()

    def enqueue(self, item):
        with self._lock:
            self._queue.append(item)

    def dequeue(self):
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def is_empty(self):
        with self._lock:
            return len(self._queue) == 0

    def clear(self):
        with self._lock:
            self._queue.clear()

class RingBuffer:
    """
    고정 크기 링 버퍼입니다.
    """
    def __init__(self, size: int = 1024):
        self._size = size
        self._buffer = bytearray(size)
        self._head = 0
        self._tail = 0
        self._count = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        with self._lock:
            written = 0
            for byte in data:
                if self._count < self._size:
                    self._buffer[self._head] = byte
                    self._head = (self._head + 1) % self._size
                    self._count += 1
                    written += 1
                else:
                    # Overwrite or drop? 
                    # For serial rx, usually we might overwrite old data or block.
                    # Here we overwrite (circular) and advance tail
                    self._buffer[self._head] = byte
                    self._head = (self._head + 1) % self._size
                    self._tail = (self._tail + 1) % self._size # Push tail
                    written += 1
            return written

    def read(self, count: int) -> bytes:
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
        with self._lock:
            self._head = 0
            self._tail = 0
            self._count = 0
