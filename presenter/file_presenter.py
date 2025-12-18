"""
파일 프레젠터 모듈

파일 전송 로직, 속도 계산, ETA 산출을 담당하는 Presenter입니다.

## WHY
* 파일 전송 UI와 비즈니스 로직 분리
* 전송 상태에 대한 정밀한 제어 및 사용자 피드백 제공

## WHAT
* FileTransferDialog(View)와 FileTransferService(Model) 연결
* 전송 속도 및 남은 시간(ETA) 계산
* 전송 시작/취소/완료/에러 처리

## HOW
* QThreadPool을 사용한 비동기 엔진 실행
* QDateTime을 이용한 시간 경과 측정 및 통계 계산
"""
from PyQt5.QtCore import QObject, QDateTime, QThreadPool
from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService
from view.dialogs.file_transfer_dialog import FileTransferDialog
from core.logger import logger
from common.dtos import FileProgressState

class FilePresenter(QObject):
    """
    파일 전송 Presenter 클래스

    View(Dialog)의 이벤트를 처리하고 Model(Engine)을 제어하며,
    계산된 진행 정보를 View에 업데이트합니다.
    """

    def __init__(self, connection_controller: ConnectionController):
        """
        FilePresenter 초기화

        Args:
            connection_controller: 포트 제어기 Model (전송 담당)
        """
        super().__init__()
        self.connection_controller = connection_controller
        self.file_transfer_service: FileTransferService = None
        self.file_transfer_dialog: FileTransferDialog = None

        # 전송 대상 포트 (다이얼로그 열림 시점에 결정됨)
        self.target_port: str = None

        # 상태 변수
        self._start_time = 0
        self._last_update_time = 0
        self._last_sent_bytes = 0

    def on_file_transfer_dialog_opened(self, dialog: FileTransferDialog, target_port: str) -> None:
        """
        파일 전송 Dialog가 열렸을 때 호출 (View 연결 및 컨텍스트 설정)

        Args:
            dialog: FileTransferDialog 인스턴스
            target_port: 파일 전송을 수행할 대상 포트 이름
        """
        self.file_transfer_dialog = dialog
        self.target_port = target_port

        if not self.target_port:
            logger.warning("File Transfer Dialog opened without active port context.")
            # 다이얼로그에 경고 표시 또는 전송 버튼 비활성화 로직을 추가할 수 있음

        # View 시그널 연결
        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)

        # 다이얼로그가 닫힐 때 참조 정리 (선택적)
        dialog.finished.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        """다이얼로그 종료 시 정리"""
        self.file_transfer_dialog = None
        self.target_port = None

    def start_transfer(self, filepath: str) -> None:
        """
        파일 전송 시작 로직

        Logic:
            - 저장된 타겟 포트(target_port) 확인
            - 포트 설정(PortConfig) 조회
            - 전송 엔진 생성 (DTO 전달)
            - 스레드 풀에서 엔진 실행
        """
        # [Fix] 임의의 활성 포트가 아닌, 다이얼로그 호출 시점의 명시적 포트 사용
        if not self.target_port:
            logger.error("File Transfer: No target port specified.")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, "No target port selected.")
            return

        # 포트 연결 확인 (이중 체크)
        if not self.connection_controller.is_connection_open(self.target_port):
             logger.error(f"File Transfer: Target port {self.target_port} is not open.")
             if self.file_transfer_dialog:
                 self.file_transfer_dialog.set_complete(False, "Port disconnected.")
             return

        # 포트 설정(DTO) 가져오기
        port_config = self.connection_controller.get_connection_config(self.target_port)

        if not port_config:
             logger.error(f"Configuration not found for port {self.target_port}")
             return

        try:
            # 엔진 생성 - DTO 전달
            self.file_transfer_service = FileTransferService(
                self.connection_controller,
                filepath,
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

            # 비동기 실행
            QThreadPool.globalInstance().start(self.file_transfer_service)
            logger.info(f"File transfer started: {filepath} -> {self.target_port}")

        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.file_transfer_dialog:
                self.file_transfer_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """전송 취소 요청"""
        if self.file_transfer_service:
            logger.info("Cancelling file transfer...")
            self.file_transfer_service.cancel()

    def _on_progress(self, state: FileProgressState) -> None:
        """
        진행률 업데이트 및 메트릭 계산

        Logic:
            - 경과 시간 계산
            - 평균 전송 속도 계산 (Total Sent / Total Time)
            - 남은 시간(ETA) 추정 (Remaining Bytes / Speed)
            - View 업데이트 메서드 호출

        Args:
            state (FileProgressState): 모델에서 전달받은 상태 객체
        """
        if not self.file_transfer_dialog:
            return

        # 계산 로직 (속도/ETA 계산하여 DTO 업데이트)
        current_time = QDateTime.currentMSecsSinceEpoch()
        elapsed_total_sec = (current_time - self._start_time) / 1000.0

        if elapsed_total_sec > 0:
            state.speed = state.sent_bytes / elapsed_total_sec

        if state.speed > 0:
            remaining_bytes = state.total_bytes - state.sent_bytes
            state.eta = remaining_bytes / state.speed

        # View 업데이트
        self.file_transfer_dialog.update_progress(state)

    def _on_completed(self, success: bool) -> None:
        """
        전송 완료 처리

        Args:
            success: 성공 여부
        """
        if self.file_transfer_dialog:
            msg = "Transfer Completed" if success else "Transfer Failed"
            self.file_transfer_dialog.set_complete(success, msg)

        self.file_transfer_service = None

        if success:
            logger.info("File transfer completed successfully")
        else:
            logger.warning("File transfer failed or cancelled")

    def _on_error(self, msg: str) -> None:
        """
        에러 발생 처리

        Args:
            msg: 에러 메시지
        """
        logger.error(f"File Transfer Error: {msg}")
        # 엔진이 에러 발생 후 completed(False)를 호출하므로,
        # 여기서는 로깅 외에 별도 UI 처리는 _on_completed에 위임하거나
        # 구체적인 에러 메시지를 UI에 전달할 수 있음.
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(False, msg)
