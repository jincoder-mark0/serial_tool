"""
공통 열거형 및 타입 정의 모듈

애플리케이션 전반에서 사용되는 상태(State) 및 타입(Type) 상수를 정의합니다.

## WHY
* 상태 및 타입 정의를 한곳에서 관리하여 유지보수 용이성 확보
* 계층 간 의존성 없이 참조 가능한 공통 위치 제공 (순환 참조 방지)

## WHAT
* PortState: 포트 연결 상태 (연결됨, 끊김, 에러)
* ParserType: 패킷 파싱 전략 타입 (Raw, AT, Delimiter 등)

## HOW
* Python의 enum.Enum을 사용하여 상태 정의
* 클래스 상수를 사용하여 문자열 타입 정의
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