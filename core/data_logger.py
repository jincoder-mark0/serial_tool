"""
데이터 로거 모듈 (Data Logger)

시리얼 포트 등에서 수신된 원본(Raw) 바이트 데이터를 파일에 실시간으로 기록합니다.
시스템 동작 로그(Logger)와 구분되어, 순수한 통신 데이터를 저장하는 역할을 수행합니다.

## WHY
* 데이터 분석을 위해 수신된 원본 데이터를 파일로 저장해야 함
* UI 스레드 블로킹 없이 고속 데이터 저장이 필요함
* 포트별로 독립적인 파일 기록이 가능해야 함

## WHAT
* DataLogger: 단일 포트의 데이터를 파일에 기록 (Producer-Consumer 패턴)
* DataLoggerManager: 여러 포트의 로거를 관리하는 중앙 관리자

## HOW
* Queue를 사용하여 데이터 수신(Write)과 파일 저장(Disk I/O)을 분리
* 별도의 백그라운드 스레드에서 파일 쓰기 수행
* 바이너리 모드('wb')로 데이터 변형 없이 저장
"""
from typing import Optional, Dict
from queue import Queue, Empty
from threading import Thread
import os
from core.logger import logger

class DataLogger:
    """
    단일 포트의 실시간 데이터 로깅을 담당하는 클래스

    백그라운드 스레드에서 파일 쓰기를 수행하여 메인 스레드에 영향을 주지 않습니다.
    Queue를 버퍼로 사용하여 순간적인 I/O 지연 시에도 데이터 유실을 방지합니다.
    """

    def __init__(self):
        """DataLogger 초기화"""
        self._file = None
        self._queue: Queue = Queue()
        self._thread: Optional[Thread] = None
        self._is_logging = False
        self.filepath: str = ""

    @property
    def is_logging(self) -> bool:
        """현재 로깅 중인지 여부 반환"""
        return self._is_logging

    def start_logging(self, filepath: str) -> bool:
        """
        로깅을 시작합니다.

        Args:
            filepath: 저장할 파일 경로

        Returns:
            bool: 시작 성공 여부
        """
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            self._file = open(filepath, 'wb')  # 바이너리 쓰기 모드
            self.filepath = filepath
            self._is_logging = True

            # 백그라운드 스레드 시작
            self._thread = Thread(target=self._write_loop, daemon=True)
            self._thread.start()

            return True
        except Exception as e:
            logger.error(f"DataLogger start failed: {e}")
            return False

    def stop_logging(self) -> None:
        """로깅을 중단하고 파일을 닫습니다."""
        self._is_logging = False

        if self._thread and self._thread.is_alive():
            # 스레드가 큐를 비우고 종료될 때까지 대기
            self._thread.join(timeout=1.0)

        if self._file:
            try:
                self._file.flush()
                self._file.close()
            except Exception as e:
                logger.error(f"Error closing log file: {e}")
            finally:
                self._file = None

        self.filepath = ""

    def write(self, data: bytes) -> None:
        """
        데이터를 로깅 큐에 추가합니다.

        이 메서드는 Non-blocking이며 즉시 리턴됩니다.

        Args:
            data: 기록할 바이트 데이터
        """
        if self._is_logging:
            self._queue.put(data)

    def _write_loop(self) -> None:
        """
        백그라운드 스레드에서 실행되는 쓰기 루프

        Logic:
            - 큐에서 데이터를 꺼내 파일에 씀
            - 로깅 중단 요청이 있어도 큐에 남은 데이터는 모두 쓰고 종료
        """
        while self._is_logging or not self._queue.empty():
            try:
                # 0.1초 대기하며 데이터 확인
                data = self._queue.get(timeout=0.1)
                if self._file:
                    self._file.write(data)
                    # 실시간성을 위해 일정 주기마다 flush 할 수도 있음
                    # self._file.flush()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"DataLogger write error: {e}")
                # 치명적 오류 시 로깅 중단
                if not self._file or self._file.closed:
                    self._is_logging = False
                    break


class DataLoggerManager:
    """
    여러 포트의 DataLogger를 관리하는 매니저 클래스 (Singleton 사용 권장)
    """

    def __init__(self):
        """DataLoggerManager 초기화"""
        # Port Name -> DataLogger 인스턴스 매핑
        self._loggers: Dict[str, DataLogger] = {}

    def start_logging(self, port_name: str, filepath: str) -> bool:
        """
        특정 포트의 로깅을 시작합니다.

        Args:
            port_name: 포트 이름 (Key)
            filepath: 저장할 파일 경로

        Returns:
            bool: 성공 시 True
        """
        # 이미 로깅 중이면 중단 후 재시작
        if port_name in self._loggers:
            self.stop_logging(port_name)

        logger_instance = DataLogger()
        if logger_instance.start_logging(filepath):
            self._loggers[port_name] = logger_instance
            return True
        return False

    def stop_logging(self, port_name: str) -> None:
        """
        특정 포트의 로깅을 중단합니다.

        Args:
            port_name: 포트 이름
        """
        if port_name in self._loggers:
            self._loggers[port_name].stop_logging()
            del self._loggers[port_name]

    def stop_all(self) -> None:
        """모든 포트의 로깅을 중단합니다."""
        for port_name in list(self._loggers.keys()):
            self.stop_logging(port_name)

    def write(self, port_name: str, data: bytes) -> None:
        """
        특정 포트의 로거에 데이터를 씁니다.

        Args:
            port_name: 포트 이름
            data: 기록할 데이터
        """
        if port_name in self._loggers:
            self._loggers[port_name].write(data)

    def is_logging(self, port_name: str) -> bool:
        """
        특정 포트가 로깅 중인지 확인합니다.

        Args:
            port_name: 포트 이름

        Returns:
            bool: 로깅 중이면 True
        """
        return port_name in self._loggers and self._loggers[port_name].is_logging

    def get_filepath(self, port_name: str) -> str:
        """
        특정 포트의 로깅 파일 경로를 반환합니다.

        Args:
            port_name: 포트 이름

        Returns:
            str: 파일 경로, 로깅 중이 아니면 빈 문자열
        """
        if port_name in self._loggers:
            return self._loggers[port_name].filepath
        return ""


# 전역 인스턴스 (Singleton)
data_logger_manager = DataLoggerManager()
