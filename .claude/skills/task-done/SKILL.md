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

# ② 전체 테스트 (기준선 118개 — 늘었으면 RULES.md·README §1.4·tests/README·이 파일 숫자 갱신)
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q

# ③ UI 문자열을 건드렸다면 (아니면 생략)
.venv\Scripts\python tools\check_language_keys.py
```

- 실패 시 완료 선언 금지 — 원인 수정 후 재실행. 기존 테스트를 임의로 삭제·완화하지 않는다.
- 보고에는 실행한 명령·결과 요약·**Mock/실기기 여부**를 명시한다.
- 실기기로만 확인 가능한 동작이 남으면 "실기기 미검증" 항목으로 보고에 적는다.

## 2. 문서 갱신

1. `Task.MD` — 해당 태스크 상태를 `✅ 완료`로, 비고에 한 줄 근거 (검증 결과 요약).
2. `doc/task.md` — 해당 Phase 체크리스트에 체크 추가 (이력 문서 — 기존 항목 재구성 금지).
3. `doc/CHANGELOG.md` — 사용자 관점의 변경 한 줄.
4. 기능·구조가 바뀌었으면 `README.md` 해당 절 현행화.
5. 작업 중 실수가 있었다면 `doc/mistakes.md`에 기록.

## 3. 커밋

- pathspec 커밋: 신규 파일만 좁은 `git add` 후 `git commit <경로...>`.
- 메시지: 한국어, `Feat:/Fix:/Docs:/Refactor:/Style:/Test:/Rule:` 접두어 + 명령형 제목 1줄,
  본문에는 왜(배경·판단 근거). 상세: `.agent/rules/git_guide.md`.
- 비밀정보·`logs/`·`__pycache__/`·`.venv/` 포함 금지.
