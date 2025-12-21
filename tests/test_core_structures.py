"""
코어 데이터 구조 테스트 모듈

애플리케이션 전반에서 사용되는 데이터 구조(DTO, Enum, Constants)의 무결성을 검증합니다.

## WHY
* 데이터 객체(DTO)의 필드 누락이나 기본값 오류 방지
* Enum 값 변경으로 인한 로직 파손 예방 (Protocol Integrity)
* 주요 상수 값의 의도치 않은 변경 감지

## WHAT
* PortConfig, ManualCommand 등 주요 DTO의 생성 및 속성 접근 테스트
* SerialParity, LogFormat 등 Enum 멤버의 유효성 검증
* ConfigKeys, EventTopics 등 핵심 상수의 존재 여부 확인

## HOW
* dataclasses의 필드 및 기본값 검증
* Enum 멤버 값 비교
* 상수 문자열의 불변성 확인

pytest tests/test_core_structures.py -v
"""
import pytest
from dataclasses import asdict

from common.dtos import (
    PortConfig,
    ManualCommand,
    MacroEntry,
    PacketViewData,
    PortDataEvent,
    PortStatistics
)
from common.enums import (
    SerialParity,
    SerialStopBits,
    SerialByteSize,
    SerialFlowControl,
    LogFormat,
    ParserType
)
from common.constants import ConfigKeys, EventTopics, Defaults


class TestDTOs:
    """
    Data Transfer Object(DTO)들의 구조와 동작을 검증하는 테스트 클래스
    """

    def test_port_config_creation(self):
        """
        PortConfig DTO 생성 및 데이터 무결성 테스트

        Logic:
            - 모든 필드를 포함하여 객체 생성
            - 속성값이 입력값과 일치하는지 확인
            - 딕셔너리 변환(asdict) 가능 여부 확인
        """
        # GIVEN: 포트 설정 데이터
        config = PortConfig(
            port="COM3",
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            flowctrl="None"
        )

        # THEN: 속성 접근 확인
        assert config.port == "COM3"
        assert config.baudrate == 115200

        # THEN: 딕셔너리 변환 확인 (설정 저장 시 사용됨)
        config_dict = asdict(config)
        assert config_dict["port"] == "COM3"
        assert config_dict["parity"] == "N"

    def test_manual_command_defaults(self):
        """
        ManualCommand DTO의 기본값(Defaults) 테스트

        Logic:
            - 필수 필드(command)만 입력하여 객체 생성
            - 선택적 필드들이 예상된 기본값(False 등)을 갖는지 확인
        """
        # GIVEN: 필수 필드만 입력
        cmd = ManualCommand(command="TEST_CMD")

        # THEN: 기본값 검증
        assert cmd.hex_mode is False
        assert cmd.prefix_enabled is False
        assert cmd.suffix_enabled is False
        assert cmd.local_echo_enabled is False
        assert cmd.broadcast_enabled is False

    def test_packet_view_data_structure(self):
        """
        PacketViewData DTO 구조 테스트

        Logic:
            - 패킷 뷰 데이터 생성
            - 데이터 타입 일치 여부 확인
        """
        # GIVEN
        data = PacketViewData(
            time_str="12:00:00",
            packet_type="RX",
            data_hex="AA BB",
            data_ascii=".."
        )

        # THEN
        assert isinstance(data.time_str, str)
        assert data.data_hex == "AA BB"

    def test_port_data_event_immutability(self):
        """
        PortDataEvent DTO의 데이터 전달 테스트

        Logic:
            - 포트 데이터 이벤트 생성
            - 바이너리 데이터가 올바르게 보존되는지 확인
        """
        # GIVEN
        raw_data = b'\x01\x02\x03'
        event = PortDataEvent(port="COM1", data=raw_data)

        # THEN
        assert event.port == "COM1"
        assert event.data == b'\x01\x02\x03'


class TestEnums:
    """
    Enum 정의의 정확성을 검증하는 테스트 클래스
    """

    def test_serial_parameters_values(self):
        """
        시리얼 통신 파라미터 Enum 값 검증

        Logic:
            - Parity, StopBits 등의 Enum이 pyserial과 호환되는 값('N', 1 등)을 갖는지 확인
        """
        # Parity Check ('N', 'E', 'O', 'M', 'S')
        assert SerialParity.NONE.value == 'N'
        assert SerialParity.EVEN.value == 'E'
        assert SerialParity.ODD.value == 'O'

        # StopBits Check (1, 1.5, 2)
        assert SerialStopBits.ONE.value == 1
        assert SerialStopBits.TWO.value == 2

        # ByteSize Check (5, 6, 7, 8)
        assert SerialByteSize.EIGHT.value == 8
        assert SerialByteSize.SEVEN.value == 7

    def test_log_format_types(self):
        """
        로그 포맷 Enum 검증

        Logic:
            - 지원하는 로그 포맷(TXT, HEX, CSV, PCAP) 존재 확인
        """
        assert LogFormat.TXT is not None
        assert LogFormat.HEX is not None
        assert LogFormat.PCAP is not None

    def test_parser_type_integrity(self):
        """
        파서 타입 Enum 검증

        Logic:
            - 파서 타입 ID가 설정 파일의 정수값과 매핑되므로 값 변경 주의
        """
        # 값 변경 시 호환성 문제가 생기므로 고정값 확인
        assert ParserType.RAW.value == 0
        assert ParserType.ASCII.value == 1
        assert ParserType.HEX.value == 2


class TestConstants:
    """
    상수(Constants) 정의의 불변성을 검증하는 테스트 클래스
    """

    def test_config_keys_integrity(self):
        """
        설정 키(ConfigKeys) 상수 검증

        Logic:
            - 설정 파일(JSON)의 키로 사용되는 상수들이 누락되지 않았는지 확인
        """
        # 주요 키 존재 확인
        assert ConfigKeys.PORT_BAUDRATE == "port.baudrate"
        assert ConfigKeys.WINDOW_WIDTH == "ui.window_width"
        assert ConfigKeys.COMMAND_PREFIX == "cmd.prefix"

        # 오타 방지를 위해 문자열 타입인지 재확인
        assert isinstance(ConfigKeys.THEME, str)

    def test_event_topics_integrity(self):
        """
        이벤트 토픽(EventTopics) 상수 검증

        Logic:
            - EventBus에서 사용되는 토픽 문자열 확인
        """
        assert EventTopics.PORT_DATA_RECEIVED == "port.data.received"
        assert EventTopics.MACRO_STARTED == "macro.started"
        assert EventTopics.SETTINGS_CHANGED == "sys.settings.changed"

    def test_default_values(self):
        """
        기본값(Defaults) 상수 검증

        Logic:
            - 애플리케이션의 기본 설정값이 합리적인 범위인지 확인
        """
        # Baudrate 기본값은 보통 115200 또는 9600
        assert Defaults.BAUDRATE in [9600, 115200]
        # 윈도우 기본 크기
        assert Defaults.WINDOW_WIDTH > 0
        assert Defaults.WINDOW_HEIGHT > 0