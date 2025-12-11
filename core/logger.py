import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class Logger:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Logger를 초기화하고 핸들러를 설정합니다."""
        if self._initialized:
            return

        self.logger = logging.getLogger("SerialTool")
        self.logger.setLevel(logging.DEBUG)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

        # Default file handler setup (Fallback)
        # configure() 메서드를 통해 ResourcePath 경로로 재설정 가능
        self._setup_file_handler("logs")

        self._initialized = True

    def configure(self, resource_path):
        """ResourcePath 사용하여 로거를 재설정합니다."""
        if resource_path and hasattr(resource_path, 'logs_dir'):
            self._setup_file_handler(str(resource_path.logs_dir))

    def _setup_file_handler(self, log_dir_path):
        """파일 핸들러를 설정합니다."""
        if not os.path.exists(log_dir_path):
            os.makedirs(log_dir_path, exist_ok=True)

        log_file = os.path.join(log_dir_path, f"serial_tool_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        # 기존 파일 핸들러 제거 후 추가 (중복 방지)
        for h in self.logger.handlers[:]:
            if isinstance(h, RotatingFileHandler):
                self.logger.removeHandler(h)

        self.logger.addHandler(file_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

# Global logger instance
logger = Logger()
