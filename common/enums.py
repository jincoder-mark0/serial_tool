"""
공통 열거형 및 타입 정의 모듈

애플리케이션 전반에서 사용되는 상태(State) 및 타입(Type) 상수를 정의합니다.

## WHY
* 상태 및 타입 정의를 한곳에서 관리하여 유지보수 용이성 확보
* 문자열 하드코딩 방지 및 IDE 자동완성 지원
* 계층 간 의존성 없이 참조 가능한 공통 위치 제공

## WHAT
* PortState, ParserType, ThemeType 등 상태 열거형
* SerialParity, SerialStopBits 등 통신 설정 열거형
* FileStatus 등 프로세스 상태
* LogFormat 등 파일 저장 형식

## HOW
* Python의 enum.Enum을 사용하여 상태 정의
* 문자열 값을 매핑하여 설정 파일 호환성 유지
"""
from enum import Enum


class PortState(Enum):
    """포트 연결 상태 열거형."""
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    ERROR = 'error'


class ConnectionProtocol:
    """PortConfig.protocol 값과 매칭되는 연결 프로토콜 상수 클래스."""
    SERIAL = "Serial"
    SPI = "SPI"
    SUPPORTED = (SERIAL,)


class ConnectionEventState(Enum):
    """PortConnectionEvent.state에 사용하는 연결 생명주기 상태."""
    OPENED = "opened"
    CLOSED = "closed"


class ParserType:
    """패킷 파서 타입 상수 클래스."""
    RAW = "Raw"
    AT = "AT"
    DELIMITER = "Delimiter"
    FIXED_LENGTH = "FixedLength"
    LENGTH_FIELD = "LengthField"
    GAP = "Gap"

    _PREFERENCE_INDEX_MAP = {
        0: RAW,
        1: AT,
        2: DELIMITER,
        3: FIXED_LENGTH,
        4: RAW,
        5: LENGTH_FIELD,
        6: GAP,
    }

    @classmethod
    def from_preference_index(cls, index: int) -> str:
        """Preferences 인덱스를 ParserFactory 문자열 상수로 변환한다."""
        return cls._PREFERENCE_INDEX_MAP.get(index, cls.RAW)


class MacroStepType(Enum):
    """MacroStepEvent.type에 사용하는 단계 이벤트 타입."""
    STARTED = "started"
    COMPLETED = "completed"


class LogLevel(Enum):
    """SystemLogEvent/ErrorContext에서 사용하는 로그 레벨."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """로그 파일 저장 형식 열거형."""
    BIN = "bin"
    HEX = "hex"
    PCAP = "pcap"


class SerialParity(Enum):
    """시리얼 패리티 비트 설정."""
    NONE = 'N'
    EVEN = 'E'
    ODD = 'O'
    MARK = 'M'
    SPACE = 'S'


class SerialStopBits(Enum):
    """시리얼 정지 비트 설정."""
    ONE = 1.0
    ONE_POINT_FIVE = 1.5
    TWO = 2.0

    def __str__(self):
        return str(self.value)


class SerialFlowControl(Enum):
    """시리얼 흐름 제어 설정."""
    NONE = 'None'
    RTS_CTS = 'RTS/CTS'
    XON_XOFF = 'XON/XOFF'


class NewlineMode(Enum):
    """줄바꿈 모드 설정."""
    RAW = "Raw"
    LF = "LF"
    CR = "CR"
    CRLF = "CRLF"


class ThemeType(Enum):
    """테마 타입."""
    DARK = "dark"
    LIGHT = "light"
    DRACULA = "dracula"
    CLASSIC = "classic"


class LanguageType(Enum):
    """설정 파일에 저장되는 지원 언어 코드."""
    ENGLISH = "en"
    KOREAN = "ko"


class ByteOrder(Enum):
    """길이 필드/정수 변환에 사용하는 바이트 순서."""
    BIG = "big"
    LITTLE = "little"


class FileStatus(Enum):
    """파일 전송 상태."""
    READY = "Ready"
    SENDING = "Sending"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
