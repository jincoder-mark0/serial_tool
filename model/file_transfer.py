import os
import time
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal
from model.port_controller import PortController
from core.event_bus import event_bus

class FileTransferSignals(QObject):
    """
    파일 전송 엔진에서 사용하는 시그널 정의
    """
    progress_updated = pyqtSignal(int, int)  # current_bytes, total_bytes
    transfer_completed = pyqtSignal(bool)    # success
    error_occurred = pyqtSignal(str)         # error_message

class FileTransferEngine(QRunnable):
    """
    파일 전송을 담당하는 엔진 (QRunnable 기반)
    별도의 스레드 풀에서 실행되며, 파일을 청크 단위로 읽어 PortController를 통해 전송합니다.
    """

    def __init__(self, port_controller: PortController, port_name: str, file_path: str, baudrate: int):
        super().__init__()
        self.port_controller = port_controller
        self.port_name = port_name
        self.file_path = file_path
        self.baudrate = baudrate
        self.signals = FileTransferSignals()
        self.event_bus = event_bus
        self._is_cancelled = False
        
        # 설정값
        self.chunk_size = 1024 # 1KB
        if self.baudrate > 115200:
            self.chunk_size = 4096 # 고속 통신 시 청크 크기 증가

    def cancel(self):
        """전송 취소 요청"""
        self._is_cancelled = True

    def run(self):
        """전송 실행 로직"""
        try:
            if not os.path.exists(self.file_path):
                self.signals.error_occurred.emit(f"File not found: {self.file_path}")
                self.signals.transfer_completed.emit(False)
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0

            with open(self.file_path, 'rb') as f:
                while not self._is_cancelled:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break # EOF

                    # 데이터 전송
                    # PortController.send_data_to_port 사용
                    success = self.port_controller.send_data_to_port(self.port_name, chunk)
                    if not success:
                        raise Exception(f"Port {self.port_name} is not open or unavailable.")

                    sent_bytes += len(chunk)
                    self.signals.progress_updated.emit(sent_bytes, total_size)
                    self.event_bus.publish("file.progress", {'current': sent_bytes, 'total': total_size})

                    # 전송 속도 조절 (Flow Control이 없으므로 Baudrate 기반 지연)
                    # 1 byte = 10 bits (8N1)
                    # time = bits / baudrate
                    wait_time = (len(chunk) * 10) / self.baudrate
                    time.sleep(wait_time)

            if self._is_cancelled:
                self.signals.error_occurred.emit("Transfer cancelled by user.")
                self.signals.transfer_completed.emit(False)
                self.event_bus.publish("file.completed", False)
            else:
                self.signals.transfer_completed.emit(True)
                self.event_bus.publish("file.completed", True)

        except Exception as e:
            self.signals.error_occurred.emit(str(e))
            self.signals.transfer_completed.emit(False)
            self.event_bus.publish("file.error", str(e))
            self.event_bus.publish("file.completed", False)
