# SerialTool AGENTS.md

이 문서는 SerialTool 저장소에서 작업하는 AI/코딩 에이전트의 **최상위 실행 지침**이다.
목표는 빠른 변경보다 **정확한 아키텍처 경계, 데이터 보존, 테스트 가능성, 검증 가능한 변경**을 우선하는 것이다.

> 현재 리팩토링 기준 문서: `doc/refactoring_validation_report_20260830.md`
> 현재 개발 브랜치: `refactor/presenter-view-boundary`
> 안정 기준 브랜치: `main`

---

## 1. 작업 시작 전 필수 원칙

1. **현재 브랜치를 확인한다.**
   - 리팩토링 작업은 `refactor/presenter-view-boundary`에서 수행한다.
   - 사용자가 명시적으로 요청하지 않는 한 `main`에 직접 write/commit/push하지 않는다.
   - GitHub API/도구를 사용할 때 write 대상 branch를 항상 명시한다.

2. **기존 코드를 먼저 읽고 수정한다.**
   - 추측으로 API, signal, DTO, constructor를 만들지 않는다.
   - 호출부와 테스트를 함께 확인한다.
   - whole-file replacement가 필요한 환경에서는 특히 public API와 기존 주석 누락을 주의한다.

3. **현재 구현이 과거 문서보다 우선한다.**
   - 다음 우선순위로 판단한다.

   ```text
   실제 현재 코드
       > doc/refactoring_validation_report_20260830.md
       > tests의 architecture contract
       > doc/00_overview.md
       > CLAUDE.md / RULES.md의 과거 설명
   ```

   - 특히 과거 문서의 `EventBus -> EventRouter -> Presenter` 설명을 현재 runtime architecture로 되살리지 않는다.

4. **검증하지 않은 상태를 정상/완료라고 표현하지 않는다.**
   - source-level review만 했으면 `source-level 확인`이라고 표현한다.
   - `pytest`, `ruff`, CI를 실제 실행하지 않았다면 `통과`라고 쓰지 않는다.

---

## 2. 현재 Architecture Invariant

현재 구조의 핵심은 **Single Composition Root + Passive View + 명시적 dependency injection + direct Qt signal**이다.

```text
main.py
  |
  v
ApplicationBootstrapper
  |
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

### 2.1 계층 의존 방향

```text
Common
  ^
Core
  ^
Model
  ^
Presenter / Coordinator
  ^
View
```

실제 코드 규칙은 다음과 같이 해석한다.

- `common/`
  - DTO, Enum, shared defaults/constants의 최하위 계층.
  - `core`, `model`, `presenter`, `view` import 금지.

- `core/`
  - 설정, logger, transport primitive, checksum 등 infrastructure.
  - `model`, `presenter`, `view` import 금지.

- `model/`
  - 통신/worker/parser/file transfer/macro runtime 등 비즈니스 및 실행 계층.
  - `presenter`, `view` import 금지.

- `presenter/`
  - View와 Model을 중재하는 Presenter 및 application coordinator.
  - `PyQt5.QtWidgets` 직접 생성 금지.
  - QWidget/QDialog 구현 세부사항은 View facade 뒤에 둔다.

- `view/`
  - Passive View.
  - Model 직접 import/호출 금지.
  - 사용자 action은 signal/request로 올리고, rendering/state apply를 담당한다.

이 규칙은 `tests/test_layer_dependencies.py`로 기계적으로 검사한다.

---

## 3. Composition Root 규칙

`application_bootstrap.py`가 **유일한 runtime object graph owner**다.

### 반드시 Bootstrapper가 소유할 것

- shared manager/service 생성
- Model/Presenter/Coordinator constructor wiring
- runtime에서 변하지 않는 signal topology
- 초기 View state 복원 순서
- ManualControl 초기 state 적용
- MainPresenter 생성
- background/lifecycle owner의 강한 참조 유지

### 금지

다음 형태를 Presenter 안에 다시 만들지 않는다.

```python
self.settings = SettingsManager()
self.worker_manager = SomeManager()
self.service = SomeService(...)
```

Presenter에 필요한 dependency는 constructor로 명시적으로 주입한다.

또한 `main.py`에서 개별 Presenter/Service를 다시 조립하지 않는다. `main.py`는 Qt/application resource 준비 후 Bootstrapper를 호출하는 entry point만 담당한다.

---

## 4. Event / Signal 규칙

현재 runtime 주요 이벤트 경로는 **Qt direct signal**이다.

대표 흐름:

```text
ConnectionController
  +-- connection_opened
  +-- connection_closing
  +-- connection_closed
  +-- data_received
  +-- data_sent
  +-- packet_received

MacroRunner
  +-- macro_started
  +-- macro_finished
  +-- error_occurred
```

### 금지

- `EventRouter` 재도입 금지.
- 동일 이벤트를 `Qt Signal + EventBus + Router`로 중복 전달하지 않는다.
- Presenter 사이 전달을 위해 callback을 무분별하게 주입하지 않는다.
- worker thread에서 QWidget/View 상태를 읽지 않는다.

### EventBus

`core/event_bus.py`가 아직 테스트/legacy utility로 남아 있을 수 있으나 **production 주요 runtime path에는 사용하지 않는다.**
새 기능을 구현할 때 EventBus를 기본 선택지로 사용하지 않는다.

---

## 5. 주요 책임 소유권

현재 아래 책임 경계를 유지한다.

### Connection

- `ConnectionController`
  - connection session registry
  - open/close/send/broadcast routing
  - connection lifecycle signal

- `ConnectionSessionFactory`
  - concrete Transport 선택
  - ConnectionWorker 생성

- `PacketParserManager`
  - parser 생성/registry/feed/flush

`ConnectionController`에 parser factory, transport 선택, file transfer registry를 다시 넣지 않는다.

### Command Transmission

`CommandTransmissionService`가 다음을 단일 소유한다.

```text
prefix/suffix
command processing
single/broadcast target resolution
connection validation
actual send
TransmissionResult
```

Manual/Macro Presenter에 `CommandProcessor`, `send_data()`, `send_broadcast_data()` 분기를 복제하지 않는다.

### Macro

- `MacroPresenter`: Macro UI interaction
- `MacroRunner`: execution QThread/runtime
- `MacroScriptManager`: script file I/O + load worker lifecycle
- `MacroExecutionCoordinator`: target snapshot, transmission orchestration, port-close interruption policy

worker thread에서 View current-port를 조회하지 않는다. 반복 실행 target은 UI thread에서 문자열 snapshot으로 보관한다.

### File Transfer

- `FileTransferManager`
  - Service 생성
  - QThreadPool scheduling
  - cancel/shutdown
  - progress/speed/ETA session state

- `FilePresenter`
  - View/dialog 표시 중재

FilePresenter가 `QThreadPool`, `FileTransferService`를 직접 생성하지 않는다.

### Port Scan

- `PortScanManager`: scan QThread lifecycle
- `PortPresenter`: scan request/result를 View와 중재

PortPresenter가 `PortScanWorker`를 생성하거나 `_scan_worker`를 소유하지 않는다.

### Logging

- `LoggingCoordinator`
  - port logging start/stop
  - system log writer lifecycle
  - save-path View facade 사용

- `TrafficMonitor`
  - RX/TX logging/statistics

- `DataTrafficHandler`
  - RX UI buffer/throttling만 담당

MainPresenter에 `TextLogWriter`, `DataLoggerManager`, log-format resolver를 다시 넣지 않는다.

### Settings

- `SettingsCoordinator`
  - Preferences/Theme/Language/Font persistence
  - runtime settings propagation

- `PreferencesCoordinator`
  - `PreferencesState <-> SettingsManager` mapping

MainPresenter/View가 설정 파일을 직접 저장하지 않는다.

### Control Enable State

`ControlStateCoordinator`가 다음 정책을 단일 소유한다.

```text
current port connected
+ any connection exists
+ Manual broadcast
+ Macro broadcast
=> Manual/Macro controls enabled state
```

View 또는 MainPresenter에 같은 enable 정책을 중복 구현하지 않는다.

### Shutdown

`ShutdownCoordinator`가 종료 순서를 단일 소유한다.

중요한 데이터 보존 순서:

```text
producer/background stop
  -> transient AutoTx stop
  -> UI state save
  -> connection close
  -> QCoreApplication.processEvents()
  -> DataLoggerManager.stop_all()
```

S-059 ordering을 바꾸지 않는다.

---

## 6. State / DTO 규칙

- 계층 경계를 넘는 상태/이벤트는 가능하면 `common/dtos.py` DTO 사용.
- raw dict는 View 내부 state serialization이나 external JSON boundary처럼 명확한 경우에만 허용.
- persistence key와 View state key를 같은 것으로 가정하지 않는다.
  - `ShutdownStateCollector`처럼 명시적 adapter를 사용한다.

### Default / Enum

- 공통 기본값은 `common/defaults.py` 또는 기존 canonical constant를 사용한다.
- 유한 상태/선택지는 `common/enums.py`를 우선한다.
- 이미 공통 정본이 있는데 Presenter/View에 literal을 다시 쓰지 않는다.
- 단, 구조 리팩토링보다 작은 magic literal cleanup을 우선하지 않는다.

---

## 7. Thread / Lifecycle 규칙

QThread/QRunnable/background worker를 도입할 때 반드시 **owner와 shutdown path를 동시에 정의**한다.

체크:

```text
누가 생성하는가?
누가 strong reference를 갖는가?
누가 cancel/stop 하는가?
앱 종료에서 누가 wait 하는가?
timeout 후 worker가 살아 있으면 어떻게 하는가?
worker thread가 View에 접근하지 않는가?
```

현재 owner 예:

- ConnectionWorker -> ConnectionController
- Port scan worker -> PortScanManager
- Macro script load worker -> MacroScriptManager
- File transfer runnable -> FileTransferManager
- Macro execution thread -> MacroRunner
- Status timer -> StatusCoordinator

`QObject.sender()`에 runtime context 추론을 의존하지 말고 가능하면 explicit argument/captured context를 전달한다.

---

## 8. Signal 연결 규칙

다른 subscriber를 침범하지 않는다.

금지:

```python
signal.disconnect()
```

이 호출은 해당 signal의 모든 subscriber를 제거할 수 있다.

대신:

- 자신이 연결한 객체를 `WeakSet` 등으로 추적
- 중복 연결만 방지
- 필요한 경우 정확한 slot만 disconnect

현재 PortPresenter/LoggingCoordinator의 방식이 기준이다.

---

## 9. 테스트 작업 규칙

현재 리팩토링은 stale API/constructor 감사와 로컬 실행 검증을 마쳤다.
가장 중요한 남은 단계는 **PR GitHub Actions Green 확인과 merge 승인**이다.

기준 문서:

```text
doc/refactoring_validation_report_20260830.md
```

### 9.1 stale test에서 우선 찾을 패턴

다음 과거 API/구조가 테스트에 남아 있지 않은지 확인한다.

```text
EventRouter
event_router
presenter.event_router
MainPresenter(... settings_manager=...)
MainPresenter(... components=...)
PortPresenter(left_section, controller)
MacroPresenter(panel, runner)
controller.parsers
_active_file_transfers
register_file_transfer
unregister_file_transfer
_scan_worker
ScriptLoadWorker imported from presenter.macro_presenter
_on_logging_start_requested
_on_sys_logging_start_requested
_sys_log_writer
```

문자열이 발견됐다고 무조건 삭제하지 않는다. 실제 현재 API와 비교해서 stale 여부를 판단한다.

### 9.2 테스트가 내부 구현을 고정하지 않게 한다

나쁜 예:

```python
assert presenter._scan_worker is not None
assert checked >= 100
assert presenter.event_router is not None
```

좋은 예:

```text
PortScanManager가 worker lifecycle을 소유하는가
MainPresenter가 bootstrapper를 모르는가
production path가 동일 SettingsManager를 주입하는가
S-059 종료 순서가 보존되는가
worker thread가 View를 조회하지 않는가
```

리팩토링 테스트는 **구현 줄 수/내부 필드**보다 **책임 경계와 외부 계약**을 고정한다.

---

## 10. 검증 순서

변경 후 한 번에 full suite부터 돌리지 말고 작은 범위에서 확대한다.

### Phase 1. Static / stale audit

```bash
rg "EventRouter|event_router|_scan_worker|_active_file_transfers" .
rg "MainPresenter\(" tests
rg "PortPresenter\(" tests
rg "MacroPresenter\(" tests
```

### Phase 2. Ruff

```bash
ruff check .
```

CI와 동일한 lint gate다.

### Phase 3. Architecture contract

```bash
python -m pytest -q \
  tests/test_layer_dependencies.py \
  tests/test_composition_root_contract.py \
  tests/test_architecture_policy_boundaries.py \
  tests/test_direct_event_topology.py \
  tests/test_presenter_view_contract.py
```

### Phase 4. High-risk lifecycle / data preservation

```bash
python -m pytest -q \
  tests/test_shutdown_coordinator.py \
  tests/test_shutdown_data_logger.py \
  tests/test_file_transfer_manager.py \
  tests/test_port_scan_shutdown.py \
  tests/test_macro_script_manager.py \
  tests/test_auto_tx.py
```

### Phase 5. Full pytest

Windows / PowerShell CI 기준:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
```

### Phase 6. Repository consistency checks

```bash
python tools/check_language_keys.py
python tools/check_task_boards.py
```

실행 명령과 결과를 반드시 보고한다.

---

## 11. 실패 유형별 수정 원칙

### `TypeError: __init__() got an unexpected keyword...`

대부분 stale constructor test다.

1. 현재 constructor 확인
2. production Bootstrapper wiring 확인
3. test fixture를 production과 같은 조립 방식으로 수정
4. production constructor에 legacy fallback을 다시 추가하지 않는다

### `AttributeError: object has no attribute ...`

삭제한 내부 필드를 테스트가 붙잡고 있는지 먼저 본다.

- 내부 구현 검사라면 테스트를 새 owner/public contract 기준으로 이동
- 실제 public API 누락이면 코드 결함으로 수정

### Signal이 두 번 발생

- duplicate wiring
- 전역 EventBus stale subscriber
- 테스트에서 runtime graph를 두 번 생성

을 우선 의심한다.

### QThread destroyed while running / shutdown hang

- owner가 누구인지 확인
- shutdown coordinator 등록 여부 확인
- stop/cancel 후 wait 여부 확인
- 긴 `sleep()`이 cancel 가능 wait인지 확인

### 데이터 손실

최적화부터 하지 않는다.

1. producer stop 순서
2. queued Qt signal drain
3. logger close 순서
4. file flush/close

를 먼저 확인한다.

---

## 12. Coding / Documentation Style

- Pythonic naming + type hint 사용.
- 주석/Docstring은 한국어 중심.
- 주석은 literal한 What보다 **Why / How / constraint**를 설명한다.
- Hardware/Signal/FSM/Worker/Manager 등 기술 주체를 명확히 쓴다.
- 표준 기술 용어는 억지 번역보다 English jargon을 사용한다.
- 긴 설명은 bullet/section hierarchy로 구조화한다.
- Signal Flow/Block Diagram이 필요하면 ASCII-only로 작성한다.
- 코드 변경 시 의미 있는 기존 주석을 이유 없이 삭제하지 않는다.

---

## 13. Git / Branch 규칙

- `main` 직접 수정 금지. 사용자의 명시적 요청 없이는 현재 작업 브랜치만 수정한다.
- destructive history rewrite (`rebase`, `squash`, force push)는 사용자 승인 후 수행한다.
- unrelated file을 함께 수정하지 않는다.
- 비밀정보/로컬 설정/개인 경로를 commit하지 않는다.
- commit message는 저장소 기존 형식에 맞춘다.

현재 리팩토링 브랜치는 `main` 대비 많은 intermediate commit이 누적되어 있다. **테스트/ruff 검증 전에 history 정리를 하지 않는다.** 먼저 Green baseline을 만든 뒤 squash/rebase를 검토한다.

---

## 14. 완료 조건

리팩토링 관련 작업을 `완료`라고 판단하려면 최소 다음을 만족해야 한다.

```text
[ ] stale constructor/API 감사 완료
[ ] ruff check . 통과
[ ] architecture contract tests 통과
[ ] lifecycle/data-preservation tests 통과
[ ] full pytest 통과
[ ] language key check 통과
[ ] task board check 통과
[ ] 문서가 현재 코드와 일치
[ ] main 대비 diff 검토
```

실제 실행하지 못한 항목은 체크하지 않는다.

---

## 15. 참고 문서

작업 전 필요한 범위만 읽는다.

- `doc/refactoring_validation_report_20260830.md`
  - 현재 리팩토링 구조와 다음 검증 계획의 기준 문서
- `doc/00_overview.md`
  - 현재 프로젝트 architecture overview
- `tests/test_composition_root_contract.py`
  - Single Composition Root / DI contract
- `tests/test_architecture_policy_boundaries.py`
  - 책임 소유권 경계
- `tests/test_layer_dependencies.py`
  - import dependency rule
- `.github/workflows/ci.yml`
  - 실제 CI command
- `RULES.md`, `CLAUDE.md`
  - 일반 개발 규칙 참고. 현재 코드/리팩토링 보고서와 충돌하는 과거 architecture 설명은 사용하지 않는다.

---

## 16. 에이전트 판단 원칙 요약

```text
구조를 먼저 본다.
    ↓
owner를 명확히 한다.
    ↓
hidden dependency를 만들지 않는다.
    ↓
static wiring은 Composition Root로 보낸다.
    ↓
정책은 한 곳만 소유한다.
    ↓
worker lifecycle과 shutdown을 같이 설계한다.
    ↓
테스트는 내부 구현보다 boundary contract를 검증한다.
    ↓
실행한 검증만 통과했다고 말한다.
```
