"""
파일 프레젠터 모듈

파일 전송 로직을 담당하는 Presenter입니다.

## WHY
* 파일 전송 UI와 비즈니스 로직 분리
* 전송 진행률 및 속도 계산
* 에러 처리 및 사용자 피드백
* Thread Pool 기반 비동기 전송 관리

## WHAT
* FileTransferDialog(View)와 FileTransferEngine(Model) 연결
* 파일 전송 시작/취소 처리
* 진행률, 속도, ETA 계산 및 UI 업데이트
* 전송 완료/실패 처리

## HOW
* QThreadPool로 FileTransferEngine 실행
* Signal/Slot으로 진행률 업데이트
* QDateTime으로 경과 시간 및 속도 계산
* PortController를 통한 데이터 전송
"""
from PyQt5.QtCore import QObject, QDateTime, QThreadPool
from model.port_controller import PortController
from model.file_transfer import FileTransferEngine
from core.logger import logger

class FilePresenter(QObject):
    """
    파일 전송 Presenter

    FileTransferDialog와 FileTransferEngine을 연결하여 파일 전송을 관리합니다.
    """
    def __init__(self, port_controller: PortController):
        """
        FilePresenter 초기화

        Args:
            port_controller: 포트 제어기 Model
        """
        super().__init__()
        self.port_controller = port_controller
        self.current_engine = None
        self.current_dialog = None

    def on_file_transfer_dialog_opened(self, dialog) -> None:
        """
        파일 전송 Dialog가 열렸을 때 호출

        Args:
            dialog: FileTransferDialog 인스턴스
        """
        self.current_dialog = dialog
        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)

    def start_transfer(self, filepath: str) -> None:
        """
        파일 전송 시작

        Logic:
            - 포트 열림 상태 확인
            - Baudrate 및 Flow Control 설정 로드
            - FileTransferEngine 생성 및 Signal 연결
            - QThreadPool에서 비동기 실행
            - 전송 시작 시간 기록

        Args:
            filepath: 전송할 파일 경로
        """
        if not self.port_controller.is_open:
            logger.warning("Port not open")
            if self.current_dialog:
                self.current_dialog.set_complete(False, "Port not open")
            return

        port_name = self.port_controller.current_port_name
        if not port_name:
            if self.current_dialog:
                self.current_dialog.set_complete(False, "No active port")
            return

        # Baudrate 및 FlowControl 가져오기 (PortController에서 조회)
        port_config = self.port_controller.get_port_config(port_name)
        baudrate = port_config.get('baudrate', 115200)
        flow_control = port_config.get('flowctrl', 'None')

        try:
            # Engine 생성 및 시작 (Flow Control 정보 전달)
            self.current_engine = FileTransferEngine(
                self.port_controller,
                port_name,
                filepath,
                baudrate,
                flow_control
            )

            # Signal 연결
            self.current_engine.signals.progress_updated.connect(self._on_progress)
            self.current_engine.signals.transfer_completed.connect(self._on_completed)
            self.current_engine.signals.error_occurred.connect(self._on_error)

            # QThreadPool에서 실행 (QRunnable)
            QThreadPool.globalInstance().start(self.current_engine)

            logger.info(f"File transfer started: {filepath} (Flow: {flow_control})")

        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.current_dialog:
                self.current_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """전송 취소"""
        if self.current_engine:
            self.current_engine.cancel()

    def _on_progress(self, sent: int, total: int) -> None:
        """
        진행률 업데이트

        Logic:
            - 전송 시작 시간 기록 (최초 1회)
            - 경과 시간 계산
            - 전송 속도 계산 (bytes/sec)
            - 남은 시간(ETA) 계산
            - Dialog에 업데이트 전달

        Args:
            sent: 전송된 바이트 수
            total: 전체 바이트 수
        """
        if self.current_dialog:
            # 전송 시작 시간 기록 (최초 1회)
            # 속도 및 ETA 계산은 여기서 하거나 Engine에서 해서 보내줄 수 있음
            # Engine은 raw bytes만 보내므로 여기서 계산 필요
            # 하지만 Engine이 start_time을 가지고 있지 않다면 여기서 계산해야 함
            # 간단하게 Dialog에 raw data만 넘기고 Dialog가 계산하게 하거나
            # 여기서 계산해서 넘김.

            # 편의상 여기서는 단순 전달 (Dialog가 계산 로직을 가지고 있다고 가정하거나,
            # MainPresenter의 로직을 가져와야 함)

            # MainPresenter의 로직을 가져오자니 state가 필요함 (start_time 등)
            # FileTransferEngine이 start_time을 가지고 있지 않음.
            # FileTransferEngine을 수정하여 start_time을 가지게 하거나
            # 여기서 관리해야 함.

            # 일단 단순화하여 sent, total만 전달 (Dialog 인터페이스 확인 필요)
            # MainPresenter를 보면 update_progress(sent, total, speed, eta)를 호출함.

            # 속도 계산을 위해 start_time 기록 필요
            if not hasattr(self, '_transfer_start_time'):
                self._transfer_start_time = QDateTime.currentMSecsSinceEpoch()

            current_time = QDateTime.currentMSecsSinceEpoch()
            elapsed_sec = (current_time - self._transfer_start_time) / 1000.0

            speed = 0.0
            eta = 0.0

            # 속도 및 ETA 계산
            if elapsed_sec > 0:
                speed = sent / elapsed_sec  # bytes/sec
                if speed > 0:
                    remaining = total - sent
                    eta = remaining / speed  # seconds

            self.current_dialog.update_progress(sent, total, speed, eta)

    def _on_completed(self, success: bool) -> None:
        """
        전송 완료 처리

        Args:
            success: 성공 여부
        """
        if self.current_dialog:
            msg = "Finished" if success else "Failed"
            self.current_dialog.set_complete(success, msg)
        self.current_engine = None
        if hasattr(self, '_transfer_start_time'):
            del self._transfer_start_time

    @staticmethod
    def _on_error(msg: str) -> None:
        """
        에러 처리

        Args:
            msg: 에러 메시지
        """
        logger.error(f"File Transfer Error: {msg}")
        # _on_completed에서 처리됨 (Engine이 error 후 completed emit)
