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
    """
    포트 연결 상태 열거형

    Attributes:
        DISCONNECTED: 연결 해제됨
        CONNECTED: 연결됨
        ERROR: 에러 발생
    """
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    ERROR = 'error'

class ConnectionProtocol:
    """
    PortConfig.protocol 값과 매칭되는 연결 프로토콜 상수 클래스

    Attributes:
        SERIAL: 시리얼 통신 (구현됨, SerialTransport).
        SPI: SPI 통신 (UI 프로토콜 콤보박스에는 선택지로 존재하나 SpiTransport가
             없어 미구현 — open_connection()이 명시적으로 거부한다, S-041 B-2).
        SUPPORTED: 실제로 연결을 시도할 수 있는 프로토콜 값의 집합.
    """
    SERIAL = "Serial"
    SPI = "SPI"

    SUPPORTED = (SERIAL,)

class ParserType:
    """
    패킷 파서 타입 상수 클래스

    Attributes:
        RAW: 바이너리 데이터 그대로 처리
        AT: AT 커맨드 (CRLF 기준)
        DELIMITER: 지정된 구분자 기준
        FIXED_LENGTH: 고정 길이 기준
    """
    RAW = "Raw"
    AT = "AT"
    DELIMITER = "Delimiter"
    FIXED_LENGTH = "FixedLength"

    # PreferencesState.parser_type / ConfigKeys.PACKET_PARSER_TYPE은 정수 인덱스로
    # 저장된다 (view/dialogs/preferences_dialog.py의 QButtonGroup 라디오 버튼 순서:
    # 0=Auto, 1=AT, 2=Delimiter, 3=Fixed, 4=Raw). ParserFactory는 문자열 상수를
    # 요구하므로 여기서 변환한다 (S-041). 라디오 버튼 순서를 바꾸면 이 매핑도 갱신할 것.
    _PREFERENCE_INDEX_MAP = {
        0: RAW,            # Auto: 자동 감지는 미구현 — 현재는 Raw로 처리
        1: AT,
        2: DELIMITER,
        3: FIXED_LENGTH,
        4: RAW,
    }

    @classmethod
    def from_preference_index(cls, index: int) -> str:
        """
        Preferences에 저장된 정수 인덱스를 ParserFactory용 문자열 상수로 변환합니다.

        Args:
            index (int): PreferencesState.parser_type / PACKET_PARSER_TYPE 값.

        Returns:
            str: ParserType 문자열 상수. 알 수 없는 인덱스는 RAW로 폴백한다.
        """
        return cls._PREFERENCE_INDEX_MAP.get(index, cls.RAW)

class LogFormat(Enum):
    """
    로그 파일 저장 형식 열거형

    Attributes:
        BIN: 바이너리 원본 (.bin)
        HEX: 텍스트 헥사 덤프 (.txt)
        PCAP: 패킷 캡처 포맷 (.pcap)
    """
    BIN = "bin"
    HEX = "hex"
    PCAP = "pcap"

class SerialParity(Enum):
    """
    시리얼 패리티 비트 설정

    Attributes:
        NONE: 없음
        EVEN: 짝수
        ODD: 홀수
        MARK: 마크
        SPACE: 스페이스
    """
    NONE = 'N'
    EVEN = 'E'
    ODD = 'O'
    MARK = 'M'
    SPACE = 'S'

class SerialStopBits(Enum):
    """
    시리얼 정지 비트 설정

    Attributes:
        ONE: 1비트
        ONE_POINT_FIVE: 1.5비트
        TWO: 2비트
    """
    ONE = 1.0
    ONE_POINT_FIVE = 1.5
    TWO = 2.0

    def __str__(self):
        return str(self.value)

class SerialFlowControl(Enum):
    """
    시리얼 흐름 제어 설정

    Attributes:
        NONE: 없음
        RTS_CTS: RTS/CTS
        XON_XOFF: XON/XOFF
    """
    NONE = 'None'
    RTS_CTS = 'RTS/CTS'
    XON_XOFF = 'XON/XOFF'

class NewlineMode(Enum):
    """
    줄바꿈 모드 설정

    Attributes:
        RAW: 바이너리 데이터 그대로 처리
        LF: \n
        CR: \r
        CRLF: \r\n
    """
    RAW = "Raw"
    LF = "LF"      # \n
    CR = "CR"      # \r
    CRLF = "CRLF"  # \r\n

class ThemeType(Enum):
    """
    테마 타입

    Attributes:
        DARK: 어두운 테마
        LIGHT: 밝은 테마
        DRACULA: 드라큘라 테마
        CLASSIC: 클래식(전통 Windows) 테마 (S-060) - 밝은 계열
    """
    DARK = "dark"
    LIGHT = "light"
    DRACULA = "dracula"
    CLASSIC = "classic"

class FileStatus(Enum):
    """
    파일 전송 상태

    Attributes:
        READY: 준비됨
        SENDING: 전송 중
        COMPLETED: 완료됨
        FAILED: 실패
        CANCELLED: 취소됨
    """
    READY = "Ready"
    SENDING = "Sending"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"