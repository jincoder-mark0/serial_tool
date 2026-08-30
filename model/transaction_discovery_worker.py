"""SPI/I2C adapter discovery worker.

## WHY
* PyFtdi/libusb enumeration은 OS/USB 상태에 따라 지연될 수 있으므로 UI thread에서 실행 금지
* optional backend 하나의 실패가 전체 discovery와 SerialTool startup을 막지 않아야 함
* libusb/driver 호출이 반환하지 않아도 QThread 자체는 interruption에 응답해 앱 종료를 막지 않아야 함

## HOW
* 실제 blocking ``AdapterBackendRegistry.enumerate()``는 daemon helper thread에서 실행
* QThread는 짧은 polling으로 결과를 기다리므로 ``requestInterruption()``에 bounded하게 응답
* 성공 결과와 실패 exception을 signal로 전달
* helper가 남아 있으면 Manager가 후속 discovery 중복 실행을 제한
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from PyQt5.QtCore import QThread, pyqtSignal

from common.constants import BACKGROUND_IO_POLL_S
from core.transport.transaction.registry import AdapterBackendRegistry


class TransactionDiscoveryWorker(QThread):
    """등록된 transaction backend의 adapter를 background에서 한 번 열거합니다."""

    adapters_found = pyqtSignal(object)
    discovery_failed = pyqtSignal(object)

    def __init__(self, registry: AdapterBackendRegistry) -> None:
        super().__init__()
        self._registry = registry
        self._io_thread: Thread | None = None

    @property
    def has_pending_io(self) -> bool:
        """QThread 종료 후에도 vendor/OS enumeration helper가 남아 있는지 반환합니다."""
        return self._io_thread is not None and self._io_thread.is_alive()

    def run(self) -> None:
        result_queue: Queue[tuple[bool, object]] = Queue()

        def collect_adapters() -> None:
            try:
                result_queue.put((True, list(self._registry.enumerate())))
            except Exception as exc:
                result_queue.put((False, exc))

        # Driver/libusb API가 영구 block되더라도 이 helper는 daemon이므로 process 종료를 막지
        # 않습니다. QThread는 interruption을 polling해 정상 Qt lifecycle로 빠르게 종료합니다.
        self._io_thread = Thread(target=collect_adapters, daemon=True)
        self._io_thread.start()

        while not self.isInterruptionRequested():
            try:
                succeeded, payload = result_queue.get(timeout=BACKGROUND_IO_POLL_S)
                break
            except Empty:
                continue
        else:
            return

        if succeeded:
            self.adapters_found.emit(payload)
        else:
            self.discovery_failed.emit(payload)
