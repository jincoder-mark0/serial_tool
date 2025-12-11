import sys
import traceback
from PyQt5.QtWidgets import QMessageBox, QApplication
from core.logger import logger

class GlobalErrorHandler:
    """
    전역 예외 처리기
    처리되지 않은 예외(Uncaught Exception)를 포착하여 로깅하고 사용자에게 알립니다.
    """

    def __init__(self):
        # 기존 excepthook 저장
        self._old_excepthook = sys.excepthook
        # 새 excepthook 등록
        sys.excepthook = self._handle_exception

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
            try:
                self._show_error_dialog(exc_type.__name__, str(exc_value), error_msg)
            except Exception as e:
                # 메시지 박스 표시 중 에러 발생 시 콘솔에 출력
                print(f"Failed to show error dialog: {e}", file=sys.stderr)
        else:
            print("Critical Error (No GUI):", error_msg, file=sys.stderr)

    def _show_error_dialog(self, error_type: str, error_message: str, traceback_str: str):
        """
        에러 다이얼로그 표시
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Critical Error")
        msg_box.setText(f"An unexpected error occurred: {error_type}")
        msg_box.setInformativeText(error_message)
        msg_box.setDetailedText(traceback_str)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

# 싱글톤 인스턴스 생성 (import 시 자동 등록되지 않음, 명시적 초기화 필요)
global_error_handler = None

def install_global_error_handler():
    global global_error_handler
    if global_error_handler is None:
        global_error_handler = GlobalErrorHandler()
        logger.info("Global error handler installed.")
