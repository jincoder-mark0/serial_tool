import sys
import traceback
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger

class GlobalErrorHandler(QObject):
    """
    전역 예외 처리기
    처리되지 않은 예외(Uncaught Exception)를 포착하여 로깅하고 사용자에게 알립니다.
    QObject를 상속받아 시그널/슬롯을 통해 UI 스레드에서 메시지 박스를 표시합니다.
    """
    # UI 스레드에서 다이얼로그를 띄우기 위한 시그널
    show_error_signal = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        # 기존 excepthook 저장
        self._old_excepthook = sys.excepthook
        # 새 excepthook 등록
        sys.excepthook = self._handle_exception
        
        # 시그널 연결 (QueuedConnection으로 동작하여 UI 스레드에서 실행됨)
        self.show_error_signal.connect(self._show_error_dialog)

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        예외 처리 핸들러
        """
        # KeyboardInterrupt는 기본 동작(종료)을 따름
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # 에러 메시지 포맷팅
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # 로깅
        logger.critical(f"Uncaught exception:\n{error_msg}")

        # UI 스레드에서 메시지 박스 표시 (QApplication이 실행 중일 때만)
        if QApplication.instance():
            # 시그널을 통해 메인 스레드로 전달
            self.show_error_signal.emit(exc_type.__name__, str(exc_value), error_msg)
        else:
            print("Critical Error (No GUI):", error_msg, file=sys.stderr)

    def _show_error_dialog(self, error_type: str, error_message: str, traceback_str: str):
        """
        에러 다이얼로그 표시 (메인 스레드에서 실행됨)
        """
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Critical Error")
            msg_box.setText(f"An unexpected error occurred: {error_type}")
            msg_box.setInformativeText(error_message)
            msg_box.setDetailedText(traceback_str)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
        except Exception as e:
            # 다이얼로그 표시 실패 시 콘솔 출력
            print(f"Failed to show error dialog: {e}", file=sys.stderr)

# 싱글톤 인스턴스 생성 (import 시 자동 등록되지 않음, 명시적 초기화 필요)
global_error_handler = None

def install_global_error_handler():
    global global_error_handler
    if global_error_handler is None:
        global_error_handler = GlobalErrorHandler()
        logger.info("Global error handler installed.")
