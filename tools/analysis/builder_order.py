"""
builder_order.py — 원본 MainWindow의 빌더 호출 순서 실측 (TASK-009 9A)

원본 `ui/main_window.pyd`가 `__init__`에서 UI 빌더(SetIcon/SetMainMenu/… , WidgetCreater)를
어떤 순서·인자로 호출하는지 계측한다. Cython은 `Set...` 호출을 모듈 전역에서 해소하므로,
`ui.main_window` 네임스페이스의 빌더를 wrap하면 실제 호출을 가로채 순서를 기록할 수 있다.

부작용은 harness.install_blockers로 전면 차단하고, 환경은 env_bootstrap으로 부트스트랩한다.
MainWindow는 생성하지만 원격 인증은 실행되지 않는다(StomCert QThread.start 차단).

사용: python tools/analysis/builder_order.py --out docs/analysis/raw/builder_order.json
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_bootstrap  # noqa: E402
import harness  # noqa: E402

_ORDER: list[dict] = []
_SEQ = 0


def _wrap(name, orig):
    def _w(*a, **k):
        global _SEQ
        _SEQ += 1
        arg_types = [type(x).__name__ for x in a]
        _ORDER.append({
            "seq": _SEQ,
            "builder": name,
            "argc": len(a),
            "arg_types": arg_types,
            "kwargs": sorted(k.keys()),
        })
        return orig(*a, **k)
    return _w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/analysis/raw/builder_order.json")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    key = env_bootstrap.install()
    base = env_bootstrap.make_fixture_workspace()
    harness.apply_overrides(base, [], "fake", key)
    harness.install_blockers()

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(sys.argv[:1])

    import ui.main_window as mod

    # 빌더 후보: 모듈 네임스페이스에서 'Set'으로 시작하거나 WidgetCreater
    wrapped = []
    for nm in dir(mod):
        if nm.startswith("Set") or nm == "WidgetCreater":
            obj = getattr(mod, nm)
            if callable(obj):
                setattr(mod, nm, _wrap(nm, obj))
                wrapped.append(nm)

    class _SplashStub:
        def __getattr__(self, name):
            return lambda *a, **k: None

    mod.MainWindow(0, _SplashStub())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {"wrapped_candidates": sorted(wrapped), "call_order": _ORDER}
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrapped {len(wrapped)} builder names, recorded {len(_ORDER)} calls")
    for e in _ORDER:
        print(f"  {e['seq']:2d}. {e['builder']}({e['argc']} args: {e['arg_types']})")
    print(f"wrote: {out}")
    env_bootstrap.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
