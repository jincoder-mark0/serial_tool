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
* ConfigKeys 등 현재 사용되는 핵심 상수의 존재 여부 확인

## HOW
* dataclasses의 필드 및 기본값 검증
* Enum 멤버 값 비교
* 상수 문자열의 불변성 확인

pytest tests/test_core_structures.py -v
"""
from dataclasses import asdict

from common.dtos import (
    PortConfig,
    ManualCommand,
    PacketViewData,
    PortDataEvent
)
from common.enums import (
    SerialParity,
    SerialStopBits,
    SerialFlowControl,
    LogFormat,
    ParserType
)
from common.constants import (
    ConfigKeys,
    DEFAULT_BAUDRATE,
    DEFAULT_LOG_MAX_LINES,
)


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
        config = PortConfig(
            port="COM3",
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            flowctrl="None"
        )

        assert config.port == "COM3"
        assert config.baudrate == 115200

        config_dict = asdict(config)
        assert config_dict["port"] == "COM3"
        assert config_dict["parity"] == "N"

    def test_manual_command_defaults(self):
        """ManualCommand DTO의 기본값(Defaults) 테스트."""
        cmd = ManualCommand(command="TEST_CMD")

        assert cmd.hex_mode is False
        assert cmd.prefix_enabled is False
        assert cmd.suffix_enabled is False
        assert cmd.local_echo_enabled is False
        assert cmd.broadcast_enabled is False

    def test_packet_view_data_structure(self):
        """PacketViewData DTO 구조 테스트."""
        data = PacketViewData(
            time_str="12:00:00",
            packet_type="RX",
            data_hex="AA BB",
            data_ascii=".."
        )

        assert isinstance(data.time_str, str)
        assert data.data_hex == "AA BB"

    def test_port_data_event_immutability(self):
        """PortDataEvent DTO의 데이터 전달 테스트."""
        raw_data = b'\x01\x02\x03'
        event = PortDataEvent(port="COM1", data=raw_data)

        assert event.port == "COM1"
        assert event.data == b'\x01\x02\x03'


class TestEnums:
    """Enum 정의의 정확성을 검증하는 테스트 클래스."""

    def test_serial_parameters_values(self):
        """시리얼 통신 파라미터 Enum 값 검증."""
        assert SerialParity.NONE.value == 'N'
        assert SerialParity.EVEN.value == 'E'
        assert SerialParity.ODD.value == 'O'

        assert SerialStopBits.ONE.value == 1
        assert SerialStopBits.TWO.value == 2

        assert SerialFlowControl.NONE.value == "None"
        assert SerialFlowControl.RTS_CTS.value == "RTS/CTS"

    def test_log_format_types(self):
        """로그 포맷 Enum 검증."""
        assert LogFormat.BIN.value == "bin"
        assert LogFormat.HEX is not None
        assert LogFormat.PCAP is not None

    def test_parser_type_integrity(self):
        """파서 타입 Enum 검증."""
        assert ParserType.RAW == "Raw"
        assert ParserType.AT == "AT"
        assert ParserType.DELIMITER == "Delimiter"
        assert ParserType.FIXED_LENGTH == "FixedLength"


class TestConstants:
    """상수(Constants) 정의의 불변성을 검증하는 테스트 클래스."""

    def test_config_keys_integrity(self):
        """설정 키(ConfigKeys) 상수 검증."""
        assert ConfigKeys.PORT_BAUDRATE == "settings.port_baudrate"
        assert ConfigKeys.WINDOW_WIDTH == "ui.window_width"
        assert ConfigKeys.COMMAND_PREFIX == "settings.command_prefix"
        assert isinstance(ConfigKeys.THEME, str)

    def test_default_values(self):
        """기본값(Defaults) 상수 검증."""
        assert DEFAULT_BAUDRATE in [9600, 115200]
        assert DEFAULT_LOG_MAX_LINES > 0
