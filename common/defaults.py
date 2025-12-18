"""
기본 설정값 정의 모듈

애플리케이션의 초기화 및 설정 파일 복구에 사용되는 기본값들을 정의합니다.
SettingsManager의 하드코딩을 방지하고 설정값 관리를 중앙화합니다.
"""
from common.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_LOG_MAX_LINES,
    DEFAULT_MACRO_DELAY_MS
)

# ==========================================
# Section Defaults
# ==========================================

DEFAULT_GLOBAL_SETTINGS = {
    "theme": "dark",
    "language": "ko"
}

DEFAULT_UI_SETTINGS = {
    "max_log_lines": DEFAULT_LOG_MAX_LINES,
    "proportional_font_family": "Segoe UI",
    "proportional_font_size": 9,
    "fixed_font_family": "Consolas",
    "fixed_font_size": 9,
    # Window state placeholders
    "window_width": 1200,
    "window_height": 800,
    "window_x": None,
    "window_y": None,
    "splitter_state": None,
    "right_section_visible": True,
    "saved_right_section_width": None
}

DEFAULT_SERIAL_SETTINGS = {
    "baudrate": DEFAULT_BAUDRATE,
    "parity": "N",
    "bytesize": 8,
    "stopbits": 1,
    "flowctrl": "None",
    "newline": "LF",
    "local_echo_enabled": False,
    "scan_interval_ms": 1000
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
    "autoscroll": True
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
        "delay_ms": str(DEFAULT_MACRO_DELAY_MS),
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
        "version": "1.0",
        "global": DEFAULT_GLOBAL_SETTINGS.copy(),
        "ui": DEFAULT_UI_SETTINGS.copy(),
        "serial": DEFAULT_SERIAL_SETTINGS.copy(),
        "command": DEFAULT_COMMAND_SETTINGS.copy(),
        "logging": DEFAULT_LOGGING_SETTINGS.copy(),
        "packet": DEFAULT_PACKET_SETTINGS.copy(),
        "ports": DEFAULT_PORTS_STATE.copy(),
        "manual_control": DEFAULT_MANUAL_CONTROL_STATE.copy(),
        "macro_list": DEFAULT_MACRO_LIST_STATE.copy()
    }