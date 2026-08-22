"""
snapshot_diff.py — 원본/신규 초기화 스냅샷 정규화 diff (snapshot-compare 스킬 §3)

`harness.py`가 만든 두 스냅샷 JSON을 비교한다. 비결정 값만 마스킹하고 나머지는 그대로 비교하며,
마스킹 규칙과 근거는 아래 `_RULES`/`NONDET`에 명시한다. TASK-014의 회귀 diff도 이 도구를 쓴다.

사용:
  python tools/analysis/snapshot_diff.py --all
  python tools/analysis/snapshot_diff.py docs/analysis/snapshots/original/smoke.json <신규.json>
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIG_DIR = REPO_ROOT / "docs" / "analysis" / "snapshots" / "original"
NEW_DIR = REPO_ROOT / "docs" / "analysis" / "snapshots" / "new"

_RULES = (
    # 임시 픽스처 디렉터리는 실행마다 새로 만들어진다
    (re.compile(r"stom_fixture_[A-Za-z0-9_]+"), "<TMPDIR>"),
    # 신규 구현은 경로 지정 로드라 모듈명이 다르다 (동작과 무관)
    (re.compile(r"ui_main_window_new"), "ui.main_window"),
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "<ADDR>"),
)

# 값 자체가 비결정이라 비교에서 제외하는 항목 (근거를 반드시 함께 적는다)
NONDET = {
    "int_time": "실행 시각 HMS 정수",
}
# 신규 구현에만 존재하는 것이 승인된 모듈 최상위 심볼 (근거를 반드시 함께 적는다)
APPROVED_MODULE_ONLY_NEW = {
    "SERIAL_AUTH_MODE":
        "TASK-008에서 추가한 이 프로젝트 고유 설정. 원본에는 없으며 utility/settings/setting_base.py "
        "에서 import 하므로 모듈 네임스페이스에 노출된다. local/remote 분기의 근거 상수다.",
}

NONDET_DICTSET_KEYS = {
    "키": "프로세스마다 새로 생성되는 임시 Fernet 키(env_bootstrap)",
}


def normalize(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text


def compare(orig_path: Path, new_path: Path) -> bool:
    o = json.loads(orig_path.read_text(encoding="utf-8"))
    n = json.loads(new_path.read_text(encoding="utf-8"))
    ok = True
    print(f"=== {orig_path.name}")

    for key in ("queues_in_dict_order", "qthreads", "qtimers", "named_widgets",
                "public_methods", "module_public", "window"):
        ov, nv = o.get(key), n.get(key)
        if key == "module_public" and isinstance(ov, list) and isinstance(nv, list):
            missing = sorted(set(ov) - set(nv))
            new_only = sorted(set(nv) - set(ov))
            approved = [x for x in new_only if x in APPROVED_MODULE_ONLY_NEW]
            unapproved = [x for x in new_only if x not in APPROVED_MODULE_ONLY_NEW]
            if missing or unapproved:
                ok = False
                print(f"  {key}: 불일치")
                print(f"    원본에만: {missing}")
                print(f"    신규에만(미승인): {unapproved}")
            else:
                note = f" (승인된 신규 전용 심볼 {approved})" if approved else ""
                print(f"  {key}: 일치{note}")
            continue
        if normalize(ov) == normalize(nv):
            print(f"  {key}: 일치")
        else:
            ok = False
            print(f"  {key}: 불일치")
            if isinstance(o.get(key), list) and isinstance(n.get(key), list):
                a, b = set(o[key]), set(n[key])
                print(f"    원본에만: {sorted(a - b)}")
                print(f"    신규에만: {sorted(b - a)}")
            else:
                print(f"    O: {normalize(o.get(key))[:400]}")
                print(f"    N: {normalize(n.get(key))[:400]}")

    # timesync 는 NTP 오프셋이 임계(0.05초)를 넘을 때만 시스템 시각 변경을 시도한다. 오프셋은
    # 실행 시점의 머신 시계 드리프트에 좌우되므로 이 호출의 유무는 **비결정**이다. 시퀀스 비교에서
    # 제외하고 건수만 참고로 출력한다. (차단 자체는 harness 가 하므로 실제 시각 변경은 없다.)
    _NONDET_TARGETS = {"win32api.SetSystemTime", "win32api.SetLocalTime"}
    ob = [(b["target"], b["args"]) for b in o.get("blocked_calls", [])
          if b["target"] not in _NONDET_TARGETS]
    nb = [(b["target"], b["args"]) for b in n.get("blocked_calls", [])
          if b["target"] not in _NONDET_TARGETS]
    osys = sum(1 for b in o.get("blocked_calls", []) if b["target"] in _NONDET_TARGETS)
    nsys = sum(1 for b in n.get("blocked_calls", []) if b["target"] in _NONDET_TARGETS)
    if osys or nsys:
        print(f"  시스템 시각 변경 시도(비결정, 참고): 원본 {osys}건 / 신규 {nsys}건 — 전부 차단됨")
    if ob == nb:
        print(f"  blocked_calls: 일치 ({len(ob)}건)")
    else:
        ok = False
        print(f"  blocked_calls: 불일치 (원본 {len(ob)}건 / 신규 {len(nb)}건)")
        for i, (a, b) in enumerate(zip(ob, nb)):
            if a != b:
                print(f"    [{i}] O={a}  N={b}")

    od, nd = o.get("instance_dict", {}), n.get("instance_dict", {})
    only_o, only_n = sorted(set(od) - set(nd)), sorted(set(nd) - set(od))
    if only_o or only_n:
        ok = False
        print(f"  instance_dict 키 차이: 원본만={only_o} 신규만={only_n}")

    diffs, masked = [], []
    for k in sorted(set(od) & set(nd)):
        if normalize(od[k]) == normalize(nd[k]):
            continue
        if k in NONDET:
            masked.append(f"{k}({NONDET[k]})")
            continue
        if k == "dict_set" and isinstance(od[k], dict) and isinstance(nd[k], dict):
            sub = [kk for kk in set(od[k]) | set(nd[k])
                   if normalize(od[k].get(kk)) != normalize(nd[k].get(kk))]
            unexpected = [kk for kk in sub if kk not in NONDET_DICTSET_KEYS]
            masked.extend(f"dict_set['{kk}']({NONDET_DICTSET_KEYS[kk]})"
                          for kk in sub if kk in NONDET_DICTSET_KEYS)
            if unexpected:
                diffs.append(f"dict_set 하위 키: {sorted(unexpected)}")
            continue
        diffs.append(k)

    print(f"  instance_dict: {len(od)}개 중 승인된 비결정 마스킹 {len(masked)}건 "
          f"({', '.join(masked) if masked else '없음'})")
    if diffs:
        ok = False
        print(f"  instance_dict 미승인 차이 {len(diffs)}건:")
        for k in diffs[:20]:
            print(f"    - {k}")
            if k in od:
                print(f"      O: {normalize(od[k])[:200]}")
                print(f"      N: {normalize(nd[k])[:200]}")
    else:
        print("  instance_dict 미승인 차이: 0건")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("orig", nargs="?")
    ap.add_argument("new", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.all:
        all_ok = True
        for op in sorted(ORIG_DIR.glob("*.json")):
            if op.name.startswith("lifecycle_"):
                continue
            np_ = NEW_DIR / op.name
            if not np_.exists():
                print(f"=== {op.name}: 신규 스냅샷 없음 — 건너뜀")
                all_ok = False
                continue
            all_ok &= compare(op, np_)
        print("\n결과:", "모든 시나리오 일치" if all_ok else "미승인 차이 있음")
        return 0 if all_ok else 1

    if not args.orig or not args.new:
        ap.error("두 개의 스냅샷 경로 또는 --all 이 필요하다")
    return 0 if compare(Path(args.orig), Path(args.new)) else 1


if __name__ == "__main__":
    sys.exit(main())
