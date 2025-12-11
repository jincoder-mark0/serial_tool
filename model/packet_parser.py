from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass
import time

@dataclass
class Packet:
    """파싱된 패킷 데이터"""
    data: bytes
    timestamp: float
    metadata: Optional[dict] = None

class IPacketParser(ABC):
    """패킷 파서 인터페이스"""
    
    @abstractmethod
    def parse(self, buffer: bytes) -> List[Packet]:
        """
        버퍼 데이터를 파싱하여 패킷 리스트를 반환합니다.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """파서 상태 초기화"""
        pass

class RawParser(IPacketParser):
    """바이너리 데이터를 그대로 패스하는 파서"""
    
    def parse(self, buffer: bytes) -> List[Packet]:
        if not buffer:
            return []
        # 모든 데이터를 하나의 패킷으로 처리
        packet = Packet(data=buffer, timestamp=time.time())
        return [packet]

    def reset(self) -> None:
        pass

class ATParser(IPacketParser):
    """AT Command 파서 (\r\n 구분, OK/ERROR 응답 처리)"""
    
    def __init__(self, max_buffer_size: int = 4096):
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        self._buffer += buffer
        
        # 버퍼 크기 제한 (메모리 보호)
        if len(self._buffer) > self._max_buffer_size:
            # 오래된 데이터 버림 (또는 에러 처리)
            self._buffer = self._buffer[-self._max_buffer_size:]
            
        packets = []
        
        while b'\r\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\r\n', 1)
            if line:
                packets.append(Packet(data=line + b'\r\n', timestamp=time.time(), metadata={"type": "AT"}))
        
        return packets

    def reset(self) -> None:
        self._buffer = b""

class DelimiterParser(IPacketParser):
    """구분자 기반 파서"""
    
    def __init__(self, delimiter: bytes = b'\n', max_buffer_size: int = 4096):
        self._delimiter = delimiter
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        self._buffer += buffer

        # 버퍼 크기 제한
        if len(self._buffer) > self._max_buffer_size:
            self._buffer = self._buffer[-self._max_buffer_size:]

        packets = []
        
        while self._delimiter in self._buffer:
            chunk, self._buffer = self._buffer.split(self._delimiter, 1)
            packets.append(Packet(data=chunk + self._delimiter, timestamp=time.time()))
            
        return packets

    def reset(self) -> None:
        self._buffer = b""

class FixedLengthParser(IPacketParser):
    """고정 길이 파서"""
    
    def __init__(self, length: int, max_buffer_size: int = 4096):
        self._length = length
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        self._buffer += buffer

        # 버퍼 크기 제한
        if len(self._buffer) > self._max_buffer_size:
            self._buffer = self._buffer[-self._max_buffer_size:]

        packets = []

        while len(self._buffer) >= self._length:
            chunk = self._buffer[:self._length]
            self._buffer = self._buffer[self._length:]
            packets.append(Packet(data=chunk, timestamp=time.time()))
            
        return packets

    def reset(self) -> None:
        self._buffer = b""

class ParserFactory:
    """파서 팩토리"""
    
    @staticmethod
    def create_parser(parser_type: str, **kwargs) -> IPacketParser:
        if parser_type == "AT":
            return ATParser()
        elif parser_type == "Delimiter":
            delimiter = kwargs.get("delimiter", b'\n')
            return DelimiterParser(delimiter)
        elif parser_type == "FixedLength":
            length = kwargs.get("length", 10)
            return FixedLengthParser(length)
        else:
            return RawParser()
