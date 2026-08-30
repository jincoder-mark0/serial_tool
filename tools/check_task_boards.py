"""
과거 태스크 상태 정합 검사 (태스크 파일 Status / tasks/README.md 교차 검증).

UI/UX나 코드가 아니라 **작업 기록의 신뢰성**을 지키는 도구입니다.

## WHY
태스크 상태가 태스크 파일 상단 `- Status:`와 `tasks/README.md`의 표에 중복
기록된다. 사람이 두 곳을 손으로 맞추다 보니 실제로 어긋났다
(2026-08-22 발견: 감사 계열 태스크 다수가 보드는 완료인데 파일 헤더는 TODO였고,
S-036은 Task.MD 안에서만 두 번 등장해 완료/대기를 동시에 말하고 있었다).
보드가 거짓을 말하면 다음 세션이 끝난 일을 다시 하거나 남은 일을 끝난 것으로
착각한다. 루트 `Task.MD`는 2026-08-30부터 현재 검증 작업만 관리하므로 과거
S-xxx 상태를 중복하지 않는다.

## WHAT
* 상태 어긋남: 같은 태스크 ID가 두 소스에서 다른 상태로 기록된 경우
* 중복 행: 한 보드 안에 같은 ID가 다른 상태로 두 번 등장하는 경우
* 미등재: `tasks/S-xxx-*.md`는 있는데 보드 표에 행이 없는 경우
* 유령 행: 보드가 태스크 파일을 링크했는데 그 파일이 없는 경우

상태 표기는 자유 서술(사유·날짜)이 뒤따르므로 **판정 토큰만** 정규화해 비교한다.
괄호 안 부연(`DONE (러너 확인 대기)` 등)은 의도적으로 무시한다 — 그 자유도가
보드의 가치이고, 검사가 막아야 할 것은 부연이 아니라 **판정 자체의 불일치**다.

## HOW
    python tools/check_task_boards.py          # 위반 시 exit 1
"""
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TASKS_DIR = PROJECT / "tasks"
README_MD = TASKS_DIR / "README.md"

TASK_ID = re.compile(r"S-\d{3}")


class Board:
    """보드 한 개에서 읽어낸 태스크 상태."""

    def __init__(self, label: str):
        self.label = label
        self.status = {}       # task_id -> 정규화된 상태
        self.linked = set()    # 태스크 파일을 링크한 ID (파일 존재를 요구하는 행)
        self.duplicates = []   # (task_id, 먼저 나온 상태, 나중에 나온 상태)


def normalize(raw: str) -> str:
    """
    자유 서술 상태 문자열에서 판정 토큰만 뽑아낸다.

    태스크 파일은 `TODO`/`DONE`, 보드는 `DONE`/`TODO`와 `⛔ 보류` 등을 사용한다.
    `대기`는 "아직 시작하지 않음"이라 TODO와 같은 판정으로 본다 (사유는 비고에 남는다).

    판정은 **부연을 떼어낸 선두 부분**으로만 내린다. `DONE (러너 확인 대기)`,
    `DONE (높이 잔여는 보류 판정)`처럼 괄호 안에 다른 판정 단어가 들어가는 표기가
    실제로 있어서, 문자열 전체를 훑으면 완료된 태스크를 대기/보류로 오독한다.
    """
    text = raw.strip()
    # 괄호·em대시 뒤의 서술은 사유·날짜이지 판정이 아니다
    head = re.split(r"[(—\-]", text, maxsplit=1)[0].strip()
    for token in ("DONE", "DOING", "TODO"):
        if head.upper().startswith(token):
            return token
    if "완료" in head:
        return "DONE"
    if "보류" in head or head.startswith("⛔"):
        return "HOLD"
    if "대기" in head or head.startswith("⏸"):
        return "TODO"
    return "UNKNOWN"


def split_row(line: str) -> list:
    """마크다운 표 행을 셀 리스트로 나눈다 (표 행이 아니면 빈 리스트)."""
    text = line.strip()
    if not text.startswith("|"):
        return []
    return [c.strip() for c in text.strip("|").split("|")]


def read_task_files() -> dict:
    """태스크 파일 상단 `- Status:` 헤더에서 ID -> 상태를 수집한다."""
    result = {}
    for path in sorted(TASKS_DIR.glob("S-*.md")):
        found = TASK_ID.match(path.name)
        if not found:
            continue
        status = "UNKNOWN"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- Status:"):
                status = normalize(line.split(":", 1)[1])
                break
        result[found.group()] = status
    return result


def read_board(path: Path, label: str) -> Board:
    """
    마크다운 표에서 태스크 상태를 수집한다.

    상태 칸의 위치는 표마다 다르다 (`| ID | 제목 | 상태 |` 도 있고
    `| ID | 제목 | Phase | 상태 | 비고 |` 도 있다). 마지막 칸을 상태로 가정하면
    비고를 상태로 오독하므로, **각 표의 헤더 행에서 `상태` 열 인덱스를 찾아**
    그 칸만 읽는다. 표가 끝나면 열 위치를 잊는다.
    """
    board = Board(label)
    status_index = None
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = split_row(line)
        if not cells:
            status_index = None
            continue
        if "상태" in cells:
            status_index = cells.index("상태")
            continue
        if status_index is None or status_index >= len(cells):
            continue
        found = TASK_ID.search(cells[0])
        if not found:
            continue
        task_id = found.group()
        status = normalize(cells[status_index])
        # 같은 ID가 한 보드에 두 번 나오면(오래된 행이 남은 경우) 서로 다른 판정을
        # 말할 수 있다 — 조용히 덮어쓰지 않고 드러낸다.
        if task_id in board.status and board.status[task_id] != status:
            board.duplicates.append((task_id, board.status[task_id], status))
        board.status[task_id] = status
        # 링크가 걸린 행만 태스크 파일 존재를 요구한다. 링크 없는 Phase 요약 행
        # (S-001~S-005)은 태스크 문서 체계 이전의 기록이라 파일이 없어도 정상이다.
        if "](" in cells[0]:
            board.linked.add(task_id)
    return board


def main() -> int:
    files = read_task_files()
    boards = [read_board(README_MD, "tasks/README.md")]

    problems = []

    for board in boards:
        for task_id, first, second in board.duplicates:
            problems.append(
                "%s: 중복 행 - %s 안에서 %s / %s 로 두 번 기록됨" % (task_id, board.label, first, second)
            )

    for task_id in sorted(files):
        sources = {"태스크 파일": files[task_id]}
        missing = []
        for board in boards:
            if task_id in board.status:
                sources[board.label] = board.status[task_id]
            else:
                missing.append(board.label)
        if missing:
            problems.append(
                "%s: 미등재 - %s 에 행이 없음 (파일 상태=%s)"
                % (task_id, ", ".join(missing), files[task_id])
            )
        if len(set(sources.values())) > 1:
            detail = ", ".join("%s=%s" % (name, value) for name, value in sources.items())
            problems.append("%s: 상태 불일치 - %s" % (task_id, detail))
        if files[task_id] == "UNKNOWN":
            problems.append("%s: 태스크 파일에 '- Status:' 헤더가 없거나 해석 불가" % task_id)

    for board in boards:
        for task_id in sorted(board.linked - set(files)):
            problems.append("%s: 유령 행 - %s 가 링크했으나 태스크 파일이 없음" % (task_id, board.label))

    if problems:
        print("[FAIL] 작업 보드 정합 위반 %d건" % len(problems))
        for item in problems:
            print("  - %s" % item)
        print("\n태스크 파일 Status와 tasks/README.md를 같은 판정으로 맞추십시오.")
        return 1

    print("[OK] 태스크 %d건의 상태가 과거 태스크 인덱스와 일치합니다." % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
