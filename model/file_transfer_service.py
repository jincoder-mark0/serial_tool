"""
파일 전송 서비스 모듈

파일 전송 로직을 담당하는 엔진을 정의합니다.

## WHY
* 대용량 파일의 안정적인 전송 (Backpressure 제어)
* UI 블로킹 없는 비동기 실행 (QRunnable)
* 전송 진행 상황 실시간 피드백

## WHAT
* FileTransferService: QRunnable 기반 전송 엔진
* 파일 청크 분할 및 흐름 제어(Flow Control)
* 전송 진행률 및 상태 시그널 발행

## HOW
* 파일을 Chunk 단위로 읽어 ConnectionController로 전송
* 전송 큐 크기를 모니터링하여 과부하 방지 (Backpressure)
"""
import os
import time
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal
from model.connection_controller import ConnectionController
from core.event_bus import event_bus
from common.dtos import FileProgressState, FileProgressEvent, PortConfig
from common.constants import EventTopics

class FileTransferSignals(QObject):
    """
    파일 전송 엔진에서 사용하는 시그널 정의
    """
    progress_updated = pyqtSignal(object)
    transfer_completed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

class FileTransferService(QRunnable):
    """
    파일 전송을 담당하는 엔진 (QRunnable 기반)

    별도의 스레드 풀에서 실행되며, 파일을 청크 단위로 읽어 ConnectionController를 통해 전송합니다.
    """

    def __init__(self, connection_controller: ConnectionController, file_path: str, config: PortConfig):
        """
        FileTransferService 초기화

        Args:
            connection_controller: 전송을 수행할 컨트롤러
            file_path: 전송할 파일 경로
            config: 포트 설정 DTO (baudrate, flowctrl 등 정보 포함)
        """
        super().__init__()
        self.connection_controller = connection_controller
        self.file_path = file_path
        self.config = config
        self.port_name = config.port # DTO에서 포트 이름 추출

        self.signals = FileTransferSignals()
        self.event_bus = event_bus
        self._is_cancelled = False

        # 설정값 (DTO에서 조회)
        self.chunk_size = 1024
        if self.config.baudrate > 115200:
            self.chunk_size = 4096

        # Backpressure 임계값 (큐에 쌓인 청크 개수)
        self.queue_threshold = 50

    def cancel(self):
        """전송 취소 요청"""
        self._is_cancelled = True

    def run(self):
        """
        파일 전송 실행 로직

        Logic:
            - 전체 로직을 try-except로 감싸 예외 누락 방지
            - 시작 시 ConnectionController에 자신을 등록
            - 파일 읽기 및 전송 루프
            - Backpressure 및 Flow Control 적용
            - 종료 시(finally) 등록 해제
        """
        try:
            # 전송 시작 등록 (Race Condition 방지)
            self.connection_controller.register_file_transfer(self.port_name, self)

            # 파일 존재 확인
            if not os.path.exists(self.file_path):
                self.signals.error_occurred.emit(f"File not found: {self.file_path}")
                self.signals.transfer_completed.emit(False)
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0

            with open(self.file_path, 'rb') as f:
                while not self._is_cancelled:
                    # Backpressure Control (역압 제어)
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
                    state = FileProgressState(
                        file_path=self.file_path,
                        sent_bytes=sent_bytes,
                        total_bytes=total_size,
                        status="Sending"
                    )
                    self.signals.progress_updated.emit(state)

                    # 2. EventBus용 이벤트 (FileProgressEvent DTO 사용)
                    self.event_bus.publish(EventTopics.FILE_PROGRESS, FileProgressEvent(current=sent_bytes, total=total_size))

                    # Speed Control (속도 제어)
                    if self.config.flowctrl in ["RTS/CTS", "XON/XOFF"]:
                        pass # 하드웨어 흐름 제어 신뢰
                    else:
                        # 전송 속도 조절 (Baudrate 기반 지연)
                        wait_time = (len(chunk) * 10) / self.config.baudrate
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
            # 예외 발생 시 전역 에러 핸들러에 보고
            try:
                from core.error_handler import get_error_handler
                handler = get_error_handler()
                if handler:
                    handler.report_error(type(e), e, e.__traceback__)
            except Exception:
                pass

            self.signals.error_occurred.emit(str(e))
            self.signals.transfer_completed.emit(False)
            self.event_bus.publish(EventTopics.FILE_ERROR, str(e))
            self.event_bus.publish(EventTopics.FILE_COMPLETED, False)

        finally:
            # 전송 종료 등록 해제
            self.connection_controller.unregister_file_transfer(self.port_name)
