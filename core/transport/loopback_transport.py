"""
루프백(더미) 전송 계층 모듈

BaseTransport 인터페이스를 구현하는 소프트웨어 전용 에코 장치입니다.

## WHY
* 실기기(COM 포트) 없이도 송수신 전 경로(RX Fast Path, 로깅, 매크로 Expect,
  AutoTx, 파일 전송)를 디버깅할 수단이 필요함 (S-033)
* com0com 등 실환경 구성 없이 상시 사용 가능한 소프트웨어 보완재 제공

## WHAT
* LoopbackTransport: write()로 들어온 바이트를 내부 버퍼에 쌓고,
  read()가 동일한 바이트를 그대로 되돌려주는(echo) BaseTransport 구현체

## HOW
* 내부 bytearray 버퍼 + threading.Lock으로 스레드 안전성 확보
  (write는 UI/기타 스레드, read/in_waiting은 ConnectionWorker 스레드에서 호출됨)
* open/close/is_open은 플래그만 관리, DTR/RTS 등 선택 훅은 무동작(no-op)
"""
import threading
from typing import Optional

from core.transport.base_transport import BaseTransport
from common.dtos import PortConfig


class LoopbackTransport(BaseTransport):
    """
    소프트웨어 루프백 BaseTransport 구현체

    write()한 바이트를 그대로 read()로 돌려주는 더미 전송 계층입니다.
    실기기 없이 앱의 송수신 경로를 검증할 때 사용합니다.
    """

    def __init__(self, config: Optional[PortConfig] = None):
        """
        LoopbackTransport 초기화

        Args:
            config (Optional[PortConfig]): 포트 연결 설정 DTO.
                루프백은 통신 파라미터를 사용하지 않으나, 다른 Transport와
                동일한 생성 시그니처를 유지하기 위해 받아 보관만 함.
        """
        self.config = config
        self._is_open = False
        self._lock = threading.Lock()
        self._buffer = bytearray()

    def open(self) -> bool:
        """
        루프백 연결 열기

        Returns:
            bool: 항상 True (실패할 하드웨어가 없음)
        """
        self._is_open = True
        return True

    def close(self) -> None:
        """루프백 연결 닫기 및 내부 버퍼 초기화"""
        self._is_open = False
        with self._lock:
            self._buffer.clear()

    def is_open(self) -> bool:
        """
        연결 상태 확인

        Returns:
            bool: 열려있으면 True
        """
        return self._is_open

    def read(self, size: int) -> bytes:
        """
        버퍼 앞에서 데이터를 읽어 반환

        Args:
            size (int): 읽을 최대 바이트 수

        Returns:
            bytes: 읽은 데이터 (닫혀있거나 버퍼가 비어있으면 빈 bytes)
        """
        if not self._is_open:
            return b""
        with self._lock:
            if not self._buffer:
                return b""
            chunk = bytes(self._buffer[:size])
            del self._buffer[:size]
            return chunk

    def write(self, data: bytes) -> None:
        """
        데이터를 버퍼에 추가 (에코)

        Args:
            data (bytes): 전송할 바이트 데이터. 다음 read() 호출 시 동일하게 반환됨.
        """
        if not self._is_open:
            return
        with self._lock:
            self._buffer.extend(data)

    @property
    def in_waiting(self) -> int:
        """
        버퍼에 대기 중인 바이트 수 반환

        Returns:
            int: 대기 중인 바이트 수
        """
        with self._lock:
            return len(self._buffer)
