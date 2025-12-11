from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass

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
        파싱된 데이터는 버퍼에서 제거된 것으로 간주하거나, 
        호출자가 반환된 패킷 길이만큼 버퍼를 비워야 합니다.
        (여기서는 파싱된 패킷 리스트만 반환하고 버퍼 관리는 호출자에게 위임하는 구조가 일반적이나,
         구현 편의를 위해 파싱 후 남은 버퍼를 반환하거나, 내부 상태를 가질 수 있음)
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """파서 상태 초기화"""
        pass

class RawParser(IPacketParser):
    """바이너리 데이터를 그대로 패스하는 파서"""
    
    def parse(self, buffer: bytes) -> List[Packet]:
        import time
        if not buffer:
            return []
        # 모든 데이터를 하나의 패킷으로 처리
        packet = Packet(data=buffer, timestamp=time.time())
        return [packet]

    def reset(self) -> None:
        pass

class ATParser(IPacketParser):
    """AT Command 파서 (\r\n 구분, OK/ERROR 응답 처리)"""
    
    def __init__(self):
        self._buffer = b""

    def parse(self, buffer: bytes) -> List[Packet]:
        import time
        self._buffer += buffer
        packets = []
        
        while b'\r\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\r\n', 1)
            # 빈 줄 무시 옵션이 필요할 수 있음
            if line:
                packets.append(Packet(data=line + b'\r\n', timestamp=time.time(), metadata={"type": "AT"}))
        
        return packets

    def reset(self) -> None:
        self._buffer = b""

class DelimiterParser(IPacketParser):
    """구분자 기반 파서"""
    
    def __init__(self, delimiter: bytes = b'\n'):
        self._delimiter = delimiter
        self._buffer = b""

    def parse(self, buffer: bytes) -> List[Packet]:
        import time
        self._buffer += buffer
        packets = []
        
        while self._delimiter in self._buffer:
            chunk, self._buffer = self._buffer.split(self._delimiter, 1)
            packets.append(Packet(data=chunk + self._delimiter, timestamp=time.time()))
            
        return packets

    def reset(self) -> None:
        self._buffer = b""

class FixedLengthParser(IPacketParser):
    """고정 길이 파서"""
    
    def __init__(self, length: int):
        self._length = length
        self._buffer = b""

    def parse(self, buffer: bytes) -> List[Packet]:
        import time
        self._buffer += buffer
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
