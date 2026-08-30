# Presenter/View Boundary 리팩토링 현황 및 검증 계획

> 기준일: 2026-08-30  
> 기준 브랜치: `refactor/presenter-view-boundary`  
> 비교 기준: `main` (`c2963eea7fdab64dfd40b1d5bcd4cbfc006ecb92`)  
> GitHub compare 기준: **265 commits ahead / 0 behind**

---

## 1. 문서 목적

이 문서는 `main` 대비 `refactor/presenter-view-boundary` 브랜치에서 진행된 구조 리팩토링의 핵심 내용을 기록하고, 다음 단계인 **전체 테스트 stale API/constructor 전수 감사 → ruff/pytest 실행 가능 상태 확보 → 실패 기준 마지막 구조 교정**을 위한 실행 기준을 정의한다.

이번 리팩토링의 목표는 단순 코드 축소가 아니라 다음 문제를 구조적으로 제거하는 것이다.

- MainPresenter의 과도한 책임과 Service Locator 성격
- View 내부의 비즈니스/연결 정책
- Presenter 간 callback 및 수평 의존
- Qt Signal + EventBus + EventRouter의 중복 이벤트 경로
- Worker/Service/QThread 생명주기 소유권 불명확
- SettingsManager와 기타 manager의 숨은 singleton 접근
- Controller가 parser, transport, file transfer 등 서로 다른 책임을 동시에 소유하는 구조
- 테스트가 내부 구현이나 제거된 API를 고정하여 리팩토링을 방해하는 문제

현재 단계에서는 큰 구조적 책임 누수는 대부분 분리되었으며, 이후 우선순위는 **실제 실행 검증과 stale test 제거**이다.

---

## 2. `main` 대비 변경 규모 요약

GitHub compare 기준 현재 브랜치는 `main`보다 **265 commits ahead, 0 behind**이다.

변경량이 큰 주요 파일은 다음과 같다.

| 영역 | 파일 | main 대비 주요 변화 |
|---|---|---|
| Composition Root | `application_bootstrap.py` | 신규. 전체 runtime object graph 생성/배선 담당 |
| Main Presenter | `presenter/main_presenter.py` | 약 `+125 / -812`. God Presenter 축소 |
| Connection | `model/connection_controller.py` | 약 `+82 / -476`. parser/transport/file-transfer 책임 분리 |
| Port Presenter | `presenter/port_presenter.py` | 약 `+113 / -415`. View facade 및 명시 DI 중심으로 축소 |
| Manual Control | `presenter/manual_control_presenter.py` | 약 `+93 / -312`. 전송 서비스 위임 및 callback 제거 |
| Macro Presenter | `presenter/macro_presenter.py` | 약 `+59 / -285`. 파일 I/O/QThread 책임 제거 |
| Packet Presenter | `presenter/packet_presenter.py` | 약 `+69 / -189`. direct signal 구조로 단순화 |
| File Presenter | `presenter/file_presenter.py` | 약 `+42 / -183`. transfer lifecycle manager로 이동 |
| Lifecycle | `presenter/lifecycle_manager.py` | 약 `+108 / -210`. View 초기 상태 복원 역할로 축소 |
| View | `view/main_window.py` | 약 `+29 / -373`. Model-affecting command 직접 처리 제거 |
| View | `view/sections/main_left_section.py` | 약 `+100 / -333`. 정책 제거, facade 역할 정리 |
| DTO | `common/dtos.py` | 약 `+156 / -356`. 계층간 canonical DTO 정리 |
| Defaults/Enums | `common/defaults.py`, `common/enums.py` | 기본값/유한 상태 단일 정본 강화 |

새로 추가된 주요 구조 파일:

```text
application_bootstrap.py

model/
├─ command_transmission_service.py
├─ connection_session_factory.py
├─ file_transfer_manager.py
├─ macro_script_manager.py
├─ packet_parser_manager.py
├─ port_scan_manager.py
└─ traffic_monitor.py

presenter/
├─ control_state_coordinator.py
├─ logging_coordinator.py
├─ macro_execution_coordinator.py
├─ settings_coordinator.py
├─ shutdown_coordinator.py
└─ status_coordinator.py
```

제거된 대표 구조:

```text
presenter/event_router.py
```

기존 `tests/test_event_router.py`도 함께 제거되었다.

---

## 3. 리팩토링 후 목표 아키텍처

현재 object graph의 중심은 `ApplicationBootstrapper`이다.

```text
main.py
  │
  ├─ ResourcePath
  ├─ SettingsManager
  ├─ Theme / Language / Color managers
  └─ MainWindow
        │
        ▼
ApplicationBootstrapper
  │
  ├─ View state restore
  │    └─ AppLifecycleManager
  │
  ├─ Model / Services
  │    ├─ ConnectionController
  │    ├─ ConnectionSessionFactory
  │    ├─ PacketParserManager
  │    ├─ CommandTransmissionService
  │    ├─ FileTransferManager
  │    ├─ PortScanManager
  │    ├─ MacroRunner
  │    ├─ MacroScriptManager
  │    └─ TrafficMonitor
  │
  ├─ Presenters
  │    ├─ PortPresenter
  │    ├─ ManualControlPresenter
  │    ├─ MacroPresenter
  │    ├─ PacketPresenter
  │    ├─ FilePresenter
  │    └─ MainPresenter
  │
  ├─ Coordinators
  │    ├─ SettingsCoordinator
  │    ├─ ControlStateCoordinator
  │    ├─ MacroExecutionCoordinator
  │    ├─ LoggingCoordinator
  │    ├─ StatusCoordinator
  │    └─ ShutdownCoordinator
  │
  └─ static signal wiring
```

### 의존 방향 원칙

```text
View
  ↑
Presenter / UI Coordinator
  ↓
Application Service / Model
  ↓
Core
  ↓
Common
```

`main.py`는 Qt/application environment만 준비하고 구체 runtime graph는 `ApplicationBootstrapper`에 위임한다.

---

## 4. 주요 리팩토링 내용

### 4.1 Single Composition Root 확립

이전에는 `main.py`, `MainPresenter`, `AppLifecycleManager`, 개별 Presenter가 객체를 각자 생성하거나 singleton을 조회했다.

현재는 `ApplicationBootstrapper`가 다음 전체 순서를 소유한다.

```text
View restore
    ↓
Model / Service 생성
    ↓
Presenter 생성
    ↓
저장된 ManualControlState 적용
    ↓
Coordinator 생성
    ↓
static signal wiring
    ↓
Shutdown graph 생성
    ↓
MainPresenter 생성
```

중요한 초기화 순서 계약:

```text
AppLifecycleManager.initialize_view()
        < PortPresenter / MacroPresenter 생성
        < ManualControlPresenter.apply_state()
        < ControlStateCoordinator 생성/초기 refresh
```

이 순서는 저장된 broadcast/manual 상태와 초기 enable 상태가 어긋나는 문제를 방지한다.

---

### 4.2 MainPresenter 축소

`main`의 MainPresenter는 연결, 전송, 매크로, 파일 전송, 로그, 설정, 상태바, 종료, View collection 순회 등 대부분의 orchestration을 직접 수행했다.

현재 MainPresenter의 역할은 주로 다음으로 제한된다.

- Port open/close/error를 사용자에게 표시
- Macro started/finished/error 표시
- Macro 중단 사유 표시
- Manual send error 표시
- File transfer 완료/실패 표시
- 시스템 로그 표시 연결
- close 요청 → ShutdownCoordinator 전달

다음 책임은 MainPresenter에서 제거됐다.

- SettingsManager 직접 소유
- Command 처리 / single-broadcast send 분기
- 현재 macro target port 관리
- Port collection traversal
- DataTrafficHandler 소유
- FileTransferManager 소유
- PortScanManager 소유
- MacroScriptManager 소유
- TrafficMonitor / Status timer 소유
- Preferences/Theme/Language/Font 저장
- Manual/Macro control enable 정책
- Connect/Disconnect/Clear shortcut relay
- File transfer dialog relay
- Logging writer/DataLogger 구현
- ApplicationBootstrapper fallback

---

### 4.3 이벤트 구조 단일화

기존에는 다음 두 경로가 동시에 존재했다.

```text
ConnectionController Qt Signal → Presenter
ConnectionController → EventBus → EventRouter → Qt Signal → Presenter
```

현재 production runtime은 direct Qt signal topology를 사용한다.

```text
ConnectionController
├─ connection_opened
├─ connection_closing
├─ connection_closed
├─ data_received
├─ data_sent
├─ packet_received
└─ error_occurred
```

`EventRouter`는 제거됐다.

`core/event_bus.py`는 현재 production 주요 경로에서는 사용하지 않으며, 독립 core 테스트/기존 테스트 인프라 때문에 아직 남아 있다. **실제 pytest 실행 후 제거 여부를 결정한다.**

---

### 4.4 CommandTransmissionService

Manual과 Macro에 중복되어 있던 다음 책임을 서비스로 통합했다.

- Prefix/Suffix 적용
- ASCII/HEX command 처리
- single/broadcast target 검증
- 실제 `send_data()` / `send_broadcast_data()` 호출
- 전송 실패 분류

실패는 `TransmissionErrorCode`를 사용하며, 사용자 번역 문구 결정은 Presenter 책임으로 유지한다.

---

### 4.5 MacroExecutionCoordinator

MainPresenter에 있던 macro cross-component 책임을 분리했다.

- 반복 실행 시작 시 target port snapshot
- worker thread에서 View 미접근 보장
- MacroRunner send handler
- 단일 row send
- 대상 포트 종료 시 macro 중단
- broadcast 대상 소멸 시 중단
- Local Echo 정책

worker thread에서는 snapshot된 문자열만 사용하며 QWidget/View를 조회하지 않는다.

---

### 4.6 SettingsCoordinator

다음을 MainPresenter에서 분리했다.

- Preferences dialog open
- PreferencesState 저장
- Theme 적용/저장
- Language 적용/저장
- Font 저장
- max log lines 적용
- local echo 설정 반영
- PacketPresenter 설정 갱신

따라서 View menu와 Preferences dialog가 동일한 설정 persistence 경로를 사용한다.

---

### 4.7 ControlStateCoordinator

Manual/Macro enable 정책의 단일 권위이다.

입력:

```text
현재 탭 연결 상태
전체 활성 연결 존재 여부
Manual broadcast 여부
Macro broadcast 여부
```

출력:

```text
ManualControlPresenter.set_enabled(...)
MacroPresenter.set_enabled(...)
```

View는 이 정책을 자체 판단하지 않는다.

---

### 4.8 LoggingCoordinator

다음을 MainPresenter에서 분리했다.

- Port DataLogger 시작/중지
- 저장 경로 선택
- logging format 판단
- System TextLogWriter lifecycle
- REC 상태 표시

또한 `signal.disconnect()`로 다른 subscriber까지 제거하던 방식을 없애고, 자신이 연결한 panel만 추적한다.

---

### 4.9 FileTransferManager

FilePresenter가 직접 수행하던 다음 책임을 이동했다.

- FileTransferService 생성
- 전용 QThreadPool scheduling
- 중복 transfer 방지
- cancel/lifecycle
- progress metric / speed / ETA
- target port close 시 cancel
- shutdown 시 cancel + wait

`ConnectionController.connection_closing`을 추가하여 포트 worker 종료 전에 transfer cancel이 먼저 일어나도록 했다.

FileTransferService의 baudrate/backpressure 대기도 cancel 가능한 wait 방식으로 변경했다.

---

### 4.10 ConnectionController 분해

분리된 책임:

- `PacketParserManager`
  - parser 생성
  - registry
  - feed / flush

- `ConnectionSessionFactory`
  - Transport 선택
  - ConnectionWorker 생성

- `FileTransferManager`
  - file transfer registry/lifecycle

현재 ConnectionController는 주로 다음에 집중한다.

```text
connection session registry
open / close lifecycle
send routing
DTR / RTS
broadcast state
connection state signals
```

---

### 4.11 Worker/Thread lifecycle 명시화

다음 worker lifecycle을 Presenter 밖으로 이동했다.

| 기능 | 소유자 |
|---|---|
| Port scan QThread | `PortScanManager` |
| Macro script load QThread | `MacroScriptManager` |
| File transfer QRunnable/QThreadPool | `FileTransferManager` |
| Status QTimer | `StatusCoordinator` |
| Data UI flush QTimer | `DataTrafficHandler` |
| Packet UI flush QTimer | `PacketPresenter` |

ShutdownCoordinator가 종료 시 생산자/background 작업을 먼저 정리한다.

---

### 4.12 ShutdownCoordinator

종료 순서를 명시적 use case로 분리했다.

```text
Macro stop
    ↓
File transfer shutdown
    ↓
Macro script worker stop
    ↓
Port scan stop
    ↓
Data handler stop
    ↓
Packet presenter stop
    ↓
Status coordinator stop
    ↓
Auto Tx stop
    ↓
System log close
    ↓
UI state save
    ↓
Connection close
    ↓
QCoreApplication.processEvents()
    ↓
DataLoggerManager.stop_all()
```

S-059의 핵심 보존 조건:

```text
Connection close → queued RX delivery → logger stop
```

Auto Tx는 transient runtime state로 취급한다. 앱 종료 시 저장 전에 반드시 중지/체크 해제하여 `auto_tx_enabled=True`가 저장되었지만 scheduler는 실행되지 않는 불일치를 방지한다.

---

### 4.13 Shutdown state adapter 수정

실제 View state shape과 `ConfigKeys` path 문자열을 혼동하던 문제를 수정했다.

```text
View left_section_state["ports"]
    → ConfigKeys.PORTS_TABS_STATE

View right_section_state["macro_panel"]["commands"]
    → ConfigKeys.MACRO_COMMANDS

View right_section_state["macro_panel"]["control_state"]
    → ConfigKeys.MACRO_CONTROL_STATE
```

ShutdownStateCollector는 이제 View DTO 구조 → Settings 구조 adapter 역할을 한다.

---

### 4.14 Common defaults / enums / DTO canonicalization

리팩토링 중 다음 원칙을 적용했다.

1. shared/global policy → `common/constants.py`
2. fallback/config default → `common/defaults.py`
3. finite state/domain value → `common/enums.py`
4. cross-layer data shape → `common/dtos.py`
5. 한 widget만 사용하는 UI option → 해당 module private constant 허용

대표적으로 parser preference, connection state, macro step state, log level, length field size, byte order 등이 canonical enum/default로 이동했다.

---

## 5. 현재 구조에서 의도적으로 남긴 것

### 5.1 EventBus

`core/event_bus.py`는 production runtime 주요 경로에서 사용하지 않는다.

그러나 현재 `tests/test_core_refinement.py`와 `tests/conftest.py`가 EventBus 자체 또는 reset fixture를 사용하고 있으므로 **전체 pytest 실행 전에 제거하지 않는다.**

검증 후 선택:

- 사용 테스트를 새 topology로 이전할 수 있으면 EventBus 완전 삭제
- 독립 utility로 유지할 실사용 계획이 있으면 runtime 미사용 계약을 테스트로 유지

### 5.2 Presenter package 안의 Coordinator

현재 `presenter/` 안에 Presenter와 application/UI coordinator가 함께 존재한다.

예:

```text
presenter/
├─ main_presenter.py
├─ port_presenter.py
├─ macro_presenter.py
├─ settings_coordinator.py
├─ control_state_coordinator.py
├─ logging_coordinator.py
├─ shutdown_coordinator.py
└─ ...
```

역할은 이미 분리되었지만, 지금 별도 `application/` 패키지로 이동하면 기능 변화 없이 import churn이 크게 증가한다.

**pytest/ruff green 이후에만 package relocation을 별도 작업으로 판단한다.**

---

# Part II. 전체 테스트 stale API / constructor 전수 감사

## 6. 감사 목표

현재 가장 큰 리스크는 production 구조가 아니라 테스트 코드가 옛 구현을 직접 가정하는 것이다.

리팩토링 중 실제로 발견된 stale 예:

- `presenter.event_router.packet_received`
- `EventRouter` constructor
- 옛 `ManualControlPresenter(..., local_echo_callback, get_active_port_callback)`
- `controller.parsers[...]`
- `presenter._scan_worker`
- `presenter._sys_log_writer`
- `presenter._on_sys_logging_start_requested()`
- `presenter.data_handler`
- `presenter.status_timer`
- `MainPresenter(view)` fallback 생성
- `PortPresenter(left_section, controller)` hidden dependency 생성
- `MacroPresenter(panel, runner)` hidden MacroScriptManager 생성
- `ScriptLoadWorker`를 `presenter.macro_presenter`에서 import

따라서 테스트 감사는 파일 이름이 아니라 **API 유형별로 수행한다.**

---

## 7. stale API 감사 체크리스트

### A. MainPresenter 직접 생성

현재 production 생성 경로:

```python
runtime = ApplicationBootstrapper(window, settings_mgr).build()
presenter = runtime.main_presenter
```

찾아야 할 패턴:

```bash
rg -n "MainPresenter\(" tests
```

판정:

- `MainPresenterDependencies` 자체 unit test를 위해 명시적으로 생성: 허용 가능
- integration/runtime test가 별도 MainPresenter를 생성: stale. Bootstrapper runtime 사용으로 변경

---

### B. PortPresenter 옛 constructor

현재 필수 의존성:

```python
PortPresenter(
    left_section,
    connection_controller,
    settings_manager,
    port_scan_manager,
)
```

검색:

```bash
rg -n "PortPresenter\(" tests
```

다음 형태는 stale:

```python
PortPresenter(left_section, controller)
PortPresenter(left_section, controller, settings_manager)
```

---

### C. MacroPresenter 옛 constructor / worker 위치

현재:

```python
MacroPresenter(panel, runner, macro_script_manager)
```

검색:

```bash
rg -n "MacroPresenter\(" tests
rg -n "ScriptLoadWorker|_MacroScriptLoadWorker" tests
```

`ScriptLoadWorker`를 `presenter.macro_presenter`에서 import하면 stale이다.

---

### D. EventRouter / EventBus runtime 가정

검색:

```bash
rg -n "EventRouter|event_router" .
rg -n "event_bus|EventBus" presenter model view main.py tests
```

판정:

- production `presenter/`, `model/`, `view/`, `main.py`에서 EventBus/EventRouter 사용: 구조 회귀
- `test_core_refinement.py`처럼 EventBus 자체를 독립 테스트: 현재 보류 항목

---

### E. 제거된 MainPresenter 내부 필드

검색:

```bash
rg -n "presenter\.(settings_manager|data_handler|status_timer|status_coordinator|file_transfer_manager|port_scan_manager|macro_script_manager|traffic_monitor|port_presenter|macro_presenter|packet_presenter)" tests
```

대체 원칙:

- runtime internals 확인 → `ApplicationComponents`
- policy 확인 → 해당 Coordinator
- feature Presenter 확인 → composition graph의 해당 객체
- MainPresenter를 Service Locator처럼 사용하지 않는다

---

### F. Logging compatibility API

다음은 제거 대상/제거된 API이다.

```text
_sys_log_writer
_connect_logging_signals
_connect_single_port_logging
_on_logging_start_requested
_on_logging_stop_requested
_on_sys_logging_start_requested
_on_sys_logging_stop_requested
_close_sys_log_writer
_on_system_log_line_appended
```

검색:

```bash
rg -n "_sys_log_writer|_on_.*logging|_connect_.*logging|_close_sys_log_writer" tests
```

모든 실제 logging 동작 테스트는 `LoggingCoordinator` public API로 이동한다.

---

### G. Port scan 내부 worker

검색:

```bash
rg -n "_scan_worker|PortScanWorker|stop_pending_scan|get_active_port_name" tests presenter
```

- worker lifecycle 테스트 → `PortScanManager`
- Presenter는 `request_scan()`만 위임

---

### H. Parser registry 내부 접근

검색:

```bash
rg -n "\.parsers\[|controller\.parsers|_parsers" tests
```

Parser 상태 확인은 `PacketParserManager` public diagnostic API를 사용한다.

---

### I. File transfer controller registry

검색:

```bash
rg -n "active_file_transfer|register_file_transfer|unregister_file_transfer" tests model presenter
```

File transfer lifecycle은 `FileTransferManager`가 소유한다.

---

### J. hidden singleton construction

Presenter 계층에서는 runtime dependency를 내부 생성하지 않는 것이 원칙이다.

검색:

```bash
rg -n "SettingsManager\(\)|PortScanManager\(\)|MacroScriptManager\(\)" presenter
```

발견 시:

- 실제 의도된 factory인가?
- 테스트 편의용 fallback인가?
- Composition root에서 주입할 수 있는가?

를 먼저 판단한다.

---

## 8. 자동/정적 contract test 우선 실행

전체 pytest보다 먼저 구조 contract만 실행하면 constructor drift를 빠르게 찾을 수 있다.

```bash
python -m pytest -q \
  tests/test_composition_root_contract.py \
  tests/test_architecture_policy_boundaries.py \
  tests/test_direct_event_topology.py \
  tests/test_layer_dependencies.py \
  tests/test_presenter_view_contract.py \
  tests/test_command_transmission_service.py \
  tests/test_control_state_coordinator.py \
  tests/test_settings_coordinator.py
```

Windows PowerShell에서는 줄 연결을 `` ` ``로 바꾸거나 한 줄로 실행한다.

---

# Part III. Ruff / Pytest 실행 가능 상태 확보

## 9. 저장소 공식 CI 기준

`.github/workflows/ci.yml` 기준 CI는 다음 네 job을 실행한다.

### Windows tests

```powershell
pip install -r requirements.txt
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
```

### Language key integrity

```bash
python tools/check_language_keys.py
```

### Task board consistency

```bash
python tools/check_task_boards.py
```

### Ruff

```bash
pip install ruff
ruff check .
```

CI trigger:

```yaml
push:
  branches: [main]
pull_request:
```

즉 현재 feature branch push만으로는 CI status가 없을 수 있다. PR 생성 시 GitHub Actions를 실제 검증 게이트로 사용할 수 있다.

---

## 10. 권장 로컬 검증 순서

### Step 1. Python 환경

CI와 동일하게 Python 3.11을 우선 사용한다.

```bash
python --version
python -m pip install -r requirements.txt
python -m pip install ruff
```

### Step 2. Ruff 먼저

```bash
ruff check .
```

왜 먼저 실행하는가:

- import drift
- unused import
- constructor 변경 후 남은 import
- 대규모 whole-file refactor 중 발생한 단순 syntax/style 문제

를 pytest보다 빠르게 찾을 수 있다.

자동 fix는 검토 없이 전체 적용하지 않는다.

```bash
ruff check . --fix
```

사용 시 각 diff를 검토한다.

### Step 3. 구조 contract test

```bash
python -m pytest -q tests/test_composition_root_contract.py
python -m pytest -q tests/test_architecture_policy_boundaries.py
python -m pytest -q tests/test_direct_event_topology.py
python -m pytest -q tests/test_layer_dependencies.py
```

### Step 4. 변경량이 큰 feature test

```bash
python -m pytest -q tests/test_presenter_init.py
python -m pytest -q tests/test_integration_refactored.py
python -m pytest -q tests/test_presenter_manual_control.py
python -m pytest -q tests/test_macro_execution_coordinator.py
python -m pytest -q tests/test_file_transfer_manager.py
python -m pytest -q tests/test_shutdown_coordinator.py
python -m pytest -q tests/test_shutdown_data_logger.py
python -m pytest -q tests/test_text_log_writer.py
```

### Step 5. 전체 suite

Linux/macOS:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

Windows PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
```

### Step 6. 나머지 CI gate

```bash
python tools/check_language_keys.py
python tools/check_task_boards.py
ruff check .
```

---

# Part IV. 실패 유형별 마지막 구조 교정 기준

## 11. 실패를 수정하는 원칙

테스트를 단순히 green으로 만들기 위해 production 구조를 다시 후퇴시키지 않는다.

### Type A. Constructor mismatch

예:

```text
TypeError: ... missing required positional argument
```

우선 판단:

1. production constructor가 새 구조상 맞는가?
2. 테스트가 옛 hidden dependency fallback을 기대하는가?

새 구조가 맞으면 테스트 fixture를 수정한다.

**금지:** 테스트를 살리기 위해 optional fallback을 다시 추가.

---

### Type B. AttributeError — 제거된 내부 필드

예:

```text
MainPresenter has no attribute 'data_handler'
MainPresenter has no attribute 'packet_presenter'
```

대부분 stale test이다.

대체:

```text
MainPresenter internal lookup
    → ApplicationComponents
    → dedicated Coordinator / Presenter public API
```

---

### Type C. Signal wiring 실패

다음을 먼저 확인한다.

1. static topology인가? → Bootstrapper
2. runtime policy인가? → Coordinator
3. View presentation인가? → Presenter
4. worker lifecycle인가? → Manager/Model

MainPresenter에 무조건 다시 연결하지 않는다.

---

### Type D. 초기 상태 불일치

특히 다음 순서를 확인한다.

```text
View restore
ManualControl apply
Coordinator refresh
Timer/background start
```

저장 상태가 적용되기 전에 Coordinator가 계산하거나 worker/timer가 시작되면 안 된다.

---

### Type E. Shutdown hang / QThread destroyed

확인 순서:

- FileTransferManager shutdown
- MacroScriptManager stop
- PortScanManager stop
- AutoTx stop
- Packet/Data timers stop
- ConnectionWorker stop

문제 해결을 위해 worker ownership을 Presenter로 다시 올리지 않는다.

---

### Type F. Data loss regression

S-059 순서를 반드시 유지한다.

```text
connection close
→ QCoreApplication.processEvents()
→ data_logger_manager.stop_all()
```

logger를 먼저 닫아 테스트를 통과시키는 수정은 금지한다.

---

### Type G. Ruff unused import

리팩토링으로 responsibility가 이동한 흔적일 가능성이 높다.

단순 noqa보다 먼저:

- 더 이상 필요 없는 dependency인가?
- 테스트가 old class를 import하고 있는가?
- type-only dependency는 `TYPE_CHECKING`으로 이동 가능한가?

를 확인한다.

---

## 12. Green 기준

리팩토링 검증 완료 조건은 다음을 모두 만족하는 것이다.

- [ ] `ruff check .` 0 errors
- [ ] `python tools/check_language_keys.py` 성공
- [ ] `python tools/check_task_boards.py` 성공
- [ ] 구조 contract tests 전체 성공
- [ ] 전체 `python -m pytest -q` 성공
- [ ] QThread/QTimer 종료 warning 없음
- [ ] 테스트 종료 시 background thread leak 없음
- [ ] `EventRouter` production 참조 0건
- [ ] MainPresenter를 Service Locator처럼 접근하는 테스트 0건
- [ ] Presenter 내부 `SettingsManager()` / manager fallback 생성 0건
- [ ] View → Model 직접 import 0건
- [ ] Model → Presenter/View import 0건
- [ ] shutdown logger/data-loss 회귀 테스트 성공
- [ ] PR CI Windows test + lint + language + task-board gate 성공

---

# Part V. 마지막 구조 감사 기준

## 13. 더 분리해야 하는 경우

다음 조건이 있을 때만 추가 coordinator/service 분리를 고려한다.

- 한 클래스가 서로 독립적인 두 개 이상의 lifecycle을 소유
- 같은 유스케이스가 두 Presenter에서 중복 구현
- worker/thread 생명주기가 View/Presenter에 숨겨짐
- 설정 저장 정책이 여러 경로로 갈림
- 같은 event가 두 topology로 전달됨
- View가 Model-affecting command를 직접 수행
- Presenter가 다른 Presenter의 내부 상태를 callback으로 조회

## 14. 더 이상 분리하지 않아야 하는 경우

다음은 현재 구조에서 정상이다.

- MainPresenter가 전역 성공/실패/status message를 View에 표시
- PortPresenter가 Port View와 ConnectionController를 중재
- MacroPresenter가 MacroPanel과 MacroRunner를 중재
- PacketPresenter가 PacketEvent를 PacketViewData로 변환
- ManualControlPresenter가 수동 입력을 ManualCommand DTO로 snapshot

이를 별도 micro-coordinator로 과도하게 쪼개면 구조 탐색 비용만 증가한다.

---

# Part VI. Merge 전 정리

## 15. 브랜치 history

현재 브랜치는 `main` 대비 265 commits ahead이다.

리팩토링 과정의 intermediate/revert/contract-test 커밋이 많이 포함되어 있으므로 PR merge 전 history 정리가 필요하다.

권장:

1. **pytest/ruff/CI green 먼저 달성**
2. 최종 diff review
3. destructive history rewrite에 대한 명시적 승인 후 squash/rebase
4. 의미 단위 커밋으로 정리

예시 최종 커밋 그룹:

```text
refactor: establish application composition root
refactor: split connection and transmission services
refactor: isolate presenter policies into coordinators
refactor: define worker lifecycle ownership
refactor: simplify view facade boundaries
refactor: canonicalize defaults enums and DTOs
test: migrate architecture and regression contracts
docs: document refactor architecture and validation
```

**주의:** green 이전에 squash하면 어떤 intermediate 변경에서 회귀가 생겼는지 추적하기 어려워질 수 있으므로 검증 완료 후 수행한다.

---

## 16. 다음 실행 작업

다음 작업 순서를 권장한다.

```text
1. stale API/constructor ripgrep 전수 감사
2. ruff check .
3. structure contract tests
4. high-risk feature tests
5. full pytest
6. language/task board checks
7. 실패 유형별 production/test 교정
8. full pytest + ruff 재실행
9. PR 생성 → GitHub Actions 확인
10. 최종 architecture review
11. 승인 후 commit history squash/rebase
```

이 단계부터는 **새 구조를 더 만드는 것보다 검증 실패를 근거로 필요한 부분만 수정하는 것**을 기본 원칙으로 한다.
