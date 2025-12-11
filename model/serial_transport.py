"""
구체적인 통신 드라이버 구현체들을 정의합니다.
"""
import serial
from typing import Dict, Any, Optional
from core.interfaces import ITransport

class SerialTransport(ITransport):
    """PySerial을 감싸는 ITransport 구현체입니다."""

    def __init__(self, port: str, baudrate: int, config: Optional[Dict[str, Any]] = None):
        self.port = port
        self.baudrate = baudrate
        self.config = config or {}
        self._serial: Optional[serial.Serial] = None

    def open(self) -> bool:
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
            # 상위 레벨(Worker)에서 에러를 처리하도록 전파하거나 False 반환
            raise e

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def read(self, size: int) -> bytes:
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
        if self.is_open():
            try:
                self._serial.write(data)
            except serial.SerialException as e:
                raise e # 상위에서 처리하도록 전파
            except Exception:
                pass

    @property
    def in_waiting(self) -> int:
        if self.is_open():
            try:
                return self._serial.in_waiting
            except serial.SerialException:
                return 0
            except Exception:
                return 0
        return 0

    def set_dtr(self, state: bool) -> None:
        if self.is_open():
            self._serial.dtr = state

    def set_rts(self, state: bool) -> None:
        if self.is_open():
            self._serial.rts = state