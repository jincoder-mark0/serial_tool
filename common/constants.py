"""
애플리케이션 전역 상수 정의 모듈

애플리케이션 전체에서 사용되는 상수와 기본 설정값을 정의합니다.

## WHY
* 매직 넘버(Magic Number) 제거로 코드 가독성 향상
* 하드코딩된 값을 한곳에서 관리하여 유지보수성 향상
* 설정값 변경 시 단일 지점 수정으로 전체 반영
* 타입 힌트로 타입 안전성 보장

## WHAT
* 시리얼 통신 파라미터 (Baudrate, Timeout, Chunk Size)
* 버퍼 및 성능 설정 (RingBuffer, Queue, Batch)
* UI 제한값 및 기본값 (Log Lines, Scan Interval)
* 타이밍 상수 (Worker Sleep, UI Refresh)
* 로그 색상 정의
* [New] ConfigKeys: 설정 키 상수 모음

## HOW
* 대문자 Snake Case로 상수 명명
* 타입 힌트로 타입 명시
* 주석으로 단위 및 의미 설명
* 논리적 그룹으로 섹션 구분
"""

from typing import List

# ==========================================
# Configuration Keys (설정 키 상수)
# ==========================================
class ConfigKeys:
    """settings.json의 키 경로를 관리하는 상수 클래스입니다."""

    # Global / Settings
    THEME = "settings.theme"
    LANGUAGE = "settings.language"
    FONT_SIZE = "settings.proportional_font_size"
    RX_MAX_LINES = "settings.rx_max_lines"
    COMMAND_PREFIX = "settings.command_prefix"
    COMMAND_SUFFIX = "settings.command_suffix"

    # Port Defaults
    PORT_BAUDRATE = "settings.port_baudrate"
    PORT_NEWLINE = "settings.port_newline"
    PORT_LOCAL_ECHO = "settings.port_local_echo"
    PORT_SCAN_INTERVAL = "settings.port_scan_interval"

    # UI State
    WINDOW_WIDTH = "ui.window_width"
    WINDOW_HEIGHT = "ui.window_height"
    WINDOW_X = "ui.window_x"
    WINDOW_Y = "ui.window_y"
    SPLITTER_STATE = "ui.splitter_state"
    RIGHT_PANEL_VISIBLE = "settings.right_section_visible"

    # Fonts (ThemeManager uses these)
    PROP_FONT_FAMILY = "ui.proportional_font_family"
    PROP_FONT_SIZE = "ui.proportional_font_size"
    FIXED_FONT_FAMILY = "ui.fixed_font_family"
    FIXED_FONT_SIZE = "ui.fixed_font_size"

    # Packet Inspector
    PACKET_PARSER_TYPE = "packet.parser_type"
    PACKET_DELIMITERS = "packet.delimiters"
    PACKET_LENGTH = "packet.packet_length"
    AT_COLOR_OK = "packet.at_color_ok"
    AT_COLOR_ERROR = "packet.at_color_error"
    AT_COLOR_URC = "packet.at_color_urc"
    AT_COLOR_PROMPT = "packet.at_color_prompt"

    # Inspector Options
    PACKET_BUFFER_SIZE = "packet.buffer_size"
    PACKET_REALTIME = "packet.realtime"
    PACKET_AUTOSCROLL = "packet.autoscroll"

    # Logging
    LOG_PATH = "logging.path"

    # Persistence (State Saving)
    MANUAL_CONTROL_STATE = "manual_control"
    PORTS_TABS_STATE = "ports.tabs"
    MACRO_COMMANDS = "macro_list.commands"
    MACRO_CONTROL_STATE = "macro_list.control_state"


# ==========================================
# Serial Communication Constants
# ==========================================

# 지원하는 Baudrate 목록
VALID_BAUDRATES: List[int] = [
    50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
    9600, 14400, 19200, 38400, 57600, 115200, 128000, 230400, 256000,
    460800, 921600, 1000000, 1500000, 2000000, 3000000, 4000000
]

# 기본 통신 설정
DEFAULT_BAUDRATE: int = 115200
DEFAULT_PORT_TIMEOUT: float = 0.0  # Non-blocking I/O
DEFAULT_READ_CHUNK_SIZE: int = 4096  # 한 번에 읽을 바이트 수

# ==========================================
# Buffer & Performance Constants
# ==========================================

# RingBuffer 기본 크기 (512KB)
RING_BUFFER_SIZE: int = 512 * 1024

# TX Queue 최대 청크 개수
TX_QUEUE_SIZE: int = 128

# UI 업데이트 Batch 설정 (SerialWorker → UI)
# 고속 통신 시 UI 프리징 방지를 위해 데이터를 모아서 전송
BATCH_SIZE_THRESHOLD: int = 1024  # 이 크기가 넘으면 즉시 전송 (bytes)
BATCH_TIMEOUT_MS: int = 50        # 이 시간이 지나면 크기가 작아도 전송 (ms)

# ==========================================
# UI Constants
# ==========================================

# 로그 뷰 최대 라인 수 (기본값)
DEFAULT_LOG_MAX_LINES: int = 2000

# 로그 삭제 청크 크기 (Trim 시 제거할 비율)
TRIM_CHUNK_RATIO: float = 0.2  # 20%

# ==========================================
# Performance & Timings
# ==========================================
WORKER_IDLE_WAIT_MS: int = 1      # 데이터 없을 때 대기 시간 (CPU 방어)
WORKER_BUSY_WAIT_US: int = 100    # 데이터 처리 중 짧은 대기 시간
UI_REFRESH_INTERVAL_MS: int = 50  # 로그 뷰 갱신 주기

# ==========================================
# UI Limits & Defaults
# ==========================================
MAX_PACKET_SIZE: int = 4096
MIN_SCAN_INTERVAL_MS: int = 1000
MAX_SCAN_INTERVAL_MS: int = 60000
DEFAULT_MACRO_DELAY_MS: int = 1000
MAX_COMMAND_HISTORY_SIZE: int = 50    # 수동 명령 히스토리 최대 크기

# ==========================================
# Colors (For Text Logs)
# ==========================================
LOG_COLOR_TIMESTAMP: str = "#9E9E9E"
LOG_COLOR_INFO: str = "gray"
LOG_COLOR_ERROR: str = "#F44336"
LOG_COLOR_WARN: str = "#FF9800"
LOG_COLOR_PROMPT: str = '#00BCD4'
LOG_COLOR_SUCCESS: str = "#4CAF50"
