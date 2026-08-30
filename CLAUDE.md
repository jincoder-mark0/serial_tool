# CLAUDE.md — SerialTool 작업 지침

이 파일은 Claude 계열 코딩 에이전트용 보조 지침이다. **최상위 정본은 [`AGENTS.md`](AGENTS.md)** 이며 충돌 시 현재 코드와 architecture contract를 우선한다.

> 현재 기준 브랜치: `main`
> 현재 작업 보드: [`Task.MD`](Task.MD)
> 리팩토링 기록: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)

Presenter/View Boundary 리팩토링은 PR #1에서 squash merge 완료됐다. 현재 작업은 post-merge `main` baseline에서 진행한다.

---

## 1. 작업 시작

1. `AGENTS.md`
2. `Task.MD`
3. 작업 대상 소스와 호출부
4. 관련 tests
5. 필요 시 `doc/00_overview.md`, `.agent/rules/`, 과거 리팩토링 기록

과거 문서와 현재 코드가 다르면 현재 코드와 architecture contract를 우선한다.

복구하지 않을 과거 구조:

```text
EventBus -> EventRouter -> MainPresenter
MainPresenter가 RX buffer/settings/workers/services를 소유
FilePresenter가 QThreadPool/FileTransferService를 직접 생성
MacroPresenter가 file I/O/QThread를 직접 소유
```

---

## 2. 핵심 Architecture

```text
main.py
  -> ApplicationBootstrapper
    -> View state restore
    -> Model / Service
    -> Presenter
    -> Coordinator
    -> static signal wiring
    -> MainPresenter
    -> ApplicationComponents
```

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

- View는 Model 직접 import/호출 금지.
- Model은 Presenter/View import 금지.
- Presenter/Coordinator는 concrete QtWidgets 생성 금지.
- worker thread는 QWidget/View 상태 조회 금지.
- production 주요 event는 direct Qt signal.
- `EventRouter` 재도입 금지.

---

## 3. 책임 소유권

- `ConnectionController`: connection lifecycle/routing
- `ConnectionSessionFactory`: Transport/Worker 생성
- `PacketParserManager`: parser lifecycle
- `CommandTransmissionService`: command 처리/target/send
- `PortScanManager`: scan worker lifecycle
- `MacroRunner`: macro execution thread
- `MacroScriptManager`: script I/O/loader lifecycle
- `MacroExecutionCoordinator`: target/send/port-close policy
- `FileTransferManager`: file transfer lifecycle
- `LoggingCoordinator`: port/system logging
- `TrafficMonitor`: Tx/Rx logging/statistics
- `DataTrafficHandler`: RX UI batching
- `StatusCoordinator`: status timer/statistics
- `SettingsCoordinator`: Preferences/Theme/Language/Font persistence
- `ControlStateCoordinator`: Manual/Macro enable policy
- `ShutdownCoordinator`: shutdown ordering/state save

Presenter 내부 hidden Manager/Service/SettingsManager fallback을 다시 만들지 않는다.

---

## 4. 검증

변경 후 작은 범위부터 확대한다.

```text
closest tests
  -> architecture/lifecycle tests if relevant
  -> ruff
  -> full pytest
  -> language/task consistency if relevant
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

현재 검증 snapshot과 미검증 범위는 `Task.MD`에 기록한다. 실행하지 않은 검증은 통과했다고 쓰지 않는다.

---

## 5. Git / 문서

- 기본 흐름: feature branch -> PR -> CI -> merge.
- `main` 직접 write는 사용자의 명시적 요청이 있는 경우에만 수행.
- squash/rebase/force update는 사용자 승인 후 수행.
- 현재 작업은 `Task.MD`에 반영.
- 중요한 변경은 `doc/CHANGELOG.md`에 기록.
- 반복 실수는 `doc/mistakes.md`에 기록.
- 과거 세션/작업은 `doc/history/`, `tasks/`에 보존.

---

## 6. 완료 조건

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
