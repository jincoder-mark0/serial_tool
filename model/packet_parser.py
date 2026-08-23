"""
패킷 파서 모듈

수신 데이터를 다양한 방식으로 파싱하는 파서들과 Expect 매처를 제공합니다.

## WHY
* 프로토콜별 데이터 파싱 지원 (AT, Hex, Delimiter 등)
* 버퍼 오버플로우 방지 및 데이터 무결성 보장
* 매크로의 Expect 기능 지원

## WHAT
* PacketParser 추상 클래스 및 구현체 (Raw, AT, Delimiter, FixedLength)
* ExpectMatcher: 정규식 기반 응답 대기 매처
* ParserFactory: 파서 생성 팩토리

## HOW
* 전략 패턴을 사용하여 파서 알고리즘 캡슐화
* 내부 버퍼 관리로 불완전한 패킷 처리
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
import time
import re

from common.enums import ParserType
from common.constants import PARSER_MAX_BUFFER_SIZE, MAX_PACKET_SIZE
from core.logger import logger

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

class PacketParser(ABC):
    """
    패킷 파서 추상 기본 클래스 (Interface)

    모든 파서는 이 클래스를 상속받아 구현해야 합니다.
    """

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

    def flush(self) -> List[Packet]:
        """
        더 이상 데이터가 오지 않을 때 남은 조각을 확정합니다 (S-072).

        대부분의 파서는 완결 기준(구분자·길이)이 명확해 남은 조각이 패킷이 될 수
        없으므로 기본 구현은 빈 리스트를 돌려준다. **유휴 시간으로 프레임을 나누는
        `GapParser`만** 이 훅이 실제로 필요하다 — 데이터가 끊기면 `parse()` 호출
        자체가 없어 마지막 조각이 영영 확정되지 않기 때문이다.

        Returns:
            List[Packet]: 확정된 잔여 패킷 (없으면 빈 리스트).
        """
        return []

class RawParser(PacketParser):
    """바이너리 데이터를 그대로 전달하는 파서"""

    def parse(self, buffer: bytes) -> List[Packet]:
        """모든 데이터를 하나의 패킷으로 처리"""
        if not buffer:
            return []
        packet = Packet(data=buffer, timestamp=time.time())
        return [packet]

    def reset(self) -> None:
        pass

class ATParser(PacketParser):
    """
    AT Command 파서

    \\r\\n 구분자로 라인 단위 파싱, OK/ERROR 응답 처리
    """

    def __init__(self, max_buffer_size: int = PARSER_MAX_BUFFER_SIZE):
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
            - \\r\\n으로 라인 분리 (완결 패킷을 먼저 전부 분리)
            - 분리 후 남은 미완결 조각이 버퍼 크기 제한을 넘으면 그때만 버림
              (S-064: 자르기를 분리보다 먼저 하면 완결 패킷까지 함께 유실된다)
        """
        self._buffer += buffer

        packets = []

        while b'\r\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\r\n', 1)
            if line:
                packets.append(Packet(data=line + b'\r\n', timestamp=time.time(), metadata={"type": "AT"}))

        # 버퍼 크기 제한 (메모리 보호) — 완결 패킷을 모두 분리하고 남은 조각에만 적용
        if len(self._buffer) > self._max_buffer_size:
            dropped = len(self._buffer) - self._max_buffer_size
            logger.warning(
                f"ATParser: incomplete buffer exceeded max_buffer_size "
                f"({self._max_buffer_size} bytes); dropping {dropped} oldest byte(s)."
            )
            self._buffer = self._buffer[-self._max_buffer_size:]

        return packets

    def reset(self) -> None:
        self._buffer = b""

class DelimiterParser(PacketParser):
    """사용자 정의 구분자 기반 파서"""

    def __init__(self, delimiter: bytes = b'\n', max_buffer_size: int = PARSER_MAX_BUFFER_SIZE):
        """
        DelimiterParser 초기화

        Args:
            delimiter: 패킷 구분자
            max_buffer_size: 최대 버퍼 크기
        """
        if not delimiter:
            raise ValueError("delimiter must not be empty")
        if max_buffer_size <= 0:
            raise ValueError("max_buffer_size must be greater than zero")

        self._delimiter = delimiter
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        """
        구분자로 패킷 분리

        Logic:
            - 새 데이터를 내부 버퍼에 추가
            - 구분자로 완결 패킷을 먼저 전부 분리
            - 분리 후 남은 미완결 조각이 버퍼 크기 제한을 넘으면 그때만 버림
              (S-064: 자르기를 분리보다 먼저 하면 완결 패킷까지 함께 유실된다)
        """
        self._buffer += buffer

        packets = []

        while self._delimiter in self._buffer:
            chunk, self._buffer = self._buffer.split(self._delimiter, 1)
            packets.append(Packet(data=chunk + self._delimiter, timestamp=time.time()))

        # 버퍼 크기 제한 (메모리 보호) — 완결 패킷을 모두 분리하고 남은 조각에만 적용
        if len(self._buffer) > self._max_buffer_size:
            dropped = len(self._buffer) - self._max_buffer_size
            logger.warning(
                f"DelimiterParser: incomplete buffer exceeded max_buffer_size "
                f"({self._max_buffer_size} bytes); dropping {dropped} oldest byte(s)."
            )
            self._buffer = self._buffer[-self._max_buffer_size:]

        return packets

    def reset(self) -> None:
        self._buffer = b""

class FixedLengthParser(PacketParser):
    """고정 길이 패킷 파서"""

    def __init__(self, length: int, max_buffer_size: int = PARSER_MAX_BUFFER_SIZE):
        """
        FixedLengthParser 초기화

        Args:
            length: 패킷 길이 (bytes)
            max_buffer_size: 최대 버퍼 크기
        """
        if length <= 0:
            raise ValueError("length must be greater than zero")
        if max_buffer_size <= 0:
            raise ValueError("max_buffer_size must be greater than zero")

        self._length = length
        self._buffer = b""
        self._max_buffer_size = max_buffer_size

    def parse(self, buffer: bytes) -> List[Packet]:
        """
        고정 길이로 패킷 분리

        Logic:
            - 새 데이터를 내부 버퍼에 추가
            - self._length 배수만큼 완결 패킷을 먼저 전부 분리
            - 분리 후 남은 미완결 조각(length 미만)이 버퍼 크기 제한을 넘으면 그때만 버림
              (S-064: 자르기를 분리보다 먼저 하면 완결 패킷까지 함께 유실된다.
              DelimiterParser/ATParser와 동일하게 "길이 도달"이 여기서의 완결 기준이다.)
        """
        self._buffer += buffer

        packets = []

        while len(self._buffer) >= self._length:
            chunk = self._buffer[:self._length]
            self._buffer = self._buffer[self._length:]
            packets.append(Packet(data=chunk, timestamp=time.time()))

        # 버퍼 크기 제한 (메모리 보호) — 완결 패킷을 모두 분리하고 남은 조각에만 적용
        if len(self._buffer) > self._max_buffer_size:
            dropped = len(self._buffer) - self._max_buffer_size
            logger.warning(
                f"FixedLengthParser: incomplete buffer exceeded max_buffer_size "
                f"({self._max_buffer_size} bytes); dropping {dropped} oldest byte(s)."
            )
            self._buffer = self._buffer[-self._max_buffer_size:]

        return packets

    def reset(self) -> None:
        self._buffer = b""

class LengthFieldParser(PacketParser):
    """
    헤더 안의 길이 필드로 가변 길이 패킷을 분리하는 파서 (S-072)

    `[SOF][LEN][PAYLOAD...][CRC]`처럼 패킷마다 길이가 달라지는 프로토콜을 다룬다.
    `FixedLengthParser`는 상수 길이만 알아서 이런 형식을 나눌 수 없다.
    """

    def __init__(
        self,
        offset: int = 0,
        size: int = 1,
        endian: str = "big",
        includes_header: bool = False,
        max_packet_size: int = MAX_PACKET_SIZE,
        max_buffer_size: int = PARSER_MAX_BUFFER_SIZE,
    ):
        """
        LengthFieldParser 초기화

        Args:
            offset: 패킷 선두에서 길이 필드까지의 바이트 수.
            size: 길이 필드 자체의 바이트 수 (1/2/4).
            endian: 길이 필드의 바이트 순서 ("big" 또는 "little").
            includes_header: 길이 값이 헤더를 포함한 전체 길이면 True,
                길이 필드 뒤의 바이트 수만 세면 False.
            max_packet_size: 정상으로 인정할 최대 패킷 크기 (기형 길이 값 방어).
            max_buffer_size: 미완결 조각 버퍼 상한.

        Raises:
            ValueError: 인자가 유효 범위를 벗어난 경우.
        """
        if offset < 0:
            raise ValueError("offset must be zero or greater")
        if size not in (1, 2, 4):
            raise ValueError("size must be one of 1, 2, 4")
        if endian not in ("big", "little"):
            raise ValueError("endian must be 'big' or 'little'")
        if max_packet_size <= 0 or max_buffer_size <= 0:
            raise ValueError("max sizes must be greater than zero")

        self._offset = offset
        self._size = size
        self._endian = endian
        self._includes_header = includes_header
        self._max_packet_size = max_packet_size
        self._max_buffer_size = max_buffer_size
        self._buffer = b""

    def _total_length(self, value: int) -> int:
        """길이 필드 값으로부터 패킷 전체 길이를 계산한다."""
        if self._includes_header:
            return value
        return self._offset + self._size + value

    def parse(self, buffer: bytes) -> List[Packet]:
        """
        길이 필드를 읽어 가변 길이 패킷을 분리합니다.

        Logic:
            - 헤더(offset+size)가 다 오지 않았으면 더 기다린다.
            - 길이 값이 기형(전체 길이가 헤더보다 짧거나 상한 초과)이면 **1바이트를
              버리고 재동기화**한다. 그대로 두면 같은 위치에서 영원히 막힌다.
            - 완결 패킷을 전부 분리한 **뒤에** 남은 조각에만 버퍼 상한을 적용한다
              (S-064 — 순서를 뒤집으면 완결 패킷까지 잘려나간다).
        """
        self._buffer += buffer
        packets: List[Packet] = []
        header_size = self._offset + self._size

        while len(self._buffer) >= header_size:
            raw_len = self._buffer[self._offset:header_size]
            total = self._total_length(int.from_bytes(raw_len, byteorder=self._endian))

            if total < header_size or total > self._max_packet_size:
                logger.warning(
                    f"LengthFieldParser: invalid length {total} "
                    f"(header={header_size}, max={self._max_packet_size}); resyncing by 1 byte."
                )
                self._buffer = self._buffer[1:]
                continue

            if len(self._buffer) < total:
                break

            packets.append(Packet(data=self._buffer[:total], timestamp=time.time()))
            self._buffer = self._buffer[total:]

        if len(self._buffer) > self._max_buffer_size:
            dropped = len(self._buffer) - self._max_buffer_size
            logger.warning(
                f"LengthFieldParser: incomplete buffer exceeded max_buffer_size "
                f"({self._max_buffer_size} bytes); dropping {dropped} oldest byte(s)."
            )
            self._buffer = self._buffer[-self._max_buffer_size:]

        return packets

    def reset(self) -> None:
        self._buffer = b""


class GapParser(PacketParser):
    """
    유휴 시간(gap)으로 프레임을 나누는 파서 (S-072)

    구분자도 길이 필드도 없이 **일정 시간 침묵**으로 프레임을 구분하는 프로토콜용이다.
    Modbus RTU의 3.5문자 유휴가 대표적이다.

    ## 한계 (설계상 명시)
    파서는 `parse()`가 호출될 때만 시간을 볼 수 있다. 따라서 유휴는 **다음 데이터가
    도착했을 때** 소급 판정된다. 데이터가 완전히 끊기면 마지막 조각은 `flush()`를
    호출해 줘야 확정된다(포트 종료·앱 종료 경로에서 호출). 살아 있는 유휴 타이머를
    두려면 Model 계층에 타이머와 스레드 친화성 설계가 필요해 이번 범위에서 제외했다.

    또한 한 번의 `parse()` 호출로 들어온 바이트 묶음 **안쪽의** 유휴는 감지할 수 없다.
    바이트별 도착 시각이 남지 않기 때문이다(워커가 배치로 넘긴다).
    """

    def __init__(
        self,
        gap_ms: int = 5,
        max_buffer_size: int = PARSER_MAX_BUFFER_SIZE,
        time_source=None,
    ):
        """
        GapParser 초기화

        Args:
            gap_ms: 이 시간(ms) 이상 데이터가 없으면 프레임 경계로 본다.
            max_buffer_size: 미완결 조각 버퍼 상한.
            time_source: 시각 조회 함수 (기본 `time.monotonic`). 테스트에서 시간을
                주입하기 위한 것 — 실제 경과 시간에 의존하는 테스트는 느리고 불안정하다.

        Raises:
            ValueError: gap_ms 또는 max_buffer_size가 0 이하인 경우.
        """
        if gap_ms <= 0:
            raise ValueError("gap_ms must be greater than zero")
        if max_buffer_size <= 0:
            raise ValueError("max_buffer_size must be greater than zero")

        self._gap_s = gap_ms / 1000.0
        self._max_buffer_size = max_buffer_size
        self._now = time_source or time.monotonic
        self._buffer = b""
        self._last_seen = None

    def parse(self, buffer: bytes) -> List[Packet]:
        """
        직전 수신 이후 유휴가 있었으면 그때까지 모인 바이트를 한 패킷으로 확정합니다.

        Logic:
            - **새 데이터를 붙이기 전에** 유휴를 판정한다. 유휴가 있었다면 이전
              버퍼가 완결된 프레임이고, 새 데이터는 다음 프레임의 시작이다.
            - 완결 처리 후 남은 조각에만 버퍼 상한을 적용한다 (S-064 순서 규칙).
        """
        now = self._now()
        packets: List[Packet] = []

        if self._buffer and self._last_seen is not None:
            if (now - self._last_seen) >= self._gap_s:
                packets.append(Packet(data=self._buffer, timestamp=time.time()))
                self._buffer = b""

        self._buffer += buffer
        self._last_seen = now

        if len(self._buffer) > self._max_buffer_size:
            dropped = len(self._buffer) - self._max_buffer_size
            logger.warning(
                f"GapParser: incomplete buffer exceeded max_buffer_size "
                f"({self._max_buffer_size} bytes); dropping {dropped} oldest byte(s)."
            )
            self._buffer = self._buffer[-self._max_buffer_size:]

        return packets

    def flush(self) -> List[Packet]:
        """
        남은 조각을 마지막 프레임으로 확정합니다 (포트 종료·앱 종료 시).

        Returns:
            List[Packet]: 잔여가 있으면 한 개, 없으면 빈 리스트.
        """
        if not self._buffer:
            return []
        packet = Packet(data=self._buffer, timestamp=time.time())
        self._buffer = b""
        return [packet]

    def reset(self) -> None:
        self._buffer = b""
        self._last_seen = None


class ParserFactory:
    """파서 생성 팩토리"""

    @staticmethod
    def create_parser(parser_type: str, **kwargs) -> PacketParser:
        """
        파서 타입에 따라 적절한 파서 인스턴스 생성

        Args:
            parser_type: 파서 타입 (ParserType 상수)
            **kwargs: 파서별 추가 인자

        Returns:
            PacketParser: 생성된 파서 인스턴스
        """
        if parser_type == ParserType.AT:
            return ATParser()
        elif parser_type == ParserType.DELIMITER:
            delimiter = kwargs.get("delimiter", b'\n')
            return DelimiterParser(delimiter)
        elif parser_type == ParserType.FIXED_LENGTH:
            length = kwargs.get("length", 10)
            return FixedLengthParser(length)
        elif parser_type == ParserType.LENGTH_FIELD:
            return LengthFieldParser(
                offset=kwargs.get("length_field_offset", 0),
                size=kwargs.get("length_field_size", 1),
                endian=kwargs.get("length_field_endian", "big"),
                includes_header=kwargs.get("length_includes_header", False),
            )
        elif parser_type == ParserType.GAP:
            return GapParser(gap_ms=kwargs.get("gap_ms", 5))
        else:
            return RawParser()

class ExpectMatcher:
    """
    정규식 기반 응답 대기 및 매칭 클래스

    매크로 Expect 기능에서 특정 응답을 기다릴 때 사용합니다.
    """
    def __init__(self, pattern: str, regex_enabled: bool = False, max_buffer_size: int = 1024 * 1024):
        """
        ExpectMatcher 초기화

        Args:
            pattern: 매칭할 패턴 (문자열 또는 정규식)
            regex_enabled: 정규식 사용 여부
            max_buffer_size: 최대 버퍼 크기 (기본 1MB)
        """
        self.pattern = pattern
        self.regex_enabled = regex_enabled
        self.max_buffer_size = max_buffer_size
        self._buffer = b""
        self._regex = None
        self._target_bytes = b""

        if regex_enabled:
            try:
                # bytes로 매칭하기 위해 pattern을 bytes로 인코딩
                self._regex = re.compile(pattern.encode('utf-8'))
            except re.error:
                # 유효하지 않은 정규식인 경우 리터럴 매칭으로 fallback
                self.regex_enabled = False
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

        if self.regex_enabled and self._regex:
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
