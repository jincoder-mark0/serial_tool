"""
lifecycle_probe.py — 이벤트/종료 수명주기 계측 (TASK-010)

`harness.py`가 "`__init__` 완료 시점의 정적 상태"를 관측한다면, 이 도구는 그 다음 단계인
**이벤트 처리와 종료 부작용의 순서**를 관측한다. 원본 `.pyd`와 신규 `.py` 양쪽에 동일하게
적용해 diff할 수 있다 (snapshot-compare 스킬 §2 "종료 부작용" 행).

관측 방식: `harness.install_blockers()`(네트워크/프로세스/스레드 차단) 위에 **부작용 기록기**를
추가로 설치한다. 큐 put, QTimer stop/start, QThread terminate/quit/wait, 위젯 close,
QMessageBox, QApplication.quit, sys.exit, qtest_qwait 를 전부 "기록 후 무해 반환"으로 대체하므로
종료 로직이 실제로 무엇을 어떤 순서로 하는지가 그대로 로그에 남는다.

중요: 기록기는 **MainWindow 생성 전에** 설치한다. 대상 모듈이 `from x import y` 로 바인딩한
함수(qtest_qwait 등)는 import 이후에 패치해도 반영되지 않기 때문이다. 대신 각 기록에
`phase`(init/scenario)를 붙여 초기화 중 발생분과 시나리오 발생분을 구분한다.

시나리오:
  close_yes     closeEvent(종료 승인) 1회
  close_no      closeEvent(종료 거부) 1회
  close_twice   closeEvent(승인) 후 다시 closeEvent(승인) — 중복 종료 안전성
  kill_running  process_kill() 2회 연속 — 중복 호출 안전성(초기화 완료 상태)
  kill_partial  일부 속성을 미초기화 상태로 되돌린 뒤 process_kill() 2회 — 부분 초기화 안전성
  timers        qtimer0~3/qtimer_exit 의 timeout 을 각각 emit — 연결된 핸들러 관측

사용:
  python tools/analysis/lifecycle_probe.py --target original --scenario close_yes \
      --out docs/analysis/snapshots/original/lifecycle_close_yes.json

RULES.md §4 준수: 원격 인증(StomCert.run)·라이브 서버(LiveClient/LiveSender.run)는 이 도구에서도
실행되지 않는다. QThread.start 차단에 더해 run/set_sock 을 기록 스텁으로 덮어 이중으로 막는다.
"""
import argparse
import json
import os
import sys
import threading
import traceback
from pathlib import Path

_REAL_EXIT = sys.exit  # install_recorders 가 sys.exit 를 덮으므로 원본을 미리 보관

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_bootstrap  # noqa: E402
import harness  # noqa: E402

# ---------------------------------------------------------------------------
# 기록기
# ---------------------------------------------------------------------------
_LOG: list[dict] = []
_PHASE = ["init"]
_QNAMES: dict[int, str] = {}


def _rec(kind: str, detail=None) -> None:
    _LOG.append({
        "seq": len(_LOG) + 1,
        "phase": _PHASE[0],
        "kind": kind,
        "detail": detail,
    })


def _short(v, n: int = 4000) -> str:
    try:
        s = repr(v)
    except Exception:
        s = "<unrepr-able>"
    return s[:n]


def _qname(q) -> str:
    return _QNAMES.get(id(q), f"<unnamed Queue {type(q).__name__}>")


def _wname(w) -> str:
    """위젯을 사람이 읽을 수 있는 이름으로. MainWindow 속성명이 있으면 그것을 쓴다."""
    return _QNAMES.get(id(w), f"<{type(w).__name__}>")


class _RecordingSplash:
    """StomSplashScreen 대체 — 호출을 통합 로그에 남긴다 (초기화 진행률 표시 순서 관측)."""

    def __getattr__(self, name):
        def _f(*a, **k):
            _rec(f"splash.{name}", {"args": [_short(x, 60) for x in a]})
        return _f


def build(target: str, auto_run: int):
    """harness.build_mainwindow 와 동일하되 splash 호출을 기록하는 스텁을 쓴다."""
    import harness as _h

    orig = _h.build_mainwindow.__globals__.get("__name__")  # noqa: F841 (문서화용)
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(sys.argv[:1])

    if target == "original":
        ref = REPO_ROOT / "ui" / "_reference" / "main_window.pyd"
        if ref.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location("ui.main_window", str(ref))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["ui.main_window"] = mod
            spec.loader.exec_module(mod)
        else:
            import ui.main_window as mod
    else:
        py = REPO_ROOT / "ui" / "main_window.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("ui_main_window_new", str(py))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ui_main_window_new"] = mod
        spec.loader.exec_module(mod)

    return app, mod.MainWindow(auto_run, _RecordingSplash())


def merge_harness_log() -> None:
    """harness 의 차단 호출(_record)을 이 도구의 단일 시퀀스 로그로 합류시킨다.

    harness 가 설치한 패치들은 호출 시점에 `harness._record` 를 이름으로 조회하므로, 모듈
    속성을 교체하면 이후의 모든 차단 호출이 여기로 들어온다 (프로세스 start / requests 등이
    큐 put·타이머 정지와 같은 순서 축에 놓인다).
    """
    def _record(target, args=(), kwargs=None):
        detail = {"target": target, "args": [_short(a, 80) for a in args]}
        if kwargs:
            detail["kwargs"] = {k: _short(v, 60) for k, v in kwargs.items()}
        _rec("blocked", detail)

    harness._record = _record


def install_recorders(answer: str) -> None:
    """부작용 기록기 설치. harness.install_blockers() 이후, MainWindow 생성 이전에 호출한다."""
    # --- 큐 put/get ---------------------------------------------------------
    from multiprocessing.queues import Queue as MPQueue

    def _put(self, obj, *a, **k):
        # 큐 이름은 MainWindow 생성 이후에야 알 수 있으므로 id를 함께 남기고 마지막에 해소한다.
        _rec("queue.put", {"queue": _qname(self), "_id": id(self), "obj": _short(obj)})

    MPQueue.put = _put

    # --- QTimer -------------------------------------------------------------
    from PyQt5.QtCore import QTimer, QThread

    def _timer_start(self, *a, **k):
        try:
            iv = self.interval()
        except Exception:
            iv = None
        _rec("QTimer.start", {"timer": _wname(self), "_id": id(self), "interval_ms": iv})

    def _timer_stop(self, *a, **k):
        _rec("QTimer.stop", {"timer": _wname(self), "_id": id(self)})

    QTimer.start = _timer_start
    QTimer.stop = _timer_stop

    # --- QThread ------------------------------------------------------------
    def _thread_start(self, *a, **k):
        _rec("QThread.start", {"thread": type(self).__name__})

    def _thread_terminate(self, *a, **k):
        _rec("QThread.terminate", {"thread": type(self).__name__})

    def _thread_quit(self, *a, **k):
        _rec("QThread.quit", {"thread": type(self).__name__})

    def _thread_wait(self, *a, **k):
        _rec("QThread.wait", {"thread": type(self).__name__, "args": _short(a)})
        return True

    QThread.start = _thread_start
    QThread.terminate = _thread_terminate
    QThread.quit = _thread_quit
    QThread.wait = _thread_wait

    # --- 위젯 close/show ----------------------------------------------------
    from PyQt5.QtWidgets import QWidget, QMessageBox, QApplication

    def _close(self, *a, **k):
        _rec("QWidget.close", {"widget": _wname(self), "_id": id(self)})
        return True

    QWidget.close = _close

    # --- QMessageBox --------------------------------------------------------
    _answers = {"yes": QMessageBox.Yes, "no": QMessageBox.No}
    ans = _answers[answer]

    def _question(*a, **k):
        # (parent, title, text, buttons, default) 중 title/text만 기록
        texts = [x for x in a if isinstance(x, str)][:2]
        _rec("QMessageBox.question", {"texts": texts, "answer": answer})
        return ans

    def _mk_msg(name, ret):
        def _f(*a, **k):
            texts = [x for x in a if isinstance(x, str)][:2]
            _rec(f"QMessageBox.{name}", {"texts": texts})
            return ret
        return _f

    QMessageBox.question = _question
    QMessageBox.information = _mk_msg("information", QMessageBox.Ok)
    QMessageBox.warning = _mk_msg("warning", QMessageBox.Ok)
    QMessageBox.critical = _mk_msg("critical", QMessageBox.Ok)

    # --- QApplication 종료 --------------------------------------------------
    def _quit(*a, **k):
        _rec("QApplication.quit")

    from PyQt5.QtCore import QCoreApplication

    QApplication.quit = _quit
    QCoreApplication.quit = _quit
    QApplication.closeAllWindows = lambda *a, **k: _rec("QApplication.closeAllWindows")

    # --- sys.exit -----------------------------------------------------------
    class _SysExit(BaseException):
        """sys.exit 대체 표식 — except Exception 에 잡히지 않게 BaseException 파생."""

    def _exit(code=0):
        _rec("sys.exit", {"code": code})
        raise _SysExit(code)

    sys.exit = _exit
    globals()["_SysExitMarker"] = _SysExit

    # --- qtest_qwait / QTest.qWait (이벤트 루프 재진입 방지) -----------------
    try:
        from utility.static_method import static_etcetera as se

        def _qwait(sec):
            _rec("qtest_qwait", {"sec": sec})

        se.qtest_qwait = _qwait
    except Exception:
        pass
    try:
        from PyQt5.QtTest import QTest

        QTest.qWait = staticmethod(lambda ms: _rec("QTest.qWait", {"ms": ms}))
    except Exception:
        pass

    # --- os.system / subprocess (harness가 이미 차단하지만 기록 형식 통일) ---
    import os as _os

    _os.system = lambda cmd: (_rec("os.system", {"cmd": _short(cmd)}) or 0)


def install_geometry_probe() -> None:
    """QWidget.x()/y() 호출을 기록한다 — 창위치 저장이 어떤 위젯을 어떤 순서로 읽는지 관측."""
    from PyQt5.QtWidgets import QWidget

    _x, _y = QWidget.x, QWidget.y

    def _rx(self):
        v = _x(self)
        _rec("QWidget.x", {"widget": _wname(self), "_id": id(self), "value": v})
        return v

    def _ry(self):
        v = _y(self)
        _rec("QWidget.y", {"widget": _wname(self), "_id": id(self), "value": v})
        return v

    QWidget.x = _rx
    QWidget.y = _ry

    for meth in ("pos", "geometry", "frameGeometry", "saveGeometry", "size"):
        orig = getattr(QWidget, meth, None)
        if orig is None:
            continue

        def _mk(m, o):
            def _f(self, *a, **k):
                v = o(self, *a, **k)
                _rec(f"QWidget.{m}", {"widget": _wname(self), "_id": id(self), "value": _short(v, 60)})
                return v
            return _f

        setattr(QWidget, meth, _mk(meth, orig))


def install_force_alive() -> None:
    """isRunning/isActive/isVisible 을 '객체별 최초 1회만 True'로 만든다.

    원본 종료 로직의 `if x.isRunning(): x.terminate()` 류 가드를 통과시켜 실제 정리 대상과
    순서를 관측하기 위한 계측 장치다. 최초 1회로 제한하는 이유는 `while x.isRunning(): wait`
    형태의 루프가 있을 경우 무한 대기를 피하기 위함이다.
    """
    from PyQt5.QtCore import QThread, QTimer
    from PyQt5.QtWidgets import QWidget

    seen: set = set()

    def _mk(name):
        def _f(self, *a, **k):
            first = id(self) not in seen
            seen.add(id(self))
            _rec(name, {"obj": _wname(self), "_id": id(self), "returns": first})
            return first
        return _f

    QThread.isRunning = _mk("QThread.isRunning")
    QTimer.isActive = _mk("QTimer.isActive")
    QWidget.isVisible = _mk("QWidget.isVisible")


class _WebDashboardStub:
    """DashboardStarter 대체 — `web_dashboard is not None` 가드 안쪽을 관측하기 위한 스텁."""

    def stop(self):
        _rec("web_dashboard.stop")

    def start(self):
        _rec("web_dashboard.start")


class _SharedCntStub:
    """multiprocessing.Value('i') 대체 — `shared_cnt is not None` 가드 안쪽 관측용."""

    value = 0


def install_optional_state(mw) -> list:
    """None 이라서 가드에 막히는 선택적 상태를 스텁으로 채운다 (--force-alive 와 함께 사용).

    `web_dashboard`(웹대시보드 프로세스)와 `shared_cnt`(백테스트 엔진)는 초기화 직후 None 이라
    종료 로직의 해당 분기가 실행되지 않는다. 복원된 문자열 테이블에 두 분기의 로그 메시지가
    존재하므로(docs/analysis/task007_remote_auth.md §6) 스텁으로 열어 순서를 확인한다.
    """
    filled = []
    if getattr(mw, "web_dashboard", "absent") is None:
        mw.web_dashboard = _WebDashboardStub()
        filled.append("web_dashboard")
    if getattr(mw, "shared_cnt", "absent") is None:
        mw.shared_cnt = _SharedCntStub()
        filled.append("shared_cnt")
    return filled


def block_remote_workers(mod) -> dict:
    """StomCert/LiveClient/LiveSender 의 run/set_sock 을 기록 스텁으로 대체 (RULES §4 이중 차단).

    QThread.start 차단만으로도 run 은 호출되지 않지만, 종료 로직이 run 을 동기 호출할
    가능성을 배제하기 위해 명시적으로 덮는다. 대체 성공 여부를 반환해 기록한다.
    """
    result = {}
    for cname in ("StomCert", "LiveClient", "LiveSender"):
        cls = getattr(mod, cname, None)
        if cls is None:
            result[cname] = "absent"
            continue
        try:
            def _mk(cn, mn):
                def _f(self, *a, **k):
                    _rec(f"{cn}.{mn}", {"blocked": True})
                return _f
            for mn in ("run", "set_sock"):
                setattr(cls, mn, _mk(cname, mn))
            # stop/cleanup 은 종료 로직의 관측 대상이므로 원본을 감싸 기록만 추가한다.
            for mn in ("stop", "cleanup"):
                orig = getattr(cls, mn, None)
                if orig is None:
                    continue

                def _wrap(cn, mn_, o):
                    def _f(self, *a, **k):
                        _rec(f"{cn}.{mn_}", None)
                        return o(self, *a, **k)
                    return _f

                setattr(cls, mn, _wrap(cname, mn, orig))
            result[cname] = "blocked"
        except Exception as e:
            result[cname] = f"patch-failed: {type(e).__name__}: {e}"
    return result


class _FakeProc:
    """multiprocessing.Process 스텁 — 종료 로직의 alive 검사를 통과시켜 이후 경로를 관측한다."""

    def __init__(self, name: str, alive: bool = False):
        self._name = name
        self._alive = alive

    def is_alive(self):
        alive = self._alive
        if alive:
            self._alive = False  # while 루프 무한 대기 방지: 최초 1회만 alive
        _rec("Process.is_alive", {"proc": self._name, "returns": alive})
        return alive

    def kill(self):
        _rec("Process.kill", {"proc": self._name})
        self._alive = False

    def terminate(self):
        _rec("Process.terminate", {"proc": self._name})
        self._alive = False

    def join(self, *a, **k):
        _rec("Process.join", {"proc": self._name})

    def poll(self):
        return None


def install_fake_procs(mw, alive: bool = False) -> list:
    """proc_* 속성 중 None 인 것을 _FakeProc(alive=False)로 채운다 (--fake-procs).

    원본 종료 로직이 `self.proc_chqs.is_alive()` 처럼 None 가드 없이 접근하는 지점을
    넘겨 그 이후 경로까지 관측하기 위한 계측 장치다. 신규 구현의 요구사항이 아니라
    관측 도구의 보조 수단임에 주의한다.
    """
    filled = []
    for k, v in list(vars(mw).items()):
        if k.startswith("proc_") and v is None:
            setattr(mw, k, _FakeProc(k, alive))
            filled.append(k)
    return filled


def install_python_tracer() -> None:
    """시나리오 구간의 파이썬 함수 호출을 기록한다 (`sys.setprofile`).

    Cython 으로 컴파일된 원본 메서드 자체는 추적되지 않지만, 원본이 호출하는 현재 트리의
    파이썬 함수(예: `ui.etcetera.process_starter.process_starter`)는 그대로 잡힌다.
    → 타이머 timeout 이 어떤 핸들러에 연결돼 있는지 식별할 수 있다.
    """
    import sysconfig

    repo = str(REPO_ROOT).lower()
    skip = (str(Path(__file__).resolve().parent).lower(),)

    def _prof(frame, event, arg):
        if event != "call":
            return
        code = frame.f_code
        fn = (code.co_filename or "").lower()
        if not fn.startswith(repo) or fn.startswith(skip):
            return
        rel = Path(code.co_filename).relative_to(REPO_ROOT).as_posix()
        _rec("py.call", {"func": f"{rel}:{code.co_name}", "line": code.co_firstlineno})

    sys.setprofile(_prof)


def tag_state(mw) -> dict:
    """저장 문자열의 출처를 식별하기 위해 후보 상태에 서로 다른 표식을 심는다.

    창위치 문자열이 `location_list`에서 오는지 `dict_set['창위치']`에서 오는지, 팩터선택이
    `factor_checkbox_list` 순서를 따르는지를 출력 문자열만 보고 판별할 수 있게 한다.
    """
    info = {}
    try:
        mw.location_list = [[f"L{i}", f"l{i}"] for i in range(len(mw.location_list))]
        info["location_list"] = "L<i>^l<i>"
    except Exception as e:
        info["location_list"] = f"skip: {e}"
    try:
        mw.dict_set["창위치"] = [[f"D{i}", f"d{i}"] for i in range(len(mw.dict_set["창위치"]))]
        info["dict_set['창위치']"] = "D<i>^d<i>"
    except Exception as e:
        info["dict_set['창위치']"] = f"skip: {e}"
    try:
        for i, cb in enumerate(mw.factor_checkbox_list):
            cb.setChecked(i % 3 == 0)  # 0,3,6,... 만 체크
        info["factor_checkbox_list"] = "i%3==0 만 체크"
    except Exception as e:
        info["factor_checkbox_list"] = f"skip: {e}"
    return info


def resolve_names() -> None:
    """로그에 남은 _id 를 name_objects() 이후의 이름으로 해소한다 (init phase 포함)."""
    for e in _LOG:
        d = e.get("detail")
        if not isinstance(d, dict):
            continue
        oid = d.pop("_id", None)
        if oid is None:
            continue
        name = _QNAMES.get(oid)
        if name:
            for key in ("queue", "timer", "widget"):
                if key in d:
                    d[key] = name


def name_objects(mw) -> None:
    """MainWindow 속성명을 id→이름 맵에 등록 (큐/타이머/다이얼로그 로그 가독성)."""
    items = list(vars(mw).items())
    for k, v in items:  # 1차: 속성명 우선
        if not isinstance(v, (list, dict)):
            _QNAMES[id(v)] = k
    for k, v in items:  # 2차: 컨테이너 원소 (속성명이 없을 때만)
        if isinstance(v, list):
            for i, item in enumerate(v):
                try:
                    _QNAMES.setdefault(id(item), f"{k}[{i}]")
                except Exception:
                    pass
    _QNAMES[id(mw)] = "MainWindow"


# ---------------------------------------------------------------------------
# 시나리오
# ---------------------------------------------------------------------------
def _close_event(mw, note: str) -> dict:
    from PyQt5.QtGui import QCloseEvent

    ev = QCloseEvent()
    ev.setAccepted(False)
    out = {"note": note}
    try:
        mw.closeEvent(ev)
        out["raised"] = None
    except BaseException as e:  # SystemExit 대체 표식 포함
        out["raised"] = f"{type(e).__name__}: {e}"
        out["traceback"] = _cython_frames()
    out["event_accepted"] = bool(ev.isAccepted())
    return out


def _call(mw, name: str, note: str) -> dict:
    out = {"note": note, "method": name}
    try:
        getattr(mw, name)()
        out["raised"] = None
    except BaseException as e:
        out["raised"] = f"{type(e).__name__}: {e}"
        out["traceback"] = _cython_frames()
    return out


def _cython_frames() -> list[str]:
    """현재 예외의 traceback 중 대상 모듈 프레임만 (Cython 은 원본 행번호를 남긴다)."""
    frames = []
    for line in traceback.format_exc().splitlines():
        s = line.strip()
        if s.startswith("File ") and ("main_window.py" in s):
            frames.append(s)
    return frames


def run_scenario(mw, scenario: str) -> list[dict]:
    steps = []
    if scenario == "close_yes":
        steps.append(_close_event(mw, "closeEvent #1 (승인)"))
    elif scenario == "close_no":
        steps.append(_close_event(mw, "closeEvent #1 (거부)"))
    elif scenario == "close_twice":
        steps.append(_close_event(mw, "closeEvent #1 (승인)"))
        _rec("--- 2nd closeEvent ---")
        steps.append(_close_event(mw, "closeEvent #2 (승인, 중복)"))
    elif scenario == "kill_running":
        steps.append(_call(mw, "process_kill", "process_kill #1 (초기화 완료 상태)"))
        _rec("--- 2nd process_kill ---")
        steps.append(_call(mw, "process_kill", "process_kill #2 (중복)"))
    elif scenario == "kill_partial":
        # 부분 초기화 상태 모사: 워커/타이머 참조를 __init__ 이전 값으로 되돌린다.
        removed = []
        for attr in ("writer", "crawling", "telegram", "tts_sound", "live_recv",
                     "live_send", "stom_cert", "qtimer0", "qtimer1", "qtimer2",
                     "qtimer3", "qtimer_exit", "proc_chqs"):
            if hasattr(mw, attr):
                try:
                    setattr(mw, attr, None)
                    removed.append(attr)
                except Exception as e:
                    removed.append(f"{attr}!{type(e).__name__}")
        _rec("--- attrs set to None ---", {"attrs": removed})
        steps.append(_call(mw, "process_kill", "process_kill #1 (부분 초기화)"))
        _rec("--- 2nd process_kill ---")
        steps.append(_call(mw, "process_kill", "process_kill #2 (부분 초기화, 중복)"))
    elif scenario == "subprocess_start":
        import time as _time

        _rec("--- sub_process_start() ---")
        step = {"note": "sub_process_start (thread_decorator 로 별도 스레드에서 실행됨)"}
        try:
            step["returned"] = _short(mw.sub_process_start(), 80)
            step["raised"] = None
        except BaseException as e:
            step["raised"] = f"{type(e).__name__}: {e}"
            step["traceback"] = _cython_frames()
        _time.sleep(3)  # 백그라운드 스레드가 팬아웃을 마치도록 대기
        _rec("--- 3s 대기 종료 ---")
        steps.append(step)

    elif scenario == "methods":
        # 이벤트/표시/기타 공개 메서드의 위임 대상을 관측한다.
        # serial_key_check 는 원격 인증 경로이므로 절대 호출하지 않는다 (RULES §4).
        from PyQt5.QtCore import QEvent, Qt
        from PyQt5.QtGui import QKeyEvent

        def _key(k, mod=Qt.NoModifier):
            return QKeyEvent(QEvent.KeyPress, k, mod)

        cases = [
            ("_finish_splash_and_show", lambda: mw._finish_splash_and_show()),
            ("web_dashboard_log", lambda: mw.web_dashboard_log("probe-log-line")),
            ("setting_serial_save", lambda: mw.setting_serial_save()),
            ("eventFilter(KeyPress Esc)", lambda: mw.eventFilter(mw, _key(Qt.Key_Escape))),
            ("eventFilter(non-key)", lambda: mw.eventFilter(mw, QEvent(QEvent.Show))),
            ("keyPressEvent(Enter)", lambda: mw.keyPressEvent(_key(Qt.Key_Return))),
            ("sub_process_start", lambda: mw.sub_process_start()),
        ]
        for label, fn in cases:
            _rec(f"--- {label} ---")
            step = {"note": label}
            try:
                step["returned"] = _short(fn(), 80)
                step["raised"] = None
            except BaseException as e:
                step["raised"] = f"{type(e).__name__}: {e}"
                step["traceback"] = _cython_frames()
            steps.append(step)

    elif scenario == "timers":
        for attr in ("qtimer0", "qtimer1", "qtimer2", "qtimer3", "qtimer_exit"):
            t = getattr(mw, attr, None)
            _rec(f"--- emit {attr}.timeout ---")
            step = {"note": f"{attr}.timeout.emit()", "timer": attr}
            if t is None:
                step["raised"] = "absent"
            else:
                try:
                    t.timeout.emit()
                    step["raised"] = None
                except BaseException as e:
                    step["raised"] = f"{type(e).__name__}: {e}"
                    step["traceback"] = _cython_frames()
            steps.append(step)
    else:
        raise ValueError(f"알 수 없는 시나리오: {scenario}")
    return steps


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def _watchdog(seconds: int, out_path: Path, scenario: str, target: str) -> None:
    """무한 대기(종료 루프 등) 방지 — 시한 초과 시 지금까지의 로그를 쓰고 강제 종료."""
    def _boom():
        payload = {
            "scenario": scenario,
            "target": target,
            "timeout": True,
            "note": f"watchdog {seconds}s 초과 — 종료 로직이 대기 상태에 빠짐",
            "log": _LOG,
        }
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                                encoding="utf-8")
        finally:
            print(f"TIMEOUT after {seconds}s — partial log written to {out_path}", flush=True)
            os._exit(3)

    t = threading.Timer(seconds, _boom)
    t.daemon = True
    t.start()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["original", "new"], default="original")
    ap.add_argument("--scenario", required=True,
                    choices=["close_yes", "close_no", "close_twice", "kill_running",
                             "kill_partial", "timers", "methods", "subprocess_start"])
    ap.add_argument("--auto-run", type=int, choices=[0, 1], default=0)
    ap.add_argument("--serial-key", choices=["none", "fake"], default="fake")
    ap.add_argument("--set", dest="sets", action="append", default=[], metavar="table.col=value")
    ap.add_argument("--answer", choices=["yes", "no"], default=None,
                    help="QMessageBox.question 응답 (기본: close_no는 no, 나머지는 yes)")
    ap.add_argument("--trace-python", action="store_true",
                    help="시나리오 구간의 파이썬 함수 호출을 기록 (핸들러 식별)")
    ap.add_argument("--tag-geometry", action="store_true",
                    help="location_list/dict_set['창위치']/팩터체크박스에 표식을 심어 저장 문자열의 출처를 판별")
    ap.add_argument("--force-alive", action="store_true",
                    help="isRunning/isActive/isVisible/is_alive 를 객체별 최초 1회 True 로 만들어 "
                         "가드 안쪽 정리 경로까지 관측")
    ap.add_argument("--probe-geometry", action="store_true",
                    help="QWidget.x()/y() 호출을 기록 (창위치 저장 대상·순서 관측)")
    ap.add_argument("--fake-procs", action="store_true",
                    help="None 인 proc_* 속성을 alive=False 스텁으로 채워 종료 경로 전체를 관측")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    answer = args.answer or ("no" if args.scenario == "close_no" else "yes")
    out = Path(args.out)
    _watchdog(args.timeout, out, args.scenario, args.target)

    key = env_bootstrap.install()
    fixture = env_bootstrap.make_fixture_workspace()
    applied = harness.apply_overrides(fixture, args.sets, args.serial_key, key)

    harness.install_blockers()
    merge_harness_log()
    install_recorders(answer)
    if args.probe_geometry:
        install_geometry_probe()

    app, mw = build(args.target, args.auto_run)
    mod = sys.modules.get("ui.main_window") or sys.modules.get("ui_main_window_new")
    blocked_workers = block_remote_workers(mod) if mod is not None else {}
    name_objects(mw)
    faked = install_fake_procs(mw, args.force_alive) if (args.fake_procs or args.force_alive) else []
    if faked:
        name_objects(mw)
    optional_state = []
    if args.force_alive:
        optional_state = install_optional_state(mw)
        name_objects(mw)
        install_force_alive()

    tagged = tag_state(mw) if args.tag_geometry else {}

    init_log_len = len(_LOG)
    _PHASE[0] = args.scenario
    if args.trace_python:
        install_python_tracer()
    try:
        steps = run_scenario(mw, args.scenario)
    finally:
        sys.setprofile(None)
    resolve_names()

    payload = {
        "scenario": args.scenario,
        "target": args.target,
        "params": {
            "auto_run": args.auto_run,
            "serial_key": args.serial_key,
            "answer": answer,
            "overrides": applied,
            "flags": {
                "fake_procs": bool(args.fake_procs),
                "force_alive": bool(args.force_alive),
                "probe_geometry": bool(args.probe_geometry),
                "tag_geometry": bool(args.tag_geometry),
                "trace_python": bool(args.trace_python),
            },
        },
        "blocked_workers": blocked_workers,
        "faked_procs": faked,
        "optional_state_stubs": optional_state,
        "tagged_state": tagged,
        "init_record_count": init_log_len,
        "steps": steps,
        "log": _LOG[init_log_len:],
        "init_log": _LOG[:init_log_len],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"target={args.target} scenario={args.scenario} answer={answer}")
    print(f"init_records={init_log_len} scenario_records={len(_LOG) - init_log_len}")
    for s in steps:
        print(f"  step: {s.get('note')} raised={s.get('raised')} accepted={s.get('event_accepted')}")
    print(f"wrote: {out}")

    env_bootstrap.cleanup()
    return 0


if __name__ == "__main__":
    _REAL_EXIT(main())
