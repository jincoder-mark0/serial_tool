"""
공통 데이터 전송 객체(DTO) 모듈

애플리케이션 전반(View, Model, Presenter, Core)에서 공통으로 사용되는
데이터 구조(Schema)를 정의합니다.

## WHY
* 계층 간 데이터 교환 시 타입 안정성(Type Safety) 보장
* 딕셔너리 사용 시 발생하는 Key Error 및 오타 방지
* 순환 참조(Circular Import) 방지를 위한 최하위 계층 위치 선정

## WHAT
* PortConfig, ManualCommand, MacroEntry 등 핵심 데이터 구조 정의
* Event, State 관련 DTO (FileProgressState, PacketEvent 등) 정의
* ColorRule 등 설정 관련 데이터 구조 정의

## HOW
* Python dataclasses 데코레이터 활용
* to_dict/from_dict 메서드를 통해 JSON 직렬화/역직렬화 지원
* 안전한 타입 변환을 위한 내부 헬퍼 메서드(_safe_cast) 적용
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time

from common.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_MACRO_INTERVAL_MS,
    FONT_FAMILY_SEGOE,
    FONT_FAMILY_CONSOLAS
)
from common.enums import (
    SerialParity,
    SerialStopBits,
    SerialFlowControl,
    FileStatus
)


def _safe_cast(value: Any, target_type: type, default: Any) -> Any:
    """
    값을 안전하게 대상 타입으로 변환합니다.
    None이거나 변환 실패 시 기본값을 반환합니다.

    Args:
        value (Any): 변환할 값.
        target_type (type): 목표로 하는 데이터 타입 (int, float, bool, str, list).
        default (Any): 변환 실패 시 반환할 기본값.

    Returns:
        Any: 변환된 값 또는 기본값.
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


# =============================================================================
# 1. 포트 및 연결 관련 DTO (Port & Connection)
# =============================================================================

@dataclass
class PortConfig:
    """
    포트 연결 설정 데이터 DTO

    Attributes:
        port (str): 포트 이름 (예: COM1).
        protocol (str): 프로토콜 (Serial, SPI 등).
        baudrate (int): 보드레이트.
        bytesize (int): 바이트 사이즈.
        parity (str): 패리티 비트 설정.
        stopbits (float): 스탑 비트 설정.
        flowctrl (str): 흐름 제어 설정.
        speed (int): SPI 속도 (Hz).
        mode (int): SPI 모드.
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
        Dictionary에서 안전하게 PortConfig 객체를 생성합니다.

        Args:
            data (Dict[str, Any]): JSON 데이터 딕셔너리.

        Returns:
            PortConfig: 생성된 PortConfig 객체.
        """
        return cls(
            port=data.get("port", ""),
            protocol=data.get("protocol", "Serial"),
            baudrate=_safe_cast(data.get("baudrate"), int, DEFAULT_BAUDRATE),
            bytesize=_safe_cast(data.get("bytesize"), int, 8),
            parity=data.get("parity", SerialParity.NONE.value),
            stopbits=_safe_cast(data.get("stopbits"), float, SerialStopBits.ONE.value),
            flowctrl=data.get("flowctrl", SerialFlowControl.NONE.value),
            speed=_safe_cast(data.get("speed"), int, 1000000),
            mode=_safe_cast(data.get("mode"), int, 0)
        )


@dataclass
class PortInfo:
    """
    검색된 포트 정보 DTO

    Attributes:
        device (str): 포트 장치 이름 (예: COM1).
        description (str): 포트 설명 (예: USB Serial Port).
    """
    device: str
    description: str


@dataclass
class PortStatistics:
    """
    포트 통신 통계 DTO

    Attributes:
        rx_bytes (int): 수신 바이트 수.
        tx_bytes (int): 송신 바이트 수.
        error_count (int): 에러 발생 횟수.
        bps (int): 초당 비트 전송률.
    """
    rx_bytes: int = 0
    tx_bytes: int = 0
    error_count: int = 0
    bps: int = 0


@dataclass
class PortConnectionEvent:
    """
    포트 연결 상태 변경 이벤트 DTO

    Attributes:
        port (str): 포트 이름.
        state (str): 연결 상태 ('opened' 또는 'closed').
    """
    port: str
    state: str


@dataclass
class PortDataEvent:
    """
    포트 데이터 수신/송신 이벤트 DTO

    Attributes:
        port (str): 포트 이름.
        data (bytes): 수신/송신된 바이트 데이터.
        timestamp (float): 이벤트 발생 시간 (Unix timestamp).
    """
    port: str
    data: bytes
    timestamp: float = field(default_factory=time.time)

@dataclass
class PortErrorEvent:
    """
    포트 에러 이벤트 DTO

    Attributes:
        port (str): 포트 이름.
        message (str): 에러 메시지 내용.
    """
    port: str
    message: str


# =============================================================================
# 2. 명령어 및 매크로 관련 DTO (Command & Macro)
# =============================================================================

@dataclass
class ManualCommand:
    """
    수동 Command 전송 데이터 DTO

    Attributes:
        command (str): 전송할 텍스트 명령어.
        hex_mode (bool): 16진수 모드 여부.
        prefix_enabled (bool): 접두사 사용 여부.
        suffix_enabled (bool): 접미사 사용 여부.
        local_echo_enabled (bool): 로컬 에코 사용 여부.
        broadcast_enabled (bool): 브로드캐스트 전송 여부.
    """
    command: str
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    local_echo_enabled: bool = False
    broadcast_enabled: bool = False

@dataclass
class MacroEntry:
    """
    매크로 항목 데이터 DTO

    Attributes:
        enabled (bool): 항목 활성화 여부.
        command (str): 전송할 명령어.
        hex_mode (bool): HEX 모드 여부.
        prefix_enabled (bool): 접두사 사용 여부 (UI상 prefix_enabled).
        suffix_enabled (bool): 접미사 사용 여부 (UI상 suffix_enabled).
        delay_ms (int): 다음 명령까지의 대기 시간 (ms).
        expect (str): 기대하는 응답 패턴 (Expect 기능용).
        timeout_ms (int): 응답 대기 시간 제한 (ms).
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
        DTO를 딕셔너리로 변환합니다 (설정 저장용).

        Returns:
            Dict[str, Any]: 속성값을 담은 딕셔너리.
        """
        return {
            "enabled": self.enabled,
            "command": self.command,
            "hex_mode": self.hex_mode,
            "prefix_enabled": self.prefix_enabled,
            "suffix_enabled": self.suffix_enabled,
            "delay_ms": self.delay_ms,
            "expect": self.expect,
            "timeout_ms": self.timeout_ms
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MacroEntry':
        """
        딕셔너리에서 MacroEntry 객체를 생성합니다 (설정 로드용).

        Args:
            data (Dict[str, Any]): 매크로 데이터 딕셔너리.

        Returns:
            MacroEntry: 생성된 인스턴스.
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
class MacroScriptData:
    """
    매크로 스크립트 데이터 DTO

    Attributes:
        file_path (str): 스크립트 파일 경로.
        data (Dict[str, Any]): 스크립트 내용 데이터.
    """
    file_path: str
    data: Dict[str, Any]

    @classmethod
    def from_dict(cls, file_path: str, data: Dict[str, Any]) -> 'MacroScriptData':
        """
        파일 경로와 데이터로 객체를 생성하며 필수 키를 보장합니다.

        Args:
            file_path (str): 파일 경로.
            data (Dict[str, Any]): JSON 로드 데이터.

        Returns:
            MacroScriptData: 생성된 객체.
        """
        if not isinstance(data, dict):
            data = {}
        # 필수 키 구조 보장
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
        max_runs (int): 최대 실행 횟수 (0=무한).
        interval_ms (int): 실행 간격 (ms).
        broadcast_enabled (bool): 브로드캐스트 사용 여부.
    """
    max_runs: int = 0
    interval_ms: int = 0
    broadcast_enabled: bool = False


@dataclass
class MacroExecutionRequest:
    """
    매크로 실행 요청 DTO

    Attributes:
        indices (List[int]): 실행할 매크로 행 인덱스 리스트.
        option (MacroRepeatOption): 반복 및 지연 설정 옵션.
    """
    indices: List[int]
    option: MacroRepeatOption


@dataclass
class MacroStepEvent:
    """
    매크로 실행 단계 이벤트 DTO

    Attributes:
        index (int): 현재 실행 중인 단계의 인덱스.
        entry (Optional[MacroEntry]): 실행된 매크로 항목 객체.
        success (bool): 실행 성공 여부.
        type (str): 이벤트 타입 ('started', 'completed' 등).
    """
    index: int
    entry: Optional[MacroEntry] = None
    success: bool = False
    type: str = "started"


@dataclass
class MacroErrorEvent:
    """
    매크로 실행 에러 이벤트 DTO

    Attributes:
        message (str): 에러 메시지.
        row_index (int): 에러가 발생한 행 인덱스 (-1이면 전역 에러).
    """
    message: str
    row_index: int = -1


# =============================================================================
# 3. 파일 전송 관련 DTO (File Transfer)
# =============================================================================

@dataclass
class FileProgressState:
    """
    파일 전송 진행 상태 DTO (UI 업데이트용)

    Attributes:
        file_path (str): 파일 경로.
        sent_bytes (int): 현재까지 전송된 바이트 수.
        total_bytes (int): 전체 파일 크기 (바이트).
        speed (float): 현재 전송 속도 (bytes/s).
        eta (float): 예상 남은 시간 (초).
        status (str): 현재 상태 문자열.
        error_msg (str): 에러 발생 시 메시지.
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
    파일 전송 진행 이벤트 DTO (EventBus용 경량 객체)

    Attributes:
        current (int): 현재 전송된 바이트 수.
        total (int): 전체 파일 크기.
    """
    current: int
    total: int


@dataclass
class FileCompletionEvent:
    """
    파일 전송 완료 이벤트 DTO

    Attributes:
        success (bool): 전송 성공 여부.
        message (str): 완료 메시지 또는 에러 메시지.
        file_path (str): 전송된 파일 경로.
    """
    success: bool
    message: str
    file_path: str = ""


@dataclass
class FileErrorEvent:
    """
    파일 전송 에러 이벤트 DTO

    Attributes:
        message (str): 에러 메시지.
        file_path (str): 관련 파일 경로.
    """
    message: str
    file_path: str = ""


# =============================================================================
# 4. 패킷 및 로그 관련 DTO (Packet & Log)
# =============================================================================

@dataclass
class PacketEvent:
    """
    패킷 파싱 완료 이벤트 DTO

    Attributes:
        port (str): 패킷이 수신된 포트 이름.
        packet (Any): 파싱된 패킷 객체 (model.packet_parser.Packet).
    """
    port: str
    packet: Any

@dataclass
class PacketViewData:
    """
    패킷 뷰 표시용 데이터 DTO

    Attributes:
        time_str (str): 타임스탬프 문자열.
        packet_type (str): 패킷 타입 문자열.
        data_hex (str): 데이터의 HEX 문자열 표현.
        data_ascii (str): 데이터의 ASCII 문자열 표현.
    """
    time_str: str
    packet_type: str
    data_hex: str
    data_ascii: str


@dataclass
class LogDataBatch:
    """
    로그 뷰어 업데이트용 데이터 배치 DTO

    Attributes:
        port (str): 데이터가 속한 포트 이름.
        data (bytes): 수신된 데이터 배치.
    """
    port: str
    data: bytes


@dataclass
class SystemLogEvent:
    """
    시스템 로그 이벤트 DTO

    Attributes:
        message (str): 로그 메시지 내용.
        level (str): 로그 레벨 (INFO, ERROR, WARN, SUCCESS).
        timestamp (float): 로그 발생 시간 (Unix timestamp). 기본값은 현재 시간.
    """
    message: str
    level: str = "INFO"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ColorRule:
    """
    단일 색상 규칙 데이터 DTO

    Attributes:
        name (str): 규칙 이름 (예: "AT_OK").
        pattern (str): 매칭 패턴 (문자열 또는 정규식).
        color (str): (Legacy) 기본 색상 코드.
        light_color (str): 라이트 테마용 색상 코드.
        dark_color (str): 다크 테마용 색상 코드.
        regex_enabled (bool): 정규식 사용 여부.
        enabled (bool): 규칙 활성화 여부.
        bold (bool): 규칙 적용 시 폰트 굵게 표시 여부.
    """
    name: str
    pattern: str
    color: str = ""
    light_color: str = ""
    dark_color: str = ""
    regex_enabled: bool = True
    enabled: bool = True
    bold: bool = False

# =============================================================================
# 5. 설정 및 상태 관련 DTO (Settings & State)
# =============================================================================

@dataclass
class FontConfig:
    """
    폰트 설정 데이터 DTO

    Attributes:
        prop_family (str): 가변폭 폰트 패밀리.
        prop_size (int): 가변폭 폰트 크기.
        fixed_family (str): 고정폭 폰트 패밀리.
        fixed_size (int): 고정폭 폰트 크기.
    """
    prop_family: str
    prop_size: int
    fixed_family: str
    fixed_size: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FontConfig':
        """
        딕셔너리에서 안전하게 FontConfig 객체를 생성합니다.

        Args:
            data (Dict[str, Any]): 폰트 설정 딕셔너리.

        Returns:
            FontConfig: 생성된 객체.
        """
        return cls(
            prop_family=_safe_cast(data.get("prop_family"), str, FONT_FAMILY_SEGOE),
            prop_size=_safe_cast(data.get("prop_size"), int, 9),
            fixed_family=_safe_cast(data.get("fixed_family"), str, FONT_FAMILY_CONSOLAS),
            fixed_size=_safe_cast(data.get("fixed_size"), int, 9)
        )

@dataclass
class PreferencesState:
    """
    환경 설정 전체 상태 DTO

    Attributes:
        theme (str): 테마 (Dark/Light).
        language (str): 언어 코드 (en/ko).
        font_size (int): UI 폰트 크기.
        max_log_lines (int): 최대 로그 라인 수.
        baudrate (int): 기본 보드레이트.
        newline (str): 줄바꿈 모드.
        local_echo_enabled (bool): 로컬 에코 사용 여부.
        scan_interval_ms (int): 포트 스캔 간격.
        command_prefix (str): 명령어 접두사.
        command_suffix (str): 명령어 접미사.
        log_dir (str): 로그 저장 디렉토리.
        parser_type (int): 파서 타입 인덱스.
        delimiters (List[str]): 구분자 목록.
        packet_length (int): 고정 패킷 길이.
        at_color_ok (bool): AT OK 색상 적용 여부.
        at_color_error (bool): AT ERROR 색상 적용 여부.
        at_color_urc (bool): AT URC 색상 적용 여부.
        at_color_prompt (bool): AT Prompt 색상 적용 여부.
        packet_buffer_size (int): 패킷 버퍼 크기.
        packet_realtime (bool): 패킷 실시간 추적 여부.
        packet_autoscroll (bool): 패킷 자동 스크롤 여부.
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
    메인 윈도우 상태 DTO (크기, 위치, 레이아웃)

    Attributes:
        width (int): 윈도우 너비.
        height (int): 윈도우 높이.
        x (Optional[int]): X 좌표.
        y (Optional[int]): Y 좌표.
        splitter_state (Optional[str]): 스플리터 상태 (Base64).
        right_panel_visible (bool): 우측 패널 표시 여부.
        right_section_width (Optional[int]): 우측 패널 저장된 너비.
        left_section_state (Dict[str, Any]): 좌측 섹션 상태 데이터.
        right_section_state (Dict[str, Any]): 우측 섹션 상태 데이터.
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
    수동 제어 위젯 상태 DTO

    Attributes:
        input_text (str): 입력창 텍스트.
        hex_mode (bool): HEX 모드 체크 상태.
        prefix_enabled (bool): 접두사 체크 상태.
        suffix_enabled (bool): 접미사 체크 상태.
        rts_enabled (bool): RTS 체크 상태.
        dtr_enabled (bool): DTR 체크 상태.
        local_echo_enabled (bool): 로컬 에코 체크 상태.
        broadcast_enabled (bool): 브로드캐스트 체크 상태.
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
class ErrorContext:
    """
    시스템 에러 컨텍스트 DTO

    Attributes:
        error_type (str): 에러 타입 이름.
        message (str): 에러 상세 메시지.
        traceback (str): 스택 트레이스 문자열.
        level (str): 에러 레벨 (기본 CRITICAL).
        timestamp (float): 에러 발생 시간 (Unix timestamp).
    """
    error_type: str
    message: str
    traceback: str
    level: str = "CRITICAL"
    timestamp: float = field(default_factory=time.time)
