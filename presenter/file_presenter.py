"""
파일 프레젠터 모듈

파일 전송 로직, 속도 계산, ETA 산출을 담당하는 Presenter입니다.

## WHY
* 파일 전송 UI와 비즈니스 로직(계산, 흐름 제어) 분리
* 전송 상태에 대한 정밀한 제어 및 사용자 피드백 제공
* MVP 패턴 준수

## WHAT
* FileTransferDialog(View)와 FileTransferEngine(Model) 연결
* 전송 속도 및 남은 시간(ETA) 계산 알고리즘 구현
* 전송 시작/취소/완료/에러 처리 루틴

## HOW
* QThreadPool을 사용한 비동기 엔진 실행
* QDateTime을 이용한 시간 경과 측정
* Signal/Slot을 통한 이벤트 기반 통신
"""
from PyQt5.QtCore import QObject, QDateTime, QThreadPool
from model.port_controller import PortController
from model.file_transfer import FileTransferEngine
from view.dialogs.file_transfer_dialog import FileTransferDialog
from core.logger import logger

class FilePresenter(QObject):
    """
    파일 전송 Presenter 클래스

    View(Dialog)의 이벤트를 처리하고 Model(Engine)을 제어하며,
    계산된 진행 정보를 View에 업데이트합니다.
    """

    def __init__(self, port_controller: PortController):
        """
        FilePresenter 초기화

        Args:
            port_controller: 포트 제어기 Model (전송 담당)
        """
        super().__init__()
        self.port_controller = port_controller
        self.current_engine: FileTransferEngine = None
        self.current_dialog: FileTransferDialog = None

        # 상태 변수
        self._start_time = 0
        self._last_update_time = 0
        self._last_sent_bytes = 0

    def on_file_transfer_dialog_opened(self, dialog: FileTransferDialog) -> None:
        """
        파일 전송 Dialog가 열렸을 때 호출 (View 연결)

        Args:
            dialog: FileTransferDialog 인스턴스
        """
        self.current_dialog = dialog

        # View 시그널 연결
        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)

        # 다이얼로그가 닫힐 때 참조 정리 (선택적)
        dialog.finished.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        """다이얼로그 종료 시 정리"""
        self.current_dialog = None

    def start_transfer(self, filepath: str) -> None:
        """
        파일 전송 시작 로직

        Logic:
            - 포트 연결 상태 확인
            - 전송 파라미터(Baudrate, FlowControl) 로드
            - 전송 엔진 생성 및 초기화
            - 상태 변수(시간, 바이트) 초기화
            - 스레드 풀에서 엔진 실행

        Args:
            filepath: 전송할 파일 경로
        """
        if not self.port_controller.is_open:
            logger.warning("File Transfer: Port not open")
            if self.current_dialog:
                self.current_dialog.set_complete(False, "Port not open")
            return

        port_name = self.port_controller.current_port_name
        if not port_name:
            if self.current_dialog:
                self.current_dialog.set_complete(False, "No active port")
            return

        # 포트 설정 가져오기
        port_config = self.port_controller.get_port_config(port_name)
        baudrate = port_config.get('baudrate', 115200)
        flow_control = port_config.get('flowctrl', 'None')

        try:
            # 엔진 생성
            self.current_engine = FileTransferEngine(
                self.port_controller,
                port_name,
                filepath,
                baudrate,
                flow_control
            )

            # 엔진 시그널 연결
            self.current_engine.signals.progress_updated.connect(self._on_progress)
            self.current_engine.signals.transfer_completed.connect(self._on_completed)
            self.current_engine.signals.error_occurred.connect(self._on_error)

            # 상태 초기화
            self._start_time = QDateTime.currentMSecsSinceEpoch()
            self._last_update_time = self._start_time
            self._last_sent_bytes = 0

            # 비동기 실행
            QThreadPool.globalInstance().start(self.current_engine)
            logger.info(f"File transfer started: {filepath} (Baud: {baudrate}, Flow: {flow_control})")

        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.current_dialog:
                self.current_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """전송 취소 요청"""
        if self.current_engine:
            logger.info("Cancelling file transfer...")
            self.current_engine.cancel()

    def _on_progress(self, sent: int, total: int) -> None:
        """
        진행률 업데이트 및 메트릭 계산

        Logic:
            - 경과 시간 계산
            - 평균 전송 속도 계산 (Total Sent / Total Time)
            - 남은 시간(ETA) 추정 (Remaining Bytes / Speed)
            - View 업데이트 메서드 호출

        Args:
            sent: 전송된 바이트 수
            total: 전체 바이트 수
        """
        if not self.current_dialog:
            return

        current_time = QDateTime.currentMSecsSinceEpoch()
        elapsed_total_sec = (current_time - self._start_time) / 1000.0

        # 속도 계산 (평균 속도)
        speed = 0.0
        if elapsed_total_sec > 0:
            speed = sent / elapsed_total_sec

        # ETA 계산
        eta = 0.0
        if speed > 0:
            remaining_bytes = total - sent
            eta = remaining_bytes / speed

        # View 업데이트 (수동적인 뷰)
        self.current_dialog.update_progress(sent, total, speed, eta)

    def _on_completed(self, success: bool) -> None:
        """
        전송 완료 처리

        Args:
            success: 성공 여부
        """
        if self.current_dialog:
            msg = "Transfer Completed" if success else "Transfer Failed"
            self.current_dialog.set_complete(success, msg)

        self.current_engine = None

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
        if self.current_dialog:
            self.current_dialog.set_complete(False, msg)
