"""
Core 및 유틸리티 기능 정밀 테스트

- DataLogger 동작 검증
- ExpectMatcher 패턴 매칭 검증
- ParserType 상수 일관성 확인

pytest tests/test_core_refinement.py -v
"""
import sys
import os
import pytest
import shutil
from pathlib import Path
import time

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_logger import DataLogger, DataLoggerManager
from model.packet_parser import ExpectMatcher, ParserType

# --- DataLogger Tests ---

@pytest.fixture
def temp_log_dir():
    """임시 로그 디렉토리 생성 및 정리"""
    path = Path("tests/temp_logs")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    if path.exists():
        shutil.rmtree(path)

def test_data_logger_lifecycle(temp_log_dir):
    """DataLogger 시작, 쓰기, 중지 라이프사이클 테스트"""
    logger = DataLogger()
    log_file = temp_log_dir / "test.bin"

    # 1. Start Logging
    assert logger.start_logging(str(log_file)) is True
    assert logger.is_logging is True

    # 2. Write Data
    test_data = b"Hello World"
    logger.write(test_data)

    # Queue 처리를 위해 잠시 대기
    time.sleep(0.1)

    # 3. Stop Logging
    logger.stop_logging()
    assert logger.is_logging is False

    # 4. Verify File Content
    assert log_file.exists()
    with open(log_file, "rb") as f:
        content = f.read()
        assert content == test_data

def test_data_logger_manager(temp_log_dir):
    """DataLoggerManager를 통한 멀티 포트 관리 테스트"""
    manager = DataLoggerManager()
    port = "COM_TEST"
    log_file = temp_log_dir / "manager_test.bin"

    # Start
    assert manager.start_logging(port, str(log_file)) is True
    assert manager.is_logging(port) is True

    # Write
    manager.write(port, b"Manager Data")
    time.sleep(0.1)

    # Stop
    manager.stop_logging(port)
    assert manager.is_logging(port) is False

    # Verify
    with open(log_file, "rb") as f:
        assert f.read() == b"Manager Data"

# --- ExpectMatcher Tests ---

def test_expect_matcher_literal():
    """문자열 리터럴 매칭 테스트"""
    matcher = ExpectMatcher("OK", is_regex=False)

    assert matcher.match(b"User Input") is False
    assert matcher.match(b"Command") is False
    assert matcher.match(b"OK") is True

    # Reset 후 재사용
    matcher.reset()
    assert matcher.match(b"Fail") is False

def test_expect_matcher_regex():
    """정규식 매칭 테스트"""
    # 숫자 3자리를 기다리는 정규식
    matcher = ExpectMatcher(r"\d{3}", is_regex=True)

    assert matcher.match(b"abc") is False
    assert matcher.match(b"12") is False
    assert matcher.match(b"3") is True # 누적되어 abc123 (Match)

    matcher.reset()
    assert matcher.match(b"456") is True

def test_expect_matcher_buffer_limit():
    """버퍼 크기 제한 동작 테스트"""
    matcher = ExpectMatcher("Target", max_buffer_size=10)

    # 버퍼를 가득 채움 (10바이트 초과)
    matcher.match(b"1234567890") # 10 bytes
    matcher.match(b"ABCDE")      # 5 bytes -> 앞의 12345는 사라짐

    # 전체가 "1234567890ABCDE" 였다면 "Target"이 없으므로 False
    # 이제 "Target"을 보내서 매칭 확인
    assert matcher.match(b"Target") is True

# --- ParserType Tests ---

def test_parser_type_constants():
    """ParserType 상수 유효성 검사"""
    assert ParserType.RAW == "Raw"
    assert ParserType.AT == "AT"
    assert ParserType.DELIMITER == "Delimiter"
    assert ParserType.FIXED_LENGTH == "FixedLength"

if __name__ == "__main__":
    pytest.main([__file__])
