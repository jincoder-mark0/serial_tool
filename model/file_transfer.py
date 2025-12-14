"""
파일 전송 모델
"""
import os
import time
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal
from model.connection_controller import ConnectionController
from core.event_bus import event_bus
from common.dtos import FileProgressState, FileProgressEvent
from common.constants import EventTopics # 상수 임포트

class FileTransferSignals(QObject):
    """
    파일 전송 엔진에서 사용하는 시그널 정의
    """
    # DTO 사용 (FileProgressState)
    progress_updated = pyqtSignal(object)
    transfer_completed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

class FileTransferEngine(QRunnable):
    """
    파일 전송을 담당하는 엔진 (QRunnable 기반)

    별도의 스레드 풀에서 실행되며, 파일을 청크 단위로 읽어 ConnectionController를 통해 전송합니다.

    ## 흐름 제어 (Flow Control) 및 안정성 개선

    - **Backpressure (역압) 제어**: `ConnectionController`의 송신 큐 크기를 모니터링하여
      PC의 송신 버퍼가 가득 차면 일시 대기합니다. 이는 메모리 폭증과 데이터 유실을 방지합니다.
    - **Flow Control 지원**: 포트 설정에 따라 속도 제어 방식을 달리합니다.
      - RTS/CTS, XON/XOFF: 하드웨어/드라이버 레벨의 흐름 제어를 신뢰하여 불필요한 sleep을 제거합니다.
      - None: Baudrate 기반의 타이밍 계산을 통해 전송 속도를 제한(Pacing)합니다.

    ## 향후 개선 계획
    - **Y-MODEM**과 같은 프로토콜의 다양화
    """

    def __init__(self, connection_controller: ConnectionController, port_name: str, file_path: str, baudrate: int, flow_control: str = "None"):
        super().__init__()
        self.connection_controller = connection_controller
        self.port_name = port_name
        self.file_path = file_path
        self.baudrate = baudrate
        self.flow_control = flow_control
        self.signals = FileTransferSignals()
        self.event_bus = event_bus
        self._is_cancelled = False

        # 설정값
        self.chunk_size = 1024 # 1KB
        if self.baudrate > 115200:
            self.chunk_size = 4096 # 고속 통신 시 청크 크기 증가

        # Backpressure 임계값 (큐에 쌓인 청크 개수)
        self.queue_threshold = 50

    def cancel(self):
        """전송 취소 요청"""
        self._is_cancelled = True

    def run(self):
        """
        파일 전송 실행 로직

        Logic:
            - 파일 존재 여부 확인
            - 파일을 청크 단위로 읽어서 전송
            - **Backpressure Check**: 송신 큐가 가득 차면 대기
            - **Flow Control Check**:
                - 하드웨어 흐름 제어 시: Blocking Write에 의존 (Sleep 없음)
                - 흐름 제어 없음: Baudrate 기반 Sleep 적용
            - 각 청크 전송 후 진행률 업데이트
            - 취소/완료/에러 처리
        """
        try:
            # 파일 존재 확인
            if not os.path.exists(self.file_path):
                self.signals.error_occurred.emit(f"File not found: {self.file_path}")
                self.signals.transfer_completed.emit(False)
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0

            with open(self.file_path, 'rb') as f:
                while not self._is_cancelled:
                    # [Logic] Backpressure Control (역압 제어)
                    # ConnectionWorker의 큐가 비워질 때까지 대기하여 메모리 보호 및 유실 방지
                    while self.connection_controller.get_write_queue_size(self.port_name) > self.queue_threshold:
                        time.sleep(0.01) # 10ms 대기
                        if self._is_cancelled:
                            break

                    if self._is_cancelled:
                        break

                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break # EOF

                    # 데이터 전송
                    success = self.connection_controller.send_data_to_connection(self.port_name, chunk)
                    if not success:
                        raise Exception(f"Port {self.port_name} is not open or unavailable.")

                    # 진행률 업데이트
                    sent_bytes += len(chunk)

                    # 1. UI용 시그널 (FileProgressState DTO 사용)
                    # 여기서는 기본 정보만 담아서 보내고 계산은 Presenter에 위임
                    state = FileProgressState(
                        file_path=self.file_path,
                        sent_bytes=sent_bytes,
                        total_bytes=total_size,
                        status="Sending"
                    )
                    self.signals.progress_updated.emit(state)

                    # 2. EventBus용 이벤트 (FileProgressEvent DTO 사용)
                    self.event_bus.publish(EventTopics.FILE_PROGRESS, FileProgressEvent(current=sent_bytes, total=total_size))

                    # [Logic] Speed Control (속도 제어)
                    # Flow Control이 활성화된 경우(RTS/CTS 등), 드라이버 레벨의 블로킹을 신뢰하고 sleep을 건너뜀
                    # Flow Control이 없는 경우, Baudrate에 맞춰 소프트웨어적으로 속도 조절 (Pacing)
                    if self.flow_control in ["RTS/CTS", "XON/XOFF"]:
                        # 하드웨어/소프트웨어 흐름 제어에 맡김 (최대 속도)
                        pass
                    else:
                        # 전송 속도 조절 (Baudrate 기반 지연)
                        # 1 byte = 10 bits (8N1: 1 start + 8 data + 1 stop)
                        wait_time = (len(chunk) * 10) / self.baudrate
                        time.sleep(wait_time)

            # 전송 완료 또는 취소 처리
            if self._is_cancelled:
                self.signals.error_occurred.emit("Transfer cancelled by user.")
                self.signals.transfer_completed.emit(False)
                self.event_bus.publish(EventTopics.FILE_COMPLETED, False)
            else:
                self.signals.transfer_completed.emit(True)
                self.event_bus.publish(EventTopics.FILE_COMPLETED, True)

        except Exception as e:
            self.signals.error_occurred.emit(str(e))
            self.signals.transfer_completed.emit(False)
            self.event_bus.publish(EventTopics.FILE_ERROR, str(e))
            self.event_bus.publish(EventTopics.FILE_COMPLETED, False)
