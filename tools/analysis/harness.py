"""
harness.py — 부작용 차단 계측 하네스 (TASK-005)

원본 `ui/main_window.pyd`(또는 신규 `ui/main_window.py`)의 `MainWindow(auto_run,
splash)`를 실제로 생성해 초기 상태를 스냅샷한다. 생성 과정의 외부 부작용(자식
프로세스/스레드 실행, 타이머, 소켓/ZeroMQ/HTTP 전송, 외부 프로세스 기동, 시스템
종료, TTS)을 전부 차단하고 호출 인자·순서만 기록한다.

전제: tools/analysis/env_bootstrap.py (레지스트리/DB 부재 우회, 시스템 무변경).

사용:
  python tools/analysis/harness.py --target original --scenario smoke \
      --auto-run 0 --serial-key fake --out docs/analysis/snapshots/original/smoke.json

반드시 별도 프로세스(.venv Python 3.13 + PyQt5)에서 실행한다.
원격 인증 코드는 이 하네스로도 실행하지 않는다 — 인증 워커(StomCert)는 QThread이며
QThread.start 차단으로 run()이 호출되지 않는다 (RULES.md §4, TASK-007).
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_bootstrap  # noqa: E402

# ---------------------------------------------------------------------------
# 부작용 차단 (monkeypatch). 모든 호출은 _CALL_LOG에 (seq, target, summary)로 기록.
# 패치 지점의 대입 가능성은 probe로 사전 확인함 (QThread/QTimer sip 포함 전부 가능).
# ---------------------------------------------------------------------------
_CALL_LOG: list[dict] = []
_SEQ = 0


def _record(target: str, args=(), kwargs=None) -> None:
    global _SEQ
    _SEQ += 1
    try:
        summary = ", ".join([repr(a)[:80] for a in args])
        if kwargs:
            summary += " | " + ", ".join(f"{k}={repr(v)[:60]}" for k, v in kwargs.items())
    except Exception:
        summary = "<unrepr-able args>"
    _CALL_LOG.append({"seq": _SEQ, "target": target, "args": summary[:400]})


class _FakePopen:
    """subprocess.Popen 대체 — OS 프로세스 미기동, 최소 속성만 제공."""

    def __init__(self, *a, **k):
        _record("subprocess.Popen", a, k)
        self.pid = -1
        self.returncode = None

    def poll(self):
        return None

    def wait(self, *a, **k):
        return 0

    def terminate(self):
        pass

    kill = terminate

    def communicate(self, *a, **k):
        return (b"", b"")


class _BlockedNetwork(RuntimeError):
    """차단된 네트워크 호출 표식 (부작용 방지용)."""


def install_blockers() -> list[dict]:
    """모든 부작용 지점을 patch하고 호출 로그 리스트를 반환한다."""
    # 1) 자식 프로세스 (multiprocessing) — 모든 Process 서브클래스의 start
    import multiprocessing.process as mpp

    def _proc_start(self, *a, **k):
        name = getattr(self, "name", "?")
        tgt = getattr(self, "_target", None)
        _record("multiprocessing.Process.start", (name, getattr(tgt, "__name__", tgt)))

    mpp.BaseProcess.start = _proc_start

    # 2) QThread / QTimer (sip)
    from PyQt5.QtCore import QThread, QTimer

    def _qthread_start(self, *a, **k):
        _record("QThread.start", (type(self).__name__,))

    QThread.start = _qthread_start

    _orig_setinterval = QTimer.setInterval

    def _qtimer_start(self, *a, **k):
        try:
            iv = self.interval()
        except Exception:
            iv = None
        _record("QTimer.start", (type(self).__name__,), {"interval_ms": iv})

    QTimer.start = _qtimer_start

    # 3) socket
    import socket

    def _sock_connect(self, *a, **k):
        _record("socket.socket.connect", a)

    socket.socket.connect = _sock_connect
    socket.socket.connect_ex = lambda self, *a, **k: (_record("socket.socket.connect_ex", a) or 0)

    # 4) zmq
    try:
        import zmq

        zmq.Socket.connect = lambda self, *a, **k: _record("zmq.Socket.connect", a)
        zmq.Socket.bind = lambda self, *a, **k: _record("zmq.Socket.bind", a)
        zmq.Socket.send = lambda self, *a, **k: _record("zmq.Socket.send", a)
        zmq.Socket.send_string = lambda self, *a, **k: _record("zmq.Socket.send_string", a)
        zmq.Socket.send_multipart = lambda self, *a, **k: _record("zmq.Socket.send_multipart", a)
    except Exception:
        pass

    # 5) 외부 프로세스 기동 / 시스템 종료
    import subprocess
    import os

    subprocess.Popen = _FakePopen
    os.system = lambda cmd: (_record("os.system", (cmd,)) or 0)

    # 6) HTTP (공인 IP 조회 등)
    import urllib.request

    def _urlopen(*a, **k):
        _record("urllib.request.urlopen", a)
        raise _BlockedNetwork("network blocked by harness")

    urllib.request.urlopen = _urlopen
    try:
        import requests

        for m in ("get", "post", "put", "delete", "head", "request"):
            def _mk(mn):
                def _f(*a, **k):
                    _record(f"requests.{mn}", a)
                    raise _BlockedNetwork("network blocked by harness")
                return _f
            setattr(requests, m, _mk(m))
    except Exception:
        pass

    # 6-1) 시스템 시각 변경 (timesync 가 NTP offset >= 0.05s 일 때 호출 — 실제 시스템을 바꾼다)
    try:
        import win32api

        win32api.SetSystemTime = lambda *a, **k: _record("win32api.SetSystemTime", a)
        win32api.SetLocalTime = lambda *a, **k: _record("win32api.SetLocalTime", a)
    except Exception:
        pass

    # 7) TTS (win32com / pyttsx3)
    try:
        import win32com.client as wc

        wc.Dispatch = lambda *a, **k: (_record("win32com.Dispatch", a) or _TtsStub())
    except Exception:
        pass

    return _CALL_LOG


class _TtsStub:
    def __getattr__(self, name):
        return lambda *a, **k: _record(f"tts.{name}", a)


# ---------------------------------------------------------------------------
# 시나리오 시리얼키 주입 (픽스처 DB 편집)
# ---------------------------------------------------------------------------
def _coerce(v: str):
    """'1' → 1, '1.5' → 1.5, 그 외 문자열 유지 (SQLite 동적 타입 대비)."""
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _compute_no(con) -> int:
    """load_settings와 동일하게 main.거래소 마지막 2자리로 per-market 행 번호 산출."""
    row = con.execute('SELECT "거래소" FROM main WHERE "index"=0').fetchone()
    exch = row[0] if row else "국내주식01"
    try:
        return int(str(exch)[-2:])
    except ValueError:
        return 1


def apply_overrides(fixture_base: str, sets: list[str], serial_mode: str, key: str) -> dict:
    """픽스처 setting.db에 시나리오 오버라이드를 적용한다.

    - sets: 'table.column=value' 목록. table=='main'이면 index=0 행, 그 외 per-market
      테이블은 (갱신된) 거래소로 산출한 no 행을 갱신한다. main.* 를 먼저 적용한 뒤
      no를 계산하고 나머지를 적용한다.
    - serial_mode: 'none'→etc.시리얼키 비움 / 'fake'→임시 키로 en_text 한 가짜 값 저장.
      거래소로 산출한 no 행(etc)에 적용한다.
    - 유효한 거래소 값: utility/settings/setting_market.py DICT_MARKET_GUBUN 키
      (예: 국내주식01, 해외주식07, 업비트09, 해외선물15, 바이낸스선물17 …).
    """
    from utility.static_method.static_fernet_key import en_text

    parsed = []
    for s in sets:
        if "." not in s or "=" not in s:
            raise ValueError(f"--set 형식 오류(table.column=value): {s!r}")
        tabcol, _, value = s.partition("=")
        table, _, col = tabcol.partition(".")
        parsed.append((table, col, _coerce(value)))

    db = Path(fixture_base) / "_database" / "setting.db"
    con = sqlite3.connect(str(db))
    applied = {"sets": [], "serial_mode": serial_mode}
    try:
        # 1) main.* 먼저 (index 0)
        for table, col, val in parsed:
            if table == "main":
                con.execute(f'UPDATE main SET "{col}"=? WHERE "index"=0', (val,))
                applied["sets"].append(f"main.{col}={val}@0")
        con.commit()

        # 2) 갱신된 거래소로 no 계산
        no = _compute_no(con)
        applied["no"] = no

        # 3) per-market 테이블 오버라이드 (index=no)
        for table, col, val in parsed:
            if table != "main":
                con.execute(f'UPDATE {table} SET "{col}"=? WHERE "index"=?', (val, no))
                applied["sets"].append(f"{table}.{col}={val}@{no}")

        # 4) 시리얼키 (etc, index=no)
        if serial_mode == "fake":
            enc = en_text(key, "TEST-FAKE-SERIAL-0000")
            con.execute('UPDATE etc SET "시리얼키"=? WHERE "index"=?', (enc, no))
        else:  # none
            con.execute('UPDATE etc SET "시리얼키"=? WHERE "index"=?', ("", no))
        con.commit()
    finally:
        con.close()
    return applied


# ---------------------------------------------------------------------------
# 스냅샷
# ---------------------------------------------------------------------------
_SIMPLE = (bool, int, float, str, type(None))
_CAP = 512  # 컨테이너 항목 상한 (dict_set ~64키 등 설정값을 온전히 담되 폭주 방지)


def _val(v, depth=0):
    """값을 JSON 안전 형태로 정규화. 비단순 객체는 <Type> 또는 요약.

    diff 정확성을 위해 조용한 손실을 피한다: 상한 초과 시 명시적 절단 마커를
    남기고, numpy 스칼라는 실제 파이썬 값으로 변환한다.
    """
    if isinstance(v, _SIMPLE):
        return v
    # numpy 스칼라 → 파이썬 값 (예: numpy.int64 타임프레임)
    item = getattr(v, "item", None)
    if item is not None and type(v).__module__ == "numpy" and getattr(v, "ndim", None) == 0:
        try:
            return v.item()
        except Exception:
            pass
    tn = type(v).__name__
    mod = type(v).__module__
    if isinstance(v, (list, tuple)):
        if depth >= 3:
            return f"<{tn}[{len(v)}]>"
        out = [_val(x, depth + 1) for x in list(v)[:_CAP]]
        if len(v) > _CAP:
            out.append(f"<...+{len(v) - _CAP} truncated>")
        return out
    if isinstance(v, dict):
        if depth >= 3:
            return f"<dict[{len(v)}]>"
        out = {str(k)[:60]: _val(x, depth + 1) for k, x in list(v.items())[:_CAP]}
        if len(v) > _CAP:
            out["__truncated__"] = len(v) - _CAP
        return out
    # multiprocessing Queue / Process / QThread / QTimer 등
    if "Queue" in tn:
        return f"<Queue {mod}.{tn}>"
    # logging.Logger: 이름/레벨/핸들러까지 비교 대상에 넣는다. 타입만 기록하면 로거 설정
    # 차이(이름·핸들러 부착 여부)가 diff를 그냥 통과해 버린다 (docs/mistakes.md 1~5와 같은 사각지대).
    import logging as _logging

    if isinstance(v, _logging.Logger):
        handlers = []
        for h in v.handlers:
            desc = type(h).__name__
            base = getattr(h, "baseFilename", None)
            if base:
                desc += f"({Path(base).name})"  # 디렉터리는 임시 경로라 파일명만
            handlers.append(desc)
        return f"<Logger name={v.name} level={v.level} propagate={v.propagate} handlers={handlers}>"
    return f"<{mod}.{tn}>"


def _widget_info(w):
    from PyQt5.QtWidgets import QWidget

    info = {"class": type(w).__name__}
    try:
        info["objectName"] = w.objectName()
    except Exception:
        pass
    for attr, fn in (
        ("visible", "isVisible"),
        ("enabled", "isEnabled"),
    ):
        try:
            info[attr] = bool(getattr(w, fn)())
        except Exception:
            pass
    try:
        g = w.geometry()
        info["geometry"] = [g.x(), g.y(), g.width(), g.height()]
    except Exception:
        pass
    for attr in ("text", "windowTitle"):
        try:
            fn = getattr(w, attr, None)
            if fn:
                t = fn()
                if t:
                    info[attr] = str(t)[:120]
        except Exception:
            pass
    return info


def snapshot(mw, scenario: str, params: dict, mod=None) -> dict:
    """MainWindow 인스턴스의 초기 상태를 관측해 dict로 반환한다."""
    from PyQt5.QtWidgets import QWidget
    from PyQt5.QtCore import QThread, QTimer

    snap: dict = {"scenario": scenario, "params": params}

    # 인스턴스 __dict__ (정규화)
    inst = {}
    queues_order = []
    processes = []
    threads = []
    timers = []
    for k in sorted(vars(mw).keys()):
        try:
            v = getattr(mw, k)
        except Exception as e:
            inst[k] = f"<getattr failed: {type(e).__name__}>"
            continue
        tn = type(v).__name__
        if "Queue" in tn:
            queues_order.append(k)
        if isinstance(v, QThread):
            threads.append({"attr": k, "class": tn})
        elif isinstance(v, QTimer):
            iv = None
            try:
                iv = v.interval()
            except Exception:
                pass
            single = None
            try:
                single = bool(v.isSingleShot())
            except Exception:
                pass
            timers.append({"attr": k, "interval_ms": iv, "single_shot": single})
        elif type(v).__module__.startswith("multiprocessing") and "Process" in tn:
            processes.append({"attr": k, "class": tn})
        inst[k] = _val(v)
    snap["instance_dict"] = inst
    snap["queues_in_dict_order"] = queues_order
    snap["processes"] = processes
    snap["qthreads"] = threads
    snap["qtimers"] = timers

    # QObject/위젯 트리: objectName이 있는 QWidget 자손을 이름순으로 (결정적)
    named = {}
    try:
        for w in mw.findChildren(QWidget):
            try:
                on = w.objectName()
            except Exception:
                on = ""
            if on:
                named[on] = _widget_info(w)
    except Exception as e:
        snap["widget_tree_error"] = f"{type(e).__name__}: {e}"
    snap["named_widgets"] = dict(sorted(named.items()))
    snap["named_widget_count"] = len(named)

    # 최상위 창 속성
    try:
        snap["window"] = _widget_info(mw)
    except Exception:
        pass

    # 공개 심볼 (인스턴스 차원 dir — 클래스 API는 TASK-002가 별도 기록)
    snap["public_methods"] = sorted(
        n for n in dir(mw)
        if not n.startswith("_") and callable(getattr(type(mw), n, None))
    )

    # 모듈 최상위 공개 심볼. 원본은 상수(HOST/CPORT/…)와 재노출 import 를 다수 갖는데, 이를
    # 기록하지 않으면 모듈 차원의 차이가 diff를 그냥 통과한다 (docs/mistakes.md 1~5와 같은 사각지대).
    if mod is not None:
        snap["module_public"] = sorted(n for n in dir(mod) if not n.startswith("_"))

    # 차단된 외부 호출 로그
    snap["blocked_calls"] = list(_CALL_LOG)
    return snap


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def build_mainwindow(target: str, auto_run: int):
    """QApplication + splash 스텁 + MainWindow(auto_run, splash) 생성."""
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    # stom.py와 동일: QtWebEngineWidgets import(ui.main_window 체인)가 QApplication
    # 생성 전에 이 속성을 요구한다.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(sys.argv[:1])

    class _SplashStub:
        """StomSplashScreen 대체 — MainWindow가 호출하는 모든 메서드를 무해 흡수."""

        def __getattr__(self, name):
            return lambda *a, **k: None

    if target == "original":
        # ui/main_window.pyd 를 확장 모듈 이름으로 로드 (아직 ui/에 있을 때는 일반
        # import로도 pyd가 우선 로드됨; _reference로 이동된 뒤에는 spec 로드 필요).
        ref = REPO_ROOT / "ui" / "_reference" / "main_window.pyd"
        if ref.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location("ui.main_window", str(ref))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["ui.main_window"] = mod
            spec.loader.exec_module(mod)
        else:
            import ui.main_window as mod
    else:  # new
        # .pyd가 아직 ui/에 있으면 `import ui.main_window`가 pyd를 우선 로드하므로,
        # 신규 .py를 경로로 명시 로드한다(TASK-012 이후에도 안전). 절대 import만 쓰므로
        # 별도 모듈명으로 로드해도 무방.
        py = REPO_ROOT / "ui" / "main_window.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("ui_main_window_new", str(py))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    MainWindow = mod.MainWindow
    mw = MainWindow(auto_run, _SplashStub())
    return app, mw, mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["original", "new"], default="original")
    ap.add_argument("--scenario", default="smoke")
    ap.add_argument("--auto-run", type=int, choices=[0, 1], default=0)
    ap.add_argument("--serial-key", choices=["none", "fake"], default="fake")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="table.col=value",
                    help="픽스처 설정 오버라이드 (반복 가능). 예: --set etc.작은창모드=1 "
                         "--set main.거래소=업비트09")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 1) 부트스트랩 (offscreen + read_key 패치 + 임시 기본 DB 픽스처)
    key = env_bootstrap.install()
    fixture_base = env_bootstrap.make_fixture_workspace()

    # 2) 시나리오 오버라이드 + 시리얼키 주입
    applied = apply_overrides(fixture_base, args.sets, args.serial_key, key)

    # 3) 부작용 차단 patch (MainWindow 생성 전)
    install_blockers()

    # 4) 생성 + 스냅샷
    params = {
        "target": args.target,
        "auto_run": args.auto_run,
        "serial_key": args.serial_key,
        "overrides": applied,
        "fixture_base": "<TMPDIR>",  # 비결정 경로는 마스킹
    }
    app, mw, mod = build_mainwindow(args.target, args.auto_run)
    snap = snapshot(mw, args.scenario, params, mod)

    # 5) 기록
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"target={args.target} scenario={args.scenario} auto_run={args.auto_run} serial_key={args.serial_key}")
    print(f"named_widgets={snap['named_widget_count']} queues={len(snap['queues_in_dict_order'])} "
          f"procs={len(snap['processes'])} qthreads={len(snap['qthreads'])} qtimers={len(snap['qtimers'])} "
          f"blocked_calls={len(snap['blocked_calls'])}")
    print(f"wrote: {out}")

    # 6) 정리 (임시 픽스처 제거). QApplication은 프로세스 종료로 회수.
    env_bootstrap.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
