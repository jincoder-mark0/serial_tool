"""
애플리케이션 전역 상수 정의 모듈입니다.

이 모듈은 애플리케이션 전체에서 사용되는 상수, 기본 설정값,
통신 파라미터 등을 정의합니다.

## WHY
* 매직 넘버(Magic Number)와 하드코딩된 문자열을 제거하여 유지보수성을 높입니다.
* 설정값을 한곳에서 관리하여 변경이 용이합니다.
"""

from typing import List

# ==========================================
# Serial Communication Constants
# ==========================================

# 지원하는 보드레이트 목록
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

# TX 큐 최대 청크 개수
TX_QUEUE_SIZE: int = 128

# UI 업데이트 배치 설정 (SerialWorker -> UI)
# 고속 통신 시 UI 프리징을 방지하기 위해 데이터를 모아서 보냅니다.
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
MAX_CMD_HISTORY_SIZE: int = 50    # 수동 명령 히스토리 최대 크기

# ==========================================
# Colors (For Text Logs)
# ==========================================
LOG_COLOR_TIMESTAMP: str = "#9E9E9E"
LOG_COLOR_INFO: str = "gray"
LOG_COLOR_ERROR: str = "#F44336"
LOG_COLOR_WARN: str = "#FF9800"
LOG_COLOR_PROMPT: str = '#00BCD4'
LOG_COLOR_SUCCESS: str = "#4CAF50"