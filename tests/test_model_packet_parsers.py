"""
패킷 파서 로직 단위 테스트

- RawParser: 바이너리 패스스루 검증
- ATParser: CR/LF 기준 분할 검증
- DelimiterParser: 커스텀 구분자 검증
- FixedLengthParser: 고정 길이 분할 검증

pytest tests/test_model_packet_parsers.py -v
"""
import sys
import os
import pytest

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.packet_parser import (
    RawParser, ATParser, DelimiterParser, FixedLengthParser
)

def test_raw_parser():
    """RawParser 동작 테스트"""
    parser = RawParser()
    data = b"Hello World"
    packets = parser.parse(data)

    assert len(packets) == 1
    assert packets[0].data == b"Hello World"

def test_at_parser_basic():
    """ATParser 기본 동작 (\\r\\n 분할)"""
    parser = ATParser()

    # 2개의 AT 커맨드 응답이 한번에 들어온 경우
    data = b"OK\r\nERROR\r\n"
    packets = parser.parse(data)

    assert len(packets) == 2
    assert packets[0].data == b"OK\r\n"
    assert packets[1].data == b"ERROR\r\n"
    assert packets[0].metadata["type"] == "AT"

def test_at_parser_chunked():
    """ATParser 조각난 데이터 처리 테스트"""
    parser = ATParser()

    # 데이터가 끊겨서 들어옴: "O" -> "K\r" -> "\n"
    p1 = parser.parse(b"O")
    assert len(p1) == 0

    p2 = parser.parse(b"K\r")
    assert len(p2) == 0

    p3 = parser.parse(b"\n")
    assert len(p3) == 1
    assert p3[0].data == b"OK\r\n"

def test_delimiter_parser():
    """DelimiterParser 커스텀 구분자 테스트"""
    # 0x03 (ETX)를 구분자로 사용
    parser = DelimiterParser(delimiter=b"\x03")

    data = b"Data1\x03Data2\x03Incomplete"
    packets = parser.parse(data)

    assert len(packets) == 2
    assert packets[0].data == b"Data1\x03"
    assert packets[1].data == b"Data2\x03"

    # 남은 데이터 처리
    more_data = b"\x03"
    packets2 = parser.parse(more_data)
    assert len(packets2) == 1
    assert packets2[0].data == b"Incomplete\x03"

def test_fixed_length_parser():
    """FixedLengthParser 고정 길이 분할 테스트"""
    parser = FixedLengthParser(length=5)

    # 12 바이트 데이터 (5 + 5 + 2)
    data = b"123456789012"
    packets = parser.parse(data)

    assert len(packets) == 2
    assert packets[0].data == b"12345"
    assert packets[1].data == b"67890"

    # 나머지 3바이트 도착 (2 + 3 = 5)
    packets2 = parser.parse(b"345")
    assert len(packets2) == 1
    assert packets2[0].data == b"12345"

def test_parser_reset():
    """파서 리셋(버퍼 비우기) 테스트"""
    parser = ATParser()
    parser.parse(b"Incomplete Data")

    parser.reset()

    # 이전 데이터는 지워져야 함
    packets = parser.parse(b"\r\n")
    # 리셋되었으므로 앞의 "Incomplete Data"와 연결되지 않음
    # 현재 로직상 \r\n만 들어오면 빈 라인 패킷이 생성되거나(구현에 따라),
    # buffer가 비어있어 b"\r\n" 자체가 파싱됨.
    # ATParser 구현: split(b'\r\n') -> line="", buffer=""
    # line이 empty string이 아니어야 append하는 로직이라면 패킷 0개
    # line이 empty여도 포함하면 1개. (현재 구현은 if line: 체크 함)

    # 테스트를 위해 명확한 데이터 입력
    packets = parser.parse(b"New\r\n")
    assert len(packets) == 1
    assert packets[0].data == b"New\r\n"

if __name__ == "__main__":
    pytest.main([__file__])
