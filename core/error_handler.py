"""
전역 에러 핸들러 모듈

처리되지 않은 예외를 포착하여 애플리케이션의 안정성을 높입니다.

## WHY
* 예상치 못한 오류로 인해 애플리케이션이 비정상 종료되는 것을 방지합니다.
* Main Thread뿐만 아니라 Worker Thread의 예외도 통합 관리합니다.
* try-except 블록 내에서도 치명적 오류를 전역 핸들러로 보고할 수단이 필요합니다.

## WHAT
* `sys.excepthook` 및 `threading.excepthook` 오버라이딩
* 예외 로깅 (CRITICAL 레벨)
* UI 알림창 표시 (Signal/Slot 기반 Thread-safe)
* 수동 에러 보고 메서드(`report_error`) 제공

## HOW
* QObject 상속 및 Signal 사용
* traceback 모듈로 스택 트레이스 추출
"""
import sys
import threading
import traceback
from typing import Type, Optional
from types import TracebackType
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger

class GlobalErrorHandler(QObject):
    """
    전역 예외 처리기

    메인 스레드 및 백그라운드 스레드의 처리되지 않은 예외를 포착합니다.
    """
    # UI 스레드에서 다이얼로그를 띄우기 위한 시그널
    show_error_signal = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        # 1. Main Thread 예외 훅
        self._old_excepthook = sys.excepthook
        sys.excepthook = self._handle_sys_exception

        # 2. Worker Thread 예외 훅 (Python 3.8+)
        # 기존 threading.excepthook이 있다면 저장 (보통 기본값은 sys.stderr 출력)
        self._old_threading_excepthook = threading.excepthook
        threading.excepthook = self._handle_threading_exception

        # 시그널 연결 (QueuedConnection으로 동작하여 UI 스레드에서 실행됨)
        self.show_error_signal.connect(self._show_error_dialog)

    def report_error(self, exc_type: Type[BaseException], exc_value: BaseException, tb: Optional[TracebackType]) -> None:
        """
        수동으로 예외를 보고하는 메서드

        try-except 블록 내에서 잡힌 예외라도, 전역적으로 알릴 필요가 있을 때 사용합니다.

        Args:
            exc_type: 예외 타입
            exc_value: 예외 인스턴스
            tb: 트레이스백 객체
        """
        self._process_exception(exc_type, exc_value, tb)

    def _handle_sys_exception(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: Optional[TracebackType]
    ) -> None:
        """
        예외 처리 핸들러

        Logic:
            - KeyboardInterrupt는 기존 훅으로 전달하여 정상적인 종료 흐름 유지
            - 그 외 예외는 로깅 후 사용자에게 알림창 표시

        Args:
            exc_type: 예외 타입
            exc_value: 예외 인스턴스
            exc_traceback: 트레이스백 객체
        """
        # KeyboardInterrupt는 기본 동작(또는 이전 훅)을 따름
        # sys.__excepthook__ 대신 저장된 _old_excepthook을 호출하여
        # 이전에 설치된 다른 핸들러가 무시되지 않도록 보장함
        if issubclass(exc_type, KeyboardInterrupt):
            if self._old_excepthook:
                self._old_excepthook(exc_type, exc_value, exc_traceback)
            else:
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self._process_exception(exc_type, exc_value, exc_traceback)

    def _handle_threading_exception(self, args) -> None:
        """
        threading.excepthook 핸들러 (Worker Threads)

        Args:
            args: (exc_type, exc_value, exc_traceback, thread)를 포함하는 네임드 튜플
        """
        if issubclass(args.exc_type, KeyboardInterrupt):
            if self._old_threading_excepthook:
                self._old_threading_excepthook(args)
            return

        logger.critical(f"Exception in thread {args.thread.name}:")
        self._process_exception(args.exc_type, args.exc_value, args.exc_traceback)

    def _process_exception(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: Optional[TracebackType]
    ) -> None:
        """공통 예외 처리 로직 (로깅 및 UI 알림 요청)"""
        # 에러 메시지 포맷팅
        try:
            error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        except Exception:
            error_msg = f"{exc_type.__name__}: {exc_value} (Traceback format failed)"

        # 로깅 (CRITICAL 레벨)
        logger.critical(f"Uncaught exception:\n{error_msg}")

        # UI 스레드에서 메시지 박스 표시 (QApplication이 실행 중일 때만)
        if QApplication.instance():
            # 시그널을 통해 메인 스레드로 전달
            self.show_error_signal.emit(exc_type.__name__, str(exc_value), error_msg)
        else:
            # GUI가 없는 경우 콘솔에 출력
            print("Critical Error (No GUI):", error_msg, file=sys.stderr)

    @staticmethod
    def _show_error_dialog(error_type: str, error_message: str, traceback_str: str) -> None:
        """
        에러 다이얼로그 표시 (메인 스레드에서 실행됨)

        Args:
            error_type: 에러 클래스 이름
            error_message: 에러 메시지
            traceback_str: 전체 스택 트레이스 문자열
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
            # 다이얼로그 표시 실패 시 콘솔 출력 (최후의 수단)
            print(f"Failed to show error dialog: {e}", file=sys.stderr)

# 싱글톤 인스턴스 변수
global_error_handler: Optional[GlobalErrorHandler] = None

def install_global_error_handler() -> None:
    """전역 에러 핸들러를 설치합니다."""
    global global_error_handler
    if global_error_handler is None:
        global_error_handler = GlobalErrorHandler()
        logger.info("Global error handler installed (Sys & Threading hooks).")

def get_error_handler() -> Optional[GlobalErrorHandler]:
    """핸들러 인스턴스 반환 (수동 호출용)"""
    return global_error_handler