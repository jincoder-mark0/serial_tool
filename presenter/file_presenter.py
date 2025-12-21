"""
파일 프레젠터 모듈

파일 전송 로직, 속도 계산, ETA 산출을 담당하는 Presenter입니다.

## WHY
* 파일 전송 UI(Dialog)와 비즈니스 로직(Service)의 분리 (MVP 패턴)
* 전송 상태에 대한 정밀한 제어 및 사용자 피드백(속도, 남은 시간) 제공 필요
* 스레드 기반의 비동기 작업 관리

## WHAT
* FileTransferDialog(View)와 FileTransferService(Model) 연결
* 전송 속도 및 남은 시간(ETA) 계산 로직
* 전송 시작/취소/완료/에러 이벤트 핸들링

## HOW
* QThreadPool을 사용한 비동기 엔진 실행
* QDateTime을 이용한 시간 경과 측정 및 통계 계산
* DTO를 통한 데이터 흐름 제어
"""
from PyQt5.QtCore import QObject, QDateTime, QThreadPool

from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService
from view.dialogs.file_transfer_dialog import FileTransferDialog
from core.logger import logger
from common.dtos import (
    FileProgressState,
    FileErrorEvent,
    FileCompletionEvent
)


class FilePresenter(QObject):
    """
    파일 전송 제어 Presenter 클래스

    View(Dialog)의 이벤트를 처리하고 Model(Engine)을 제어하며,
    계산된 진행 정보를 View에 업데이트합니다.
    """

    def __init__(self, connection_controller: ConnectionController):
        """
        FilePresenter 초기화

        Args:
            connection_controller (ConnectionController): 포트 제어 및 전송을 담당하는 컨트롤러.
        """
        super().__init__()
        self.connection_controller = connection_controller
        self.file_transfer_service: FileTransferService = None
        self.file_transfer_dialog: FileTransferDialog = None

        # 전송 대상 포트 (다이얼로그 열림 시점에 결정됨)
        self.target_port: str = None

        # 상태 변수 (속도 계산용)
        self._start_time = 0
        self._last_update_time = 0
        self._last_sent_bytes = 0

    def on_file_transfer_dialog_opened(self, dialog: FileTransferDialog, target_port: str) -> None:
        """
        파일 전송 Dialog가 열렸을 때 호출됩니다.
        View 연결 및 전송 컨텍스트(대상 포트)를 설정합니다.

        Args:
            dialog (FileTransferDialog): 열린 다이얼로그 인스턴스.
            target_port (str): 파일 전송을 수행할 대상 포트 이름.
        """
        self.file_transfer_dialog = dialog
        self.target_port = target_port

        if not self.target_port:
            logger.warning("File Transfer Dialog opened without active port context.")
            # 필요 시 다이얼로그에 경고 표시 가능

        # View 시그널 연결
        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)

        # 다이얼로그가 닫힐 때 참조 정리
        dialog.finished.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        """다이얼로그 종료 시 참조를 정리합니다."""
        self.file_transfer_dialog = None
        self.target_port = None

    def start_transfer(self, file_path: str) -> None:
        """
        파일 전송 시작 로직을 수행합니다.

        Logic:
            1. 타겟 포트 설정 확인
            2. 포트 연결 상태 재확인
            3. 포트 설정(PortConfig) 조회
            4. 전송 엔진(Service) 생성 및 DTO 주입
            5. 스레드 풀에서 엔진 비동기 실행

        Args:
            file_path (str): 전송할 파일 경로.
        """
        # 1. 타겟 포트 확인
        if not self.target_port:
            logger.error("File Transfer: No target port specified.")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, "No target port selected.")
            return

        # 2. 포트 연결 확인 (이중 체크)
        if not self.connection_controller.is_connection_open(self.target_port):
            logger.error(f"File Transfer: Target port {self.target_port} is not open.")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, "Port disconnected.")
            return

        # 3. 포트 설정(DTO) 가져오기
        port_config = self.connection_controller.get_connection_config(self.target_port)
        if not port_config:
            logger.error(f"Configuration not found for port {self.target_port}")
            return

        try:
            # 4. 엔진 생성 - DTO 전달
            self.file_transfer_service = FileTransferService(
                self.connection_controller,
                file_path,
                port_config
            )

            # 엔진 시그널 연결
            self.file_transfer_service.signals.progress_updated.connect(self._on_progress)
            self.file_transfer_service.signals.transfer_completed.connect(self._on_completed)
            self.file_transfer_service.signals.error_occurred.connect(self._on_error)

            # 상태 초기화
            self._start_time = QDateTime.currentMSecsSinceEpoch()
            self._last_update_time = self._start_time
            self._last_sent_bytes = 0

            # 5. 비동기 실행
            QThreadPool.globalInstance().start(self.file_transfer_service)
            logger.info(f"File transfer started: {file_path} -> {self.target_port}")

        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """사용자의 전송 취소 요청을 처리합니다."""
        if self.file_transfer_service:
            logger.info("Cancelling file transfer...")
            self.file_transfer_service.cancel()

    def _on_progress(self, state: FileProgressState) -> None:
        """
        진행률 업데이트 및 메트릭(속도, ETA) 계산 핸들러

        Logic:
            - 경과 시간 계산
            - 평균 전송 속도 계산 (총 전송량 / 총 경과시간)
            - 남은 시간(ETA) 추정 (남은 바이트 / 속도)
            - View 업데이트 메서드 호출 (DTO 전달)

        Args:
            state (FileProgressState): 모델에서 전달받은 상태 객체.
        """
        if not self.file_transfer_dialog:
            return

        # 속도 및 ETA 계산 로직
        current_time = QDateTime.currentMSecsSinceEpoch()
        elapsed_total_sec = (current_time - self._start_time) / 1000.0

        if elapsed_total_sec > 0:
            state.speed = state.sent_bytes / elapsed_total_sec

        if state.speed > 0:
            remaining_bytes = state.total_bytes - state.sent_bytes
            state.eta = remaining_bytes / state.speed

        # View 업데이트
        self.file_transfer_dialog.update_progress(state)

    def _on_completed(self, event: FileCompletionEvent) -> None:
        """
        전송 완료 처리 핸들러 (DTO 기반)

        Args:
            event (FileCompletionEvent): 완료 이벤트 DTO.
        """
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(event.success, event.message)

        # 서비스 참조 해제
        self.file_transfer_service = None

        if event.success:
            logger.info(f"File transfer completed: {event.file_path}")
        else:
            logger.warning(f"File transfer failed/cancelled: {event.message}")

    def _on_error(self, event: FileErrorEvent) -> None:
        """
        에러 발생 처리 핸들러 (DTO 기반)

        Args:
            event (FileErrorEvent): 에러 이벤트 DTO.
        """
        logger.error(f"File Transfer Error: {event.message}")

        # 엔진이 에러 발생 후 completed(False)를 호출하므로,
        # 여기서는 로깅을 수행하고 필요한 경우 다이얼로그에 상태를 반영합니다.
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(False, event.message)