"""
패킷 파서 모듈

수신 데이터를 다양한 방식으로 파싱하는 파서들을 제공합니다.

## WHY
* 프로토콜별 데이터 파싱 지원
* 버퍼 오버플로우 방지
* 패킷 단위 처리로 데이터 무결성 보장
* 확장 가능한 파서 아키텍처
* 매크로의 Expect 기능 지원 (패턴 매칭)

## WHAT
* IPacketParser 인터페이스 정의
* RawParser (바이너리 그대로 전달)
* ATParser (AT Command, \\r\\n 구분)
* DelimiterParser (사용자 정의 구분자)
* FixedLengthParser (고정 길이 패킷)
* ExpectMatcher (정규식 기반 응답 대기)
* ParserFactory (파서 생성 팩토리)

## HOW
* ABC로 인터페이스 정의
* 내부 버퍼로 불완전한 패킷 보관
* 버퍼 크기 제한으로 메모리 보호
* Packet dataclass로 타임스탬프 및 메타데이터 포함
* Factory 패턴으로 파서 생성
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass
import time
import re

class ParserType:
    """파서 타입 상수"""
    RAW = "Raw"
    AT = "AT"
    DELIMITER = "Delimiter"
    FIXED_LENGTH = "FixedLength"

@dataclass
class Packet:
    """
    파싱된 패킷 데이터

    Attributes:
        data: 패킷 바이트 데이터
        timestamp: 수신 시각 (Unix timestamp)
        metadata: 추가 정보 (파서 타입, 상태 등)
    """
    data: bytes
    timestamp: float
    metadata: Optional[dict] = None

class IPacketParser(ABC):
    """패킷 파서 인터페이스"""

    @abstractmethod
    def parse(self, buffer: bytes) -> List[Packet]:
        """
        버퍼 데이터를 파싱하여 패킷 리스트 반환

        Args:
            buffer: 파싱할 바이트 데이터

        Returns:
            List[Packet]: 파싱된 패킷 리스트
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """파서 상태 초기화 (내부 버퍼 클리어)"""
        pass

class RawParser(IPacketParser):
    """바이너리 데이터를 그대로 전달하는 파서"""

    def parse(self, buffer: bytes) -> List[Packet]:
        """모든 데이터를 하나의 패킷으로 처리"""
        if not buffer:
            return []
        packet = Packet(data=buffer, timestamp=time.time())
        return [packet]

    def reset(self) -> None:
        pass

class ATParser(IPacketParser):
    """
    AT Command 파서

    \\r\\n 구분자로 라인 단위 파싱, OK/ERROR 응답 처리
    """

    def __init__(self, max_buffer_size: int = 4096):
        """
        ATParser 초기화

        Args:
            max_buffer_size: 최대 버퍼 크기 (메모리 보호)
        """
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        """
        \\r\\n 구분자로 라인 단위 파싱

        Logic:
            - 새 데이터를 내부 버퍼에 추가
            - 버퍼 크기 제한 확인 (초과 시 오래된 데이터 버림)
            - \\r\\n으로 라인 분리
            - 각 라인을 Packet으로 변환
        """
        self._buffer += buffer

        # 버퍼 크기 제한 (메모리 보호)
        if len(self._buffer) > self._max_buffer_size:
            # 오래된 데이터 버림
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
    """사용자 정의 구분자 기반 파서"""

    def __init__(self, delimiter: bytes = b'\n', max_buffer_size: int = 4096):
        """
        DelimiterParser 초기화

        Args:
            delimiter: 패킷 구분자
            max_buffer_size: 최대 버퍼 크기
        """
        self._delimiter = delimiter
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        """구분자로 패킷 분리"""
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
    """고정 길이 패킷 파서"""

    def __init__(self, length: int, max_buffer_size: int = 4096):
        """
        FixedLengthParser 초기화

        Args:
            length: 패킷 길이 (bytes)
            max_buffer_size: 최대 버퍼 크기
        """
        self._length = length
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        """고정 길이로 패킷 분리"""
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
    """파서 생성 팩토리"""

    @staticmethod
    def create_parser(parser_type: str, **kwargs) -> IPacketParser:
        """
        파서 타입에 따라 적절한 파서 인스턴스 생성

        Args:
            parser_type: 파서 타입 (ParserType 상수)
            **kwargs: 파서별 추가 인자

        Returns:
            IPacketParser: 생성된 파서 인스턴스
        """
        if parser_type == ParserType.AT:
            return ATParser()
        elif parser_type == ParserType.DELIMITER:
            delimiter = kwargs.get("delimiter", b'\n')
            return DelimiterParser(delimiter)
        elif parser_type == ParserType.FIXED_LENGTH:
            length = kwargs.get("length", 10)
            return FixedLengthParser(length)
        else:
            return RawParser()

class ExpectMatcher:
    """
    정규식 기반 응답 대기 및 매칭 클래스

    매크로 Expect 기능에서 특정 응답을 기다릴 때 사용합니다.
    """
    def __init__(self, pattern: str, is_regex: bool = False, max_buffer_size: int = 1024 * 1024):
        """
        ExpectMatcher 초기화

        Args:
            pattern: 매칭할 패턴 (문자열 또는 정규식)
            is_regex: 정규식 사용 여부
            max_buffer_size: 최대 버퍼 크기 (기본 1MB)
        """
        self.pattern = pattern
        self.is_regex = is_regex
        self.max_buffer_size = max_buffer_size
        self._buffer = b""
        self._regex = None
        self._target_bytes = b""

        if is_regex:
            try:
                # bytes로 매칭하기 위해 pattern을 bytes로 인코딩
                self._regex = re.compile(pattern.encode('utf-8'))
            except re.error:
                # 유효하지 않은 정규식인 경우 리터럴 매칭으로 fallback
                self.is_regex = False
                self._target_bytes = pattern.encode('utf-8')
        else:
            self._target_bytes = pattern.encode('utf-8')

    def match(self, data: bytes) -> bool:
        """
        데이터를 버퍼에 추가하고 매칭 여부 확인

        Logic:
            - 새 데이터를 버퍼에 추가
            - 버퍼 크기 제한 확인 (오래된 데이터 삭제)
            - 정규식 또는 리터럴 매칭 수행

        Args:
            data: 수신된 바이트 데이터

        Returns:
            bool: 패턴이 매칭되면 True
        """
        self._buffer += data

        # 버퍼 크기 제한 (메모리 보호)
        if len(self._buffer) > self.max_buffer_size:
            self._buffer = self._buffer[-self.max_buffer_size:]

        if self.is_regex and self._regex:
            # search는 부분 매칭도 허용
            if self._regex.search(self._buffer):
                return True
        else:
            if self._target_bytes in self._buffer:
                return True

        return False

    def reset(self) -> None:
        """버퍼 초기화"""
        self._buffer = b""
