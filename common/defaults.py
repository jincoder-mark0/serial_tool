"""
기본 설정값 정의 모듈

애플리케이션의 초기화 및 설정 파일 복구에 사용되는 기본값들을 정의합니다.
SettingsManager의 하드코딩을 방지하고 설정값 관리를 중앙화합니다.
"""
from common.constants import (
    DEFAULT_LOG_MAX_LINES,
    DEFAULT_MACRO_INTERVAL_MS
)

# ==========================================
# Section Defaults
# ==========================================

# settings.* 정본 블록의 기본값 (S-027 — 과거 global 블록 기본값 유지)
DEFAULT_SETTINGS_BLOCK = {
    "theme": "dark",
    "language": "ko"
}

DEFAULT_UI_SETTINGS = {
    "max_log_lines": DEFAULT_LOG_MAX_LINES,
    # S-027: 폰트 키(proportional/fixed font family/size)는 죽은 키였다 —
    # 실사용은 settings.* 쪽(ConfigKeys.PROP_FONT_*)이므로 여기서 제거.
    # Window state placeholders
    "window_width": 1200,
    "window_height": 800,
    "window_x": None,
    "window_y": None,
    "splitter_state": None,
    "right_section_visible": True,
    "saved_right_section_width": None
}

DEFAULT_COMMAND_SETTINGS = {
    "prefix": "",
    "suffix": ""
}

DEFAULT_LOGGING_SETTINGS = {
    "log_dir": ""
}

DEFAULT_PACKET_SETTINGS = {
    "parser_type": 0, # Auto
    "delimiters": ["\\r\\n"],
    "packet_length": 64,
    "at_color_ok": True,
    "at_color_error": True,
    "at_color_urc": True,
    "at_color_prompt": True,
    "buffer_size": 100,
    "realtime": True,
    "autoscroll": True,
    # 체크섬 검증 (S-071). algorithm="none"이면 검증하지 않는다(기본값).
    # offset은 패킷 끝에서 체크섬 필드가 시작하는 위치를 음수로 센다 —
    # 대부분의 프로토콜이 체크섬을 말미에 두므로 끝 기준이 안정적이다.
    # exclude_leading/trailing은 계산 대상에서 제외할 앞/뒤 바이트 수다
    # (SOF 헤더 제외, 체크섬 필드 자신 제외 등).
    # 프레이밍 확장 (S-072). 길이 필드는 [LEN][PAYLOAD] 형태를 기본으로 잡는다.
    "length_field_offset": 0,
    "length_field_size": 1,
    "length_field_endian": "big",
    "length_includes_header": False,
    # 갭 기반 프레이밍의 유휴 임계(ms). Modbus RTU의 3.5문자 유휴가 9600bps에서
    # 약 4ms라 그보다 조금 큰 값을 기본으로 둔다.
    "gap_ms": 5,
    "checksum_algorithm": "none",
    "checksum_offset": -1,
    "checksum_exclude_leading": 0,
    "checksum_exclude_trailing": 0
}

DEFAULT_PORTS_STATE = {
    "tabs": [] # Tab state persistence
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
        "broadcast_enabled": False
    }
}

DEFAULT_MACRO_LIST_STATE = {
    "commands": [],
    "control_state": {
        "delay_ms": str(DEFAULT_MACRO_INTERVAL_MS),
        "max_runs": 0,
        "broadcast_enabled": False
    }
}

# ==========================================
# Full Fallback Configuration
# ==========================================
def create_fallback_settings() -> dict:
    """
    전체 기본 설정 딕셔너리를 생성하여 반환합니다.
    """
    return {
        "version": "1.3",
        "settings": DEFAULT_SETTINGS_BLOCK.copy(),
        "ui": DEFAULT_UI_SETTINGS.copy(),
        "command": DEFAULT_COMMAND_SETTINGS.copy(),
        "logging": DEFAULT_LOGGING_SETTINGS.copy(),
        "packet": DEFAULT_PACKET_SETTINGS.copy(),
        "ports": DEFAULT_PORTS_STATE.copy(),
        "manual_control": DEFAULT_MANUAL_CONTROL_STATE.copy(),
        "macro_list": DEFAULT_MACRO_LIST_STATE.copy()
    }