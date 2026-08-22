"""
애플리케이션 전역 상수 정의 모듈

애플리케이션 전체에서 사용되는 상수와 기본 설정값을 정의합니다.

## WHY
* 하드코딩된 값을 한곳에서 관리하여 유지보수성 향상
* 설정값 변경 시 단일 지점 수정으로 전체 반영
* 타입 힌트로 타입 안전성 보장

## WHAT
* 시리얼 통신 파라미터 (Baudrate, Timeout, Chunk Size)
* 버퍼 및 성능 설정 (RingBuffer, Queue, Batch)
* UI 제한값 및 기본값 (Log Lines, Scan Interval)
* 타이밍 상수 (Worker Sleep, UI Refresh)
* 로그 색상 정의 및 ConfigKeys, EventTopics

## HOW
* 대문자 Snake Case로 상수 명명
* 타입 힌트로 타입 명시
* 논리적 그룹으로 섹션 구분
"""
from typing import List

# ==========================================
# Event Bus Topics (이벤트 토픽 상수)
# ==========================================
class EventTopics:
    """EventBus에서 사용하는 토픽 상수 클래스입니다."""

    # Port Events
    PORT_OPENED = "port.opened"
    PORT_CLOSED = "port.closed"
    PORT_ERROR = "port.error"
    PORT_DATA_RECEIVED = "port.data_received"
    PORT_DATA_SENT = "port.data_sent"
    PORT_PACKET_RECEIVED = "port.packet_received"

    # Macro Events
    MACRO_STARTED = "macro.started"
    MACRO_FINISHED = "macro.finished"
    MACRO_ERROR = "macro.error"

    # File Transfer Events
    FILE_PROGRESS = "file.progress"
    FILE_COMPLETED = "file.completed"
    FILE_ERROR = "file.error"

    # System Events
    SETTINGS_CHANGED = "system.settings_changed"


# ==========================================
# Configuration Keys (설정 키 상수)
# ==========================================
class ConfigKeys:
    """
    settings.json의 키 경로를 관리하는 상수 클래스입니다.
    CORE_SETTINGS_SCHEMA 구조와 일치해야 합니다.
    """

    THEME = "settings.theme"
    LANGUAGE = "settings.language"

    # Fonts (ThemeManager uses these)
    PROP_FONT_FAMILY = "settings.proportional_font_family"
    PROP_FONT_SIZE = "settings.proportional_font_size"
    FIXED_FONT_FAMILY = "settings.fixed_font_family"
    FIXED_FONT_SIZE = "settings.fixed_font_size"

    # Port Defaults
    PORT_BAUDRATE = "settings.port_baudrate"
    PORT_NEWLINE = "settings.port_newline"
    PORT_LOCAL_ECHO = "settings.port_local_echo"
    PORT_SCAN_INTERVAL = "settings.port_scan_interval_ms"

    # UI (화면 표시 관련)
    RX_MAX_LINES = "settings.max_log_lines"

    # Command (Command 형식)
    COMMAND_PREFIX = "settings.command_prefix"
    COMMAND_SUFFIX = "settings.command_suffix"

    # UI State (윈도우 상태 저장)
    WINDOW_WIDTH = "ui.window_width"
    WINDOW_HEIGHT = "ui.window_height"
    WINDOW_X = "ui.window_x"
    WINDOW_Y = "ui.window_y"
    SPLITTER_STATE = "ui.splitter_state"
    RIGHT_PANEL_VISIBLE = "ui.right_section_visible"
    SAVED_RIGHT_WIDTH = "ui.saved_right_section_width"

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

# 쓰기(write) 완료 확인 타임아웃(초) — S-039
# write_timeout=0은 pyserial 3.5의 Windows 구현(serialwin32.py)에서 쓰기 완료를
# 확인하지 않은 채(GetOverlappedResult 생략) 성공을 보고해 데이터 유실을 놓칠 수 있다.
# 0이 아닌 값을 주면 완료를 확인하고, 실패 시 SerialTimeoutException을 올려
# 상위(ConnectionWorker)가 유실을 인지하게 한다.
# 1.0초는 잠정값: 너무 작으면 저속 보드레이트/큰 청크에서 정상 전송도 타임아웃으로
# 오판하고, 너무 크면 close() 시 드레인·종료가 그만큼 지연된다. ConnectionWorker는
# 별도 QThread이므로 이 지연이 UI를 멈추지는 않는다. 실제 시리얼 타이밍(저속
# 보드레이트, 대용량 청크)에서의 적정값 재검증은 S-010(가상 포트)/실기기 대상.
WRITE_TIMEOUT_S: float = 1.0

# DataLogger.stop_logging() 드레인 상한(초) — S-045
# stop_logging()은 배경 스레드가 큐를 비울 때까지 기다린 뒤 파일을 닫는다.
# 상한 없이 기다리면 디스크 지연 시 종료가 무기한 멈출 수 있고, 상한 없이
# 곧바로 파일을 닫으면 아직 쓰이지 않은 잔여 큐가 조용히 사라진다(WRITE_TIMEOUT_S와
# 동일한 문제의식). 1차 대기(DRAIN)로 정상 드레인 기회를 주고, 그래도 못 끝내면
# FORCE로 루프를 강제 종료 요청한 뒤 남은 개수를 경고로 표면화한다.
DATA_LOGGER_STOP_DRAIN_TIMEOUT_S: float = 1.0
DATA_LOGGER_STOP_FORCE_TIMEOUT_S: float = 0.5

# 더미 포트 예약명 (S-033) — 실기기 없이 송수신 경로를 디버깅하기 위한 루프백 에코 포트.
# 실제 장치명(COMx 등)과 충돌하지 않는 이름으로 고정.
LOOPBACK_PORT_NAME: str = "LOOPBACK"

# ==========================================
# Buffer & Performance Constants
# ==========================================

# RingBuffer 기본 크기 (512KB)
RING_BUFFER_SIZE: int = 512 * 1024

# TX Queue 최대 청크 개수
TX_QUEUE_SIZE: int = 128

# UI 업데이트 Batch 설정 (SerialWorker → UI)
BATCH_SIZE_THRESHOLD: int = 8192  # 이 크기가 넘으면 즉시 전송 (bytes)
BATCH_TIMEOUT_MS: int = 50        # 이 시간이 지나면 크기가 작아도 전송 (ms)

# PacketParser(AT/Delimiter/FixedLength) 내부 버퍼 상한 기본값 (S-064)
# BATCH_SIZE_THRESHOLD(=한 번의 emit 최대 크기)의 배수로 정의한다: 완결 패킷을 모두
# 분리한 뒤 남는 미완결 조각이 배치 한 번 분량만큼 더 누적돼도 곧바로 잘려나가지
# 않도록 여유를 둔다. 파서 자체는 "먼저 분리, 남는 조각만 상한 적용" 순서로
# 동작하므로 이 값은 정상적인 완결 패킷 유실을 막는 안전장치가 아니라, 구분자가
# 오지 않는 미완결 조각(폭주/기형 스트림)에 대한 메모리 보호 목적이다.
PARSER_MAX_BUFFER_SIZE: int = BATCH_SIZE_THRESHOLD * 2  # 16384

# ==========================================
# Performance & Timings
# ==========================================
WORKER_IDLE_WAIT_MS: int = 1      # 데이터 없을 때 대기 시간 (CPU 방어)
WORKER_BUSY_WAIT_US: int = 100    # 데이터 처리 중 짧은 대기 시간
UI_REFRESH_INTERVAL_MS: int = 30  # 로그 뷰 갱신 주기 (약 33 FPS)
# presenter/data_handler.py(RX 로그 뷰)와 presenter/packet_presenter.py(패킷 뷰, S-061)가
# 동일한 "즉시 반영 대신 짧은 주기로 모아서 반영" 스로틀 개념을 공유하므로 같은 상수를
# 재사용한다 — 실측(tasks/S-061-packet-view-throttle.md "측정 결과·판정" 절)으로
# 병목이 확인된 뒤 도입. 별도 상수로 분리할 근거(서로 다른 튜닝이 필요해질 때)가
# 생기면 그때 나눈다.

# ==========================================
# UI Limits & Defaults
# ==========================================
DEFAULT_LOG_MAX_LINES: int = 2000
TRIM_CHUNK_RATIO: float = 0.2  # 20%
MAX_PACKET_SIZE: int = 4096
MIN_SCAN_INTERVAL_MS: int = 1000
MAX_SCAN_INTERVAL_MS: int = 60000
DEFAULT_MACRO_INTERVAL_MS: int = 1000
MIN_MACRO_DELAY_MS: int = 1
MIN_AUTO_TX_INTERVAL_MS: int = 50  # 과도한 폴링으로 인한 TX 큐 포화 방지 (S-006)
MAX_COMMAND_HISTORY_SIZE: int = 50    # 수동 명령 History 최대 크기

# ==========================================
# Colors (For Text Logs)
# ==========================================
LOG_COLOR_DARK_TIMESTAMP: str = "#9E9E9E"
LOG_COLOR_DARK_INFO: str = "#2196F3"
LOG_COLOR_DARK_ERROR: str = "#FF6B6B"  # 다크/드라큘라 배경에서 WCAG 4.5:1 확보 (S-022, color_rules.json과 동일 값 유지)
LOG_COLOR_DARK_WARN: str = "#D4A017"
LOG_COLOR_DARK_PROMPT: str = '#00BCD4'
LOG_COLOR_DARK_SUCCESS: str = "#4CAF50"

LOG_COLOR_LIGHT_TIMESTAMP: str = "#808080"
LOG_COLOR_LIGHT_INFO: str = "#0000FF"
LOG_COLOR_LIGHT_ERROR: str = "#CC0000"
LOG_COLOR_LIGHT_WARN: str = "#D4A017"
LOG_COLOR_LIGHT_PROMPT: str = '#008B8B'
LOG_COLOR_LIGHT_SUCCESS: str = "#008000"

# ==========================================
# Layout & Sizing Constants (S-025: 위젯 간 여백/크기 상수화)
# ==========================================
LAYOUT_MARGIN_NONE: int = 0      # 여백 없음 (내부 컨테이너 레이아웃 기본값)
LAYOUT_MARGIN_DEFAULT: int = 5   # 일반 패널 외곽 여백
LAYOUT_MARGIN_DIALOG: int = 15   # 다이얼로그 외곽 여백 (여유 있는 룩)
LAYOUT_SPACING_TIGHT: int = 2    # 툴바 등 촘촘한 배치 간격
LAYOUT_SPACING_DEFAULT: int = 5  # 일반 위젯 간 기본 간격
ICON_BUTTON_SIZE: int = 30       # 아이콘형 소형 버튼 한 변 길이 (정사각형)

# 섹션 제목 → 내용 간격 (S-035). QGroupBox 타이틀 여백(~20px)과의 10배 차이를 좁히기 위해
# section-title 계열의 margin-bottom을 이 값으로 통일한다.
# QSS(resources/themes/common.qss)는 이 상수를 읽지 못하므로 값이 바뀌면 양쪽을 함께 수정할 것.
LAYOUT_SPACING_TITLE: int = 8
# 체크박스 등 옵션 항목 간 그루핑 간격 (S-035). 체크박스 내부 인디케이터-라벨 간격(QSS spacing 5px,
# LAYOUT_SPACING_DEFAULT와 동일)보다 커야 "항목 간 구분 > 항목 내부 구성"이 성립해 소속이 헷갈리지 않는다.
LAYOUT_SPACING_GROUP: int = 10

# ==========================================
# Timing Constants (S-047: 매직 넘버 상수화)
# ==========================================
# 로그 뷰 검색 필터 디바운스 (view/custom_qt/smart_list_view.py)
# 정규식 입력마다 즉시 필터링하면 복잡한 패턴에서 UI가 멈출 수 있어 입력 정지 후 반영한다.
FILTER_DEBOUNCE_MS: int = 300

# 상태바(포트/속도/버퍼) 주기 갱신 간격 (presenter/lifecycle_manager.py)
# 값이 DEFAULT_MACRO_INTERVAL_MS(1000)와 같지만 의미가 다르므로(매크로 반복 vs UI 갱신 주기)
# 별도 상수로 관리한다 — 한쪽이 바뀌어도 다른 쪽에 영향이 없어야 한다.
STATUS_BAR_UPDATE_INTERVAL_MS: int = 1000

# 파일 전송 backpressure 대기 (model/file_transfer_service.py)
# TX 큐가 임계값을 넘거나(전송 중) 완료 후 큐가 비워지길 기다릴 때 사용하는 폴링 간격.
FILE_TRANSFER_BACKPRESSURE_WAIT_S: float = 0.01

# ==========================================
# Dialog & Widget Fixed Sizes (S-047: 매직 넘버 상수화)
# 값이 같아도 위젯/용도가 다르면 재사용하지 않고 별도 상수로 관리한다.
# ==========================================
# About 다이얼로그 (view/dialogs/about_dialog.py)
DIALOG_SIZE_ABOUT_WIDTH: int = 400
DIALOG_SIZE_ABOUT_HEIGHT: int = 300
DIALOG_SPACING_ABOUT: int = 20
CONTROL_WIDTH_ABOUT_CLOSE_BTN: int = 100

# 파일 전송 다이얼로그 (view/dialogs/file_transfer_dialog.py)
DIALOG_SIZE_FILE_TRANSFER_WIDTH: int = 450
DIALOG_SIZE_FILE_TRANSFER_HEIGHT: int = 250
CONTROL_WIDTH_FILE_TRANSFER_SELECT_BTN: int = 100

# 폰트 설정 다이얼로그 (view/dialogs/font_settings_dialog.py)
DIALOG_SPACING_FONT_SETTINGS: int = 15

# 포트 설정 위젯의 Serial 콤보박스 고정 폭 (view/widgets/port_settings.py)
CONTROL_WIDTH_PORT_DATA_COMBO: int = 40
CONTROL_WIDTH_PORT_PARITY_COMBO: int = 40
CONTROL_WIDTH_PORT_STOP_COMBO: int = 45

# 메인 상태바 (view/sections/main_status_bar.py)
CONTROL_WIDTH_MAIN_STATUS_PORT_LBL: int = 100
CONTROL_WIDTH_MAIN_STATUS_BUFFER_BAR: int = 100

# 파일 전송 진행률 위젯 (view/widgets/file_progress.py)
CONTROL_WIDTH_FILE_PROGRESS_CANCEL_BTN: int = 60

# 데이터 로그 위젯의 개행 모드 콤보박스 (view/widgets/data_log.py)
CONTROL_WIDTH_DATA_LOG_NEWLINE_COMBO: int = 100

# 우측 섹션 최소 폭 (view/sections/main_right_section.py)
# 매크로 테이블의 7개 컬럼 중 6개가 ResizeToContents라 내용보다 좁아지지 않는다.
# 이 폭보다 좁아지면 매크로 목록에 가로 스크롤이 생겨 편집이 불편해진다.
# 근거(실측, 2026-08-22): 4테마 x 2언어 전 조합에서 임계값이 동일하게 나왔다 —
# ko 566px / en 575px. 최댓값 575에 여유를 더해 잡는다. 컬럼 구성이나 헤더 문구가
# 바뀌면 이 값도 다시 재야 한다(tests/test_right_section_min_width.py가 강제).
CONTROL_MIN_WIDTH_RIGHT_SECTION: int = 580

# ==========================================
# System & File Constants
# ==========================================
PLATFORM_WINDOWS = "Windows"
PLATFORM_LINUX = "Linux"
PLATFORM_MACOS = "Darwin"

FILE_FILTER_JSON = "JSON Files (*.json);;All Files (*)"
FILE_FILTER_LOG = "Binary Files (*.bin);;All Files (*)"
FILE_FILTER_ALL = "All Files (*)"

# Default Fonts
FONT_FAMILY_SEGOE = "Segoe UI"
FONT_FAMILY_CONSOLAS = "Consolas"
FONT_FAMILY_UBUNTU = "Ubuntu"
FONT_FAMILY_MONOSPACE = "Monospace"
FONT_FAMILY_MENLO = "Menlo"

# 언어 콤보 폴백 표시명 (S-036) - preferences_dialog.py에서 언어 리소스 JSON 로드가
# 완전히 실패했을 때만 쓰는 최후의 표시명이라 language_manager.get_text()를 거칠 수
# 없다(그 자체가 JSON 의존). 값을 여기 상수로 빼서 tests/test_ui_guidelines.py의
# 한글 리터럴 검사(view/·presenter/ 스캔) 대상 밖에 둔다 - endonym이라 언어 키로도
# 옮기지 않는다("English"가 항상 "English"인 것과 같은 이유).
LANGUAGE_DISPLAY_NAME_KOREAN = "한국어"
