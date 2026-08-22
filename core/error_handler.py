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
* DTO(ErrorContext)를 사용하여 에러 정보 전달
* 다이얼로그 문구는 조립 계층(main.py)이 콜백으로 주입 (core는 번역을 모른다, S-056)
"""
import sys
import threading
import traceback
import time
from typing import Type, Optional, Callable, Tuple
from types import TracebackType
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger
from common.dtos import ErrorContext

# 다이얼로그 문구(제목, 메시지 템플릿)를 돌려주는 콜백 타입.
# core는 view/language_manager를 모른 채로 지내고, 조립 계층(main.py)이 호출 시점마다
# 최신 언어로 문구를 계산해 돌려준다 - 문자열을 한 번만 주입하지 않고 콜백을 받는 이유는
# 앱 실행 중 언어를 바꿔도 "다음 크래시"부터 즉시 새 언어가 반영되게 하기 위함이다(S-056).
MessageProvider = Callable[[], Tuple[str, str]]

# 콜백이 주입되지 않았거나(라이브러리 사용/테스트) 콜백 자체가 실패했을 때(손상된 상태)
# 쓰는 최후의 안전망. core는 항상 이 값만으로도 정상 동작해야 한다.
_FALLBACK_TITLE = "Critical Error"
_FALLBACK_MESSAGE_TEMPLATE = "An unexpected error occurred: {0}"

class GlobalErrorHandler(QObject):
    """
    전역 예외 처리기

    메인 스레드 및 백그라운드 스레드의 처리되지 않은 예외를 포착합니다.
    """
    # UI 스레드에서 다이얼로그를 띄우기 위한 시그널
    show_error_signal = pyqtSignal(object)

    def __init__(self, message_provider: Optional[MessageProvider] = None):
        """
        Args:
            message_provider: 다이얼로그 (제목, 메시지 템플릿)을 돌려주는 콜백.
                None이면 영어 하드코딩 폴백을 그대로 사용한다(손상 상태·테스트 안전).
        """
        super().__init__()
        self._message_provider = message_provider
        # 1. Main Thread 예외 훅
        self._old_excepthook = sys.excepthook
        sys.excepthook = self._handle_sys_exception

        # 2. Worker Thread 예외 훅 (Python 3.8+)
        # 기존 threading.excepthook이 있다면 저장 (보통 기본값은 sys.stderr 출력)
        self._old_threading_excepthook = threading.excepthook
        threading.excepthook = self._handle_threading_exception

        # 시그널 연결 (QueuedConnection으로 동작하여 UI 스레드에서 실행됨)
        self.show_error_signal.connect(self._show_error_dialog)

    def set_message_provider(self, message_provider: Optional[MessageProvider]) -> None:
        """
        다이얼로그 문구 콜백을 교체합니다.

        installed 시점에는 아직 LanguageManager가 준비되지 않았을 수 있으므로,
        조립 계층(main.py)이 초기화를 마친 뒤 이 메서드로 나중에 주입한다.

        Args:
            message_provider: 다이얼로그 (제목, 메시지 템플릿)을 돌려주는 콜백. None이면
                영어 하드코딩 폴백으로 되돌린다.
        """
        self._message_provider = message_provider

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

        # DTO 생성
        error_context = ErrorContext(
            error_type=exc_type.__name__,
            message=str(exc_value),
            traceback=error_msg,
            timestamp=time.time()
        )

        # UI 스레드에서 메시지 박스 표시 (QApplication이 실행 중일 때만)
        if QApplication.instance():
            # 시그널을 통해 메인 스레드로 전달
            self.show_error_signal.emit(error_context)
        else:
            # GUI가 없는 경우 콘솔에 출력
            print("Critical Error (No GUI):", error_msg, file=sys.stderr)

    def _show_error_dialog(self, context: ErrorContext) -> None:
        """
        에러 다이얼로그 표시 (메인 스레드에서 실행됨)

        Args:
            context (ErrorContext): 에러 정보 DTO
        """
        # 다이얼로그 문구는 조립 계층이 주입한 콜백(self._message_provider)으로 얻는다.
        # core는 view/language_manager를 모른다(S-056) - 콜백이 없거나(주입 전/테스트/
        # 라이브러리 사용) 콜백 호출 자체가 실패하면(손상된 상태, 깨진 언어 리소스 등)
        # 아래 영어 하드코딩 폴백으로 조용히 떨어진다. 이 다이얼로그는 손상된 상태에서도
        # 반드시 떠야 하는 최후의 안전망이기 때문이다.
        title = _FALLBACK_TITLE
        text = _FALLBACK_MESSAGE_TEMPLATE.format(context.error_type)
        if self._message_provider is not None:
            try:
                title, message_template = self._message_provider()
                text = message_template.format(context.error_type)
            except Exception:
                pass  # 콜백 실패 - 위에서 이미 설정한 영어 폴백을 그대로 사용

        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(text)
            msg_box.setInformativeText(context.message)
            msg_box.setDetailedText(context.traceback)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
        except Exception as e:
            # 다이얼로그 표시 실패 시 콘솔 출력 (최후의 수단)
            print(f"Failed to show error dialog: {e}", file=sys.stderr)

# 싱글톤 인스턴스 변수
global_error_handler: Optional[GlobalErrorHandler] = None

def install_global_error_handler(message_provider: Optional[MessageProvider] = None) -> None:
    """
    전역 에러 핸들러를 설치합니다.

    이미 설치되어 있으면 훅은 재설치하지 않고(idempotent), message_provider가
    주어졌다면 기존 인스턴스의 문구 콜백만 갱신한다.

    Args:
        message_provider: 다이얼로그 (제목, 메시지 템플릿) 콜백. 생략하면 영어
            하드코딩 폴백이 기본값으로 남는다(손상 상태·테스트·라이브러리 사용 시 안전).
    """
    global global_error_handler
    if global_error_handler is None:
        global_error_handler = GlobalErrorHandler(message_provider)
        logger.info("Global error handler installed (Sys & Threading hooks).")
    elif message_provider is not None:
        global_error_handler.set_message_provider(message_provider)

def set_error_message_provider(message_provider: Optional[MessageProvider]) -> None:
    """
    이미 설치된 전역 에러 핸들러의 다이얼로그 문구 콜백을 교체합니다.

    설치(훅 등록) 자체는 main.py 초기화 초반(LanguageManager보다 먼저)에 이뤄지지만,
    문구 콜백은 LanguageManager가 준비된 뒤 별도로 주입해야 하므로 분리한다(S-056).
    핸들러가 아직 설치되지 않았다면 아무 일도 하지 않는다.

    Args:
        message_provider: 다이얼로그 (제목, 메시지 템플릿) 콜백. None이면 영어
            하드코딩 폴백으로 되돌린다.
    """
    if global_error_handler is not None:
        global_error_handler.set_message_provider(message_provider)

def get_error_handler() -> Optional[GlobalErrorHandler]:
    """핸들러 인스턴스 반환 (수동 호출용)"""
    return global_error_handler
