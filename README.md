# SerialTool

**최종 업데이트: 2026-08-30**

SerialTool은 Python/PyQt5 기반의 멀티포트 시리얼 통신·자동화·프로토콜 분석 도구입니다.
현재 구조는 **Passive View + 명시적 Dependency Injection + Single Composition Root + direct Qt signal**을 핵심 원칙으로 사용합니다.

> 현재 리팩토링 브랜치: `refactor/presenter-view-boundary`  
> 상세 리팩토링 보고서: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)  
> 현재 작업 체크리스트: [`Task.MD`](Task.MD)  
> AI/코딩 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

현재 브랜치는 구조 리팩토링 후 **전체 stale API/constructor 감사와 pytest/ruff 재검증 단계**입니다.
따라서 과거 문서에 기록된 테스트 통과 개수를 현재 기준선으로 간주하지 않습니다.

---

## 1. 주요 기능

### 통신

- 다중 Serial 포트 연결/해제
- LOOPBACK 디버그 포트
- ASCII / HEX 송신
- Prefix / Suffix
- Local Echo
- Broadcast 송신
- RTS / DTR 제어
- 비동기 Port Scan

### Auto Tx / Macro

- 주기 Auto Tx
- Macro List 순차/반복 실행
- Delay / Expect / Timeout
- Broadcast Macro
- JSON script 저장/비동기 로드
- 전송 실패 결과를 실제 Macro 실행 결과에 반영

### File Transfer

- Chunk 기반 파일 전송
- Backpressure 제어
- 진행률 / 속도 / ETA
- 취소 가능
- 대상 포트 종료 또는 앱 shutdown 시 안전한 cancellation

### RX / Logging

- 대량 RX 데이터를 UI에 batch/throttle 처리
- Tx/Rx byte statistics
- Raw / Hex Dump / PCAP 저장
- 전이중 Tx/Rx logging
- 시스템 로그 파일 저장
- 색상 규칙 기반 로그 강조 및 검색

### Packet Inspection

- Raw / AT / Delimiter / Fixed Length
- Length Field framing
- Gap framing
- Checksum validation
- packet buffer / realtime / autoscroll 설정

### UI / 설정

- Dark / Light / Dracula / Classic 테마
- 한국어 / 영어
- proportional / fixed font
- 설정 schema validation + migration
- 번들 실행 시 사용자 설정/로그 경로 분리

---

## 2. 현재 구현 범위

- 실제 하드웨어 Transport는 `SerialTransport`가 중심입니다.
- LOOPBACK Transport는 테스트/디버깅용으로 제공합니다.
- SPI/I2C Transport와 Plugin system은 후속 후보이며 현재 구현 범위가 아닙니다.
- PyInstaller onedir 패키징 구성이 존재합니다.
- GitHub Actions CI는 Windows pytest, language-key 검사, task-board 검사, ruff를 실행합니다.
- 현재 리팩토링 브랜치는 CI/전체 pytest Green을 아직 확인하지 않았으므로 검증 완료로 선언하지 않습니다.

---

## 3. 설치 및 실행

### 요구 사항

- Python 3.10+
- PyQt5
- pyserial
- commentjson
- jsonschema

```bash
git clone https://github.com/kjlee-inlct/serial_tool.git
cd serial_tool
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 4. 검증

GitHub CI와 동일한 핵심 검증은 다음입니다.

Windows / PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

현재 리팩토링 검증은 다음 순서를 권장합니다.

```text
stale API/constructor audit
        ↓
ruff
        ↓
architecture contract tests
        ↓
lifecycle/threading tests
        ↓
feature tests
        ↓
full pytest
        ↓
GitHub Actions CI
```

상세 체크리스트는 [`Task.MD`](Task.MD)를 사용합니다.

---

## 5. 현재 아키텍처

### 5.1 Single Composition Root

`application_bootstrap.py`의 `ApplicationBootstrapper`가 완전한 runtime object graph를 생성합니다.

```text
main.py
  │
  ├─ ResourcePath / Settings / Theme / Language 준비
  │
  ▼
ApplicationBootstrapper
  │
  ├─ View state restore
  ├─ Model / Service 생성
  ├─ Presenter 생성
  ├─ Coordinator 생성
  ├─ static signal wiring
  ├─ MainPresenter 생성
  └─ ApplicationComponents 반환
```

`main.py`는 개별 Model/Presenter를 조립하지 않습니다.

### 5.2 계층 방향

```text
Common
  ↑
Core
  ↑
Model
  ↑
Presenter / Coordinator
  ↑
View
```

핵심 규칙:

- View는 Model을 직접 import/호출하지 않습니다.
- Model은 Presenter/View를 알지 않습니다.
- Presenter/Coordinator는 concrete QtWidgets를 직접 생성하지 않습니다.
- 계층 간 의미 있는 데이터 전달은 DTO를 우선 사용합니다.
- worker thread에서 QWidget/View 상태를 직접 읽지 않습니다.

이 규칙은 `tests/test_layer_dependencies.py` 및 architecture contract tests로 검사합니다.

### 5.3 Event topology

현재 production 주요 runtime event는 **direct Qt signal**을 사용합니다.

```text
ConnectionWorker
      ↓
ConnectionController
  ├─ connection_opened
  ├─ connection_closing
  ├─ connection_closed
  ├─ error_occurred
  ├─ data_received
  ├─ data_sent
  └─ packet_received
```

`EventRouter`는 제거됐습니다. 같은 이벤트를 `Qt Signal + EventBus + Router`로 중복 전달하지 않습니다.
`core/event_bus.py`가 legacy/test utility로 남아 있을 수 있으나 production 주요 runtime path의 기본 event mechanism으로 사용하지 않습니다.

### 5.4 RX data path

```text
SerialTransport
      ↓
ConnectionWorker
      ↓
ConnectionController.data_received
      ├─ DataTrafficHandler ── 30ms UI batching ──> MainWindow/View
      ├─ MacroRunner Expect
      └─ PacketParserManager / PacketPresenter path

TrafficMonitor
      ├─ Tx/Rx logging
      └─ statistics
```

MainPresenter는 RX buffer/throttling을 소유하지 않습니다.

---

## 6. 주요 책임 구조

### Connection

- `ConnectionController`
  - connection registry
  - open / close
  - send / broadcast routing
  - lifecycle signal
- `ConnectionSessionFactory`
  - Transport 선택
  - ConnectionWorker 생성
- `PacketParserManager`
  - parser 생성 / registry / feed / flush

### Command Transmission

- `CommandTransmissionService`
  - Prefix/Suffix
  - HEX/ASCII command processing
  - single/broadcast target resolution
  - connection validation
  - 실제 send
  - `TransmissionResult`

Manual/Macro Presenter는 send policy를 복제하지 않습니다.

### Port

- `PortPresenter`
  - Port View와 ConnectionController 중재
- `PortScanManager`
  - Port scan QThread lifecycle

### Manual Control

- `ManualControlPresenter`
  - View state → `ManualCommand`
  - Auto Tx UI orchestration
  - RTS/DTR
  - Local Echo signal

### Macro

- `MacroPresenter`
  - Macro UI orchestration
- `MacroRunner`
  - execution QThread
- `MacroScriptManager`
  - JSON save/load + loader thread lifecycle
- `MacroExecutionCoordinator`
  - target-port snapshot
  - CommandTransmissionService 호출
  - target port close interruption

### File Transfer

- `FileTransferManager`
  - Service/session 생성
  - QThreadPool scheduling
  - progress/speed/ETA
  - cancel/shutdown
- `FilePresenter`
  - dialog/View presentation

### Logging / Traffic

- `LoggingCoordinator`
  - port/system recording control
  - system TextLogWriter lifecycle
- `TrafficMonitor`
  - Tx/Rx logging/statistics
- `DataTrafficHandler`
  - RX UI buffer/throttling
- `StatusCoordinator`
  - 상태바 timer/statistics 표시

### Settings / UI state

- `SettingsCoordinator`
  - Preferences / Theme / Language / Font persistence
- `PreferencesCoordinator`
  - PreferencesState ↔ SettingsManager mapping
- `ControlStateCoordinator`
  - current connection + broadcast 기반 Manual/Macro enable policy
- `AppLifecycleManager`
  - 초기 View state 복원
- `ShutdownCoordinator`
  - runtime shutdown 순서 및 state 저장

---

## 7. Shutdown 규칙

종료는 background producer와 logger의 데이터 보존 때문에 순서가 중요합니다.

대표 순서:

```text
Macro/FileTransfer/MacroScript/PortScan/AutoTx stop
        ↓
DataHandler/Packet/Status stop
        ↓
System log close
        ↓
UI state save
        ↓
Connection close
        ↓
QCoreApplication.processEvents()
        ↓
DataLogger stop_all()
```

특히 connection worker가 종료 직전 emit한 queued RX를 전달하기 전에 data logger를 닫지 않습니다.

---

## 8. 프로젝트 구조

```text
serial_tool/
├─ main.py
├─ application_bootstrap.py
├─ common/
├─ core/
├─ model/
│  ├─ connection_controller.py
│  ├─ connection_session_factory.py
│  ├─ connection_worker.py
│  ├─ command_transmission_service.py
│  ├─ packet_parser_manager.py
│  ├─ port_scan_manager.py
│  ├─ macro_runner.py
│  ├─ macro_script_manager.py
│  ├─ file_transfer_service.py
│  ├─ file_transfer_manager.py
│  └─ traffic_monitor.py
├─ presenter/
│  ├─ main_presenter.py
│  ├─ port_presenter.py
│  ├─ manual_control_presenter.py
│  ├─ macro_presenter.py
│  ├─ packet_presenter.py
│  ├─ file_presenter.py
│  ├─ lifecycle_manager.py
│  ├─ macro_execution_coordinator.py
│  ├─ settings_coordinator.py
│  ├─ control_state_coordinator.py
│  ├─ logging_coordinator.py
│  ├─ status_coordinator.py
│  └─ shutdown_coordinator.py
├─ view/
├─ resources/
├─ tests/
├─ tools/
├─ tasks/
└─ doc/
```

Coordinator가 현재 `presenter/`에 함께 위치하지만, 기능 경계가 안정된 후 별도 application/coordinator package로 이동하는 것은 후속 후보입니다.

---

## 9. 설정 및 리소스

`SettingsManager`는 JSON Schema validation과 migration을 담당합니다.

- 개발 모드: 프로젝트의 개발용 설정 경로 사용
- 번들 모드: `%APPDATA%\SerialTool\` 사용자 경로 사용
- 손상 설정 파일은 안전한 fallback/backup 정책을 적용

리소스:

```text
resources/
├─ configs/
├─ languages/
├─ themes/
└─ icons/
```

UI 문자열을 추가하거나 변경하면 한국어/영어 리소스를 함께 갱신하고 다음을 실행합니다.

```bash
python tools/check_language_keys.py
```

---

## 10. PyInstaller

```powershell
pip install pyinstaller
pyinstaller serial_tool.spec --noconfirm
```

onedir 결과는 `dist/SerialTool/`에 생성됩니다.

---

## 11. 개발 규칙

작업 전 [`AGENTS.md`](AGENTS.md)를 읽습니다.

핵심 원칙:

- 현재 코드와 architecture contract를 과거 문서보다 우선
- explicit DI 유지
- EventRouter 재도입 금지
- worker → QWidget 접근 금지
- hidden singleton/fallback 재도입 금지
- broad `signal.disconnect()` 금지
- 변경 후 가장 작은 테스트부터 전체 테스트까지 확대
- 실행하지 않은 검증을 통과했다고 표현하지 않음

---

## 12. 문서

| 문서 | 목적 |
|---|---|
| `AGENTS.md` | AI/코딩 에이전트 최상위 작업 규칙 |
| `Task.MD` | 현재 완료/잔여 작업 체크리스트 |
| `doc/00_overview.md` | 현재 아키텍처 요약 |
| `doc/refactoring_validation_report_20260830.md` | main 대비 리팩토링 결과와 검증 계획 |
| `doc/implementation_plan.md` | 초기 설계/과거 계획 보존 문서 |
| `doc/task.md` | 과거 Phase 완료 이력 |
| `doc/CHANGELOG.md` | 변경 이력 |
| `doc/mistakes.md` | 반복 실수/교정 기록 |
| `tasks/` | 세부 S-xxx 작업 이력 |

---

## 13. 현재 다음 작업

현재 우선순위는 [`Task.MD`](Task.MD)의 P0 검증입니다.

1. stale API / constructor 전수 감사
2. `ruff check .`
3. architecture contract tests
4. lifecycle/threading tests
5. 전체 `pytest`
6. 실패 기준 마지막 구조 교정
7. 문서 정합성 확인
8. PR/CI Green
9. 검증 완료 후 squash/rebase 여부 판단

현재 브랜치에서 전체 검증을 아직 실행하지 않았으므로 Green baseline 숫자는 검증 후 기록합니다.
