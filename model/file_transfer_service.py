"""
파일 전송 서비스 모듈

파일 전송 로직을 담당하는 엔진을 정의합니다.

## WHY
* 대용량 파일의 안정적인 전송 (Backpressure 제어 및 메모리 관리)
* UI 블로킹 없는 비동기 실행 (QRunnable 활용)
* 전송 진행 상황 실시간 피드백 및 취소 기능 제공

## WHAT
* FileTransferService: QRunnable 기반 전송 엔진
* 파일 청크(Chunk) 분할 및 흐름 제어(Flow Control)
* 전송 진행률, 완료, 에러 상태 시그널 발행 (DTO 기반)

## HOW
* 파일을 Chunk 단위로 읽어 ConnectionController로 전송
* 전송 큐 크기를 모니터링하여 과부하 방지 (Backpressure)
* EventBus와 PyQt Signal을 동시에 사용하여 상태 전파
"""
import os
import time
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal

from model.connection_controller import ConnectionController
from core.event_bus import event_bus
from core.logger import logger
from common.dtos import (
    FileProgressState,
    FileProgressEvent,
    PortConfig,
    FileCompletionEvent,
    FileErrorEvent
)
from common.constants import EventTopics


class FileTransferSignals(QObject):
    """
    파일 전송 엔진에서 사용하는 시그널 정의 클래스

    QRunnable은 QObject가 아니므로 시그널을 직접 가질 수 없어 별도 클래스로 분리합니다.
    """
    progress_updated = pyqtSignal(object)       # FileProgressState
    transfer_completed = pyqtSignal(object)     # FileCompletionEvent
    error_occurred = pyqtSignal(object)         # FileErrorEvent


class FileTransferService(QRunnable):
    """
    파일 전송을 담당하는 엔진 (QRunnable 기반)

    별도의 스레드 풀에서 실행되며, 파일을 청크 단위로 읽어 ConnectionController를 통해 전송합니다.
    """

    def __init__(self, connection_controller: ConnectionController, file_path: str, config: PortConfig):
        """
        FileTransferService 초기화

        Args:
            connection_controller (ConnectionController): 전송을 수행할 컨트롤러 인스턴스.
            file_path (str): 전송할 파일의 절대 경로.
            config (PortConfig): 포트 설정 DTO (Baudrate, Flow Control 등 정보 포함).
        """
        super().__init__()
        self.connection_controller = connection_controller
        self.file_path = file_path
        self.config = config
        self.port_name = config.port  # DTO에서 포트 이름 추출

        self.signals = FileTransferSignals()
        self.event_bus = event_bus
        self._is_cancelled = False

        # 청크 크기 설정 (Baudrate에 따른 적응형 크기)
        # 고속 통신(115200 초과)에서는 4KB, 그 외에는 1KB 사용
        self.chunk_size = 4096 if self.config.baudrate > 115200 else 1024

        # Backpressure 임계값 (큐에 쌓인 청크 개수)
        # 큐가 이 값보다 많이 차면 전송을 일시 대기합니다.
        self.queue_threshold = 50

    def cancel(self) -> None:
        """전송 취소를 요청합니다."""
        self._is_cancelled = True

    def run(self) -> None:
        """
        파일 전송 실행 로직 (스레드 진입점)

        Logic:
            1. 전송 시작을 Controller에 등록 (Race Condition 방지)
            2. 파일 존재 여부 확인
            3. 파일을 청크 단위로 읽으며 루프 실행
            4. Backpressure 체크 (큐가 가득 차면 대기)
            5. 데이터 전송 및 진행률 업데이트
            6. 완료 또는 취소 시 결과 이벤트 발행
            7. 종료 시 Controller 등록 해제
        """
        try:
            # 전송 시작 등록
            self.connection_controller.register_file_transfer(self.port_name, self)

            # 파일 존재 확인
            if not os.path.exists(self.file_path):
                msg = f"File not found: {self.file_path}"

                # 에러 이벤트 생성 (DTO)
                error_event = FileErrorEvent(message=msg, file_path=self.file_path)
                self.signals.error_occurred.emit(error_event)

                # 완료 이벤트 생성 (실패)
                comp_event = FileCompletionEvent(success=False, message=msg, file_path=self.file_path)
                self.signals.transfer_completed.emit(comp_event)
                return

            total_size = os.path.getsize(self.file_path)
            sent_bytes = 0

            with open(self.file_path, 'rb') as f:
                while not self._is_cancelled:
                    # Backpressure Control (역압 제어)
                    # 전송 큐가 임계값을 초과하면 잠시 대기하여 메모리 폭증 방지
                    while self.connection_controller.get_write_queue_size(self.port_name) > self.queue_threshold:
                        time.sleep(0.01)  # 10ms 대기
                        if self._is_cancelled:
                            break

                    if self._is_cancelled:
                        break

                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break  # EOF (파일 끝 도달)

                    # 데이터 전송 시도
                    success = self.connection_controller.send_data_to_connection(self.port_name, chunk)
                    if not success:
                        raise Exception(f"Port {self.port_name} is not open or unavailable.")

                    # 진행률 업데이트
                    sent_bytes += len(chunk)

                    # 1. UI용 시그널 발행 (FileProgressState DTO)
                    state = FileProgressState(
                        file_path=self.file_path,
                        sent_bytes=sent_bytes,
                        total_bytes=total_size,
                        status="Sending"
                    )
                    self.signals.progress_updated.emit(state)

                    # 2. EventBus용 이벤트 발행 (FileProgressEvent DTO)
                    self.event_bus.publish(
                        EventTopics.FILE_PROGRESS,
                        FileProgressEvent(current=sent_bytes, total=total_size)
                    )

                    # Speed Control (소프트웨어 흐름 제어)
                    # 하드웨어 흐름 제어가 없는 경우, Baudrate에 맞춰 인위적 지연 추가
                    if self.config.flowctrl in ["RTS/CTS", "XON/XOFF"]:
                        pass  # 하드웨어/소프트웨어 핸드쉐이킹 신뢰
                    else:
                        # (데이터 크기 * 10비트) / Baudrate = 전송 소요 시간 (초)
                        wait_time = (len(chunk) * 10) / self.config.baudrate
                        time.sleep(wait_time)

            # 전송 완료 또는 취소 처리
            if self._is_cancelled:
                msg = "Transfer cancelled by user."

                # 에러 이벤트 (취소도 에러의 일종으로 처리하거나 별도 처리 가능)
                error_event = FileErrorEvent(message=msg, file_path=self.file_path)
                self.signals.error_occurred.emit(error_event)

                # 완료 이벤트 (실패)
                comp_event = FileCompletionEvent(success=False, message=msg, file_path=self.file_path)
                self.signals.transfer_completed.emit(comp_event)

                self.event_bus.publish(EventTopics.FILE_COMPLETED, comp_event)
            else:
                # 완료 이벤트 (성공)
                comp_event = FileCompletionEvent(success=True, message="Transfer successful", file_path=self.file_path)
                self.signals.transfer_completed.emit(comp_event)

                self.event_bus.publish(EventTopics.FILE_COMPLETED, comp_event)

        except Exception as e:
            # 예외 발생 시 전역 에러 핸들러에 보고 (선택 사항)
            try:
                from core.error_handler import get_error_handler
                handler = get_error_handler()
                if handler:
                    handler.report_error(type(e), e, e.__traceback__)
            except Exception:
                pass

            error_msg = str(e)

            # 에러 이벤트 발행 (DTO)
            error_event = FileErrorEvent(message=error_msg, file_path=self.file_path)
            self.signals.error_occurred.emit(error_event)

            # 완료 이벤트 발행 (실패)
            comp_event = FileCompletionEvent(success=False, message=error_msg, file_path=self.file_path)
            self.signals.transfer_completed.emit(comp_event)

            self.event_bus.publish(EventTopics.FILE_ERROR, error_event)
            self.event_bus.publish(EventTopics.FILE_COMPLETED, comp_event)

        finally:
            # 전송 종료 등록 해제
            self.connection_controller.unregister_file_transfer(self.port_name)