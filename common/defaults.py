"""
기본 설정값 정의 모듈

애플리케이션의 초기화 및 설정 파일 복구에 사용되는 기본값들을 정의합니다.
SettingsManager의 하드코딩을 방지하고 설정값 관리를 중앙화합니다.

## WHY
* 설정 파일이 일부 누락되거나 손상됐을 때 호출 위치마다 서로 다른 fallback을
  사용하면 동일한 앱 상태가 경로에 따라 달라질 수 있습니다.
* DTO/Presenter/View가 각자 숫자·문자열 기본값을 복제하지 않도록 설정 기본값의
  단일 정본(single source of truth)을 제공합니다.

## HOW
* 재사용 가능한 scalar 기본값을 먼저 정의합니다.
* fallback 딕셔너리는 scalar 기본값을 조립해서 만듭니다.
* 런타임에서 설정값을 읽을 때도 가능한 한 이 scalar 기본값을 참조합니다.
"""
from common.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_LOG_MAX_LINES,
    DEFAULT_MACRO_INTERVAL_MS,
    FONT_FAMILY_CONSOLAS,
    FONT_FAMILY_SEGOE,
)

# ==========================================
# Canonical Scalar Defaults
# ==========================================
SETTINGS_VERSION: str = "1.3"

DEFAULT_THEME: str = "dark"
DEFAULT_LANGUAGE: str = "ko"
DEFAULT_PROP_FONT_FAMILY: str = FONT_FAMILY_SEGOE
DEFAULT_PROP_FONT_SIZE: int = 10
DEFAULT_FIXED_FONT_FAMILY: str = FONT_FAMILY_CONSOLAS
DEFAULT_FIXED_FONT_SIZE: int = 9

DEFAULT_WINDOW_WIDTH: int = 1200
DEFAULT_WINDOW_HEIGHT: int = 800
DEFAULT_RIGHT_PANEL_VISIBLE: bool = True

DEFAULT_PORT_NEWLINE: str = "\n"
DEFAULT_PORT_LOCAL_ECHO: bool = False
DEFAULT_PORT_SCAN_INTERVAL_MS: int = 1000

DEFAULT_COMMAND_PREFIX: str = ""
DEFAULT_COMMAND_SUFFIX: str = ""
DEFAULT_LOG_PATH: str = ""

DEFAULT_PACKET_PARSER_TYPE: int = 0
DEFAULT_PACKET_DELIMITERS = ["\\r\\n"]
DEFAULT_PACKET_LENGTH: int = 64
DEFAULT_PACKET_AT_COLOR_OK: bool = True
DEFAULT_PACKET_AT_COLOR_ERROR: bool = True
DEFAULT_PACKET_AT_COLOR_URC: bool = True
DEFAULT_PACKET_AT_COLOR_PROMPT: bool = True
DEFAULT_PACKET_BUFFER_SIZE: int = 100
DEFAULT_PACKET_REALTIME: bool = True
DEFAULT_PACKET_AUTOSCROLL: bool = True
DEFAULT_PACKET_LENGTH_FIELD_OFFSET: int = 0
DEFAULT_PACKET_LENGTH_FIELD_SIZE: int = 1
DEFAULT_PACKET_LENGTH_FIELD_ENDIAN: str = "big"
DEFAULT_PACKET_LENGTH_INCLUDES_HEADER: bool = False
DEFAULT_PACKET_GAP_MS: int = 5
DEFAULT_PACKET_CHECKSUM_ALGORITHM: str = "none"
DEFAULT_PACKET_CHECKSUM_OFFSET: int = -1
DEFAULT_PACKET_CHECKSUM_EXCLUDE_LEADING: int = 0
DEFAULT_PACKET_CHECKSUM_EXCLUDE_TRAILING: int = 0


# ==========================================
# Section Defaults
# ==========================================

# settings.* 정본 블록의 기본값 (S-027 — 과거 global 블록 기본값 유지)
DEFAULT_SETTINGS_BLOCK = {
    "theme": DEFAULT_THEME,
    "language": DEFAULT_LANGUAGE,
    "proportional_font_family": DEFAULT_PROP_FONT_FAMILY,
    "proportional_font_size": DEFAULT_PROP_FONT_SIZE,
    "fixed_font_family": DEFAULT_FIXED_FONT_FAMILY,
    "fixed_font_size": DEFAULT_FIXED_FONT_SIZE,
    "max_log_lines": DEFAULT_LOG_MAX_LINES,
    "port_baudrate": DEFAULT_BAUDRATE,
    "port_newline": DEFAULT_PORT_NEWLINE,
    "port_local_echo": DEFAULT_PORT_LOCAL_ECHO,
    "port_scan_interval_ms": DEFAULT_PORT_SCAN_INTERVAL_MS,
    "command_prefix": DEFAULT_COMMAND_PREFIX,
    "command_suffix": DEFAULT_COMMAND_SUFFIX,
}

DEFAULT_UI_SETTINGS = {
    "max_log_lines": DEFAULT_LOG_MAX_LINES,
    # S-027: 폰트 키(proportional/fixed font family/size)는 죽은 키였다 —
    # 실사용은 settings.* 쪽(ConfigKeys.PROP_FONT_*)이므로 여기서 제거.
    # Window state placeholders
    "window_width": DEFAULT_WINDOW_WIDTH,
    "window_height": DEFAULT_WINDOW_HEIGHT,
    "window_x": None,
    "window_y": None,
    "splitter_state": None,
    "right_section_visible": DEFAULT_RIGHT_PANEL_VISIBLE,
    "saved_right_section_width": None,
}

DEFAULT_COMMAND_SETTINGS = {
    "prefix": DEFAULT_COMMAND_PREFIX,
    "suffix": DEFAULT_COMMAND_SUFFIX,
}

DEFAULT_LOGGING_SETTINGS = {
    # ConfigKeys.LOG_PATH의 실제 경로는 logging.path이다.
    # 과거 log_dir만 있어 SettingsManager fallback이 경로마다 달라질 수 있었다.
    "path": DEFAULT_LOG_PATH,
    "log_dir": DEFAULT_LOG_PATH,
}

DEFAULT_PACKET_SETTINGS = {
    "parser_type": DEFAULT_PACKET_PARSER_TYPE,  # Auto
    "delimiters": list(DEFAULT_PACKET_DELIMITERS),
    "packet_length": DEFAULT_PACKET_LENGTH,
    "at_color_ok": DEFAULT_PACKET_AT_COLOR_OK,
    "at_color_error": DEFAULT_PACKET_AT_COLOR_ERROR,
    "at_color_urc": DEFAULT_PACKET_AT_COLOR_URC,
    "at_color_prompt": DEFAULT_PACKET_AT_COLOR_PROMPT,
    "buffer_size": DEFAULT_PACKET_BUFFER_SIZE,
    "realtime": DEFAULT_PACKET_REALTIME,
    "autoscroll": DEFAULT_PACKET_AUTOSCROLL,
    # 체크섬 검증 (S-071). algorithm="none"이면 검증하지 않는다(기본값).
    # offset은 패킷 끝에서 체크섬 필드가 시작하는 위치를 음수로 센다 —
    # 대부분의 프로토콜이 체크섬을 말미에 두므로 끝 기준이 안정적이다.
    # exclude_leading/trailing은 계산 대상에서 제외할 앞/뒤 바이트 수다
    # (SOF 헤더 제외, 체크섬 필드 자신 제외 등).
    # 프레이밍 확장 (S-072). 길이 필드는 [LEN][PAYLOAD] 형태를 기본으로 잡는다.
    "length_field_offset": DEFAULT_PACKET_LENGTH_FIELD_OFFSET,
    "length_field_size": DEFAULT_PACKET_LENGTH_FIELD_SIZE,
    "length_field_endian": DEFAULT_PACKET_LENGTH_FIELD_ENDIAN,
    "length_includes_header": DEFAULT_PACKET_LENGTH_INCLUDES_HEADER,
    # 갭 기반 프레이밍의 유휴 임계(ms). Modbus RTU의 3.5문자 유휴가 9600bps에서
    # 약 4ms라 그보다 조금 큰 값을 기본으로 둔다.
    "gap_ms": DEFAULT_PACKET_GAP_MS,
    "checksum_algorithm": DEFAULT_PACKET_CHECKSUM_ALGORITHM,
    "checksum_offset": DEFAULT_PACKET_CHECKSUM_OFFSET,
    "checksum_exclude_leading": DEFAULT_PACKET_CHECKSUM_EXCLUDE_LEADING,
    "checksum_exclude_trailing": DEFAULT_PACKET_CHECKSUM_EXCLUDE_TRAILING,
}

DEFAULT_PORTS_STATE = {
    "tabs": [],  # Tab state persistence
}

DEFAULT_MANUAL_CONTROL_STATE = {
    "manual_control_widget": {
        "input_text": "",
        "hex_mode": False,
        "prefix_enabled": False,
        "suffix_enabled": False,
        "rts_enabled": False,
        "dtr_enabled": False,
        "local_echo_enabled": False,
        "broadcast_enabled": False,
        "auto_tx_enabled": False,
        "auto_tx_interval_ms": DEFAULT_MACRO_INTERVAL_MS,
    }
}

DEFAULT_MACRO_LIST_STATE = {
    "commands": [],
    "control_state": {
        "delay_ms": str(DEFAULT_MACRO_INTERVAL_MS),
        "max_runs": 0,
        "broadcast_enabled": False,
    },
}


# ==========================================
# Full Fallback Configuration
# ==========================================
def create_fallback_settings() -> dict:
    """전체 기본 설정 딕셔너리를 생성하여 반환합니다."""
    return {
        "version": SETTINGS_VERSION,
        "settings": DEFAULT_SETTINGS_BLOCK.copy(),
        "ui": DEFAULT_UI_SETTINGS.copy(),
        "command": DEFAULT_COMMAND_SETTINGS.copy(),
        "logging": DEFAULT_LOGGING_SETTINGS.copy(),
        "packet": DEFAULT_PACKET_SETTINGS.copy(),
        "ports": DEFAULT_PORTS_STATE.copy(),
        "manual_control": DEFAULT_MANUAL_CONTROL_STATE.copy(),
        "macro_list": DEFAULT_MACRO_LIST_STATE.copy(),
    }
