from PyQt5.QtCore import QObject, QTimer, QDateTime
from model.port_controller import PortController
from model.file_transfer import FileTransferEngine
from core.logger import logger
import os

class FilePresenter(QObject):
    """
    파일 전송 로직을 담당하는 Presenter
    """
    def __init__(self, port_controller: PortController):
        super().__init__()
        self.port_controller = port_controller
        self.current_engine = None
        self.current_dialog = None
        
    def on_file_transfer_dialog_opened(self, dialog) -> None:
        """
        파일 전송 다이얼로그가 열렸을 때 호출됩니다.
        """
        self.current_dialog = dialog
        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)
        
    def start_transfer(self, filepath: str) -> None:
        """파일 전송 시작"""
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

        # Baudrate 가져오기 (설정에서)
        # PortController는 설정을 직접 모르므로, Worker나 Transport에서 가져와야 하는데
        # 현재 구조상 PortController.workers[port_name].transport.baudrate 접근이 필요하거나
        # SettingsManager를 사용해야 함.
        # 여기서는 SettingsManager를 사용하는 것이 안전.
        from core.settings_manager import SettingsManager
        settings = SettingsManager()
        baudrate = settings.get('settings.port_baudrate', 115200)

        try:
            # 엔진 생성 및 시작
            self.current_engine = FileTransferEngine(self.port_controller, port_name, filepath, baudrate)
            
            # 시그널 연결
            self.current_engine.signals.progress_updated.connect(self._on_progress)
            self.current_engine.signals.transfer_completed.connect(self._on_completed)
            self.current_engine.signals.error_occurred.connect(self._on_error)
            
            # QRunnable이므로 QThreadPool에서 실행해야 함
            from PyQt5.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self.current_engine)
            
            logger.info(f"File transfer started: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to start file transfer: {e}")
            if self.current_dialog:
                self.current_dialog.set_complete(False, str(e))

    def cancel_transfer(self) -> None:
        """전송 취소"""
        if self.current_engine:
            self.current_engine.cancel()
            
    def _on_progress(self, sent: int, total: int) -> None:
        """진행률 업데이트"""
        if self.current_dialog:
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
            
            if elapsed_sec > 0:
                speed = sent / elapsed_sec
                if speed > 0:
                    remaining = total - sent
                    eta = remaining / speed
                    
            self.current_dialog.update_progress(sent, total, speed, eta)

    def _on_completed(self, success: bool) -> None:
        """완료 처리"""
        if self.current_dialog:
            msg = "Finished" if success else "Failed"
            self.current_dialog.set_complete(success, msg)
        self.current_engine = None
        if hasattr(self, '_transfer_start_time'):
            del self._transfer_start_time

    def _on_error(self, msg: str) -> None:
        """에러 처리"""
        logger.error(f"File Transfer Error: {msg}")
        # _on_completed에서 처리됨 (Engine이 error 후 completed emit)
