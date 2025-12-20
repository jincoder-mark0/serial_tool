"""
로거 모듈

애플리케이션 전역 로깅 시스템을 제공합니다.

## WHY
* 디버깅 및 문제 해결을 위한 로그 기록
* 콘솔과 파일 동시 출력으로 개발/운영 환경 지원
* 로그 파일 자동 로테이션으로 디스크 공간 관리
* 싱글톤 패턴으로 전역 일관성 보장

## WHAT
* 콘솔 및 파일 핸들러 제공
* 로그 레벨별 메서드 (debug, info, warning, error, critical)
* 날짜별 로그 파일 생성
* 파일 크기 기반 로테이션 (10MB, 최대 5개 백업)
* 동적 로그 디렉토리 설정

## HOW
* Python logging 모듈 활용
* RotatingFileHandler로 자동 로테이션
* 싱글톤 패턴으로 전역 인스턴스 제공
* ResourcePath를 통한 동적 경로 설정
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class Logger:
    """
    애플리케이션 전역 로거 클래스

    싱글톤 패턴으로 구현되어 애플리케이션 전체에서 동일한 로거 인스턴스를 사용합니다.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        """싱글톤 인스턴스 생성"""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Logger를 초기화하고 핸들러를 설정합니다

        Logic:
            - 중복 초기화 방지 (_initialized 플래그)
            - 콘솔 핸들러 설정 (INFO 레벨)
            - 기본 파일 핸들러 설정 (DEBUG 레벨)
            - 포매터 적용 (타임스탬프, 로거명, 레벨, 메시지)
        """
        if self._initialized:
            return

        self.logger = logging.getLogger("SerialTool")
        self.logger.setLevel(logging.DEBUG)

        # Console Handler (개발 중 실시간 확인용)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter (통일된 로그 형식)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

        # Default file handler setup (Fallback)
        # configure() 메서드를 통해 ResourcePath 경로로 재설정 가능
        self._setup_file_handler("logs")

        self._initialized = True

    def configure(self, resource_path):
        """
        ResourcePath 사용하여 로거를 재설정합니다

        Args:
            resource_path: ResourcePath 인스턴스 (logs_dir 속성 필요)
        """
        if resource_path and hasattr(resource_path, 'logs_dir'):
            self._setup_file_handler(str(resource_path.logs_dir))

    def _setup_file_handler(self, log_dir_path):
        """
        파일 핸들러를 설정합니다

        Logic:
            - 로그 디렉토리 생성 (없으면)
            - 날짜별 로그 파일명 생성 (serial_tool_YYYYMMDD.log)
            - RotatingFileHandler 생성 (10MB, 5개 백업)

        Args:
            log_dir_path: 로그 파일을 저장할 디렉토리 경로
        """
        # 로그 디렉토리 생성
        if not os.path.exists(log_dir_path):
            os.makedirs(log_dir_path, exist_ok=True)

        # 날짜별 로그 파일명
        log_file = os.path.join(log_dir_path, f"serial_tool_{datetime.now().strftime('%Y%m%d')}.log")

        # RotatingFileHandler 설정
        # maxBytes: 10MB, backupCount: 5개 백업 파일 유지
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))

        for handler in self.logger.handlers[:]:
            if isinstance(handler, RotatingFileHandler):
                self.logger.removeHandler(handler)

        self.logger.addHandler(file_handler)

    def debug(self, message):
        """DEBUG 레벨 로그 기록"""
        self.logger.debug(message, stacklevel=2)

    def info(self, message):
        """INFO 레벨 로그 기록"""
        self.logger.info(message, stacklevel=2)

    def warning(self, message):
        """WARNING 레벨 로그 기록"""
        self.logger.warning(message, stacklevel=2)

    def error(self, message):
        """ERROR 레벨 로그 기록"""
        self.logger.error(message, stacklevel=2)

    def critical(self, message):
        """CRITICAL 레벨 로그 기록"""
        self.logger.critical(message, stacklevel=2)

# Global logger instance
logger = Logger()
