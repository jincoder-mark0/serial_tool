"""
데이터 로거 모듈 (Data Logger)

수신된 원본 바이트 데이터를 파일에 실시간으로 기록합니다.
백그라운드 스레드에서 비동기로 처리하여 UI에 영향을 주지 않습니다.

## WHY
* 데이터 누락 없이 수신 데이터를 기록해야 함
* UI 스레드 블로킹 방지 필요
* 포트별 독립적인 로깅 지원 필요

## WHAT
* DataLogger: 단일 포트 로깅 담당
* DataLoggerManager: 여러 포트의 로깅 관리

## HOW
* Queue와 백그라운드 스레드로 비동기 파일 쓰기
* 바이너리 모드('wb')로 원본 bytes 그대로 저장
"""
from typing import Optional, Dict
from queue import Queue, Empty
from threading import Thread
import os
from core.logger import logger

class DataLogger:
    """
    단일 포트의 실시간 로깅를 담당합니다.

    백그라운드 스레드에서 파일 쓰기를 수행하여 UI에 영향을 주지 않습니다.
    Queue를 사용하여 데이터 누락을 방지합니다.

    Attributes:
        filepath (str): 로깅 파일 경로
        is_logging (bool): 로깅 중 여부
    """

    def __init__(self):
        """DataLogger를 초기화합니다."""
        self._file = None
        self._queue: Queue = Queue()
        self._thread: Optional[Thread] = None
        self._running = False
        self.filepath: str = ""

    @property
    def is_logging(self) -> bool:
        """로깅 중 여부를 반환합니다."""
        return self._running

    def start(self, filepath: str) -> bool:
        """
        로깅를 시작합니다.

        Args:
            filepath: 저장할 파일 경로

        Returns:
            bool: 성공 시 True, 실패 시 False
        """
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            self._file = open(filepath, 'wb')  # 바이너리 모드
            self.filepath = filepath
            self._running = True

            # 백그라운드 스레드 시작
            self._thread = Thread(target=self._write_loop, daemon=True)
            self._thread.start()

            return True
        except Exception as e:
            logger.error(f"DataLogger start failed: {e}")
            return False

    def stop(self) -> None:
        """로깅를 중단하고 파일을 닫습니다."""
        self._running = False

        if self._thread and self._thread.is_alive():
            # self._thread.join(timeout=2.0)
            self._thread.join() # UI 스레드가 잠시 멈추는 것이 우려됨.

        if self._file:
            self._file.close()
            self._file = None

        self.filepath = ""

    def record(self, data: bytes) -> None:
        """
        데이터를 로깅 큐에 추가합니다.

        논블로킹으로 동작하여 UI에 영향을 주지 않습니다.

        Args:
            data: 로깅할 바이트 데이터
        """
        if self._running:
            self._queue.put(data)

    def _write_loop(self) -> None:
        """백그라운드 스레드에서 파일에 데이터를 씁니다."""
        while self._running or not self._queue.empty():
            try:
                data = self._queue.get(timeout=0.1)
                if self._file:
                    self._file.write(data)
                    self._file.flush()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"DataLogger write error: {e}")


class DataLoggerManager:
    """
    여러 포트의 로깅를 관리합니다.

    포트별로 별도의 DataLogger 인스턴스를 생성하고 관리합니다.
    """

    def __init__(self):
        """DataLoggerManager를 초기화합니다."""
        self._recorders: Dict[str, DataLogger] = {}

    def start_logging(self, port_name: str, filepath: str) -> bool:
        """
        특정 포트의 로깅를 시작합니다.

        Args:
            port_name: 포트 이름 (예: "COM1")
            filepath: 저장할 파일 경로

        Returns:
            bool: 성공 시 True
        """
        # 이미 로깅 중이면 중단
        if port_name in self._recorders:
            self.stop_logging(port_name)

        recorder = DataLogger()
        if recorder.start(filepath):
            self._recorders[port_name] = recorder
            return True
        return False

    def stop_logging(self, port_name: str) -> None:
        """
        특정 포트의 로깅를 중단합니다.

        Args:
            port_name: 포트 이름
        """
        if port_name in self._recorders:
            self._recorders[port_name].stop()
            del self._recorders[port_name]

    def stop_all(self) -> None:
        """모든 포트의 로깅를 중단합니다."""
        for port_name in list(self._recorders.keys()):
            self.stop_logging(port_name)

    def record(self, port_name: str, data: bytes) -> None:
        """
        특정 포트의 데이터를 로깅합니다.

        Args:
            port_name: 포트 이름
            data: 로깅할 바이트 데이터
        """
        if port_name in self._recorders:
            self._recorders[port_name].record(data)

    def is_logging(self, port_name: str) -> bool:
        """
        특정 포트가 로깅 중인지 확인합니다.

        Args:
            port_name: 포트 이름

        Returns:
            bool: 로깅 중이면 True
        """
        return port_name in self._recorders and self._recorders[port_name].is_logging

    def get_filepath(self, port_name: str) -> str:
        """
        특정 포트의 로깅 파일 경로를 반환합니다.

        Args:
            port_name: 포트 이름

        Returns:
            str: 파일 경로, 로깅 중이 아니면 빈 문자열
        """
        if port_name in self._recorders:
            return self._recorders[port_name].filepath
        return ""


# 전역 인스턴스 (싱글톤)
log_recorder_manager = DataLoggerManager()
