"""
공통 데이터 전송 객체(DTO) 모듈

애플리케이션 전반(View, Model, Presenter, Core)에서 공통으로 사용되는
데이터 구조(Schema)를 정의합니다.

## WHY
* 계층 간 데이터 교환 시 타입 안정성 보장 (Type Safety)
* 딕셔너리 사용 시 발생하는 Key Error 및 오타 방지
* 순환 참조(Circular Import) 방지를 위한 최하위 계층 위치

## WHAT
* ManualCommand: 수동 제어 명령어
* PortConfig: 포트 연결 설정
* FontConfig: 폰트 설정
* MacroEntry: 매크로(자동화) 항목
* FileProgressState: 파일 전송 상태
* PortDataEvent: 포트 데이터 이벤트
* PortErrorEvent: 포트 에러 이벤트
* PacketEvent: 패킷 수신 이벤트

## HOW
* python dataclasses 활용
* to_dict/from_dict 메서드를 통해 JSON 직렬화 지원
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ManualCommand:
    """
    수동 명령어 전송 데이터
    View(ManualCtrl) -> Presenter -> Model로 전달됩니다.
    """
    text: str
    hex_mode: bool = False
    prefix: bool = False
    suffix: bool = False
    local_echo: bool = False
    is_broadcast: bool = False

@dataclass
class PortConfig:
    """
    포트 연결 설정 데이터
    View(PortSettings) -> Presenter -> Model로 전달됩니다.
    """
    port: str
    protocol: str = "Serial"  # Serial, SPI, I2C

    # Serial Options
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1.0
    flowctrl: str = "None"

    # SPI Options
    speed: int = 1000000
    mode: int = 0

@dataclass
class FontConfig:
    """
    폰트 설정 데이터
    ThemeManager 및 설정 저장 시 사용됩니다.
    """
    prop_family: str
    prop_size: int
    fixed_family: str
    fixed_size: int

@dataclass
class MacroEntry:
    """
    매크로 항목 데이터 클래스

    Attributes:
        enabled: 활성화 여부
        command: 전송할 명령어
        is_hex: HEX 모드 여부
        prefix: 접두사 사용 여부
        suffix: 접미사 사용 여부
        delay_ms: 다음 명령까지 대기 시간 (ms)
        expect: 기대하는 응답 패턴 (Expect 기능)
        timeout_ms: 응답 대기 시간 (ms)
    """
    enabled: bool = True
    command: str = ""
    is_hex: bool = False
    prefix: bool = False
    suffix: bool = False
    delay_ms: int = 0
    expect: str = ""
    timeout_ms: int = 5000

    def to_dict(self) -> dict:
        """
        Dictionary로 변환 (설정 저장용)

        Returns:
            dict: 모든 속성을 포함하는 Dictionary
        """
        return {
            "enabled": self.enabled,
            "command": self.command,
            "is_hex": self.is_hex,
            "prefix": self.prefix,
            "suffix": self.suffix,
            "delay_ms": self.delay_ms,
            "expect": self.expect,
            "timeout_ms": self.timeout_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MacroEntry':
        """
        Dictionary에서 MacroEntry 생성 (설정 로드용)

        Args:
            data: 매크로 데이터 Dictionary

        Returns:
            MacroEntry: 생성된 인스턴스
        """
        return cls(
            enabled=data.get("enabled", True),
            command=data.get("command", ""),
            is_hex=data.get("is_hex", False),
            prefix=data.get("prefix", False),
            suffix=data.get("suffix", False),
            delay_ms=data.get("delay_ms", 0),
            expect=data.get("expect", ""),
            timeout_ms=data.get("timeout_ms", 5000)
        )

@dataclass
class FileProgressState:
    """
    파일 전송 진행 상태 DTO
    Model -> Presenter -> View
    """
    file_path: str = ""
    sent_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0      # bytes/sec
    eta: float = 0.0        # seconds
    status: str = "Sending" # Sending, Completed, Error, Cancelled
    error_msg: str = ""     # 에러 발생 시 메시지

@dataclass
class PortDataEvent:
    """
    포트 데이터 수신/송신 이벤트 DTO
    Model -> EventBus -> Router -> Presenter
    """
    port: str
    data: bytes
    timestamp: float = 0.0

@dataclass
class PortErrorEvent:
    """
    포트 에러 이벤트 DTO
    Model -> EventBus -> Router -> Presenter
    """
    port: str
    message: str

@dataclass
class PacketEvent:
    """
    패킷 파싱 완료 이벤트 DTO
    Model -> EventBus -> Router -> Presenter
    """
    port: str
    packet: Any # model.packet_parser.Packet 객체
