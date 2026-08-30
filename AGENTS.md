# SerialTool AGENTS.md

이 문서는 SerialTool 저장소에서 작업하는 AI/코딩 에이전트의 **최상위 실행 지침**이다.
목표는 빠른 변경보다 **정확한 아키텍처 경계, 데이터 보존, 테스트 가능성, 검증 가능한 변경**을 우선하는 것이다.

> 현재 기준 브랜치: `main`
> 현재 작업 보드: [`Task.MD`](Task.MD)
> 리팩토링 기록: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)

Presenter/View Boundary 리팩토링은 PR #1에서 squash merge 완료됐다. 현재 작업은 `main`의 post-merge baseline을 기준으로 진행한다.

---

## 1. 작업 시작 전 원칙

1. 현재 브랜치와 작업 목적을 확인한다.
2. 기존 코드, 호출부, 관련 테스트를 먼저 읽는다.
3. 현재 코드와 architecture contract를 과거 계획 문서보다 우선한다.
4. 실행하지 않은 검증을 통과했다고 표현하지 않는다.
5. `main` 직접 write는 일반적으로 피하고 feature branch + PR을 사용한다. 사용자가 명시적으로 직접 수정을 요청한 경우에만 예외적으로 수행한다.

Source of truth:

```text
현재 코드
  > AGENTS.md
  > architecture contract tests
  > Task.MD
  > doc/00_overview.md
  > 리팩토링/역사 문서
```

---

## 2. Architecture Invariant

핵심은 **Single Composition Root + Passive View + explicit dependency injection + direct Qt signal**이다.

```text
main.py
  |
  v
ApplicationBootstrapper
  +-- View state restore
  +-- Model / Service 생성
  +-- Presenter 생성
  +-- Coordinator 생성
  +-- static signal wiring
  +-- MainPresenter 생성
  |
  v
ApplicationComponents
```

Dependency direction:

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

규칙:

- `common/`: DTO/Enum/default/constants. 상위 계층 import 금지.
- `core/`: infrastructure. model/presenter/view import 금지.
- `model/`: runtime/business/I/O. presenter/view import 금지.
- `presenter/`: View/Model orchestration. concrete QtWidgets 생성 금지.
- `view/`: Passive View. Model 직접 import/호출 금지.

`tests/test_layer_dependencies.py`와 architecture contract tests가 이 경계를 고정한다.

---

## 3. Composition Root / DI

`application_bootstrap.py`가 유일한 runtime object graph owner다.

Bootstrapper가 소유할 것:

- shared Manager/Service 생성
- Model/Presenter/Coordinator constructor wiring
- static signal topology
- 초기 View state restore
- MainPresenter 생성
- runtime owner strong reference

Presenter 내부 hidden construction 금지:

```python
self.settings = SettingsManager()
self.manager = SomeManager()
self.service = SomeService(...)
```

필요 dependency는 constructor로 주입한다.

---

## 4. Event / Signal

production 주요 이벤트는 direct Qt signal을 사용한다.

- `EventRouter` 재도입 금지
- 동일 event의 `Qt Signal + EventBus + Router` 중복 전달 금지
- worker thread에서 QWidget/View 상태 조회 금지
- Presenter 간 callback으로 숨은 수평 의존 생성 금지
- broad `signal.disconnect()` 금지

`core/event_bus.py`는 legacy/core test utility로 남을 수 있으나 새 production feature의 기본 event mechanism으로 사용하지 않는다.

---

## 5. 책임 소유권

### Connection

- `ConnectionController`: session registry/open/close/send/broadcast/lifecycle
- `ConnectionSessionFactory`: Transport + ConnectionWorker 생성
- `PacketParserManager`: parser lifecycle/feed/flush

### Transmission

- `CommandTransmissionService`: command processing/prefix/suffix/target resolution/validation/send

### Port / Macro / File

- `PortPresenter`: Port View 중재
- `PortScanManager`: scan worker lifecycle
- `MacroPresenter`: Macro UI
- `MacroRunner`: execution thread
- `MacroScriptManager`: script I/O + loader lifecycle
- `MacroExecutionCoordinator`: target snapshot/send/port-close policy
- `FileTransferManager`: transfer lifecycle/QThreadPool/progress/cancel
- `FilePresenter`: dialog/View presentation

### Logging / State

- `LoggingCoordinator`: port/system recording
- `TrafficMonitor`: Tx/Rx logging/statistics
- `DataTrafficHandler`: RX UI batching
- `StatusCoordinator`: status timer/statistics
- `SettingsCoordinator`: preferences/theme/language/font persistence
- `ControlStateCoordinator`: Manual/Macro enable policy
- `ShutdownCoordinator`: shutdown ordering/state save

---

## 6. DTO / Settings / Defaults

- 계층 경계를 넘는 의미 있는 payload는 `common/dtos.py` DTO 우선.
- persistence key는 `ConfigKeys` 사용.
- canonical 기본값은 `common/defaults.py` / `common/constants.py` 사용.
- View state와 Settings path를 동일한 key shape로 가정하지 않는다.
- UI 문자열은 language resource를 사용한다.

---

## 7. Thread / Lifecycle

새 QThread/QRunnable/background worker에는 반드시 owner와 shutdown path를 동시에 정의한다.

확인 항목:

```text
누가 생성하는가?
누가 strong reference를 갖는가?
누가 cancel/stop 하는가?
shutdown에서 누가 wait 하는가?
timeout 후 살아 있으면 어떤 제한을 두는가?
worker가 View에 접근하지 않는가?
```

현재 owner:

- ConnectionWorker -> ConnectionController
- Port scan worker -> PortScanManager
- Macro script loader -> MacroScriptManager
- File transfer runnable -> FileTransferManager
- Macro execution -> MacroRunner
- Status timer -> StatusCoordinator

반환하지 않는 OS/file I/O helper는 강제 종료하지 않으며 Manager가 outstanding helper를 작업별 최대 1개로 제한한다.

---

## 8. Shutdown Data Preservation

```text
background producers stop
  -> AutoTx stop
  -> UI/data timers stop
  -> system log close
  -> state save
  -> connection close
  -> QCoreApplication.processEvents()
  -> DataLoggerManager.stop_all()
```

queued RX가 drain되기 전에 DataLogger를 닫지 않는다.

---

## 9. 검증 순서

변경 후 작은 범위부터 확대한다.

```text
closest tests
  -> architecture/lifecycle tests if relevant
  -> ruff check .
  -> full pytest
  -> language/task checks if relevant
  -> GitHub Actions
```

Windows 기준:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

2026-08-30 post-merge baseline은 `Task.MD`에 기록한다.

---

## 10. 실패 교정 원칙

- constructor mismatch -> 현재 explicit DI contract로 test/caller 수정
- removed internal field -> 실제 owner public API 사용
- signal mismatch -> direct Qt signal topology 기준 수정
- QThread failure -> 실제 Manager/Service owner에서 수정
- state persistence mismatch -> View shape와 Settings shape 사이 explicit adapter 사용
- 데이터 손실 -> producer stop / queued signal drain / logger close 순서를 먼저 감사

테스트를 맞추기 위해 production architecture를 옛 구조로 되돌리지 않는다.

---

## 11. Coding / Documentation Style

- Pythonic naming + type hint
- 한국어 주석/Docstring, Why/How 중심
- Hardware/Signal/FSM/Worker/Manager 등 기술 주체 명확화
- standard English technical jargon 사용
- 긴 설명은 section/bullet hierarchy
- Signal Flow/Block Diagram은 ASCII-only
- 의미 있는 기존 주석을 이유 없이 삭제하지 않음

---

## 12. Git / 문서

- 기본 개발 흐름은 feature branch -> PR -> CI -> merge.
- `main` 직접 write는 사용자의 명시적 요청이 있는 경우에만 수행.
- squash/rebase/force update는 사용자 승인 후 수행.
- 현재 작업 상태는 `Task.MD`에 기록.
- 사용자 관점 변경은 `doc/CHANGELOG.md`에 기록.
- 반복 실수는 `doc/mistakes.md`에 기록.
- 과거 작업/결정은 `doc/history/`, `tasks/`에 보존.

---

## 13. 완료 조건

작업 완료를 선언하려면 해당 변경에 필요한 검증을 실제 실행하고 결과를 기록한다.

```text
Architecture boundary preserved
No hidden dependency
No worker -> QWidget access
No duplicate event topology
Relevant tests Green
Ruff Green
Repository consistency Green when applicable
Docs match current main
```
