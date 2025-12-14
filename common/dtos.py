"""
공통 데이터 전송 객체(DTO) 모듈

애플리케이션 전반(View, Model, Presenter, Core)에서 공통으로 사용되는
데이터 구조(Schema)를 정의합니다.

## WHY
* 계층 간 데이터 교환 시 타입 안정성 보장 (Type Safety)
* 딕셔너리 사용 시 발생하는 Key Error 및 오타 방지
* 순환 참조(Circular Import) 방지를 위한 최하위 계층 위치

## WHAT
* ManualCommand: 수동 제어 Command
* PortConfig: 포트 연결 설정
* FontConfig: 폰트 설정
* MacroEntry: 매크로(자동화) 항목
* FileProgressState: 파일 전송 상태
* FileProgressEvent: 파일 전송 진행 이벤트
* PortDataEvent: 포트 데이터 이벤트
* PortErrorEvent: 포트 에러 이벤트
* PacketEvent: 패킷 수신 이벤트
* ErrorContext: 시스템 에러 컨텍스트
* MacroScriptData: 매크로 스크립트 데이터
* MacroRepeatOption: 매크로 반복 설정 옵션
* MacroStepEvent: 매크로 실행 스텝 이벤트
* PreferencesState: 환경 설정 상태
* MainWindowState: 메인 윈도우 상태
* ManualControlState: 수동 제어 상태

## HOW
* python dataclasses 활용
* to_dict/from_dict 메서드를 통해 JSON 직렬화 지원
* 안전한 타입 변환을 위한 헬퍼 메서드 적용
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

def _safe_cast(value: Any, target_type: type, default: Any) -> Any:
    """
    값을 안전하게 대상 타입으로 변환합니다.
    None이거나 변환 실패 시 기본값을 반환합니다.
    """
    if value is None:
        return default
    try:
        if target_type is bool:
            # "true"/"false" 문자열 처리
            if isinstance(value, str):
                return value.lower() == "true"
            return bool(value)
        if target_type is int:
            return int(value)
        if target_type is float:
            return float(value)
        if target_type is str:
            return str(value)
        if target_type is list:
            return list(value) if isinstance(value, (list, tuple)) else default
        return value
    except (ValueError, TypeError):
        return default

@dataclass
class ManualCommand:
    """
    수동 Command 전송 데이터
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PortConfig':
        """Dictionary에서 안전하게 PortConfig 생성"""
        return cls(
            port=_safe_cast(data.get("port"), str, ""),
            protocol=_safe_cast(data.get("protocol"), str, "Serial"),
            baudrate=_safe_cast(data.get("baudrate"), int, 115200),
            bytesize=_safe_cast(data.get("bytesize"), int, 8),
            parity=_safe_cast(data.get("parity"), str, "N"),
            stopbits=_safe_cast(data.get("stopbits"), float, 1.0),
            flowctrl=_safe_cast(data.get("flowctrl"), str, "None"),
            speed=_safe_cast(data.get("speed"), int, 1000000),
            mode=_safe_cast(data.get("mode"), int, 0)
        )

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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FontConfig':
        """Dictionary에서 안전하게 FontConfig 생성"""
        return cls(
            prop_family=_safe_cast(data.get("prop_family"), str, "Segoe UI"),
            prop_size=_safe_cast(data.get("prop_size"), int, 9),
            fixed_family=_safe_cast(data.get("fixed_family"), str, "Consolas"),
            fixed_size=_safe_cast(data.get("fixed_size"), int, 9)
        )

@dataclass
class MacroEntry:
    """
    매크로 항목 데이터 클래스

    Attributes:
        enabled: 활성화 여부
        command: 전송할 Command
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

    def to_dict(self) -> Dict[str, Any]:
        """
        Dictionary로 변환 (설정 저장용)

        Returns:
            Dict[str, Any]: 모든 속성을 포함하는 Dictionary
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
    def from_dict(cls, data: Dict[str, Any]) -> 'MacroEntry':
        """
        Dictionary에서 MacroEntry 생성 (설정 로드용)

        Args:
            data: 매크로 데이터 Dictionary

        Returns:
            MacroEntry: 생성된 인스턴스
        """
        return cls(
            enabled=_safe_cast(data.get("enabled"), bool, True),
            command=_safe_cast(data.get("command"), str, ""),
            is_hex=_safe_cast(data.get("is_hex"), bool, False),
            prefix=_safe_cast(data.get("prefix"), bool, False),
            suffix=_safe_cast(data.get("suffix"), bool, False),
            delay_ms=_safe_cast(data.get("delay_ms"), int, 0),
            expect=_safe_cast(data.get("expect"), str, ""),
            timeout_ms=_safe_cast(data.get("timeout_ms"), int, 5000)
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
class FileProgressEvent:
    """
    파일 전송 진행 이벤트 DTO
    Model -> EventBus -> Router -> External/Plugins
    """
    current: int
    total: int

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

@dataclass
class ErrorContext:
    """
    시스템 에러 컨텍스트 DTO
    GlobalErrorHandler -> UI
    """
    error_type: str
    message: str
    traceback: str
    level: str = "CRITICAL"
    timestamp: float = 0.0

@dataclass
class MacroScriptData:
    """
    매크로 스크립트 데이터 DTO (저장/로드)
    View -> Presenter
    """
    filepath: str
    data: Dict[str, Any] # commands 리스트와 control_state 포함

    @classmethod
    def from_dict(cls, filepath: str, data: Dict[str, Any]) -> 'MacroScriptData':
        """안전한 생성 메서드"""
        if not isinstance(data, dict):
            data = {}
        # 필수 키 보장
        if "commands" not in data:
            data["commands"] = []
        if "control_state" not in data:
            data["control_state"] = {}
        return cls(filepath=filepath, data=data)

@dataclass
class MacroRepeatOption:
    """
    매크로 반복 실행 옵션 DTO
    View(Widget) -> View(Panel) -> Presenter
    """
    delay_ms: int
    max_runs: int = 0
    interval_ms: int = 0
    is_broadcast: bool = False

@dataclass
class MacroStepEvent:
    """
    매크로 실행 단계 이벤트 DTO
    Model -> Presenter -> View
    """
    index: int
    entry: Optional[MacroEntry] = None
    success: bool = False
    type: str = "started" # "started" or "completed"

@dataclass
class PreferencesState:
    """
    환경 설정 상태 DTO
    PreferencesDialog와 Presenter 간 데이터 교환용
    """
    # General
    theme: str = "Dark"
    language: str = "en"
    font_size: int = 10
    max_log_lines: int = 1000

    # Serial Defaults
    baudrate: int = 115200
    newline: str = "LF"
    local_echo: bool = False
    scan_interval: int = 1000

    # Command
    cmd_prefix: str = ""
    cmd_suffix: str = ""

    # Logging
    log_path: str = ""

    # Packet
    parser_type: int = 0
    delimiters: List[str] = field(default_factory=lambda: ["\\r\\n"])
    packet_length: int = 64
    at_color_ok: bool = True
    at_color_error: bool = True
    at_color_urc: bool = True
    at_color_prompt: bool = True
    packet_buffer_size: int = 100
    packet_realtime: bool = True
    packet_autoscroll: bool = True

@dataclass
class MainWindowState:
    """
    메인 윈도우 상태 DTO
    윈도우 복원 및 종료 시 상태 저장용
    """
    width: int = 1200
    height: int = 800
    x: Optional[int] = None
    y: Optional[int] = None
    splitter_state: Optional[str] = None
    right_panel_visible: bool = True
    saved_right_width: Optional[int] = None

    # Sub-component states (딕셔너리로 유지하여 유연성 확보)
    left_section_state: Dict[str, Any] = field(default_factory=dict)
    right_section_state: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ManualControlState:
    """
    수동 제어 위젯의 상태 DTO
    """
    input_text: str = ""
    hex_mode: bool = False
    prefix_chk: bool = False
    suffix_chk: bool = False
    rts_chk: bool = False
    dtr_chk: bool = False
    local_echo_chk: bool = False
    broadcast_chk: bool = False
    command_history: List[str] = field(default_factory=list)
