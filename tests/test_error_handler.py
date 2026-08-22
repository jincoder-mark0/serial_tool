"""
S-045 커버리지 테스트: GlobalErrorHandler (core/error_handler.py)

## WHY
* `core/error_handler.py`는 기존 테스트가 0건이었다. `sys.excepthook`/
  `threading.excepthook`을 실제로 덮어쓰는 전역 부작용이 있는 모듈이라, 검증
  없이 방치하면 훅이 실제로 설치되는지, KeyboardInterrupt를 이전 훅으로
  올바르게 위임하는지, 로깅이 실제로 일어나는지 확신할 수 없다.
* 동시에 이 모듈은 프로세스 전역 상태(sys.excepthook, threading.excepthook,
  모듈 싱글톤 `global_error_handler`)를 건드리므로, 테스트가 실제
  `sys.excepthook`을 오염시킨 채 끝나면 이후 실행되는 다른 테스트나 pytest
  자체의 예외 보고가 깨질 수 있다 — 그래서 모든 테스트는 설치 전 상태를
  저장했다가 반드시 복원한다(clean_error_handler_state fixture).
* `QMessageBox.exec_()`는 실제로 호출하면 사용자 입력을 기다리며 블로킹되어
  offscreen 테스트 환경에서 멈춘다 — `_show_error_dialog`를 몽키패치해
  실제 다이얼로그를 띄우지 않고 호출 여부/인자만 검증한다.

## WHAT
* `install_global_error_handler()`가 `sys.excepthook`/`threading.excepthook`을
  실제로 설치하는지, 두 번 호출해도 싱글톤을 유지하는지(idempotent).
* 설치된 훅을 통해(또는 `report_error()`로 수동) 예외가 들어오면
  CRITICAL 레벨로 로깅되고, UI 다이얼로그 콜백(`show_error_signal`)이
  올바른 `ErrorContext`와 함께 호출되는지.
* KeyboardInterrupt는 정상 처리 경로를 타지 않고 "이전에 설치돼 있던 훅"으로
  위임되는지 (로깅/다이얼로그 없음).
* QApplication이 없는 경우 콘솔(stderr) 출력 경로로 폴백하는지.

## HOW
* `clean_error_handler_state` fixture가 테스트 전후로 `sys.excepthook`,
  `threading.excepthook`, `core.error_handler.global_error_handler`를
  저장/복원한다 — 설치→검증→복원을 항상 보장.
* `GlobalErrorHandler._show_error_dialog`를 인스턴스 생성 전에 몽키패치하여
  실제 QMessageBox.exec_() 호출을 막는다.
"""
import sys
import threading
import types
from pathlib import Path

import pytest

import core.error_handler as error_handler_module
from core.error_handler import (
    GlobalErrorHandler,
    install_global_error_handler,
    get_error_handler,
)

# clean_error_handler_state fixture가 매 테스트마다 GlobalErrorHandler._show_error_dialog를
# 몽키패치로 가로채므로(QMessageBox.exec_() 블로킹 방지용), 문구 계산 로직 자체를 검증하는
# 테스트는 몽키패치되기 전(모듈 임포트 시점)에 잡아둔 이 원본 구현을 직접 호출한다.
_ORIGINAL_SHOW_ERROR_DIALOG = GlobalErrorHandler._show_error_dialog


def _install_fake_message_box(monkeypatch) -> dict:
    """
    core.error_handler.QMessageBox를 가짜 클래스로 교체하고, setWindowTitle/setText로
    들어온 값을 담을 dict를 반환한다.

    QMessageBox.Critical/Ok 같은 클래스 상수는 실제 값을 그대로 물려받아야
    `msg_box.setIcon(QMessageBox.Critical)` 호출이 AttributeError 없이 통과한다.
    """
    from PyQt5.QtWidgets import QMessageBox as _RealQMessageBox

    captured: dict = {}

    class _FakeMsgBox:
        Critical = _RealQMessageBox.Critical
        Ok = _RealQMessageBox.Ok

        def setIcon(self, *a): pass
        def setWindowTitle(self, title): captured["title"] = title
        def setText(self, text): captured["text"] = text
        def setInformativeText(self, *a): pass
        def setDetailedText(self, *a): pass
        def setStandardButtons(self, *a): pass
        def exec_(self): pass

    monkeypatch.setattr(error_handler_module, "QMessageBox", _FakeMsgBox)
    return captured


# -----------------------------------------------------------------------------
# Fixture: sys.excepthook / threading.excepthook / 모듈 싱글톤 오염 방지
# -----------------------------------------------------------------------------

@pytest.fixture
def clean_error_handler_state(monkeypatch):
    """
    설치 전 sys.excepthook/threading.excepthook/모듈 싱글톤을 저장했다가
    테스트 종료 시 반드시 원래 상태로 복원한다 (실제 sys.excepthook 오염 방지).
    """
    original_sys_hook = sys.excepthook
    original_threading_hook = threading.excepthook
    original_singleton = error_handler_module.global_error_handler

    error_handler_module.global_error_handler = None

    # 실제 QMessageBox.exec_()를 호출하면 offscreen 환경에서 블로킹되므로
    # 다이얼로그 표시 자체를 몽키패치로 가로챈다 (인자 기록만 수행).
    dialog_calls = []
    monkeypatch.setattr(
        GlobalErrorHandler,
        "_show_error_dialog",
        staticmethod(lambda context: dialog_calls.append(context)),
    )

    # 로깅 호출 여부/내용을 확인하기 위해 critical만 기록용으로 감시
    critical_calls = []
    monkeypatch.setattr(
        error_handler_module.logger, "critical", lambda msg: critical_calls.append(msg)
    )

    yield types.SimpleNamespace(dialog_calls=dialog_calls, critical_calls=critical_calls)

    sys.excepthook = original_sys_hook
    threading.excepthook = original_threading_hook
    error_handler_module.global_error_handler = original_singleton


def _make_exc_info(message: str = "boom"):
    """실제로 raise/except하여 정상적인 traceback 객체를 가진 exc_info를 만든다."""
    try:
        raise ValueError(message)
    except ValueError:
        return sys.exc_info()


# -----------------------------------------------------------------------------
# 설치(install) 검증
# -----------------------------------------------------------------------------

def test_install_sets_sys_and_threading_excepthooks(qapp, clean_error_handler_state):
    """install_global_error_handler()가 두 훅을 실제로 자신의 핸들러로 교체한다."""
    install_global_error_handler()
    handler = get_error_handler()

    assert handler is not None
    assert sys.excepthook == handler._handle_sys_exception
    assert threading.excepthook == handler._handle_threading_exception


def test_install_is_idempotent_and_keeps_single_instance(qapp, clean_error_handler_state):
    """두 번 호출해도 동일한 싱글톤 인스턴스를 유지한다 (중복 훅 설치 방지)."""
    install_global_error_handler()
    first = get_error_handler()

    install_global_error_handler()
    second = get_error_handler()

    assert first is second


def test_get_error_handler_returns_none_before_install(qapp, clean_error_handler_state):
    """설치 전에는 get_error_handler()가 None을 반환한다."""
    assert get_error_handler() is None


# -----------------------------------------------------------------------------
# 예외 포착 → 로깅 + 다이얼로그 콜백 (정상 예외)
# -----------------------------------------------------------------------------

def test_installed_sys_excepthook_logs_and_requests_dialog_for_normal_exception(
    qapp, clean_error_handler_state
):
    """
    설치된 sys.excepthook을 통해 일반 예외가 들어오면 CRITICAL 로깅과
    다이얼로그 콜백이 올바른 ErrorContext로 호출된다.
    """
    install_global_error_handler()
    exc_type, exc_value, tb = _make_exc_info("via sys.excepthook")

    # 실제로 설치된 훅을 직접 호출해 전체 체인(설치->포착->처리)을 검증
    sys.excepthook(exc_type, exc_value, tb)

    assert len(clean_error_handler_state.critical_calls) == 1
    assert "ValueError" in clean_error_handler_state.critical_calls[0]
    assert "via sys.excepthook" in clean_error_handler_state.critical_calls[0]

    assert len(clean_error_handler_state.dialog_calls) == 1
    context = clean_error_handler_state.dialog_calls[0]
    assert context.error_type == "ValueError"
    assert context.message == "via sys.excepthook"
    assert "Traceback" in context.traceback or "ValueError" in context.traceback


def test_report_error_manual_path_also_logs_and_requests_dialog(qapp, clean_error_handler_state):
    """
    try/except 안에서 잡은 예외를 수동으로 report_error()에 넘겨도
    동일하게 로깅 + 다이얼로그 콜백 경로를 탄다.
    """
    handler = GlobalErrorHandler()
    exc_type, exc_value, tb = _make_exc_info("manual report")

    handler.report_error(exc_type, exc_value, tb)

    assert len(clean_error_handler_state.critical_calls) == 1
    assert len(clean_error_handler_state.dialog_calls) == 1
    assert clean_error_handler_state.dialog_calls[0].message == "manual report"


def test_threading_excepthook_logs_thread_name_and_requests_dialog(qapp, clean_error_handler_state):
    """워커 스레드에서 발생한 미처리 예외도 threading.excepthook 경로로 포착된다."""
    install_global_error_handler()
    handler = get_error_handler()

    exc_type, exc_value, tb = _make_exc_info("thread boom")
    fake_thread = threading.Thread(name="WorkerThread-Test")
    args = types.SimpleNamespace(
        exc_type=exc_type, exc_value=exc_value, exc_traceback=tb, thread=fake_thread
    )

    handler._handle_threading_exception(args)

    # thread 예외는 "Exception in thread ..." critical 로그 + 공통 처리 critical 로그, 2건
    assert len(clean_error_handler_state.critical_calls) == 2
    assert "WorkerThread-Test" in clean_error_handler_state.critical_calls[0]
    assert len(clean_error_handler_state.dialog_calls) == 1
    assert clean_error_handler_state.dialog_calls[0].message == "thread boom"


# -----------------------------------------------------------------------------
# KeyboardInterrupt는 이전 훅으로 위임 (정상 처리 경로를 타지 않음)
# -----------------------------------------------------------------------------

def test_keyboard_interrupt_is_delegated_to_previous_hook_without_logging(
    qapp, clean_error_handler_state, monkeypatch
):
    """
    KeyboardInterrupt는 CRITICAL 로깅/다이얼로그 경로를 타지 않고, 설치 시점에
    저장해 둔 "이전 훅"으로 그대로 위임되어야 한다.
    """
    delegated_calls = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: delegated_calls.append(a))

    handler = GlobalErrorHandler()  # 생성 시점의 sys.excepthook(위 patch)을 old로 저장

    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exc_type, exc_value, tb = sys.exc_info()

    handler._handle_sys_exception(exc_type, exc_value, tb)

    assert len(delegated_calls) == 1
    assert delegated_calls[0][0] is KeyboardInterrupt
    # 정상 처리 경로(critical 로깅/다이얼로그)는 타지 않아야 함
    assert clean_error_handler_state.critical_calls == []
    assert clean_error_handler_state.dialog_calls == []


def test_threading_keyboard_interrupt_is_delegated_without_logging(
    qapp, clean_error_handler_state, monkeypatch
):
    """threading.excepthook 경로에서도 KeyboardInterrupt는 이전 훅으로 위임된다."""
    delegated_calls = []
    monkeypatch.setattr(threading, "excepthook", lambda args: delegated_calls.append(args))

    handler = GlobalErrorHandler()  # 생성 시점의 threading.excepthook(위 patch)을 old로 저장

    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exc_type, exc_value, tb = sys.exc_info()

    args = types.SimpleNamespace(
        exc_type=exc_type, exc_value=exc_value, exc_traceback=tb, thread=threading.current_thread()
    )
    handler._handle_threading_exception(args)

    assert len(delegated_calls) == 1
    assert clean_error_handler_state.critical_calls == []
    assert clean_error_handler_state.dialog_calls == []


# -----------------------------------------------------------------------------
# QApplication이 없는 경우 콘솔(stderr) 폴백
# -----------------------------------------------------------------------------

def test_falls_back_to_stderr_when_no_qapplication_instance(
    qapp, clean_error_handler_state, monkeypatch, capsys
):
    """QApplication.instance()가 None이면 다이얼로그 대신 stderr로 출력한다."""
    handler = GlobalErrorHandler()

    monkeypatch.setattr(error_handler_module.QApplication, "instance", staticmethod(lambda: None))

    exc_type, exc_value, tb = _make_exc_info("no gui")
    handler.report_error(exc_type, exc_value, tb)

    captured = capsys.readouterr()
    assert "Critical Error (No GUI):" in captured.err
    assert "no gui" in captured.err

    # 다이얼로그 콜백은 호출되지 않아야 함 (QApplication 없을 때는 콘솔 전용)
    assert clean_error_handler_state.dialog_calls == []
    # 로깅 자체는 QApplication 유무와 무관하게 여전히 수행됨
    assert len(clean_error_handler_state.critical_calls) == 1


# -----------------------------------------------------------------------------
# S-056: 다이얼로그 문구 콜백 주입 (core는 view.language_manager를 모른 채로
# 조립 계층이 주입한 콜백으로만 문구를 얻는다) - 실제 QMessageBox는 여전히
# 몽키패치로 가로채되, `_show_error_dialog`의 문구 계산 로직 자체를 검증한다.
# -----------------------------------------------------------------------------

def test_show_error_dialog_uses_english_fallback_without_provider(
    qapp, clean_error_handler_state, monkeypatch
):
    """
    콜백을 주입하지 않으면(기본값) 영어 하드코딩 폴백 문구가 그대로 쓰인다.
    (손상된 상태·테스트·라이브러리 사용 시 안전을 위한 기본 동작)
    """
    from common.dtos import ErrorContext
    from core.error_handler import _FALLBACK_TITLE, _FALLBACK_MESSAGE_TEMPLATE

    captured_kwargs = _install_fake_message_box(monkeypatch)

    handler = GlobalErrorHandler()  # message_provider 생략 -> None
    context = ErrorContext(
        error_type="ValueError", message="boom", traceback="tb", timestamp=0.0
    )
    _ORIGINAL_SHOW_ERROR_DIALOG(handler, context)

    assert captured_kwargs["title"] == _FALLBACK_TITLE
    assert captured_kwargs["text"] == _FALLBACK_MESSAGE_TEMPLATE.format("ValueError")


def test_show_error_dialog_uses_injected_message_provider(
    qapp, clean_error_handler_state, monkeypatch
):
    """주입된 콜백이 있으면 그 콜백이 돌려준 (제목, 메시지 템플릿)을 사용한다."""
    from common.dtos import ErrorContext

    captured_kwargs = _install_fake_message_box(monkeypatch)

    handler = GlobalErrorHandler(
        message_provider=lambda: ("치명적 오류", "예상치 못한 오류가 발생했습니다: {0}")
    )
    context = ErrorContext(
        error_type="ValueError", message="boom", traceback="tb", timestamp=0.0
    )
    _ORIGINAL_SHOW_ERROR_DIALOG(handler, context)

    assert captured_kwargs["title"] == "치명적 오류"
    assert captured_kwargs["text"] == "예상치 못한 오류가 발생했습니다: ValueError"


def test_show_error_dialog_falls_back_when_provider_raises(
    qapp, clean_error_handler_state, monkeypatch
):
    """콜백 호출 자체가 실패하면(손상된 상태) 영어 하드코딩 폴백으로 조용히 떨어진다."""
    from common.dtos import ErrorContext
    from core.error_handler import _FALLBACK_TITLE, _FALLBACK_MESSAGE_TEMPLATE

    captured_kwargs = _install_fake_message_box(monkeypatch)

    def _broken_provider():
        raise RuntimeError("language resource load failed")

    handler = GlobalErrorHandler(message_provider=_broken_provider)
    context = ErrorContext(
        error_type="ValueError", message="boom", traceback="tb", timestamp=0.0
    )
    _ORIGINAL_SHOW_ERROR_DIALOG(handler, context)

    assert captured_kwargs["title"] == _FALLBACK_TITLE
    assert captured_kwargs["text"] == _FALLBACK_MESSAGE_TEMPLATE.format("ValueError")


def test_set_error_message_provider_updates_installed_handler(qapp, clean_error_handler_state):
    """set_error_message_provider()로 이미 설치된 핸들러의 콜백을 나중에 주입할 수 있다."""
    from core.error_handler import set_error_message_provider

    install_global_error_handler()
    handler = get_error_handler()

    def provider():
        return ("주입된 제목", "주입된 메시지: {0}")

    set_error_message_provider(provider)

    assert handler._message_provider is provider


def test_set_error_message_provider_noop_before_install(clean_error_handler_state):
    """핸들러가 설치되기 전에 호출해도 예외 없이 아무 일도 하지 않는다."""
    from core.error_handler import set_error_message_provider

    assert get_error_handler() is None
    set_error_message_provider(lambda: ("x", "y"))  # 예외 없이 통과해야 함
    assert get_error_handler() is None


def test_install_global_error_handler_no_args_defaults_to_no_provider(
    qapp, clean_error_handler_state
):
    """인자 없이 install_global_error_handler()를 호출하면 콜백이 주입되지 않은 상태(None)다."""
    install_global_error_handler()
    handler = get_error_handler()

    assert handler._message_provider is None


def test_core_error_handler_module_does_not_import_view():
    """
    core/error_handler.py 소스에 view 계층 import가 없어야 한다(S-056).

    문자열 검색이 아니라 AST로 확인해, 함수 내부의 지연 import(S-036이 도입했던
    형태)까지 포함해 전부 잡아낸다. tests/test_layer_dependencies.py의
    core/ 전체 검사와 취지는 같지만, 이 파일 자체에서도 회귀를 바로 알 수 있도록
    좁혀서 한 번 더 고정한다.
    """
    import ast

    source = Path(error_handler_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imported_roots.add(node.module.split(".")[0])

    assert "view" not in imported_roots
    assert "presenter" not in imported_roots
    assert "model" not in imported_roots
