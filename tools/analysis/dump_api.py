"""
dump_api.py

TASK-002 helper: reflect on the compiled `ui/main_window.pyd` extension
module WITHOUT instantiating MainWindow (or any other class it exports).

This script MUST be run in a separate process (see tools/analysis/README or
tasks/TASK-002.md) — never import ui.main_window directly in an assistant
session. It must be run from the repository root so the `ui` package
resolves, and with a Python 3.13 interpreter that has PyQt5 installed
(this repo's `.venv`).

What it does:
  1. Sets QT_QPA_PLATFORM=offscreen *before* any Qt import happens (import
     ui.main_window transitively imports PyQt5).
  2. `import ui.main_window as mw` — import only, no instantiation.
  3. Reflects on the module and on every public (non-underscore) class found
     in the module's dir(): __mro__, dir(), per-attribute type name,
     best-effort inspect.signature() (Cython/builtin callables often refuse
     introspection — falls back to the first line of __doc__), and class
     attributes that are not callable.
  4. Writes docs/analysis/task002_api.json.

No `MainWindow(...)` call (or any other class call) appears anywhere in this
file. No methods are invoked either — reflection only.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "docs" / "analysis" / "task002_api.json"

# 부트스트랩을 어떤 ui/utility import보다 먼저 적용한다: QT_QPA_PLATFORM=offscreen
# 설정 + 저장소 루트 sys.path 삽입 + read_key() 몽키패치(레지스트리 키 부재 우회).
# 시스템/레지스트리에 아무것도 쓰지 않는다 (tools/analysis/env_bootstrap.py 참고).
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_bootstrap

env_bootstrap.install()  # 임시 Fernet 키로 read_key 패치, offscreen 설정
env_bootstrap.make_fixture_workspace()  # 임시 기본 DB 픽스처 생성 (실제 _database 미생성)

import inspect
import json


def safe_repr(obj, limit: int = 200) -> str:
    try:
        r = repr(obj)
    except Exception as exc:  # pragma: no cover - defensive
        r = f"<repr failed: {exc!r}>"
    if len(r) > limit:
        r = r[: limit - 3] + "..."
    return r


def first_doc_line(obj) -> str | None:
    doc = getattr(obj, "__doc__", None)
    if not doc:
        return None
    line = doc.strip().splitlines()[0].strip() if doc.strip() else None
    return line


def describe_signature(obj):
    """Return (signature_str_or_None, doc_first_line_or_None)."""
    try:
        sig = str(inspect.signature(obj))
        return sig, None
    except (ValueError, TypeError):
        # Cython-compiled callables frequently do not support introspection.
        return None, first_doc_line(obj)


def describe_attr(cls, name: str) -> dict:
    entry: dict = {"name": name}
    try:
        attr = inspect.getattr_static(cls, name)
    except AttributeError:
        # Fall back to plain getattr (covers dynamic/Cython descriptors that
        # getattr_static cannot resolve). This does NOT call/instantiate
        # anything - getattr on a class only resolves the descriptor.
        try:
            attr = getattr(cls, name)
        except Exception as exc:  # pragma: no cover - defensive
            entry["error"] = repr(exc)
            return entry

    entry["type"] = type(attr).__name__
    entry["is_callable"] = callable(attr)
    entry["doc_first_line"] = first_doc_line(attr)

    if callable(attr) and not isinstance(attr, (int, str, float, bytes, bool, type(None))):
        sig, doc_fallback = describe_signature(attr)
        entry["signature"] = sig
        if sig is None and doc_fallback is not None:
            entry["doc_first_line"] = doc_fallback
    else:
        entry["signature"] = None
        entry["value_repr"] = safe_repr(attr)

    return entry


def describe_class(cls) -> dict:
    mro = [f"{c.__module__}.{c.__qualname__}" for c in cls.__mro__]
    names = sorted(set(dir(cls)))
    attrs = [describe_attr(cls, n) for n in names]
    return {
        "name": cls.__qualname__,
        "module": cls.__module__,
        "mro": mro,
        "qmainwindow_in_mro": any(m.endswith("QMainWindow") for m in mro),
        "doc": getattr(cls, "__doc__", None),
        "dir": names,
        "attributes": attrs,
    }


def main() -> None:
    # sys.path/offscreen/read_key 패치는 env_bootstrap.install()에서 이미 처리됨.

    # --- Import only. No instantiation of MainWindow or any other class. ---
    # 레지스트리 키 부재로 인한 load_settings 실패는 부트스트랩으로 우회되지만,
    # 그 외의 import 실패(진짜 ABI 문제, 누락 의존성 등)는 여전히 우회하지 않고
    # 그대로 기록·중단한다.
    import traceback

    try:
        import ui.main_window as mw  # noqa: E402  (must follow QT_QPA_PLATFORM set above)
    except BaseException as exc:  # capture as data, do not "fix" the cause
        failure = {
            "import_succeeded": False,
            "exception_type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "exception_str": str(exc),
            "traceback": traceback.format_exc(),
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(failure, indent=2, ensure_ascii=False), encoding="utf-8")
        print("IMPORT FAILED - see recorded traceback below and in", OUT_PATH)
        print(failure["traceback"])
        return

    module_info = {
        "import_succeeded": True,
        "dir": sorted(dir(mw)),
        "doc": mw.__doc__,
        "file": getattr(mw, "__file__", None),
    }

    # Collect every class defined/re-exported at module top level (public
    # names only, i.e. not starting with "_"), so we don't limit ourselves
    # to MainWindow alone - StomCert/LiveSender/LiveClient etc. from
    # TASK-001's static analysis are relevant too.
    classes = {}
    for name in module_info["dir"]:
        if name.startswith("_"):
            continue
        obj = getattr(mw, name)
        if inspect.isclass(obj):
            classes[name] = describe_class(obj)

    result = {
        "source_module_file": module_info["file"],
        "module": module_info,
        "classes": classes,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"python: {sys.executable}")
    print(f"module file: {module_info['file']}")
    print(f"module dir entries: {len(module_info['dir'])}")
    print(f"classes reflected: {list(classes.keys())}")
    print(f"wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
