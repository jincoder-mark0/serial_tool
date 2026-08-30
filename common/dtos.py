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
    DEFAULT_LOG_MAX_LINES,
    DEFAULT_MACRO_INTERVAL_MS,
)
from common.defaults import (
    DEFAULT_COMMAND_PREFIX,
    DEFAULT_COMMAND_SUFFIX,
    DEFAULT_FIXED_FONT_FAMILY,
    DEFAULT_FIXED_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_LOG_PATH,
    DEFAULT_PACKET_AT_COLOR_ERROR,
    DEFAULT_PACKET_AT_COLOR_OK,
    DEFAULT_PACKET_AT_COLOR_PROMPT,
    DEFAULT_PACKET_AT_COLOR_URC,
    DEFAULT_PACKET_AUTOSCROLL,
    DEFAULT_PACKET_BUFFER_SIZE,
    DEFAULT_PACKET_DELIMITERS,
    DEFAULT_PACKET_GAP_MS,
    DEFAULT_PACKET_LENGTH,
    DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
    DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
    DEFAULT_PACKET_LENGTH_FIELD_SIZE,
    DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
    DEFAULT_PACKET_PARSER_TYPE,
    DEFAULT_PACKET_REALTIME,
    DEFAULT_PORT_BYTESIZE,
    DEFAULT_PORT_LOCAL_ECHO,
    DEFAULT_PORT_NEWLINE,
    DEFAULT_PORT_PROTOCOL,
    DEFAULT_PORT_SCAN_INTERVAL_MS,
    DEFAULT_PROP_FONT_FAMILY,
    DEFAULT_PROP_FONT_SIZE,
    DEFAULT_RIGHT_PANEL_VISIBLE,
    DEFAULT_SPI_MODE,
    DEFAULT_SPI_SPEED,
    DEFAULT_THEME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from common.enums import (
    ConnectionEventState,
    FileStatus,
    LogLevel,
    MacroStepType,
    SerialFlowControl,
    SerialParity,
    SerialStopBits,
)


def _safe_cast(value: Any, target_type: type, default: Any) -> Any:
    """
    값을 안전하게 대상 타입으로 변환합니다.
    None이거나 변환 실패 시 기본값을 반환합니다.

    Logic:
        - 값이 None이면 기본값 반환
        - 목표 타입에 맞춰 형변환 시도
        - bool 타입의 경우 "true"/"false" 문자열 처리 지원
        - 변환 중 에러 발생 시 기본값 반환

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
        parser_type (int): 패킷 파서 설정 (Preferences 정수 인덱스, S-041).
        packet_delimiter (str): DELIMITER 파서용 구분자.
        packet_length (int): FIXED_LENGTH 파서용 고정 길이.
        length_field_offset (int): LENGTH_FIELD 길이 필드 오프셋.
        length_field_size (int): LENGTH_FIELD 길이 필드 크기.
        length_field_endian (str): LENGTH_FIELD 바이트 순서.
        length_includes_header (bool): 길이 값이 헤더를 포함하는지.
        gap_ms (int): GAP 파서 프레임 경계 유휴 시간.
    """
    port: str
    protocol: str = DEFAULT_PORT_PROTOCOL

    # Serial Options
    baudrate: int = DEFAULT_BAUDRATE
    bytesize: int = DEFAULT_PORT_BYTESIZE
    parity: str = SerialParity.NONE.value
    stopbits: float = SerialStopBits.ONE.value
    flowctrl: str = SerialFlowControl.NONE.value

    # SPI Options
    speed: int = DEFAULT_SPI_SPEED
    mode: int = DEFAULT_SPI_MODE

    # Packet Parser Options
    parser_type: int = DEFAULT_PACKET_PARSER_TYPE
    packet_delimiter: str = DEFAULT_PACKET_DELIMITERS[0]
    packet_length: int = DEFAULT_PACKET_LENGTH
    length_field_offset: int = DEFAULT_PACKET_LENGTH_FIELD_OFFSET
    length_field_size: int = DEFAULT_PACKET_LENGTH_FIELD_SIZE
    length_field_endian: str = DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
    length_includes_header: bool = DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
    gap_ms: int = DEFAULT_PACKET_GAP_MS

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PortConfig':
        """
        Dictionary에서 안전하게 PortConfig 객체를 생성합니다.

        누락 필드는 DTO 내부 리터럴이 아니라 common.defaults의 정본을 사용합니다.
        S-072에서 추가된 length-field/gap 필드도 저장 상태에서 완전 복원합니다.
        """
        return cls(
            port=data.get("port", ""),
            protocol=data.get("protocol", DEFAULT_PORT_PROTOCOL),
            baudrate=_safe_cast(data.get("baudrate"), int, DEFAULT_BAUDRATE),
            bytesize=_safe_cast(data.get("bytesize"), int, DEFAULT_PORT_BYTESIZE),
            parity=data.get("parity", SerialParity.NONE.value),
            stopbits=_safe_cast(data.get("stopbits"), float, SerialStopBits.ONE.value),
            flowctrl=data.get("flowctrl", SerialFlowControl.NONE.value),
            speed=_safe_cast(data.get("speed"), int, DEFAULT_SPI_SPEED),
            mode=_safe_cast(data.get("mode"), int, DEFAULT_SPI_MODE),
            parser_type=_safe_cast(data.get("parser_type"), int, DEFAULT_PACKET_PARSER_TYPE),
            packet_delimiter=_safe_cast(
                data.get("packet_delimiter"), str, DEFAULT_PACKET_DELIMITERS[0]
            ),
            packet_length=_safe_cast(data.get("packet_length"), int, DEFAULT_PACKET_LENGTH),
            length_field_offset=_safe_cast(
                data.get("length_field_offset"), int, DEFAULT_PACKET_LENGTH_FIELD_OFFSET
            ),
            length_field_size=_safe_cast(
                data.get("length_field_size"), int, DEFAULT_PACKET_LENGTH_FIELD_SIZE
            ),
            length_field_endian=_safe_cast(
                data.get("length_field_endian"), str, DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
            ),
            length_includes_header=_safe_cast(
                data.get("length_includes_header"), bool, DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
            ),
            gap_ms=_safe_cast(data.get("gap_ms"), int, DEFAULT_PACKET_GAP_MS),
        )


@dataclass
class PortInfo:
    """검색된 포트 정보 DTO."""
    device: str
    description: str


@dataclass
class PortStatistics:
    """포트 통신 통계 DTO."""
    rx_bytes: int = 0
    tx_bytes: int = 0
    error_count: int = 0
    bps: int = 0


@dataclass
class PortConnectionEvent:
    """
    포트 연결 상태 변경 이벤트 DTO.

    state는 직렬화 호환성을 위해 str로 유지하지만 값은
    ConnectionEventState.OPENED/CLOSED.value를 사용합니다.
    """
    port: str
    state: str


@dataclass
class PortDataEvent:
    """포트 데이터 수신/송신 이벤트 DTO."""
    port: str
    data: bytes
    timestamp: float = field(default_factory=time.time)


@dataclass
class PortErrorEvent:
    """포트 에러 이벤트 DTO."""
    port: str
    message: str


# =============================================================================
# 2. 명령어 및 매크로 관련 DTO (Command & Macro)
# =============================================================================

@dataclass
class ManualCommand:
    """수동 Command 전송 데이터 DTO."""
    command: str
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    local_echo_enabled: bool = False
    broadcast_enabled: bool = False


@dataclass
class MacroEntry:
    """매크로 항목 데이터 DTO."""
    enabled: bool = True
    command: str = ""
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    delay_ms: int = 0
    expect: str = ""
    timeout_ms: int = 5000

    def to_dict(self) -> Dict[str, Any]:
        """DTO를 딕셔너리로 변환합니다."""
        return {
            "enabled": self.enabled,
            "command": self.command,
            "hex_mode": self.hex_mode,
            "prefix_enabled": self.prefix_enabled,
            "suffix_enabled": self.suffix_enabled,
            "delay_ms": self.delay_ms,
            "expect": self.expect,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MacroEntry':
        """딕셔너리에서 MacroEntry 객체를 생성합니다."""
        return cls(
            enabled=_safe_cast(data.get("enabled"), bool, True),
            command=_safe_cast(data.get("command"), str, ""),
            hex_mode=_safe_cast(data.get("hex_mode"), bool, False),
            prefix_enabled=_safe_cast(data.get("prefix_enabled"), bool, False),
            suffix_enabled=_safe_cast(data.get("suffix_enabled"), bool, False),
            delay_ms=_safe_cast(data.get("delay_ms"), int, 0),
            expect=_safe_cast(data.get("expect"), str, ""),
            timeout_ms=_safe_cast(data.get("timeout_ms"), int, 5000),
        )


@dataclass
class MacroScriptData:
    """매크로 스크립트 데이터 DTO."""
    file_path: str
    data: Dict[str, Any]

    @classmethod
    def from_dict(cls, file_path: str, data: Dict[str, Any]) -> 'MacroScriptData':
        """파일 경로와 데이터로 객체를 생성하며 필수 키를 보장합니다."""
        if not isinstance(data, dict):
            data = {}
        if "commands" not in data:
            data["commands"] = []
        if "control_state" not in data:
            data["control_state"] = {}
        return cls(file_path=file_path, data=data)


@dataclass
class MacroRepeatOption:
    """매크로 반복 실행 옵션 DTO."""
    max_runs: int = 0
    interval_ms: int = 0
    broadcast_enabled: bool = False
    stop_on_error: bool = True


@dataclass
class MacroExecutionRequest:
    """매크로 실행 요청 DTO."""
    indices: List[int]
    option: MacroRepeatOption


@dataclass
class MacroStepEvent:
    """
    매크로 실행 단계 이벤트 DTO.

    type은 직렬화 호환성을 위해 str로 유지하며 MacroStepType 값을 사용합니다.
    """
    index: int
    entry: Optional[MacroEntry] = None
    success: bool = False
    type: str = MacroStepType.STARTED.value


@dataclass
class MacroErrorEvent:
    """매크로 실행 에러 이벤트 DTO."""
    message: str
    row_index: int = -1


# =============================================================================
# 3. 파일 전송 관련 DTO (File Transfer)
# =============================================================================

@dataclass
class FileProgressState:
    """파일 전송 진행 상태 DTO (UI 업데이트용)."""
    file_path: str = ""
    sent_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: float = 0.0
    status: str = FileStatus.SENDING.value
    error_msg: str = ""


@dataclass
class FileProgressEvent:
    """파일 전송 진행 이벤트 DTO."""
    current: int
    total: int


@dataclass
class FileCompletionEvent:
    """파일 전송 완료 이벤트 DTO."""
    success: bool
    message: str
    file_path: str = ""


@dataclass
class FileErrorEvent:
    """파일 전송 에러 이벤트 DTO."""
    message: str
    file_path: str = ""


# =============================================================================
# 4. 패킷 및 로그 관련 DTO (Packet & Log)
# =============================================================================

@dataclass
class PacketEvent:
    """패킷 파싱 완료 이벤트 DTO."""
    port: str
    packet: Any


@dataclass
class PacketViewData:
    """패킷 뷰 표시용 데이터 DTO."""
    time_str: str
    packet_type: str
    data_hex: str
    data_ascii: str
    checksum_ok: Optional[bool] = None


@dataclass
class LogDataBatch:
    """로그 뷰어 업데이트용 데이터 배치 DTO."""
    port: str
    data: bytes


@dataclass
class SystemLogEvent:
    """시스템 로그 이벤트 DTO."""
    message: str
    level: str = LogLevel.INFO.value
    timestamp: float = field(default_factory=time.time)


@dataclass
class ColorRule:
    """단일 색상 규칙 데이터 DTO."""
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
    """폰트 설정 데이터 DTO."""
    prop_family: str
    prop_size: int
    fixed_family: str
    fixed_size: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FontConfig':
        """딕셔너리에서 안전하게 FontConfig 객체를 생성합니다."""
        return cls(
            prop_family=_safe_cast(data.get("prop_family"), str, DEFAULT_PROP_FONT_FAMILY),
            prop_size=_safe_cast(data.get("prop_size"), int, DEFAULT_PROP_FONT_SIZE),
            fixed_family=_safe_cast(data.get("fixed_family"), str, DEFAULT_FIXED_FONT_FAMILY),
            fixed_size=_safe_cast(data.get("fixed_size"), int, DEFAULT_FIXED_FONT_SIZE),
        )


@dataclass
class PreferencesState:
    """환경 설정 전체 상태 DTO."""
    # General
    theme: str = DEFAULT_THEME
    language: str = DEFAULT_LANGUAGE
    font_size: int = DEFAULT_PROP_FONT_SIZE
    max_log_lines: int = DEFAULT_LOG_MAX_LINES

    # Serial Defaults
    baudrate: int = DEFAULT_BAUDRATE
    newline: str = DEFAULT_PORT_NEWLINE
    local_echo_enabled: bool = DEFAULT_PORT_LOCAL_ECHO
    scan_interval_ms: int = DEFAULT_PORT_SCAN_INTERVAL_MS

    # Command
    command_prefix: str = DEFAULT_COMMAND_PREFIX
    command_suffix: str = DEFAULT_COMMAND_SUFFIX

    # Logging
    log_dir: str = DEFAULT_LOG_PATH

    # Packet
    parser_type: int = DEFAULT_PACKET_PARSER_TYPE
    delimiters: List[str] = field(default_factory=lambda: list(DEFAULT_PACKET_DELIMITERS))
    packet_length: int = DEFAULT_PACKET_LENGTH
    length_field_offset: int = DEFAULT_PACKET_LENGTH_FIELD_OFFSET
    length_field_size: int = DEFAULT_PACKET_LENGTH_FIELD_SIZE
    length_field_endian: str = DEFAULT_PACKET_LENGTH_FIELD_ENDIAN
    length_includes_header: bool = DEFAULT_PACKET_LENGTH_INCLUDES_HEADER
    gap_ms: int = DEFAULT_PACKET_GAP_MS
    at_color_ok: bool = DEFAULT_PACKET_AT_COLOR_OK
    at_color_error: bool = DEFAULT_PACKET_AT_COLOR_ERROR
    at_color_urc: bool = DEFAULT_PACKET_AT_COLOR_URC
    at_color_prompt: bool = DEFAULT_PACKET_AT_COLOR_PROMPT
    packet_buffer_size: int = DEFAULT_PACKET_BUFFER_SIZE
    packet_realtime: bool = DEFAULT_PACKET_REALTIME
    packet_autoscroll: bool = DEFAULT_PACKET_AUTOSCROLL


@dataclass
class MainWindowState:
    """메인 윈도우 상태 DTO (크기, 위치, 레이아웃)."""
    width: int = DEFAULT_WINDOW_WIDTH
    height: int = DEFAULT_WINDOW_HEIGHT
    x: Optional[int] = None
    y: Optional[int] = None
    splitter_state: Optional[str] = None
    right_panel_visible: bool = DEFAULT_RIGHT_PANEL_VISIBLE
    right_section_width: Optional[int] = None
    left_section_state: Dict[str, Any] = field(default_factory=dict)
    right_section_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ManualControlState:
    """수동 제어 위젯 상태 DTO."""
    input_text: str = ""
    hex_mode: bool = False
    prefix_enabled: bool = False
    suffix_enabled: bool = False
    rts_enabled: bool = False
    dtr_enabled: bool = False
    local_echo_enabled: bool = False
    broadcast_enabled: bool = False
    auto_tx_enabled: bool = False
    auto_tx_interval_ms: int = DEFAULT_MACRO_INTERVAL_MS


@dataclass
class ErrorContext:
    """시스템 에러 컨텍스트 DTO."""
    error_type: str
    message: str
    traceback: str
    level: str = LogLevel.CRITICAL.value
    timestamp: float = field(default_factory=time.time)


@dataclass
class MacroSendResult:
    """
    매크로 명령 1건의 전송 결과 DTO (S-080).

    매크로 스텝의 성공/실패 판정이 실제 전송 결과와 이어지도록 하기 위한 반환 타입입니다.
    """
    success: bool
    message: str = ""
    data: bytes = b""
