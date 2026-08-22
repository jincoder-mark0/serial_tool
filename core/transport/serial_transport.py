"""
시리얼 전송 계층 모듈

BaseTransport 인터페이스의 구체적인 구현체를 제공합니다.

## WHY
* 하드웨어 독립성 (BaseTransport 추상화) 확보
* PySerial 라이브러리 캡슐화로 상위 계층 의존성 제거
* 에러 처리 및 안전한 I/O 보장

## WHAT
* PySerial 기반 시리얼 통신 구현
* Non-blocking I/O 및 흐름 제어 지원
* 연결 예외 처리 및 Write Timeout 설정

## HOW
* BaseTransport 인터페이스 구현
* serial.Serial 객체 래핑 및 위임
"""
import serial
from typing import Optional
from core.transport.base_transport import BaseTransport
from common.dtos import PortConfig
from common.constants import WRITE_TIMEOUT_S

class SerialTransport(BaseTransport):
    """
    PySerial 기반 BaseTransport 구현체

    시리얼 포트 통신을 위한 구체적인 전송 계층 구현입니다.
    """

    def __init__(self, config: PortConfig):
        """
        SerialTransport 초기화

        Args:
            config (PortConfig): 포트 연결 설정 DTO
        """
        self.config = config
        self._serial: Optional[serial.Serial] = None

    def open(self) -> bool:
        """
        시리얼 포트 열기

        Logic:
            - DTO에서 설정값 로드
            - 흐름 제어 설정 (RTS/CTS)
            - Non-blocking I/O 설정 (timeout=0)
            - Write Timeout 설정 (WRITE_TIMEOUT_S — 쓰기 완료 확인, S-039)
              워커 스레드(ConnectionWorker)에서만 블로킹되므로 UI는 멈추지 않음
            - serial.Serial 객체 생성
            - 에러 발생 시 Exception 전파

        Returns:
            bool: 포트가 성공적으로 열렸는지 여부

        Raises:
            serial.SerialException: 포트 열기 실패 시
        """
        try:
            # DTO 속성 사용 (타입 안전성 확보)
            flowctrl = self.config.flowctrl
            rtscts = (flowctrl == 'RTS/CTS')
            xonxoff = (flowctrl == 'XON/XOFF')

            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                timeout=0,                    # Read timeout (Non-blocking)
                write_timeout=WRITE_TIMEOUT_S, # Write timeout (완료 확인, S-039)
                xonxoff=xonxoff,
                rtscts=rtscts,
                dsrdtr=False     # DTR 자동 제어 비활성화 (필요 시 수동 제어)
            )
            return self._serial.is_open
        except serial.SerialException as e:
            # 상위 레벨(Worker)에서 에러 처리하도록 전파
            raise e

    def close(self) -> None:
        """시리얼 포트 닫기 및 리소스 해제"""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_open(self) -> bool:
        """
        포트 열림 상태 확인

        Returns:
            bool: 포트가 열려있으면 True
        """
        return self._serial is not None and self._serial.is_open

    def read(self, size: int) -> bytes:
        """
        데이터 읽기

        Args:
            size (int): 읽을 최대 바이트 수

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

        write_timeout=WRITE_TIMEOUT_S(0이 아님)이므로 pyserial(Windows
        serialwin32.py)이 GetOverlappedResult로 쓰기 완료를 확인한 뒤 반환한다.
        완료 전 타임아웃되면 SerialTimeoutException이 발생하며, 이를 상위
        (Worker)로 전파해 데이터 유실을 인지하도록 한다.
        (정정, S-039) write_timeout=0으로 두면 반대로 동작한다 — 설치된
        pyserial 3.5의 Windows 구현은 이때 완료 확인 자체를 생략하고
        ERROR_SUCCESS/ERROR_IO_PENDING만으로 len(data)를 반환해(성공 오보),
        실제로는 유실됐는데도 예외가 올라오지 않는다. 과거 주석("write_timeout=0
        으로 예외를 전파하여 데이터 유실을 방지")은 이 실측과 반대였다.

        Args:
            data (bytes): 전송할 바이트 데이터

        Raises:
            serial.SerialTimeoutException: 쓰기 타임아웃 발생 시 (완료 미확인)
            serial.SerialException: 전송 실패 시
        """
        if self.is_open():
            # 예외를 상위(Worker)로 전파하여 처리하도록 함
            self._serial.write(data)

    @property
    def in_waiting(self) -> int:
        """
        수신 버퍼에 대기 중인 바이트 수 반환

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

    def set_broadcast(self, state: bool) -> None:
        """
        broadcasting 설정 (시리얼에서는 특별한 하드웨어 동작 없음)
        """
        pass

    def set_dtr(self, state: bool) -> None:
        """
        DTR(Data Terminal Ready) 신호 설정

        Args:
            state (bool): True=ON, False=OFF
        """
        if self.is_open():
            self._serial.dtr = state

    def set_rts(self, state: bool) -> None:
        """
        RTS(Request To Send) 신호 설정

        Args:
            state (bool): True=ON, False=OFF
        """
        if self.is_open():
            self._serial.rts = state
