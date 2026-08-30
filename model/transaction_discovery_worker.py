"""SPI/I2C adapter discovery worker.

## WHY
* PyFtdi/libusb enumeration은 OS/USB 상태에 따라 지연될 수 있으므로 UI thread에서 실행 금지
* optional backend 하나의 실패가 전체 discovery와 SerialTool startup을 막지 않아야 함

## HOW
* one-shot QThread에서 ``AdapterBackendRegistry.enumerate()`` 실행
* 성공 결과와 실패 exception을 signal로 전달
* Manager가 worker strong reference와 중복 실행 방지를 소유
"""
from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal

from core.transport.transaction.registry import AdapterBackendRegistry


class TransactionDiscoveryWorker(QThread):
    """등록된 transaction backend의 adapter를 background thread에서 한 번 열거합니다."""

    adapters_found = pyqtSignal(object)
    discovery_failed = pyqtSignal(object)

    def __init__(self, registry: AdapterBackendRegistry) -> None:
        super().__init__()
        self._registry = registry

    def run(self) -> None:
        try:
            descriptors = list(self._registry.enumerate())
            if not self.isInterruptionRequested():
                self.adapters_found.emit(descriptors)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.discovery_failed.emit(exc)
