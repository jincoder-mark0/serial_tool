# RULES.md — SerialTool 운영 규칙

이 문서는 SerialTool의 작업·검증·커밋 운영 규율을 정의한다. 아키텍처 최상위 규칙은 `AGENTS.md`, 현재 작업 상태는 `Task.MD`를 우선한다.

> 현재 기준 브랜치: `main`
> Presenter/View Boundary 리팩토링: PR #1 squash merge 완료

---

## 1. Source of Truth

```text
사용자의 최신 명시적 지시
  > 현재 코드
  > AGENTS.md
  > architecture contract tests
  > RULES.md (이 문서)
  > Task.MD
  > doc/00_overview.md
  > 리팩토링/역사 문서
```

**사용자 지시가 최상위다.** 이 문서에 적힌 절차와 충돌하면 사용자 지시를 따르고,
반복되는 지시는 이 문서를 고쳐 규칙으로 만든다 (2026-09-03 추가 — 머지 방식이 실제로
충돌했다: 아래 §8이 squash를 규정하기 전까지 매 PR마다 사용자에게 되물었다).

초기 설계/과거 문서의 EventBus/EventRouter 구조를 현재 runtime에 되살리지 않는다.

---

## 2. 검증 규율

변경 완료는 실제로 실행한 검증만 근거로 선언한다.

1. 변경과 가장 가까운 테스트
2. architecture/lifecycle 관련 테스트
3. `ruff check .`
4. 전체 `pytest`
5. UI 문자열 변경 시 language key 검사
6. Task 문서 변경 시 task-board consistency 검사
7. merge 대상 변경은 GitHub Actions 확인

Windows 기준:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

보고 규칙:

- 실행하지 않은 테스트를 `통과`라고 쓰지 않는다.
- source review만 했으면 `source-level 확인`이라고 쓴다.
- Mock / LOOPBACK / virtual Serial / 실기기 검증을 구분한다.
- 실제 장비로만 확인 가능한 항목은 `실기기 미검증`으로 남긴다.

현재 post-merge baseline과 backlog는 `Task.MD`에 기록한다.

---

## 3. Architecture Discipline

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

- View -> Model 직접 import/호출 금지
- Model -> Presenter/View import 금지
- Presenter/Coordinator concrete QtWidgets 생성 금지
- `ApplicationBootstrapper` = 유일한 runtime composition root
- Presenter hidden singleton/manager fallback 금지
- production 주요 event = direct Qt signal
- `EventRouter`, `core/event_bus.py`, `EventTopics` 재도입 금지
- 동일 event를 복수 전달 체계로 중복 전달 금지

`tests/test_direct_event_topology.py`가 제거된 event relay 계층의 재생성을 차단한다.

---

## 4. Composition / Lifecycle

Bootstrapper가 소유한다.

- Model/Service 생성
- Presenter/Coordinator 생성
- 초기 View state restore
- static signal wiring
- MainPresenter 생성
- runtime owner strong reference

Worker/QThread/QRunnable 변경 시 최소 확인:

- start / normal finish
- cancel / stop
- port close와의 경쟁
- application shutdown
- bounded wait / outstanding worker 정책
- worker -> View 접근 여부

---

## 5. Shutdown Data Preservation

```text
background producers stop
        ↓
AutoTx / UI-data timers stop
        ↓
system log close
        ↓
state save
        ↓
connection close
        ↓
QCoreApplication.processEvents()
        ↓
DataLogger stop_all()
```

queued RX를 drain하기 전에 DataLogger를 닫지 않는다.

---

## 6. DTO / Settings / UI

- 계층 간 payload는 DTO 우선.
- Config key는 `ConfigKeys` 사용.
- canonical 기본값은 `common/defaults.py` / `common/constants.py` 사용.
- View state와 Settings path 사이 explicit adapter 사용.
- UI 텍스트는 language resource 사용.
- 테마 색/폰트는 resource/QSS/View manager 사용.
- offscreen은 기능 검증용이며 최종 UX/폰트 판정 수단으로 사용하지 않는다.

---

## 7. Stale Test 교정

- constructor mismatch -> 현재 explicit DI contract로 test/caller 수정
- removed internal field -> 실제 owner public API 사용
- removed EventRouter/EventBus/EventTopics contract -> direct Qt signal 기준으로 test 수정
- worker ownership mismatch -> 실제 Manager/Service owner 테스트

테스트를 맞추기 위해 production architecture를 옛 구조로 되돌리지 않는다.

---

## 8. Git 규율

기본 개발 흐름:

```text
feature branch
  -> PR
  -> CI
  -> review
  -> merge
```

- `main` 직접 write는 사용자의 명시적 요청이 있는 경우에만 수행.
- rebase/force update는 destructive operation이므로 사용자 승인 후 수행.
- commit message는 `Feat:`, `Fix:`, `Docs:`, `Refactor:`, `Style:`, `Test:`, `Rule:` 접두어를 사용.
- unrelated 변경을 섞지 않는다.
- 비밀정보, logs, `.venv`, `__pycache__` 등을 commit하지 않는다.

### 8.1 머지 방식

**이 저장소는 squash merge를 쓰고 머지 후 브랜치를 삭제한다.**

```powershell
gh pr merge <번호> --squash --delete-branch
git switch main; git pull --ff-only
```

머지 실행 여부는 사용자가 정한다 — CI Green이어도 자동으로 머지하지 않는다.
방식 자체는 위와 같이 고정이므로 매번 되묻지 않는다.

### 8.2 브랜치를 딴 base를 확인한다

PR을 만들기 전에 **base 대비 커밋 목록**을 확인한다. 로컬 `main`이 `origin/main`보다
앞서 있으면 그 커밋들이 전부 PR에 딸려 들어간다.

```powershell
git log --oneline origin/main..HEAD
```

실제 사고(2026-09-02, PR #19): push되지 않은 로컬 커밋 3개 위에서 브랜치를 따는 바람에
S-084 수정과 문서 2건이 함께 squash되어, 그 작업들이 자기 커밋 메시지를 잃었다.
`git diff --cached --stat`은 로컬 HEAD 기준이라 이것을 보여주지 않는다.

### 8.3 스테이징은 pathspec으로 한다

```powershell
git add <경로...>          # 의도한 파일만
git status                  # 무엇이 올라가는지 확인
git commit -F <메시지파일> <경로...>
```

`git add -A` / `git add .`는 쓰지 않는다 — 출처 불명 파일이 리뷰 없이 딸려 들어간다
(`doc/mistakes.md` #3의 실제 사고). 여러 줄 커밋 메시지는 셸 인용을 거치지 않도록
파일로 넘긴다 (#10).

### 8.4 완료 보고에는 수치를 적는다

커밋 메시지와 PR 본문에 **실행한 검증의 실측치**를 적는다. 체크 표시만 있고 수치가
없으면 완료 보고로 인정하지 않는다.

```text
검증: 785 passed, ruff 0건, language/task-board gate Green
```

여러 번 돌린 경우 횟수도 적는다 (`781 passed, 순차 10회 반복 동일`) — 타이밍에
민감한 변경은 1회 통과가 근거가 되지 못한다.

---

## 9. Task / 문서 운영

- 현재 해야 할 일은 `Task.MD` 한 곳에서 관리.
- 과거 S-xxx 상세 이력은 `tasks/`, `doc/history/`, `doc/CHANGELOG.md`에 보존.
- 중요한 사용자 관점 변경은 `doc/CHANGELOG.md`에 기록.
- 반복 실수는 `doc/mistakes.md`에 기록.
- `doc/refactoring_validation_report_20260830.md`는 PR #1 merge 당시의 감사/검증 snapshot으로 보존.

문서가 코드와 충돌하면 문서를 현행화한다. 문서에 맞추기 위해 올바른 production architecture를 되돌리지 않는다.

---

## 10. 완료 조건

해당 변경의 위험도에 맞는 검증을 실제 수행하고 다음을 확인한다.

```text
Architecture boundary preserved
No hidden runtime fallback
No worker -> QWidget access
No duplicate event topology
Relevant tests Green
Ruff Green
Repository consistency Green when applicable
Docs match current main
```

---

## 11. 판정 근거 도구 (Evidence Tooling)

판정에 쓴 스크립트가 세션 스크래치에만 남으면 그 판정은 **재현할 수 없는 주장**이 된다.
스크래치는 소모품이므로 근거는 저장소 안에 자리를 갖는다.

### 11.1 승격 대상

커밋 메시지·PR·`doc/CHANGELOG.md`·`Task.MD`에 **인용되는 수치를 만든 스크립트**는
저장소로 옮긴다. "간단한 스크립트였다"는 예외 사유가 아니다.

| 자리 | 대상 |
|---|---|
| `tools/` | 두 번 이상 실행하거나 게이트·CI에 들어가는 정식 도구 |
| `tools/oneoff/` | 한 번 쓰고 끝났지만 **결론의 근거**인 스크립트 |

`tools/oneoff/`는 상단 주석 4줄(무엇을 / 언제 / 무엇을 증명 / 실행법)만 갖추고
**그때 돌린 그대로** 둔다. 리팩토링·일반화하지 않는다 (`tools/oneoff/README.md`).

예외는 하나다 — **호출 시그니처가 바뀌어 실행 자체가 불가능해진 경우**에만 최소 변경으로
맞추고 무엇을 왜 바꿨는지 README에 적는다. 돌아가지 않는 스크립트는 근거가 아니다
(2026-09-03 추가 — View manager 주입으로 `MainWindow()` 시그니처가 바뀌면서 실제로 발생).

비밀값(토큰·키)을 다루는 스크립트는 승격하지 않는다. 스크래치에 두고 절차만 문서화한다.

### 11.2 새 검사기는 네거티브 테스트를 먼저 통과해야 한다

새 검사기·계약 테스트·게이트는 **고의로 넣은 결함을 실제로 잡아낸다는 증거**를 남긴 뒤에야
게이트로 인정한다. 정상 입력이 통과하는 것은 증거가 아니다.

```text
1. 수정을 되돌리거나 결함을 주입한다
2. 새 검사기가 실패하는지 확인하고 실패 메시지를 기록한다
3. 원복한 뒤 통과를 확인한다
```

회귀 시 **hang이 아니라 실패**로 드러나게 만든다 — 채우기·대기 루프에는 상한을 둔다.
멈추는 테스트는 실패하는 테스트보다 진단이 어렵다.

### 11.3 게이트 도구를 고칠 때

판정 로직이 바뀌면 그 도구로 낸 **과거 판정이 여전히 유효한지** 확인하고, 다시 돌려야
하는 대상을 `Task.MD`에 적는다. 도구가 관대해지면 통과는 의미를 잃는다.

도구의 출력 형식은 **저장된 파일이 정본**이다. 도구가 저장 형식을 바꾸면 절차를 따를
때마다 무관한 재포맷이 diff를 덮는다 (`tests/test_language_tool_format.py`가 고정한다).

---

## 12. 셸·파일 조작 규율

이 환경은 PowerShell과 Bash를 둘 다 제공하고 문법이 다르다. 여기서 반복 사고가 났다
(`doc/mistakes.md` #10, 2026-09-03 재발).

- **여러 줄 텍스트나 이스케이프(`\n`, 정규식)가 섞인 파일 내용은 heredoc으로 만들지 않는다.**
  Write 도구로 파일을 직접 쓴다. heredoc 안의 `\n`은 셸·Python 양쪽에서 해석되어
  문자열 미종료 SyntaxError를 만든다.
- **임시 파일은 세션 스크래치패드 절대경로만 쓴다.** `/tmp`는 Bash와 Windows Python이
  서로 다른 곳을 가리켜, Bash로 쓴 파일을 Python이 못 찾는다.
- 파일 내용을 문자열 치환으로 수술하지 말고, 짧으면 Write로 다시 쓴다. 치환이 조용히
  실패하면 "고쳤다고 믿는 상태"가 되고, 네거티브 대조가 통과해 버린다 (실제 발생).
