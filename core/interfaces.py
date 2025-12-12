"""
통신 인터페이스 정의 모듈
모든 통신 드라이버(Serial, SPI, I2C 등)가 구현해야 할 기본 인터페이스입니다.
"""
from abc import ABC, abstractmethod

class ITransport(ABC):
    """
    모든 통신 방식이 구현해야 할 추상 기본 클래스입니다.
    """

    @abstractmethod
    def open(self) -> bool:
        """연결을 엽니다."""
        pass

    @abstractmethod
    def close(self) -> None:
        """연결을 닫습니다."""
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """연결 상태를 확인합니다."""
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        """
        데이터를 읽습니다.
        Args:
            size (int): 읽을 최대 바이트 수
        Returns:
            bytes: 읽은 데이터
        """
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        """
        데이터를 씁니다.
        Args:
            data (bytes): 보낼 데이터
        """
        pass

    @property
    @abstractmethod
    def in_waiting(self) -> int:
        """읽기 대기 중인 바이트 수를 반환합니다."""
        pass

    # 시리얼 제어 신호 (선택적 구현)
    def set_dtr(self, state: bool) -> None:
        pass

    def set_rts(self, state: bool) -> None:
        pass
