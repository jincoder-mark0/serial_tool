# CLAUDE.md — SerialTool 작업 지침

이 파일은 Claude 계열 코딩 에이전트가 SerialTool 저장소에서 작업할 때 사용하는 보조 지침이다.
**최상위 정본은 [`AGENTS.md`](AGENTS.md)** 이며, 충돌 시 `AGENTS.md`와 현재 코드/architecture contract를 우선한다.

> 현재 작업 브랜치: `refactor/presenter-view-boundary`
> 안정 브랜치: `main`
> 현재 작업 보드: [`Task.MD`](Task.MD)
> 리팩토링 보고서: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)

---

## 1. 작업 시작

작업 전 다음 순서로 확인한다.

1. `AGENTS.md`
2. `Task.MD`
3. 작업 대상 소스와 호출부
4. 관련 tests
5. `doc/refactoring_validation_report_20260830.md`
6. 필요 시 `.agent/rules/`

과거 문서의 설명이 현재 코드와 다르면 현재 코드와 architecture contract를 우선한다.

특히 다음 과거 구조를 복구하지 않는다.

```text
EventBus -> EventRouter -> MainPresenter
MainPresenter가 RX buffer/throttling 소유
MainPresenter가 SettingsManager/Worker/Service를 내부 생성
FilePresenter가 QThreadPool/FileTransferService를 직접 생성
MacroPresenter가 script file I/O/QThread를 직접 소유
```

---

## 2. 현재 핵심 Architecture

```text
main.py
  ↓
ApplicationBootstrapper
  ├─ View state restore
  ├─ Model / Service 생성
  ├─ Presenter 생성
  ├─ Coordinator 생성
  ├─ static signal wiring
  ├─ MainPresenter 생성
  └─ ApplicationComponents
```

### Dependency direction

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

해석:

- `common/`: shared DTO/enum/default/constants. 상위 계층 import 금지.
- `core/`: infrastructure. model/presenter/view import 금지.
- `model/`: runtime/business/I/O. presenter/view import 금지.
- `presenter/`: View/Model orchestration. QtWidgets concrete creation 금지.
- `view/`: Passive View. Model 직접 import/호출 금지.

기계적 검사는 `tests/test_layer_dependencies.py`가 담당한다.

---

## 3. Runtime Event 규칙

production 주요 이벤트는 **direct Qt signal**을 사용한다.

`EventRouter`는 제거됐다. 다시 만들지 않는다.

```text
ConnectionController
  ├─ connection_opened
  ├─ connection_closing
  ├─ connection_closed
  ├─ error_occurred
  ├─ data_received
  ├─ data_sent
  └─ packet_received
```

`core/event_bus.py`가 legacy/test utility로 남아 있을 수 있지만 새 production feature의 기본 event mechanism으로 선택하지 않는다.

동일 이벤트를 다음과 같이 중복 전달하지 않는다.

```text
Qt Signal + EventBus + Router
```

worker thread에서 View/QWidget 상태를 읽지 않는다.

---

## 4. 현재 책임 소유권

### Connection

- `ConnectionController`: session registry/open/close/send/broadcast/lifecycle signal
- `ConnectionSessionFactory`: concrete Transport + ConnectionWorker 생성
- `PacketParserManager`: parser lifecycle/feed/flush

### Transmission

- `CommandTransmissionService`: command processing, prefix/suffix, target resolution, validation, send

### Port

- `PortPresenter`: View ↔ ConnectionController
- `PortScanManager`: scan QThread lifecycle

### Manual

- `ManualControlPresenter`: ManualCommand snapshot, AutoTx UI orchestration, RTS/DTR

### Macro

- `MacroPresenter`: Macro UI
- `MacroRunner`: execution QThread
- `MacroScriptManager`: JSON save/load + load thread
- `MacroExecutionCoordinator`: target snapshot/send/connection-close policy

### File Transfer

- `FileTransferManager`: transfer service/QThreadPool/session/cancel/progress
- `FilePresenter`: dialog/View presentation

### Logging / Traffic

- `LoggingCoordinator`: recording control/system log writer
- `TrafficMonitor`: Tx/Rx logging/statistics
- `DataTrafficHandler`: RX UI batching
- `StatusCoordinator`: status timer/statistics rendering

### Settings / State

- `SettingsCoordinator`: Preferences/Theme/Language/Font persistence
- `PreferencesCoordinator`: PreferencesState mapping
- `ControlStateCoordinator`: current connection + broadcast enable policy
- `AppLifecycleManager`: initial View restore
- `ShutdownCoordinator`: shutdown sequence/state save

---

## 5. 절대 금지

- `main` branch에 사용자 승인 없이 직접 write
- Presenter 내부에서 `SettingsManager()`/Manager/Service fallback 생성
- EventRouter 재도입
- worker thread → QWidget 접근
- Presenter 간 callback으로 숨은 수평 의존 생성
- broad `signal.disconnect()`로 다른 listener 제거
- View에서 Model 직접 호출
- Controller에 parser/file-transfer/transport creation 책임 재집중
- 테스트를 맞추기 위해 production architecture를 옛 구조로 되돌리기
- 실행하지 않은 테스트를 통과했다고 보고

---

## 6. DTO / Settings / UI 규칙

- 계층 간 의미 있는 payload는 `common/dtos.py` DTO를 우선한다.
- 설정 persistence는 `SettingsManager`와 전용 Coordinator를 사용한다.
- Config key는 `ConfigKeys`를 사용한다.
- canonical 기본값은 `common/defaults.py` / `common/constants.py`를 사용한다.
- UI 사용자 문자열은 language resource를 사용한다.
- 테마/색상은 resource/QSS/View manager를 통해 적용한다.
- 주석과 Docstring은 한국어, Why/How 중심으로 작성한다.
- public 함수/중요 내부 함수는 타입 힌트를 유지한다.

세부 코딩 규칙은 `.agent/rules/`를 따른다.

---

## 7. 현재 검증 순서

현재 브랜치는 구조 구현보다 **검증이 최우선**이다.

```text
stale API / constructor audit
        ↓
ruff check .
        ↓
architecture contract tests
        ↓
lifecycle/threading tests
        ↓
feature tests
        ↓
full pytest
        ↓
language/task checks
        ↓
PR CI
```

Windows CI와 동일한 기본 명령:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

세부 대상은 `Task.MD`의 P0 체크리스트를 따른다.

---

## 8. 실패 교정 원칙

### constructor mismatch

새 explicit DI 계약으로 호출부/test를 이동한다.
optional fallback을 production에 다시 추가하지 않는다.

### removed internal attribute

실제 owner의 public API를 사용한다.
MainPresenter를 service locator로 되돌리지 않는다.

### signal mismatch

direct Qt signal topology를 기준으로 고친다.
EventBus/EventRouter bridge를 복구하지 않는다.

### QThread/QRunnable failure

해당 worker의 실제 owner Manager에서 수정한다.
Presenter가 worker를 다시 소유하게 만들지 않는다.

### state persistence mismatch

View DTO shape와 Settings shape 사이에 explicit adapter를 둔다.

---

## 9. 완료 조건

다음 모두 확인돼야 현재 리팩토링 검증을 완료로 본다.

- stale API/constructor 감사 완료
- ruff 0건
- architecture contract tests Green
- lifecycle/threading tests Green
- full pytest Green
- language key 검사 Green
- task board 검사 Green
- GitHub Actions PR CI Green
- README/AGENTS/CLAUDE/RULES/overview와 코드 정합

실제 실행 전에는 테스트 개수 기준선을 문서에 확정하지 않는다.

---

## 10. Git / 문서

- 현재 리팩토링 작업은 `refactor/presenter-view-boundary`에만 반영한다.
- destructive squash/rebase는 검증 Green 이후 사용자 승인 후 수행한다.
- 문서 변경도 코드 구조와 함께 커밋한다.
- 현재 상태는 `Task.MD`에 체크한다.
- 중요한 설계 변경은 `doc/CHANGELOG.md`에 기록한다.
- 반복 실수는 `doc/mistakes.md`에 기록한다.
