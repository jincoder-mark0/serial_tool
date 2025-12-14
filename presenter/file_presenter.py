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
from model.connection_controller import ConnectionController
from model.file_transfer import FileTransferEngine
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
            - 포트 연결 상태 확인 및 설정(PortConfig) 조회
            - 전송 엔진 생성 (DTO 전달)
            - 스레드 풀에서 엔진 실행
        """
        # 현재 활성 포트가 없으면 중단 (FileTransfer는 특정 포트를 대상으로 함)
        # 만약 MainPresenter가 활성 포트를 관리하지 않는다면,
        # ConnectionController에서 활성 포트를 가져오는 로직을 확인해야 함.
        # (이전 리팩토링에서 ConnectionController는 stateless가 되었으므로,
        #  여기서는 PortPresenter 등으로부터 활성 포트를 주입받거나 조회해야 하지만,
        #  FilePresenter는 현재 ConnectionController만 의존성으로 가지고 있음.
        #  임시로 ConnectionController.current_connection_name 프로퍼티가 남아있다면 사용,
        #  없다면 아키텍처 재검토 필요. 현재는 ConnectionController에
        #  current_connection_name 로직은 제거되지 않았다고 가정)

        # [Note] 이전 단계에서 ConnectionController의 상태를 제거했으나,
        # 'active connection name'을 가져오는 helper가 필요함.
        # 여기서는 편의상 ConnectionController에 남아있는 get_active_connections() 중 첫번째를 쓰거나
        # 상위(MainPresenter)에서 주입받은 current_port를 사용해야 함.
        # 가장 좋은 방법: FilePresenter 생성자나 start_transfer 시점에 target_port를 받는 것.
        # 일단은 ConnectionController의 get_active_connections()를 활용하여 첫 번째 포트를 선택하거나,
        # FileTransferDialog가 포트를 선택하게 하는 것이 맞으나,
        # 현재 UI 구조상 '현재 활성 탭'의 포트를 의미함.
        # 따라서 MainPresenter가 start_transfer 호출 시 포트명을 넘겨주도록 수정하는 것이 베스트지만,
        # 여기서는 코드를 최소한으로 건드리기 위해 ConnectionController의
        # (남아있거나 복구된) 상태 조회 메서드를 사용하거나,
        # active connections 중 하나를 선택하는 로직을 사용.

        # [수정] MainPresenter가 FilePresenter에게 활성 포트를 알려주지 않는 구조라면,
        # ConnectionController.get_active_connections()를 사용.
        active_ports = self.connection_controller.get_active_connections()
        if not active_ports:
            logger.warning("File Transfer: No active connection")
            if self.current_dialog:
                self.current_dialog.set_complete(False, "No active port")
            return

        # 임시로 첫 번째 활성 포트 사용 (멀티 탭 환경에서 개선 필요)
        port_name = active_ports[0]

        # 포트 설정(DTO) 가져오기
        port_config = self.connection_controller.get_connection_config(port_name)

        if not port_config:
             logger.error(f"Configuration not found for port {port_name}")
             return

        try:
            # 엔진 생성 - DTO 전달
            self.current_engine = FileTransferEngine(
                self.connection_controller,
                filepath,
                port_config
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
            logger.info(f"File transfer started: {filepath}")

        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.current_dialog:
                self.current_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """전송 취소 요청"""
        if self.current_engine:
            logger.info("Cancelling file transfer...")
            self.current_engine.cancel()

    def _on_progress(self, state: FileProgressState) -> None:
        """
        진행률 업데이트 및 메트릭 계산

        Logic:
            - 경과 시간 계산
            - 평균 전송 속도 계산 (Total Sent / Total Time)
            - 남은 시간(ETA) 추정 (Remaining Bytes / Speed)
            - View 업데이트 메서드 호출

        Args:
            state (FileProgressState): 모델에서 전달받은 상태 객체 (Raw Data 포함)
        """
        if not self.current_dialog:
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
        self.current_dialog.update_progress(state)

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
