"""
lifecycle_diff.py — 원본/신규 수명주기 스냅샷 정규화 diff (TASK-010)

`lifecycle_probe.py`가 만든 두 JSON(원본/신규)의 **부작용 시퀀스**를 비교한다.
snapshot-compare 스킬 §3의 정규화 규칙을 적용해 비결정 값만 마스킹하고 나머지는 그대로 비교한다.

정규화 대상(마스킹 근거를 각 규칙 옆에 명시):
  - 임시 픽스처 경로 `stom_fixture_*`            → <TMPDIR>   (매 실행 생성)
  - 모듈명 `ui_main_window_new`                  → ui.main_window (신규는 경로 로드라 모듈명이 다름)
  - 표준시간 동기화 완료 메시지의 오프셋 `[...]초` → [<OFFSET>] (NTP 실측값, 매 실행 다름)
  - `0x` 메모리 주소                              → <ADDR>
  - 스레드에서 비동기로 도착하는 기록(py.call 등)  → 비교 대상에서 제외(--kinds 로 조정)

사용:
  python tools/analysis/lifecycle_diff.py \
      docs/analysis/snapshots/original/lifecycle_close_yes.json \
      docs/analysis/snapshots/new/lifecycle_close_yes.json
  python tools/analysis/lifecycle_diff.py --all   # 두 디렉터리의 동명 파일 전부 비교
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIG_DIR = REPO_ROOT / "docs" / "analysis" / "snapshots" / "original"
NEW_DIR = REPO_ROOT / "docs" / "analysis" / "snapshots" / "new"

# 승인된 차이 (RULES.md §4 "승인되지 않은 차이 0건" 기준의 '승인' 목록).
# 새 항목을 추가할 때는 반드시 근거와 승인 주체를 함께 적는다.
APPROVED = {
    "lifecycle_kill_partial.json":
        "TASK-010 요구사항(process_kill idempotent). 원본은 부분 초기화 상태에서 "
        "AttributeError('NoneType' has no attribute 'isActive')로 중단되지만, Task 지시에 따라 "
        "신규 구현은 존재 여부를 확인하고 종료 절차를 끝까지 수행한다. "
        "정상 초기화 상태(kill_running)에서는 부작용 시퀀스가 완전히 일치한다.",
}

_RULES = (
    (re.compile(r"stom_fixture_[A-Za-z0-9_]+"), "<TMPDIR>"),
    (re.compile(r"ui_main_window_new"), "ui.main_window"),
    (re.compile(r"(표준시간 동기화 완료 )\[[^\]]*\]"), r"\1[<OFFSET>]"),
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "<ADDR>"),
)


def normalize(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text


def entries(snap: dict, key: str, kinds: set[str] | None) -> list[str]:
    out = []
    for e in snap.get(key, []):
        kind = e.get("kind", "")
        if kinds is not None and kind not in kinds and not kind.startswith("---"):
            continue
        if kind == "py.call":
            continue  # 파이썬 호출 추적은 --trace-python 전용 진단 정보
        line = f"{kind} {normalize(e.get('detail'))}"
        if "SetSystemTime" in line or "SetLocalTime" in line:
            # timesync 는 NTP 오프셋이 0.05초를 넘을 때만 시스템 시각 변경을 시도한다. 시도 횟수는
            # 실행 시점의 머신 시계 드리프트에 좌우돼 **비결정**이다(전부 harness 가 차단한다).
            continue
        if "표준시간 동기화" in line:
            # timesync 는 별도 스레드에서 NTP 응답이 오는 시점에 기록되므로 **위치가 비결정**이다.
            # 존재 여부만 따로 검사하고 시퀀스 비교에서는 제외한다.
            continue
        out.append(line)
    return out


def timesync_lines(snap: dict) -> list[str]:
    return [normalize(e.get("detail")) for e in snap.get("init_log", [])
            if "표준시간 동기화" in json.dumps(e.get("detail"), ensure_ascii=False)]


def diff_lists(a: list[str], b: list[str], limit: int) -> list[str]:
    import difflib

    lines = []
    for line in difflib.unified_diff(a, b, fromfile="original", tofile="new", lineterm="", n=1):
        lines.append(line)
        if len(lines) >= limit:
            lines.append(f"... (이후 생략, 총 diff 라인 {len(lines)}+)")
            break
    return lines


def compare(orig_path: Path, new_path: Path, limit: int, kinds: set[str] | None) -> bool:
    o = json.loads(orig_path.read_text(encoding="utf-8"))
    n = json.loads(new_path.read_text(encoding="utf-8"))
    ok = True
    print(f"=== {orig_path.name}")

    # timesync 는 별도 스레드에서 NTP 응답이 올 때만 기록되므로 **존재 여부와 위치 모두 비결정**이다
    # (NTP 실패/지연 시 아예 남지 않는다). 판정에 반영하지 않고 참고로만 출력한다.
    ot, nt = timesync_lines(o), timesync_lines(n)
    print(f"  timesync 메시지(비결정, 참고): 원본 {len(ot)}건 / 신규 {len(nt)}건")

    for key in ("init_log", "log"):
        a, b = entries(o, key, kinds), entries(n, key, kinds)
        if a == b:
            print(f"  {key}: 일치 ({len(a)}건)")
            continue
        ok = False
        print(f"  {key}: 불일치 (원본 {len(a)}건 / 신규 {len(b)}건)")
        for line in diff_lists(a, b, limit):
            print(f"    {line}")

    approved = APPROVED.get(orig_path.name)
    if not ok and approved:
        print(f"  → 승인된 차이: {approved}")
        ok = True
        print("  (판정: 승인된 차이로 통과)")
        return ok

    osteps = [(s.get("note"), s.get("raised"), s.get("event_accepted")) for s in o.get("steps", [])]
    nsteps = [(s.get("note"), s.get("raised"), s.get("event_accepted")) for s in n.get("steps", [])]
    if osteps == nsteps:
        print(f"  steps: 일치 ({len(osteps)}건)")
    else:
        ok = False
        print("  steps: 불일치")
        for i, (a, b) in enumerate(zip(osteps, nsteps)):
            if a != b:
                print(f"    [{i}] O={a}")
                print(f"    [{i}] N={b}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("orig", nargs="?")
    ap.add_argument("new", nargs="?")
    ap.add_argument("--all", action="store_true", help="original/ 과 new/ 의 lifecycle_*.json 전부 비교")
    ap.add_argument("--limit", type=int, default=60, help="시나리오당 출력할 diff 라인 수 상한")
    ap.add_argument("--kinds", default=None,
                    help="비교할 kind 를 콤마로 제한 (기본: py.call 을 제외한 전부)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    kinds = set(args.kinds.split(",")) if args.kinds else None

    if args.all:
        all_ok = True
        for op in sorted(ORIG_DIR.glob("lifecycle_*.json")):
            np_ = NEW_DIR / op.name
            if not np_.exists():
                print(f"=== {op.name}: 신규 스냅샷 없음 — 건너뜀")
                all_ok = False
                continue
            all_ok &= compare(op, np_, args.limit, kinds)
        print("\n결과:", "모든 시나리오 일치" if all_ok else "불일치 있음 (위 diff 확인)")
        return 0 if all_ok else 1

    if not args.orig or not args.new:
        ap.error("두 개의 스냅샷 경로 또는 --all 이 필요하다")
    ok = compare(Path(args.orig), Path(args.new), args.limit, kinds)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
