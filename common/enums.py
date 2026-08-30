"""
공통 열거형 및 타입 정의 모듈

애플리케이션 전반에서 사용되는 상태(State) 및 타입(Type) 상수를 정의합니다.
문자열/정수 선택값을 공통 위치에 두어 View·Presenter·Model 간 하드코딩 분기를 방지합니다.
"""
from enum import Enum, IntEnum


class PortState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionProtocol:
    SERIAL = "Serial"
    SPI = "SPI"
    SUPPORTED = (SERIAL,)


class ConnectionEventState(Enum):
    OPENED = "opened"
    CLOSED = "closed"


class ParserPreferenceIndex(IntEnum):
    """PreferencesState.parser_type 및 QButtonGroup ID의 공통 정본."""
    AUTO = 0
    AT = 1
    DELIMITER = 2
    FIXED_LENGTH = 3
    RAW = 4
    LENGTH_FIELD = 5
    GAP = 6


class ParserType:
    RAW = "Raw"
    AT = "AT"
    DELIMITER = "Delimiter"
    FIXED_LENGTH = "FixedLength"
    LENGTH_FIELD = "LengthField"
    GAP = "Gap"

    _PREFERENCE_INDEX_MAP = {
        ParserPreferenceIndex.AUTO: RAW,
        ParserPreferenceIndex.AT: AT,
        ParserPreferenceIndex.DELIMITER: DELIMITER,
        ParserPreferenceIndex.FIXED_LENGTH: FIXED_LENGTH,
        ParserPreferenceIndex.RAW: RAW,
        ParserPreferenceIndex.LENGTH_FIELD: LENGTH_FIELD,
        ParserPreferenceIndex.GAP: GAP,
    }

    @classmethod
    def from_preference_index(cls, index: int) -> str:
        try:
            preference = ParserPreferenceIndex(index)
        except (TypeError, ValueError):
            return cls.RAW
        return cls._PREFERENCE_INDEX_MAP.get(preference, cls.RAW)


class LengthFieldSize(IntEnum):
    """LengthFieldParser가 허용하는 길이 필드 크기(bytes)."""
    ONE = 1
    TWO = 2
    FOUR = 4


class MacroStepType(Enum):
    STARTED = "started"
    COMPLETED = "completed"


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    CRITICAL = "CRITICAL"


class TransmissionErrorCode(Enum):
    """CommandTransmissionService가 반환하는 UI 비의존 실패 분류."""
    INVALID_COMMAND = "invalid_command"
    EMPTY_DATA = "empty_data"
    NO_BROADCAST_TARGET = "no_broadcast_target"
    BROADCAST_SEND_FAILED = "broadcast_send_failed"
    NO_ACTIVE_PORT = "no_active_port"
    PORT_NOT_OPEN = "port_not_open"
    SEND_FAILED = "send_failed"


class LogFormat(Enum):
    BIN = "bin"
    HEX = "hex"
    PCAP = "pcap"


class SerialParity(Enum):
    NONE = "N"
    EVEN = "E"
    ODD = "O"
    MARK = "M"
    SPACE = "S"


class SerialStopBits(Enum):
    ONE = 1.0
    ONE_POINT_FIVE = 1.5
    TWO = 2.0

    def __str__(self):
        return str(self.value)


class SerialFlowControl(Enum):
    NONE = "None"
    RTS_CTS = "RTS/CTS"
    XON_XOFF = "XON/XOFF"


class NewlineMode(Enum):
    RAW = "Raw"
    LF = "LF"
    CR = "CR"
    CRLF = "CRLF"


class ThemeType(Enum):
    DARK = "dark"
    LIGHT = "light"
    DRACULA = "dracula"
    CLASSIC = "classic"


class LanguageType(Enum):
    ENGLISH = "en"
    KOREAN = "ko"


class ByteOrder(Enum):
    BIG = "big"
    LITTLE = "little"


class FileStatus(Enum):
    READY = "Ready"
    SENDING = "Sending"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
