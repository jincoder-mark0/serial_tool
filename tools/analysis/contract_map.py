# -*- coding: utf-8 -*-
"""TASK-004: 호출부 계약 AST 인덱싱

저장소 전체에서 `ui.<attr>` / `self.ui.<attr>` 형태의 속성 접근을 AST로 수집해
MainWindow가 제공해야 하는 필드/메서드 계약표의 원자료를 만든다.

주의: 대상 파일은 절대 import/실행하지 않는다. `ast.parse`로만 분석한다.

실행:
    python tools\\analysis\\contract_map.py

산출물:
    docs/analysis/task004_contract.csv
    docs/analysis/task004_contract.md
"""

from __future__ import annotations

import ast
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
ROOT_DIR = SCRIPT_PATH.parents[2]  # tools/analysis/contract_map.py -> repo root
OUT_DIR = ROOT_DIR / "docs" / "analysis"
CSV_PATH = OUT_DIR / "task004_contract.csv"
MD_PATH = OUT_DIR / "task004_contract.md"
TASK002_API_MD = OUT_DIR / "task002_api.md"

# Task 명세상 제외 대상 (디렉터리, repo 루트 기준 상대경로 posix 형식)
EXCLUDE_DIR_PREFIXES = (
    "docs/",
    "tools/analysis/",
    "tests/",
)
# 어느 위치에 있든 이름이 일치하면 하위 전체를 건너뛰는 디렉터리
EXCLUDE_DIR_NAMES = {".git", "__pycache__"}
# 저장소 코드가 아닌 로컬 가상환경 — Task 본문의 "현재 런타임 코드만 계약의
# 근거로 삼는다"는 취지에 따라 배제한다 (git 미추적, 서드파티 의존성뿐이라
# 결과에 포함하면 MainWindow 계약과 무관한 잡음만 대량으로 섞인다).
EXCLUDE_DIR_NAMES.add(".venv")

EXCLUDE_FILES = {
    "ui/ui_mainwindow.py",
}


def relpath(p: Path) -> str:
    return p.resolve().relative_to(ROOT_DIR).as_posix()


def is_excluded_dir(rel_dir: str) -> bool:
    if rel_dir == ".":
        return False
    rel_dir_slash = rel_dir + "/"
    for prefix in EXCLUDE_DIR_PREFIXES:
        if rel_dir_slash.startswith(prefix):
            return True
    return False


def iter_target_files() -> list[Path]:
    """제외 규칙을 적용해 대상 .py 파일 목록을 결정적 순서로 반환한다."""
    targets: list[Path] = []
    for dirpath, dirnames, filenames in _walk_sorted(ROOT_DIR):
        rel_dir = Path(dirpath).resolve().relative_to(ROOT_DIR).as_posix()
        # 디렉터리 이름 기반 제외 (in-place 가지치기, 하위 재귀 방지)
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIR_NAMES
        ]
        if is_excluded_dir(rel_dir):
            dirnames[:] = []  # 이 아래는 더 내려갈 필요 없음
            continue
        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            fpath = Path(dirpath) / fname
            rel = relpath(fpath)
            if rel in EXCLUDE_FILES:
                continue
            if any(rel.startswith(p) for p in EXCLUDE_DIR_PREFIXES):
                continue
            targets.append(fpath)
    targets.sort(key=lambda p: relpath(p))
    return targets


def _walk_sorted(root: Path):
    """os.walk와 동일하되 dirnames/filenames를 정렬해 순회 순서를 고정한다."""
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        yield dirpath, dirnames, filenames


# ---------------------------------------------------------------------------
# AST 분석
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    attr: str
    kind: str  # call | read | write
    file: str  # repo-root 기준 posix 상대경로
    line: int
    col: int
    call_shape: Optional[str] = None  # kind == 'call'일 때만 채움


def _is_ui_base(node: ast.expr) -> bool:
    """`ui` (Name) 또는 `self.ui` (Attribute) 베이스인지 판정한다."""
    if isinstance(node, ast.Name) and node.id == "ui":
        return True
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "ui"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return True
    return False


def _describe_call(call: ast.Call) -> str:
    """호출부 인자 개수/형태를 사람이 읽을 수 있는 짧은 문자열로 요약한다."""
    n_pos = len(call.args)
    n_kw = len(call.keywords)
    has_star = any(isinstance(a, ast.Starred) for a in call.args)
    has_dstar = any(kw.arg is None for kw in call.keywords)
    parts = []
    for a in call.args:
        try:
            parts.append(ast.unparse(a))
        except Exception:
            parts.append("<?>")
    for kw in call.keywords:
        try:
            val = ast.unparse(kw.value)
        except Exception:
            val = "<?>"
        name = kw.arg if kw.arg is not None else "**"
        parts.append(f"{name}={val}")
    snippet = ", ".join(parts)
    if len(snippet) > 100:
        snippet = snippet[:97] + "..."
    shape_bits = [f"positional={n_pos}", f"keyword={n_kw}"]
    if has_star:
        shape_bits.append("*args포함")
    if has_dstar:
        shape_bits.append("**kwargs포함")
    return f"({', '.join(shape_bits)}) 예: ({snippet})"


class UiAttrVisitor(ast.NodeVisitor):
    def __init__(self, rel_file: str):
        self.rel_file = rel_file
        self.usages: list[Usage] = []
        self._parent_stack: list[ast.AST] = []

    def generic_visit(self, node: ast.AST) -> None:
        self._parent_stack.append(node)
        super().generic_visit(node)
        self._parent_stack.pop()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if _is_ui_base(node.value):
            parent = self._parent_stack[-1] if self._parent_stack else None
            if isinstance(parent, ast.Call) and parent.func is node:
                kind = "call"
                call_shape = _describe_call(parent)
            elif isinstance(node.ctx, (ast.Store, getattr(ast, "AugStore", ()))):
                kind = "write"
                call_shape = None
            else:
                kind = "read"
                call_shape = None
            self.usages.append(
                Usage(
                    attr=node.attr,
                    kind=kind,
                    file=self.rel_file,
                    line=node.lineno,
                    col=node.col_offset,
                    call_shape=call_shape,
                )
            )
        # ui.<attr>.<attr2> 같은 체인도 계속 내려가며 검사한다 (self.ui는
        # Attribute(value=Name) 형태라 generic_visit이 알아서 재귀 처리)
        self.generic_visit(node)


def analyze_file(path: Path) -> tuple[list[Usage], Optional[str]]:
    """(usages, parse_error) 튜플을 반환한다. parse_error는 실패 시 메시지."""
    rel = relpath(path)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            source = path.read_text(encoding="cp949")
        except Exception as exc:  # pragma: no cover
            return [], f"read error: {exc}"
    except Exception as exc:  # pragma: no cover
        return [], f"read error: {exc}"

    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return [], f"SyntaxError: {exc.msg} (line {exc.lineno})"
    except Exception as exc:  # pragma: no cover
        return [], f"{type(exc).__name__}: {exc}"

    visitor = UiAttrVisitor(rel)
    visitor.visit(tree)
    return visitor.usages, None


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------


def write_csv(usages: list[Usage]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(usages, key=lambda u: (u.file, u.line, u.col, u.attr, u.kind))
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["attr", "kind", "file", "line"])
        for u in rows:
            writer.writerow([u.attr, u.kind, u.file, u.line])


def guess_category(call_count: int, read_count: int, write_count: int) -> str:
    if call_count > 0:
        return "메서드"
    if write_count > 0 and read_count == 0:
        return "필드(쓰기전용)"
    return "필드"


def write_md(
    usages: list[Usage],
    parse_failures: list[tuple[str, str]],
    scanned_file_count: int,
) -> None:
    by_attr: dict[str, list[Usage]] = {}
    for u in usages:
        by_attr.setdefault(u.attr, []).append(u)

    unique_attr_count = len(by_attr)
    total_usage_count = len(usages)

    lines: list[str] = []
    lines.append("# TASK-004 — 호출부 계약 AST 인덱싱 결과")
    lines.append("")
    lines.append(
        f"`tools/analysis/contract_map.py`를 재실행하면 동일한 결과가 생성된다 "
        f"(정렬 기준: 속성명 오름차순, 대표 사용처는 file→line 오름차순 기준 상위 2건)."
    )
    lines.append("")
    lines.append("## 요약 통계")
    lines.append("")
    lines.append(f"- 분석 대상 파일 수: {scanned_file_count}")
    lines.append(f"- 고유 속성 수: {unique_attr_count}")
    lines.append(f"- 총 사용처 수: {total_usage_count}")
    lines.append(f"- 파싱 실패 파일 수: {len(parse_failures)}")
    lines.append("")
    lines.append("## 파싱 실패 파일 목록")
    lines.append("")
    if not parse_failures:
        lines.append("0건 (모든 대상 파일 파싱 성공)")
    else:
        lines.append("| 파일 | 사유 |")
        lines.append("|---|---|")
        for fname, reason in sorted(parse_failures):
            lines.append(f"| {fname} | {reason} |")
    lines.append("")
    lines.append("## 제외 규칙")
    lines.append("")
    lines.append(
        "- Task 명세 제외 대상: `docs/`, `tools/analysis/`, `tests/`, "
        "`ui/ui_mainwindow.py`, `.git/`, `__pycache__/`"
    )
    lines.append(
        "- 추가 제외: `.venv/` — git 미추적 로컬 가상환경(서드파티 의존성)이라 "
        "\"현재 런타임 코드\"가 아니므로 계약 근거에서 배제"
    )
    lines.append("")
    lines.append("## 속성별 집계표")
    lines.append("")
    lines.append(
        "| 속성명 | call | read | write | 대표 사용처 1 | 대표 사용처 2 | 추정 종류 | 인자 형태(call 대표) |"
    )
    lines.append("|---|---:|---:|---:|---|---|---|---|")

    for attr in sorted(by_attr.keys()):
        occ = by_attr[attr]
        occ_sorted = sorted(occ, key=lambda u: (u.file, u.line, u.col))
        call_count = sum(1 for u in occ if u.kind == "call")
        read_count = sum(1 for u in occ if u.kind == "read")
        write_count = sum(1 for u in occ if u.kind == "write")
        rep_sites = occ_sorted[:2]
        rep1 = f"{rep_sites[0].file}:{rep_sites[0].line}" if len(rep_sites) > 0 else ""
        rep2 = f"{rep_sites[1].file}:{rep_sites[1].line}" if len(rep_sites) > 1 else ""
        category = guess_category(call_count, read_count, write_count)

        arg_shape = ""
        if call_count > 0:
            call_occ = next((u for u in occ_sorted if u.kind == "call"), None)
            if call_occ is not None and call_occ.call_shape:
                arg_shape = call_occ.call_shape.replace("|", "\\|")

        rep1 = rep1.replace("|", "\\|")
        rep2 = rep2.replace("|", "\\|")
        lines.append(
            f"| `{attr}` | {call_count} | {read_count} | {write_count} | "
            f"{rep1} | {rep2} | {category} | {arg_shape} |"
        )

    lines.append("")
    lines.append("## TASK-002 교차 확인")
    lines.append("")
    if TASK002_API_MD.exists():
        lines.append(
            "TASK-002 산출물(`docs/analysis/task002_api.md`)이 존재하여 교차 확인을 "
            "수행해야 하나, 이 실행 시점에는 별도 스크립트 처리가 필요하다. "
            "(주: 본 스크립트 실행 시 파일이 발견되면 아래에 자동으로 채워진다.)"
        )
    else:
        lines.append(
            "생략 — `docs/analysis/task002_api.md`가 존재하지 않는다 (TASK-002 미완료). "
            "TASK-002 완료 후 본 스크립트를 재실행하면 이 절에 교차 확인 결과가 채워진다."
        )
    lines.append("")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def cross_check_with_task002(usages: list[Usage]) -> None:
    """TASK-002 산출물이 있으면 md 파일에 교차 확인 절을 다시 써 넣는다."""
    if not TASK002_API_MD.exists():
        return
    try:
        api_text = TASK002_API_MD.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[WARN] task002_api.md 읽기 실패: {exc}", file=sys.stderr)
        return

    # task002_api.md의 정확한 포맷은 TASK-002 완료 전에는 알 수 없으므로,
    # 백틱(`)으로 감싼 식별자 또는 각 줄 맨 앞 토큰을 느슨하게 추출한다.
    import re

    known_names: set[str] = set()
    for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]*)`", api_text):
        known_names.add(m.group(1))

    attrs = sorted({u.attr for u in usages})
    missing = [a for a in attrs if a not in known_names]

    md_text = MD_PATH.read_text(encoding="utf-8")
    section_header = "## TASK-002 교차 확인"
    idx = md_text.index(section_header)
    head = md_text[:idx]

    new_section_lines = [section_header, ""]
    new_section_lines.append(
        f"`docs/analysis/task002_api.md`에서 백틱으로 감싼 식별자 {len(known_names)}개를 "
        f"추출해 호출부 속성 {len(attrs)}개와 대조했다."
    )
    new_section_lines.append("")
    if missing:
        new_section_lines.append(
            f"호출부에는 있으나 원본 API 덤프에서 식별자를 찾지 못한 속성 {len(missing)}개:"
        )
        new_section_lines.append("")
        for a in missing:
            new_section_lines.append(f"- `{a}`")
    else:
        new_section_lines.append("모든 호출부 속성이 원본 API 덤프의 식별자 목록에서 발견되었다.")
    new_section_lines.append("")

    MD_PATH.write_text(head + "\n".join(new_section_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def main() -> int:
    files = iter_target_files()
    all_usages: list[Usage] = []
    parse_failures: list[tuple[str, str]] = []

    for f in files:
        usages, err = analyze_file(f)
        if err is not None:
            rel = relpath(f)
            parse_failures.append((rel, err))
            print(f"[SKIP] {rel}: {err}", file=sys.stderr)
            continue
        all_usages.extend(usages)

    write_csv(all_usages)
    write_md(all_usages, parse_failures, len(files))
    cross_check_with_task002(all_usages)

    unique_attr_count = len({u.attr for u in all_usages})
    print(f"분석 대상 파일: {len(files)}개")
    print(f"고유 속성: {unique_attr_count}개")
    print(f"총 사용처: {len(all_usages)}건")
    print(f"파싱 실패: {len(parse_failures)}개")
    print(f"CSV: {CSV_PATH}")
    print(f"MD:  {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
