#!/usr/bin/env python3
"""chatlog.py -- file-based conversation log & remote-command channel.

Daily log file:  chatlog/chat_SerialTool_YY-MM-DD.md
(user spec was chat_{PROJECT}_YY:MM:DD.md -- ':' is illegal in Windows
filenames, so '-' is used.)

Subcommands (all silent on stdout unless noted -- hook stdout becomes model
context on some events):
  init        ensure today's file exists; on date rollover copy the previous
              day's LAST USER turn in as turn (1) for continuity.
              Prints a one-line pointer (SessionStart breadcrumb).
  log-user    read hook JSON from stdin ({"prompt": ...}), append a USER turn.
  log-agent   read hook JSON from stdin (Stop event, {"transcript_path": ...}),
              extract the LAST assistant text message from the JSONL
              transcript, append an AGENT turn.
  append --role USER|AGENT --text "..."   manual append (fallback).
  tail [--lines N]   print the last N lines of today's (or newest) log.
              THIS is how sessions read the log -- never read the whole file
              unless the user explicitly asks to review history.

Turn format:
  ## (N) USER -- 2026-08-13 09:12:33
  <content>

Hooks must never break the session: every entry point exits 0 on any error.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGDIR = ROOT / "chatlog"
PROJECT = "SerialTool"
MAX_AGENT_CHARS = 8000

_TURN_RE = re.compile(r"^## \((\d+)\) (USER|AGENT) -- ", re.M)


def today_path(now=None):
    now = now or datetime.datetime.now()
    return LOGDIR / f"chat_{PROJECT}_{now.strftime('%y-%m-%d')}.md"


def newest_log():
    logs = sorted(LOGDIR.glob(f"chat_{PROJECT}_*.md"))
    return logs[-1] if logs else None


def last_turn_no(text):
    nums = [int(m.group(1)) for m in _TURN_RE.finditer(text)]
    return max(nums) if nums else 0


def last_user_turn(text):
    """Return the full text of the last USER turn block, or None."""
    blocks = list(_TURN_RE.finditer(text))
    for m in reversed(blocks):
        if m.group(2) == "USER":
            start = m.start()
            nxt = next((b.start() for b in blocks if b.start() > start),
                       len(text))
            return text[start:nxt].strip()
    return None


def ensure_today(quiet=True):
    LOGDIR.mkdir(exist_ok=True)
    p = today_path()
    if p.exists():
        return p
    now = datetime.datetime.now()
    header = (f"# chat log -- {PROJECT} -- {now.strftime('%Y-%m-%d')}\n\n"
              "형식: `## (턴번호) USER|AGENT -- 시각` + 내용. "
              "읽을 때는 `python tools\\chatlog.py tail` (전체 읽기 금지).\n")
    body = ""
    prev = newest_log()
    if prev is not None and prev != p:
        carry = last_user_turn(prev.read_text(encoding="utf-8",
                                              errors="replace"))
        if carry:
            # renumber the carried turn as (1) and mark its origin
            carry = _TURN_RE.sub(lambda m: f"## (1) {m.group(2)} -- ",
                                 carry, count=1)
            body = (f"\n{carry}\n\n"
                    f"> (전일 {prev.name}의 마지막 커맨드를 연속성 유지를 위해 복사)\n")
    p.write_text(header + body, encoding="utf-8", newline="\n")
    return p


def append_turn(role, text):
    p = ensure_today()
    content = p.read_text(encoding="utf-8", errors="replace")
    n = last_turn_no(content) + 1
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = (text or "").strip()
    if len(text) > MAX_AGENT_CHARS:
        text = text[:MAX_AGENT_CHARS] + "\n... (truncated)"
    entry = f"\n## ({n}) {role} -- {stamp}\n\n{text}\n"
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(entry)


def read_stdin_json():
    try:
        raw = sys.stdin.buffer.read()
        # utf-8-sig: tolerate the BOM PowerShell pipes prepend
        return json.loads(raw.decode("utf-8-sig", errors="replace"))
    except Exception:
        return {}


def last_assistant_text(transcript_path):
    """Last assistant text message from a Claude Code JSONL transcript."""
    best = None
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                msg = e.get("message") or {}
                if e.get("type") == "assistant" or msg.get("role") == "assistant":
                    parts = msg.get("content")
                    if isinstance(parts, list):
                        texts = [c.get("text", "") for c in parts
                                 if isinstance(c, dict)
                                 and c.get("type") == "text"]
                        t = "\n".join(t for t in texts if t).strip()
                        if t:
                            best = t
    except Exception:
        pass
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "log-user", "log-agent",
                                    "append", "tail"])
    ap.add_argument("--role", default="AGENT")
    ap.add_argument("--text", default="")
    ap.add_argument("--lines", type=int, default=60)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        if args.cmd == "init":
            p = ensure_today()
            print(f"chatlog: {p.relative_to(ROOT)} "
                  f"(읽기: python tools\\chatlog.py tail)")
        elif args.cmd == "log-user":
            data = read_stdin_json()
            prompt = data.get("prompt", "")
            if prompt.strip():
                append_turn("USER", prompt)
        elif args.cmd == "log-agent":
            data = read_stdin_json()
            tp = data.get("transcript_path")
            if tp:
                t = last_assistant_text(tp)
                if t:
                    append_turn("AGENT", t)
        elif args.cmd == "append":
            append_turn(args.role.upper(), args.text)
        elif args.cmd == "tail":
            p = today_path()
            if not p.exists():
                p = newest_log()
            if p is None:
                print("(no chat log yet)")
                return 0
            lines = p.read_text(encoding="utf-8",
                                errors="replace").splitlines()
            print(f"--- {p.name} (마지막 {min(args.lines, len(lines))}줄"
                  f"/전체 {len(lines)}줄) ---")
            for ln in lines[-args.lines:]:
                print(ln)
    except Exception:
        # hooks must never break the session
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
