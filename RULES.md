# RULES.md — SerialTool 운영 규칙

이 문서는 SerialTool의 작업·검증·커밋 운영 규율을 정의한다. 아키텍처 최상위 규칙은 `AGENTS.md`, 현재 작업 상태는 `Task.MD`를 우선한다.

> 현재 기준 브랜치: `main`
> Presenter/View Boundary 리팩토링: PR #1 squash merge 완료

---

## 1. Source of Truth

```text
현재 코드
  > AGENTS.md
  > architecture contract tests
  > Task.MD
  > doc/00_overview.md
  > 리팩토링/역사 문서
```

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
- squash/rebase/force update는 destructive operation이므로 사용자 승인 후 수행.
- commit message는 `Feat:`, `Fix:`, `Docs:`, `Refactor:`, `Style:`, `Test:`, `Rule:` 접두어를 사용.
- unrelated 변경을 섞지 않는다.
- 비밀정보, logs, `.venv`, `__pycache__` 등을 commit하지 않는다.

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
