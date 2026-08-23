---
name: task-done
description: SerialTool 태스크 완료 판정·마감 절차 — 검증 3단계, 문서 갱신, 커밋 규약
---

# task-done — 태스크 완료 절차

태스크(기능 구현·버그 수정·리팩토링)를 "완료"로 선언하기 전에 이 절차를 그대로 수행한다.
하나라도 건너뛰면 완료가 아니다 (RULES.md §2).

## 1. 검증 (순서대로)

```powershell
# ① 변경과 가장 가까운 테스트
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest tests/test_<관련>.py -q

# ② 전체 테스트 (기준선 473개 — 늘었으면 RULES.md·README §1.4·tests/README·이 파일 숫자 갱신)
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q

# ③ UI 문자열을 건드렸다면 (아니면 생략)
.venv\Scripts\python tools\check_language_keys.py

# ④ 문서 갱신(2단계) 후 — 작업 보드 3중 정합
.venv\Scripts\python tools\check_task_boards.py
```

- 실패 시 완료 선언 금지 — 원인 수정 후 재실행. 기존 테스트를 임의로 삭제·완화하지 않는다.
- 보고에는 실행한 명령·결과 요약·**Mock/실기기 여부**를 명시한다.
- 실기기로만 확인 가능한 동작이 남으면 "실기기 미검증" 항목으로 보고에 적는다.

## 2. 문서 갱신

**상태는 세 곳에 있다 — 셋 다 같은 판정으로 갱신한다.** 하나만 고치면 보드가 거짓을
말하고, 다음 세션이 끝난 일을 다시 하거나 남은 일을 끝난 것으로 착각한다
(2026-08-22 실측 30건 드리프트 → `tools/check_task_boards.py`로 기계 고정).

1. **`tasks/S-0xx-*.md` 상단 `- Status:`** — `DONE (날짜 — 수행 주체, 한 줄 근거)`.
   가장 빠뜨리기 쉬운 곳이다. 판정 토큰(`DONE`/`TODO`/`⛔ 보류`)을 **맨 앞**에 둔다 —
   뒤따르는 부연은 자유롭게 써도 되지만 선두 토큰이 검사 대상이다.
2. **`Task.MD`** — 해당 행 상태를 `✅ 완료`로, 비고에 한 줄 근거 (검증 결과 요약).
3. **`tasks/README.md`** — 해당 행 상태를 `DONE`으로. 표에 행이 없으면 **추가**한다.
4. `doc/task.md` — 해당 Phase 체크리스트에 체크 추가 (이력 문서 — 기존 항목 재구성 금지).
5. `doc/CHANGELOG.md` — 사용자 관점의 변경 한 줄.
6. 기능·구조가 바뀌었으면 `README.md` 해당 절 현행화.
   **UI 최소 크기(minimumSizeHint)가 바뀌었으면 `.agent/rules/ui_guide.md` §4의 회귀
   기준선도 함께 갱신한다** — 빠뜨리면 다음 작업자가 실측치를 회귀로 오인한다
   (doc/mistakes.md #5).
7. 작업 중 실수가 있었다면 `doc/mistakes.md`에 기록.

## 3. 커밋

- pathspec 커밋: 신규 파일만 좁은 `git add` 후 `git commit <경로...>`.
- 메시지: 한국어, `Feat:/Fix:/Docs:/Refactor:/Style:/Test:/Rule:` 접두어 + 명령형 제목 1줄,
  본문에는 왜(배경·판단 근거). 상세: `.agent/rules/git_guide.md`.
- 비밀정보·`logs/`·`__pycache__/`·`.venv/` 포함 금지.
