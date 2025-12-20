"""
공통 데이터 전송 객체(DTO) 모듈

애플리케이션 전반(View, Model, Presenter, Core)에서 공통으로 사용되는
데이터 구조(Schema)를 정의합니다.

## WHY
* 계층 간 데이터 교환 시 타입 안정성 보장 (Type Safety)
* 딕셔너리 사용 시 발생하는 Key Error 및 오타 방지
* 순환 참조(Circular Import) 방지를 위한 최하위 계층 위치

## WHAT
* PortConfig, ManualCommand, MacroEntry 등 핵심 데이터 구조
* Event, State 관련 DTO (FileProgressState, PacketEvent 등)
* ColorRule 등 설정 관련 데이터 구조

## HOW
* python dataclasses 활용
* to_dict/from_dict 메서드를 통해 JSON 직렬화 지원
* 안전한 타입 변환을 위한 헬퍼 메서드(_safe_cast) 적용
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from common.constants import (
    DEFAULT_BAUDRATE, DEFAULT_MACRO_DELAY_MS,
    FONT_FAMILY_SEGOE, FONT_FAMILY_CONSOLAS
)
from common.enums import SerialParity, SerialStopBits, SerialFlowControl, FileStatus

def _safe_cast(value: Any, target_type: type, default: Any) -> Any:
    """
    값을 안전하게 대상 타입으로 변환합니다.
    None이거나 변환 실패 시 기본값을 반환합니다.

    Args:
        value: 변환할 값
        target_type: 대상 타입
        default: 변환 실패 시 반환할 기본값
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

    Attributes:
        command (str): 전송할 텍스트
        hex_mode (bool): 16진수 모드
        prefix_enabled (bool): 접두사 사용
        suffix_enabled (bool): 접미사 사용
        local_echo_enabled (bool): 로컬 에코
        broadcast_enabled (bool): 브로드캐스트
    """
    command: str
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    local_echo_enabled: bool = False
    broadcast_enabled: bool = False

@dataclass
class PortConfig:
    """
    포트 연결 설정 데이터

    Attributes:
        port (str): 포트 이름
        protocol (str): 프로토콜
        baudrate (int): 보드레이트
        bytesize (int): 바이트 사이즈
        parity (str): 페어리티
        stopbits (float): 스탑비트
        flowctrl (str): 흐름 제어
        speed (int): 속도
        mode (int): 모드
    """
    port: str
    protocol: str = "Serial"

    # Serial Options
    baudrate: int = DEFAULT_BAUDRATE
    bytesize: int = 8
    parity: str = SerialParity.NONE.value
    stopbits: float = SerialStopBits.ONE.value
    flowctrl: str = SerialFlowControl.NONE.value

    # SPI Options
    speed: int = 1000000
    mode: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PortConfig':
        """
        Dictionary에서 안전하게 PortConfig 생성

        Args:
            data (Dict[str, Any]): JSON 데이터

        Returns:
            PortConfig: 생성된 PortConfig 객체
        """
        hex_mode_val = data.get("hex_mode")
        if hex_mode_val is None:
            hex_mode_val = data.get("is_hex", False)

        return cls(
            enabled=_safe_cast(data.get("enabled"), bool, True),
            command=_safe_cast(data.get("command"), str, ""),
            hex_mode=_safe_cast(hex_mode_val, bool, False),
            prefix_enabled=_safe_cast(data.get("prefix_enabled"), bool, False),
            suffix_enabled=_safe_cast(data.get("suffix_enabled"), bool, False),
            delay_ms=_safe_cast(data.get("delay_ms"), int, 0),
            expect=_safe_cast(data.get("expect"), str, ""),
            timeout_ms=_safe_cast(data.get("timeout_ms"), int, 5000)
        )

@dataclass
class FontConfig:
    """
    폰트 설정 데이터

    Attributes:
        prop_family (str): 비정비 폰트
        prop_size (int): 비정비 폰트 크기
        fixed_family (str): 정비 폰트
        fixed_size (int): 정비 폰트 크기
    """
    prop_family: str
    prop_size: int
    fixed_family: str
    fixed_size: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FontConfig':
        """
        Dictionary에서 안전하게 FontConfig 생성

        Args:
            data (Dict[str, Any]): JSON 데이터

        Returns:
            FontConfig: 생성된 FontConfig 객체
        """
        return cls(
            prop_family=_safe_cast(data.get("prop_family"), str, FONT_FAMILY_SEGOE),
            prop_size=_safe_cast(data.get("prop_size"), int, 9),
            fixed_family=_safe_cast(data.get("fixed_family"), str, FONT_FAMILY_CONSOLAS),
            fixed_size=_safe_cast(data.get("fixed_size"), int, 9)
        )

@dataclass
class MacroEntry:
    """
    매크로 항목 데이터 클래스

    Attributes:
        enabled: 활성화 여부
        command: 전송할 Command
        hex_mode: HEX 모드 여부
        prefix: 접두사 사용 여부
        suffix: 접미사 사용 여부
        delay_ms: 다음 명령까지 대기 시간 (ms)
        expect: 기대하는 응답 패턴 (Expect 기능)
        timeout_ms: 응답 대기 시간 (ms)
    """
    enabled: bool = True
    command: str = ""
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
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
            "hex_mode": self.hex_mode,
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
            hex_mode=_safe_cast(data.get("hex_mode"), bool, False),
            prefix_enabled=_safe_cast(data.get("prefix_enabled"), bool, False),
            suffix_enabled=_safe_cast(data.get("suffix_enabled"), bool, False),
            delay_ms=_safe_cast(data.get("delay_ms"), int, 0),
            expect=_safe_cast(data.get("expect"), str, ""),
            timeout_ms=_safe_cast(data.get("timeout_ms"), int, 5000)
        )

@dataclass
class PortInfo:
    """
    검색된 포트 정보 DTO

    Attributes:
        device (str): 포트 이름
        description (str): 포트 설명
    """
    device: str
    description: str

@dataclass
class PortStatistics:
    """
    포트 통신 통계 DTO
    """
    rx_bytes: int = 0
    tx_bytes: int = 0
    error_count: int = 0
    bps: int = 0

@dataclass
class PortConnectionEvent:
    """
    포트 연결 상태 변경 이벤트 DTO
    """
    port: str
    state: str  # 'opened' or 'closed'

@dataclass
class PacketViewData:
    """
    패킷 뷰 표시용 데이터 DTO

    Attributes:
        time_str (str): 시간 문자열
        packet_type (str): 패킷 타입
        data_hex (str): 헥스 데이터
        data_ascii (str): 아스키 데이터
    """
    time_str: str
    packet_type: str
    data_hex: str
    data_ascii: str

@dataclass
class FileProgressState:
    """
    파일 전송 진행 상태 DTO

    Attributes:
        file_path (str): 파일 경로
        sent_bytes (int): 전송된 바이트 수
        total_bytes (int): 총 파일 크기
        speed (float): 전송 속도 (바이트/초)
        eta (float): 예상 완료 시간 (초)
        status (str): 파일 전송 상태
        error_msg (str): 에러 메시지
    """
    file_path: str = ""
    sent_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: float = 0.0
    status: str = FileStatus.SENDING.value
    error_msg: str = ""

@dataclass
class FileProgressEvent:
    """
    파일 전송 진행 이벤트 DTO

    Attributes:
        current (int): 현재 전송된 바이트 수
        total (int): 총 파일 크기
    """
    current: int
    total: int

@dataclass
class PortDataEvent:
    """
    포트 데이터 수신/송신 이벤트 DTO

    Attributes:
        port (str): 포트 이름
        data (bytes): 수신/송신 데이터
        timestamp (float): 이벤트 발생 시간
    """
    port: str
    data: bytes
    timestamp: float = 0.0

@dataclass
class PortErrorEvent:
    """
    포트 에러 이벤트 DTO

    Attributes:
        port (str): 포트 이름
        message (str): 에러 메시지
    """
    port: str
    message: str

@dataclass
class PacketEvent:
    """
    패킷 파싱 완료 이벤트 DTO

    Attributes:
        port (str): 포트 이름
        packet (Any): 파싱된 패킷
    """
    port: str
    packet: Any

@dataclass
class ErrorContext:
    """
    시스템 에러 컨텍스트 DTO

    Attributes:
        error_type (str): 에러 타입
        message (str): 에러 메시지
        traceback (str): 에러 추적 정보
        level (str): 에러 레벨
        timestamp (float): 에러 발생 시간
    """
    error_type: str
    message: str
    traceback: str
    level: str = "CRITICAL"
    timestamp: float = 0.0

@dataclass
class MacroScriptData:
    """
    매크로 스크립트 데이터 DTO

    Attributes:
        file_path (str): 스크립트 파일 경로
        data (Dict[str, Any]): 스크립트 데이터
    """
    file_path: str
    data: Dict[str, Any]

    @classmethod
    def from_dict(cls, file_path: str, data: Dict[str, Any]) -> 'MacroScriptData':
        """안전한 생성 메서드"""
        if not isinstance(data, dict):
            data = {}
        # 필수 키 보장
        if "commands" not in data:
            data["commands"] = []
        if "control_state" not in data:
            data["control_state"] = {}
        return cls(file_path=file_path, data=data)

@dataclass
class MacroRepeatOption:
    """
    매크로 반복 실행 옵션 DTO

    Attributes:
        delay_ms (int): 실행 간격 (밀리초)
        max_runs (int): 최대 실행 횟수
        interval_ms (int): 실행 간격 (밀리초)
        broadcast_enabled (bool): 브로드캐스트 사용 여부
    """
    delay_ms: int
    max_runs: int = 0
    interval_ms: int = 0
    broadcast_enabled: bool = False

@dataclass
class MacroExecutionRequest:
    """
    매크로 실행 요청 DTO

    Attributes:
        indices (List[int]): 실행할 매크로 행 인덱스 리스트
        option (MacroRepeatOption): 반복/지연 설정
    """
    indices: List[int]
    option: MacroRepeatOption

@dataclass
class MacroStepEvent:
    """
    매크로 실행 단계 이벤트 DTO

    Attributes:
        index (int): 단계 인덱스
        entry (Optional[MacroEntry]): 실행된 매크로 엔트리
        success (bool): 실행 성공 여부
        type (str): 이벤트 타입
    """
    index: int
    entry: Optional[MacroEntry] = None
    success: bool = False
    type: str = "started"

@dataclass
class PreferencesState:
    """
    환경 설정 상태 DTO

    Attributes:
        theme (str): 테마
        language (str): 언어
        font_size (int): 폰트 크기
        max_log_lines (int): 최대 로그 라인 수
    """
    # General
    theme: str = "Dark"
    language: str = "en"
    font_size: int = 10
    max_log_lines: int = 1000

    # Serial Defaults
    baudrate: int = DEFAULT_BAUDRATE
    newline: str = "LF"
    local_echo_enabled: bool = False
    scan_interval_ms: int = 1000

    # Command
    command_prefix: str = ""
    command_suffix: str = ""

    # Logging
    log_dir: str = ""

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

    Attributes:
        width (int): 너비
        height (int): 높이
        x (Optional[int]): x 좌표
        y (Optional[int]): y 좌표
        splitter_state (Optional[str]): 스플리터 상태
        right_panel_visible (bool): 오른쪽 패널 표시 여부
        right_section_width (Optional[int]): 오른쪽 패널 너비
        left_section_state (Dict[str, Any]): 왼쪽 섹션 상태
        right_section_state (Dict[str, Any]): 오른쪽 섹션 상태
    """
    width: int = 1200
    height: int = 800
    x: Optional[int] = None
    y: Optional[int] = None
    splitter_state: Optional[str] = None
    right_panel_visible: bool = True
    right_section_width: Optional[int] = None
    left_section_state: Dict[str, Any] = field(default_factory=dict)
    right_section_state: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ManualControlState:
    """
    수동 제어 위젯의 상태 DTO

    Attributes:
        input_text (str): 입력 텍스트
        hex_mode (bool): 헥스 모드
        prefix_enabled (bool): 프리픽스 체크
        suffix_enabled (bool): 사фф픽스 체크
        rts_enabled (bool): RTS 체크
        dtr_enabled (bool): DTR 체크
        local_echo_enabled (bool): 로컬 에코 체크
        broadcast_enabled (bool): 브로드캐스트 체크
    """
    input_text: str = ""
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    rts_enabled: bool = False
    dtr_enabled: bool = False
    local_echo_enabled: bool = False
    broadcast_enabled: bool = False

@dataclass
class ColorRule:
    """
    단일 색상 규칙 데이터 클래스 (DTO)

    테마별 색상 지원을 위해 light_color와 dark_color 필드가 추가되었습니다.
    기존 color 필드는 하위 호환성을 위해 유지되지만, 내부적으로는 테마별 필드로 마이그레이션됩니다.

    Attributes:
        name (str): 규칙 이름 (예: "AT_OK")
        pattern (str): 정규식 패턴 또는 문자열
        color (str): (Deprecated) 기본 색상 코드
        light_color (str): 라이트 테마용 색상 코드
        dark_color (str): 다크 테마용 색상 코드
        regex_enabled (bool): 정규식 사용 여부
        enabled (bool): 규칙 활성화 여부
    """
    name: str
    pattern: str
    color: str = "" # 하위 호환성 유지
    light_color: str = ""
    dark_color: str = ""
    regex_enabled: bool = True
    enabled: bool = True

@dataclass
class LogDataBatch:
    """
    로그 뷰어 업데이트용 데이터 배치 DTO
    """
    port: str
    data: bytes
