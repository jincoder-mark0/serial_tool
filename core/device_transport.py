"""
장치 전송 인터페이스 모듈

물리적 장치(Serial, SPI, I2C 등)와의 통신을 위한 표준 인터페이스를 정의합니다.

## WHY
* 다양한 하드웨어 통신 방식을 동일한 인터페이스로 제어하기 위함
* 상위 계층(Worker, Controller)이 구체적인 하드웨어 구현에 의존하지 않도록 분리(DIP)
* 테스트 용이성 확보 (Mock Object 사용 가능)

## WHAT
* DeviceTransport 추상 클래스 정의
* 연결(Open/Close), 입출력(Read/Write), 상태 확인(IsOpen/InWaiting) 메서드 명세
* 하드웨어 제어 신호(DTR/RTS) 인터페이스 제공

## HOW
* ABC(Abstract Base Class)를 상속받아 인터페이스 정의
* @abstractmethod로 필수 구현 메서드 강제
* 제어 신호는 선택적 구현을 위해 기본값(pass) 제공
"""
from abc import ABC, abstractmethod

class DeviceTransport(ABC):
    """
    모든 통신 장치 드라이버가 구현해야 할 추상 기본 클래스

    이 클래스는 '물리적 장치와의 데이터 운송 수단(Transport)'을 의미합니다.
    """

    @abstractmethod
    def open(self) -> bool:
        """
        장치 연결을 엽니다.

        Returns:
            bool: 성공 시 True, 실패 시 False
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """장치 연결을 닫고 리소스를 해제합니다."""
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """
        장치가 현재 연결되어 있는지 확인합니다.

        Returns:
            bool: 연결되어 있으면 True
        """
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        """
        장치로부터 데이터를 읽습니다.

        Args:
            size (int): 읽을 최대 바이트 수

        Returns:
            bytes: 읽은 데이터
        """
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        """
        장치로 데이터를 씁니다.

        Args:
            data (bytes): 전송할 바이트 데이터
        """
        pass

    @property
    @abstractmethod
    def in_waiting(self) -> int:
        """
        수신 버퍼에 대기 중인 바이트 수를 반환합니다.

        Returns:
            int: 대기 중인 바이트 수
        """
        pass

    # ---------------------------------------------------------
    # 하드웨어 제어 신호 (선택적 구현)
    # ---------------------------------------------------------
    def set_dtr(self, state: bool) -> None:
        """
        DTR(Data Terminal Ready) 신호를 제어합니다.
        지원하지 않는 장치는 무시합니다.

        Args:
            state (bool): True=ON, False=OFF
        """
        pass

    def set_rts(self, state: bool) -> None:
        """
        RTS(Request To Send) 신호를 제어합니다.
        지원하지 않는 장치는 무시합니다.

        Args:
            state (bool): True=ON, False=OFF
        """
        pass
