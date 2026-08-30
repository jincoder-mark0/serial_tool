# RULES.md — SerialTool 운영 규칙

이 문서는 SerialTool의 작업·검증·커밋 운영 규율을 정의한다.
아키텍처 최상위 규칙은 `AGENTS.md`, 현재 작업 상태는 `Task.MD`를 우선한다.

---

## 1. Source of Truth

충돌 시 우선순위:

```text
현재 코드
  > AGENTS.md
  > architecture contract tests
  > Task.MD
  > doc/refactoring_validation_report_20260830.md
  > README.md / doc/00_overview.md
  > 과거 이력 문서
```

초기 설계/과거 문서의 EventBus/EventRouter 구조를 현재 runtime에 되살리지 않는다.

---

## 2. 검증 규율

### 완료 선언

변경 완료는 다음 중 실제로 실행한 검증을 정확히 보고해야 한다.

1. 변경과 가장 가까운 테스트
2. architecture/lifecycle 관련 테스트
3. `ruff check .`
4. 전체 `pytest`
5. UI 문자열 변경 시 language key 검사
6. Task 문서 변경 시 task-board consistency 검사

현재 리팩토링 브랜치는 전체 Green baseline이 아직 다시 확정되지 않았다.
과거의 `497 passed` 같은 숫자를 현재 완료 기준으로 사용하지 않는다.
전체 pytest를 실제 실행한 뒤 그 결과를 새 기준선으로 기록한다.

Windows/CI 기준:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

### 보고 규칙

- 실행하지 않은 테스트는 `통과`라고 쓰지 않는다.
- source review만 했으면 `source-level 확인`이라고 쓴다.
- Mock/LOOPBACK/실기기 여부를 구분한다.
- 실제 장비로만 확인 가능한 항목은 `실기기 미검증`으로 남긴다.

### Threading 변경

Worker/QThread/QRunnable 변경은 최소 다음을 확인한다.

- start
- normal finish
- cancel/stop
- application shutdown
- port close와 겹치는 경우
- running object가 파괴되지 않는지

---

## 3. Architecture Discipline

현재 architecture invariant는 `AGENTS.md`를 따른다.

### 필수 방향

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

- View는 Model 직접 import/호출 금지.
- Model은 Presenter/View import 금지.
- Presenter/Coordinator는 concrete QtWidgets 생성 금지.
- `ApplicationBootstrapper`가 유일한 runtime composition root.
- Presenter 내부 hidden singleton/manager fallback 생성 금지.

### Event 규칙

production 주요 이벤트는 **direct Qt signal**을 기본으로 한다.

- `EventRouter` 재도입 금지.
- 동일 event의 `Qt Signal + EventBus + Router` 중복 전달 금지.
- `core/event_bus.py`는 legacy/test utility로 남아 있을 수 있으나 새 runtime 기능의 기본 수단으로 사용하지 않는다.
- 새 event topic이 필요하다는 이유만으로 EventBus를 확장하지 않는다. 먼저 명확한 owner의 Qt signal로 표현 가능한지 검토한다.

### DTO

계층 간 의미 있는 payload는 `common/dtos.py` DTO를 우선한다.
raw dict를 새 public contract로 만들지 않는다.

### Settings

- persistence는 `SettingsManager`와 전용 Coordinator를 통한다.
- Config key는 `ConfigKeys`를 사용한다.
- schema 변경 시 migration/fallback을 함께 검토한다.
- 기본값은 `common/defaults.py` / `common/constants.py` 정본을 사용한다.

---

## 4. Composition / Lifecycle 규칙

### Runtime object 생성

다음은 `ApplicationBootstrapper`가 소유한다.

- Model/Service 생성
- Presenter/Coordinator 생성
- View 초기 state restore 순서
- static signal wiring
- MainPresenter 생성
- runtime owner의 강한 참조

테스트 편의를 위해 production Presenter에 optional fallback 생성자를 다시 추가하지 않는다.

### Shutdown

`ShutdownCoordinator`의 핵심 data-preservation 순서를 유지한다.

```text
background producers stop
        ↓
UI/data timers stop
        ↓
state save
        ↓
connection close
        ↓
QCoreApplication.processEvents()
        ↓
DataLogger stop_all()
```

S-059의 queued RX 보존 순서를 깨지 않는다.

Auto Tx는 transient runtime state다. 종료 시 state 저장 전에 stop/check 해제한다.

---

## 5. UI / 다국어 규율

- UI 텍스트는 language resource를 사용한다.
- 새 key/변경 key는 en/ko를 함께 관리한다.
- `tools/check_language_keys.py`를 실행한다.
- 테마 색/폰트는 QSS/resource/View manager를 통한다.
- widget 코드에 새로운 하드코딩 색을 넣지 않는다.
- UI/UX 판정이 필요한 변경은 가능하면 실제 화면/네이티브 렌더를 확인한다.
- offscreen은 기능 테스트용이지 폰트/잘림의 최종 UX 판정 수단이 아니다.

---

## 6. Stale Test 교정 규칙

대규모 리팩토링 중 테스트가 옛 architecture를 붙잡고 있을 수 있다.

### constructor mismatch

테스트를 새 explicit DI/composition root 구조로 이동한다.
production에 optional fallback을 복구하지 않는다.

### removed internal field

실제 owner의 public API나 `ApplicationComponents`를 사용한다.
MainPresenter를 service locator로 되돌리지 않는다.

### removed EventRouter/EventBus path

direct Qt signal topology로 테스트를 수정한다.
옛 bridge를 production에 복원하지 않는다.

### worker ownership mismatch

실제 Manager/Service owner를 테스트한다.
Presenter 내부 worker field를 다시 추가하지 않는다.

---

## 7. 커밋 규율

- 현재 리팩토링 write는 `refactor/presenter-view-boundary`에만 수행한다.
- `main` 직접 write 금지.
- 커밋 메시지는 한국어, 접두어 사용:
  - `Feat:`
  - `Fix:`
  - `Docs:`
  - `Refactor:`
  - `Style:`
  - `Test:`
  - `Rule:`
- 무엇보다 **왜** 바꿨는지를 커밋 메시지/문서에 남긴다.
- unrelated 변경을 섞지 않는다.
- 비밀정보, logs, .venv, __pycache__ 등을 커밋하지 않는다.

### History rewrite

squash/rebase/force update는 destructive operation이다.

- 검증 Green 이전에는 수행하지 않는다.
- 사용자 명시 승인 없이 수행하지 않는다.

---

## 8. Task / 문서 운영

- 현재 해야 할 일은 `Task.MD`에 체크리스트로 관리한다.
- 과거 S-xxx 상세 이력은 `tasks/`, `doc/history/`, `doc/CHANGELOG.md`에 보존한다.
- 중요한 구조 변경은 `doc/CHANGELOG.md`에 기록한다.
- 반복 실수는 `doc/mistakes.md`에 기록한다.
- 현재 리팩토링 판단 근거는 `doc/refactoring_validation_report_20260830.md`를 참조한다.

문서가 코드와 충돌하면 문서를 현행화한다. 문서에 맞추기 위해 올바른 production architecture를 되돌리지 않는다.

---

## 9. 자가 진화 규칙

실수/빌드 오류/규약 위반이 발생하면 `doc/mistakes.md`에 기록한다.

형식 예:

```text
YYYY-MM-DD | 증상 | 원인 | 일회성: 예/아니오 | 조치
```

동일 원인이 반복되면 가장 강한 수단으로 차단한다.

```text
테스트/도구 자동 검사
    > 작업 절차/스킬
    > 문서 규칙
```

규칙화 커밋은 `Rule:` 접두어를 사용한다.

---

## 10. 현재 리팩토링 완료 조건

다음이 모두 Green일 때 구조 리팩토링 검증 완료로 본다.

- stale API/constructor 전수 감사
- ruff 0건
- layer/architecture contract tests Green
- lifecycle/threading tests Green
- 전체 pytest Green
- language key 검사 Green
- task-board 검사 Green
- GitHub Actions PR CI Green
- README/AGENTS/CLAUDE/RULES/overview와 현재 코드 정합

완료 조건의 세부 순서는 `Task.MD`를 따른다.
