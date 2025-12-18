"""
데이터 로거 모듈 (Data Logger)

시리얼 포트 등에서 수신된 데이터를 파일에 실시간으로 기록합니다.
단순 바이너리뿐만 아니라, 텍스트(HEX) 및 PCAP 포맷을 지원하여

## WHY
* 데이터 분석을 위해 수신된 원본 데이터를 파일로 저장해야 함
* Wireshark 등 전문 도구 분석을 위한 표준 포맷(PCAP) 지원 필요
* UI 스레드 블로킹 없이 고속 데이터 저장이 필요함

## WHAT
* DataLogger: 단일 포트의 데이터를 파일에 기록 (Producer-Consumer 패턴)
* 포맷 지원: BIN (Raw), HEX (Text Dump), PCAP (Wireshark)
* DataLoggerManager: 여러 포트의 로거를 관리하는 중앙 관리자

## HOW
* Queue를 사용하여 데이터 수신(Write)과 파일 저장(Disk I/O)을 분리
* 쓰기 시점의 타임스탬프를 캡처하여 PCAP 정밀도 보장
* 백그라운드 스레드에서 포맷에 따른 인코딩 및 파일 쓰기 수행
"""
from typing import Optional, Dict, Tuple
from queue import Queue, Empty
from threading import Thread
import os
import time
import struct
from core.logger import logger
from common.enums import LogFormat

class DataLogger:
    """
    단일 포트의 실시간 데이터 로깅을 담당하는 클래스

    백그라운드 스레드에서 파일 쓰기를 수행하여 메인 스레드에 영향을 주지 않습니다.
    Queue를 버퍼로 사용하여 순간적인 I/O 지연 시에도 데이터 유실을 방지합니다.
    """

    def __init__(self):
        """DataLogger 초기화"""
        self._file = None
        self._queue: Queue = Queue() # (timestamp, data) 튜플 저장
        self._thread: Optional[Thread] = None
        self._is_logging = False
        self.filepath: str = ""
        self.format: LogFormat = LogFormat.BIN

    @property
    def is_logging(self) -> bool:
        """현재 로깅 중인지 여부 반환"""
        return self._is_logging

    def start_logging(self, filepath: str, log_format: LogFormat = LogFormat.BIN) -> bool:
        """
        로깅을 시작합니다.

        Logic:
            - 디렉토리 생성
            - 포맷에 따라 파일 열기 모드 결정 (바이너리/텍스트)
            - PCAP 포맷인 경우 글로벌 헤더 작성
            - 백그라운드 스레드 시작

        Args:
            filepath: 저장할 파일 경로
            log_format: 저장 포맷 (BIN, HEX, PCAP)

        Returns:
            bool: 시작 성공 여부
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            self.format = log_format
            self.filepath = filepath

            # 모든 포맷을 바이너리 모드로 엽니다 (텍스트 인코딩 이슈 방지 및 PCAP 호환)
            self._file = open(filepath, 'wb')

            # PCAP 포맷인 경우 글로벌 헤더 작성
            if self.format == LogFormat.PCAP:
                self._write_pcap_global_header()

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
        데이터를 로깅 큐에 추가합니다. (Non-blocking)
        데이터 수신 시점의 타임스탬프를 함께 캡처합니다.

        Args:
            data: 기록할 바이트 데이터
        """
        if self._is_logging:
            timestamp = time.time()
            self._queue.put((timestamp, data))

    def _write_loop(self) -> None:
        """
        백그라운드 스레드에서 실행되는 쓰기 루프

        Logic:
            - 큐에서 (timestamp, data)를 꺼냄
            - 포맷에 따라 데이터 가공 후 파일 쓰기
        """
        while self._is_logging or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
                timestamp, data = item

                if not self._file:
                    continue

                if self.format == LogFormat.PCAP:
                    self._write_pcap_packet(timestamp, data)
                elif self.format == LogFormat.HEX:
                    self._write_hex_dump(timestamp, data)
                else:
                    # BIN (Default)
                    self._file.write(data)

            except Empty:
                continue
            except Exception as e:
                logger.error(f"DataLogger write error: {e}")
                if not self._file or self._file.closed:
                    self._is_logging = False
                    break

    def _write_pcap_global_header(self) -> None:
        """
        PCAP 파일 글로벌 헤더 작성

        Format:
            Magic Number (4B): 0xa1b2c3d4 (Microsecond resolution)
            Major Ver (2B): 2
            Minor Ver (2B): 4
            ThisZone (4B): 0
            SigFigs (4B): 0
            SnapLen (4B): 65535
            Network (4B): 147 (DLT_USER0) - 사용자 정의
        """
        header = struct.pack('IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 147)
        self._file.write(header)

    def _write_pcap_packet(self, timestamp: float, data: bytes) -> None:
        """
        PCAP 패킷 데이터 작성

        Args:
            timestamp: 수신 시간 (float)
            data: 페이로드 데이터
        """
        ts_sec = int(timestamp)
        ts_usec = int((timestamp - ts_sec) * 1_000_000)
        length = len(data)

        # Packet Header: ts_sec(4) + ts_usec(4) + incl_len(4) + orig_len(4)
        header = struct.pack('IIII', ts_sec, ts_usec, length, length)
        self._file.write(header)
        self._file.write(data)

    def _write_hex_dump(self, timestamp: float, data: bytes) -> None:
        """
        사람이 읽기 쉬운 HEX 포맷으로 작성

        Format: [HH:MM:SS.mmm] 00 01 02 ...
        """
        time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
        ms = int((timestamp % 1) * 1000)
        hex_str = " ".join(f"{b:02X}" for b in data)

        line = f"[{time_str}.{ms:03d}] {hex_str}\n"
        self._file.write(line.encode('utf-8'))

class DataLoggerManager:
    """
    여러 포트의 DataLogger를 관리하는 매니저 클래스 (Singleton)
    """

    def __init__(self):
        self._loggers: Dict[str, DataLogger] = {}

    def start_logging(self, port_name: str, filepath: str, log_format: LogFormat = LogFormat.BIN) -> bool:
        """
        특정 포트의 로깅을 시작합니다.

        Args:
            port_name: 포트 이름
            filepath: 저장할 파일 경로
            log_format: 저장 포맷 (기본 BIN)

        Returns:
            bool: 성공 시 True
        """
        if port_name in self._loggers:
            self.stop_logging(port_name)

        logger_instance = DataLogger()
        if logger_instance.start_logging(filepath, log_format):
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
