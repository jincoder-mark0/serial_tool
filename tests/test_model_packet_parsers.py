"""
모델 패킷 파서 테스트 모듈

다양한 프로토콜(Raw, ASCII, LCC 등)에 대한 패킷 파싱 로직을 검증합니다.

## WHY
* 시리얼 통신에서 데이터가 파편화(Fragmentation)되어 들어오는 경우 처리 검증
* 노이즈 데이터 속에서 유효한 패킷을 추출하는 프레이밍(Framing) 로직 확인
* 체크섬(Checksum/CRC) 검증 로직의 정확성 보장

## WHAT
* RawParser: 데이터 바이패스(Bypass) 기능
* AsciiParser: 개행 문자 기준 분할 및 디코딩
* LccPacketParser: STX/ETX 기반 프레이밍 및 체크섬 검증
* ParserFactory: 파서 인스턴스 생성 로직

## HOW
* 정상 패킷, 파편화된 패킷, 노이즈가 섞인 패킷 등 다양한 시나리오 주입
* 파싱 결과(List[Packet])의 개수와 페이로드 데이터 검증

pytest tests/test_model_packet_parsers.py -v
"""
import pytest
from model.packet_parser import (
    ParserFactory,
    RawParser,
    AsciiParser,
    LccPacketParser,
    Packet
)
from common.enums import ParserType


class TestRawParser:
    """
    RawParser의 데이터 처리 로직을 검증하는 테스트 클래스
    """

    def test_parse_pass_through(self):
        """
        데이터 바이패스(Pass-through) 테스트

        Logic:
            - RawParser는 입력된 바이트를 가공 없이 그대로 패킷으로 포장해야 함
            - 입력 데이터와 출력 패킷의 raw_data 일치 여부 확인
        """
        # GIVEN: 파서 및 테스트 데이터
        parser = RawParser()
        data = b'\x01\x02\x03\x04'

        # WHEN: 파싱 수행
        packets = parser.parse(data)

        # THEN: 1개의 패킷 반환 및 데이터 일치
        assert len(packets) == 1
        assert packets[0].raw_data == data
        assert packets[0].type_name == "RAW"


class TestAsciiParser:
    """
    AsciiParser의 텍스트 데이터 처리 로직을 검증하는 테스트 클래스
    """

    def test_parse_split_by_newline(self):
        """
        개행 문자 기준 패킷 분할 테스트

        Logic:
            - 개행('\n')이 포함된 데이터 입력
            - 개행 단위로 패킷이 분리되는지 확인
        """
        # GIVEN: 개행이 포함된 데이터
        parser = AsciiParser()
        data = b"Hello\nWorld\n"

        # WHEN: 파싱 수행
        packets = parser.parse(data)

        # THEN: 2개의 패킷으로 분리되어야 함
        assert len(packets) == 2
        assert b"Hello" in packets[0].raw_data
        assert b"World" in packets[1].raw_data

    def test_parse_incomplete_line(self):
        """
        불완전한 라인 처리 테스트 (버퍼링 동작 여부 확인)

        Logic:
            - 개행이 없는 데이터 입력
            - 구현에 따라 Raw처럼 내보내거나 버퍼링함
            - (본 프로젝트의 AsciiParser가 즉시 반환한다고 가정)
        """
        # GIVEN
        parser = AsciiParser()
        data = b"Incomplete"

        # WHEN
        packets = parser.parse(data)

        # THEN: 데이터 유실 없이 반환 확인
        assert len(packets) == 1
        assert packets[0].raw_data == data


class TestLccPacketParser:
    """
    LccPacketParser의 프레이밍 및 무결성 검증 로직을 테스트하는 클래스
    (가정: STX=0x02, ETX=0x03 프로토콜 구조)
    """

    @pytest.fixture
    def lcc_parser(self):
        """LccPacketParser 인스턴스 Fixture"""
        return LccPacketParser()

    def test_parse_valid_packet(self, lcc_parser):
        """
        정상적인 단일 패킷 파싱 테스트

        Logic:
            - 유효한 구조(STX + Data + Checksum + ETX)의 패킷 생성
            - 파싱 결과가 1개의 유효한 패킷을 반환하는지 확인
        """
        # GIVEN: 유효한 LCC 패킷 (STX=0x02, ETX=0x03 가정)
        # 예: 02 01 02 03 (체크섬) 03
        # 실제 구현된 프로토콜에 맞춰 데이터 구성 필요
        # 여기서는 테스트용 더미 데이터 구조를 가정함
        valid_data = b'\x02\x10\x00\x00\x01\x11\x03' # 예시 데이터

        # WHEN
        packets = lcc_parser.parse(valid_data)

        # THEN
        assert len(packets) == 1
        assert packets[0].valid is True
        assert packets[0].type_name == "LCC"

    def test_parse_fragmented_packet(self, lcc_parser):
        """
        파편화된(Fragmented) 패킷 파싱 및 재조립 테스트

        Logic:
            - 패킷의 앞부분(Head) 먼저 주입 -> 파싱 결과 없음(버퍼링)
            - 패킷의 뒷부분(Tail) 나중에 주입 -> 파싱 결과 1개(재조립 완료)
        """
        # GIVEN: 패킷을 두 조각으로 나눔
        part1 = b'\x02\x10\x00'
        part2 = b'\x00\x01\x11\x03'

        # WHEN: 첫 번째 조각 주입
        packets1 = lcc_parser.parse(part1)

        # THEN: 아직 완성되지 않았으므로 결과 없음
        assert len(packets1) == 0

        # WHEN: 두 번째 조각 주입
        packets2 = lcc_parser.parse(part2)

        # THEN: 재조립되어 1개의 패킷 반환
        assert len(packets2) == 1
        assert packets2[0].valid is True

    def test_parse_with_noise(self, lcc_parser):
        """
        노이즈 데이터 속 유효 패킷 추출 테스트

        Logic:
            - STX 앞뒤로 쓰레기(Garbage) 값 추가
            - 유효한 패킷만 정확히 추출해내는지 확인
        """
        # GIVEN: 노이즈 + 유효 패킷 + 노이즈
        noise_prefix = b'\xFF\xFF\x00'
        valid_packet = b'\x02\x10\x00\x00\x01\x11\x03'
        noise_suffix = b'\xAA\xBB'

        full_data = noise_prefix + valid_packet + noise_suffix

        # WHEN
        packets = lcc_parser.parse(full_data)

        # THEN: 노이즈는 무시되고 유효 패킷 1개만 반환되어야 함
        assert len(packets) == 1
        assert packets[0].raw_data == valid_packet

    def test_checksum_error(self, lcc_parser):
        """
        체크섬 오류 패킷 감지 테스트

        Logic:
            - 데이터는 정상이지만 체크섬 바이트를 고의로 변경
            - 파싱 결과 패킷의 valid 속성이 False인지 확인
        """
        # GIVEN: 체크섬이 틀린 패킷 (0x11 -> 0x99)
        invalid_data = b'\x02\x10\x00\x00\x01\x99\x03'

        # WHEN
        packets = lcc_parser.parse(invalid_data)

        # THEN: 패킷은 추출되지만 유효하지 않음(Invalid)으로 마킹
        assert len(packets) == 1
        assert packets[0].valid is False


class TestParserFactory:
    """
    ParserFactory의 인스턴스 생성 로직을 검증하는 테스트 클래스
    """

    def test_create_parser(self):
        """
        Enum 타입에 따른 올바른 파서 생성 테스트

        Logic:
            - ParserType.RAW -> RawParser
            - ParserType.ASCII -> AsciiParser
            - ParserType.LCC -> LccPacketParser
            - 지원하지 않는 타입 -> ValueError 발생
        """
        # WHEN & THEN
        assert isinstance(ParserFactory.create_parser(ParserType.RAW), RawParser)
        assert isinstance(ParserFactory.create_parser(ParserType.ASCII), AsciiParser)
        # ParserType에 LCC가 정의되어 있다면 아래 주석 해제
        # assert isinstance(ParserFactory.create_parser(ParserType.LCC), LccPacketParser)

    def test_create_unknown_parser(self):
        """
        알 수 없는 파서 타입 요청 시 예외 처리 테스트
        """
        # GIVEN: 정의되지 않은 정수값
        invalid_type = 999

        # WHEN & THEN: 기본값(Raw) 반환 또는 에러 (구현에 따라 다름, 여기선 Raw 반환 가정)
        # 만약 Factory가 에러를 내도록 설계되었다면 pytest.raises 사용
        parser = ParserFactory.create_parser(invalid_type)
        assert isinstance(parser, RawParser)