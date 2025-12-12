"""
시리얼 전송 계층 모듈

ITransport 인터페이스의 구체적인 구현체를 제공합니다.

## WHY
* 하드웨어 독립성 (ITransport 추상화)
* PySerial 라이브러리 캡슐화
* 에러 처리 및 안전한 I/O
* 다양한 통신 설정 지원

## WHAT
* PySerial 기반 시리얼 통신 구현
* Non-blocking I/O 지원
* 흐름 제어 (RTS/CTS) 지원
* DTR/RTS 제어 신호 관리
* 에러 처리 및 복구

## HOW
* ITransport 인터페이스 구현
* serial.Serial 객체 래핑
* 설정 Dictionary로 유연한 파라미터 전달
* Exception 처리로 안정성 보장
"""
import serial
from typing import Dict, Any, Optional
from core.interfaces import ITransport

class SerialTransport(ITransport):
    """
    PySerial 기반 ITransport 구현체

    시리얼 포트 통신을 위한 구체적인 전송 계층 구현입니다.
    """

    def __init__(self, port: str, baudrate: int, config: Optional[Dict[str, Any]] = None):
        """
        SerialTransport 초기화

        Args:
            port: 포트 이름 (예: 'COM1', '/dev/ttyUSB0')
            baudrate: 통신 속도
            config: 추가 설정 (bytesize, parity, stopbits, flowctrl 등)
        """
        self.port = port
        self.baudrate = baudrate
        self.config = config or {}
        self._serial: Optional[serial.Serial] = None

    def open(self) -> bool:
        """
        시리얼 포트 열기

        Logic:
            - 설정값 파싱 (기본값 적용)
            - 흐름 제어 설정 (RTS/CTS)
            - Non-blocking I/O 설정 (timeout=0)
            - serial.Serial 객체 생성
            - 에러 발생 시 Exception 전파

        Returns:
            bool: 포트가 성공적으로 열렸는지 여부

        Raises:
            serial.SerialException: 포트 열기 실패 시
        """
        try:
            # 설정값 파싱 (기본값 설정)
            bytesize = self.config.get('bytesize', serial.EIGHTBITS)
            parity = self.config.get('parity', serial.PARITY_NONE)
            stopbits = self.config.get('stopbits', serial.STOPBITS_ONE)
            flowctrl = self.config.get('flowctrl', 'None')
            rtscts = (flowctrl == 'RTS/CTS')

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=0,  # Non-blocking I/O
                xonxoff=False,
                rtscts=rtscts,
                dsrdtr=False
            )
            return self._serial.is_open
        except serial.SerialException as e:
            # 상위 레벨(Worker)에서 에러 처리하도록 전파
            raise e

    def close(self) -> None:
        """시리얼 포트 닫기"""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_open(self) -> bool:
        """포트 열림 상태 확인"""
        return self._serial is not None and self._serial.is_open

    def read(self, size: int) -> bytes:
        """
        데이터 읽기

        Args:
            size: 읽을 최대 바이트 수

        Returns:
            bytes: 읽은 데이터 (에러 시 빈 bytes)
        """
        if self.is_open():
            try:
                return self._serial.read(size)
            except serial.SerialException:
                # 치명적인 에러 (연결 끊김 등)
                return b""
            except Exception:
                return b""
        return b""

    def write(self, data: bytes) -> None:
        """
        데이터 쓰기

        Args:
            data: 전송할 바이트 데이터

        Raises:
            serial.SerialException: 전송 실패 시
        """
        if self.is_open():
            try:
                self._serial.write(data)
            except serial.SerialException as e:
                raise e  # 상위에서 처리하도록 전파
            except Exception:
                pass

    @property
    def in_waiting(self) -> int:
        """
        수신 버퍼에 대기 중인 바이트 수

        Returns:
            int: 대기 중인 바이트 수 (에러 시 0)
        """
        if self.is_open():
            try:
                return self._serial.in_waiting
            except serial.SerialException:
                return 0
            except Exception:
                return 0
        return 0

    def set_dtr(self, state: bool) -> None:
        """DTR(Data Terminal Ready) 신호 설정"""
        if self.is_open():
            self._serial.dtr = state

    def set_rts(self, state: bool) -> None:
        """RTS(Request To Send) 신호 설정"""
        if self.is_open():
            self._serial.rts = state

    def set_local_echo(self, state: bool) -> None:
        """Local Echo 신호 설정"""
        if self.is_open():
            pass # TODO