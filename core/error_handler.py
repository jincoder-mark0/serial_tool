"""
전역 에러 핸들러 모듈

처리되지 않은 예외를 포착하여 애플리케이션의 안정성을 높입니다.

## WHY
* 예상치 못한 오류로 인해 애플리케이션이 비정상 종료되는 것을 방지합니다.
* 사용자에게 오류 발생을 명확히 알리고, 개발자가 디버깅할 수 있도록 상세 정보를 로깅합니다.
* UI 스레드가 아닌 다른 스레드에서 발생한 예외도 안전하게 처리합니다.

## WHAT
* `sys.excepthook`을 오버라이드하여 처리되지 않은 모든 예외를 가로챕니다.
* 예외 정보를 로그 파일에 `CRITICAL` 레벨로 기록합니다.
* PyQt의 시그널/슬롯 메커니즘을 사용하여 UI 스레드에서 안전하게 에러 다이얼로그를 표시합니다.
* `KeyboardInterrupt`는 기본 동작을 따르도록 예외 처리합니다.

## HOW
* `QObject`를 상속하고 `pyqtSignal`을 사용하여 스레드 간 안전한 통신을 구현합니다.
* `install_global_error_handler` 함수를 통해 애플리케이션 시작 시 핸들러를 등록합니다.
* `traceback` 모듈을 사용하여 상세한 스택 트레이스 정보를 포맷팅합니다.
"""
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
