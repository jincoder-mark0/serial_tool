# SerialTool

**최종 업데이트: 2026-08-30**

SerialTool은 Python/PyQt5 기반 멀티포트 Serial 통신·자동화·프로토콜 분석 도구입니다.
현재 정본 브랜치는 `main`이며, Presenter/View Boundary 리팩토링은 PR #1에서 squash merge 완료했습니다.

> 현재 기준 브랜치: `main`
> 현재 작업 보드: [`Task.MD`](Task.MD)
> AI/코딩 에이전트 규칙: [`AGENTS.md`](AGENTS.md)
> 리팩토링 기록: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)

## 1. 현재 상태

2026-08-30 기준 구조 리팩토링과 검증은 완료됐습니다.

```text
Local Windows / Python 3.13.15
  pytest: 643 passed, 0 failed, 0 skipped
  Ruff: 0 errors
  language key integrity: Green
  task board consistency: Green

PR #1 / GitHub Actions / Python 3.11
  test-windows: success
  lang-keys: success
  task-boards: success
  lint: success

main post-merge CI
  squash merge push: Green
  latest documentation push: Green
```

검증 범위와 알려진 제한사항은 [`Task.MD`](Task.MD)에 기록합니다.

---

## 2. 주요 기능

### Serial / Connection

- 다중 Serial port tab
- 연결/해제 및 per-port 설정
- LOOPBACK debug transport
- ASCII / HEX 송신
- Prefix / Suffix / Newline mode
- Local Echo / Broadcast
- RTS / DTR
- 비동기 Port Scan

### Auto Tx / Macro

- 주기 Auto Tx
- Macro list 저장/로드/실행
- Delay / Expect / Timeout
- 반복/Broadcast 실행
- 실제 전송 성공/실패를 Macro 결과에 반영

### File Transfer

- Chunk 기반 비동기 전송
- Backpressure
- progress / speed / ETA
- cancel / port-close / shutdown 대응
- Queue뿐 아니라 실제 `transport.write()` idle/error까지 확인 후 완료 판정

### RX / Logging / Packet

- 대량 RX UI batching/throttling
- Tx/Rx statistics
- BIN / HEX / PCAP logging
- System log
- Raw / AT / Delimiter / Fixed-Length / Length-Field / Gap framing
- checksum validation

### UI / Settings

- Dark / Light / Dracula / Classic theme
- 한국어 / 영어
- proportional / fixed font
- schema validation + migration
- 사용자 설정/로그 경로 분리

---

## 3. 설치 및 실행

요구 사항:

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

Windows / PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

GitHub Actions는 `.github/workflows/ci.yml`의 `SerialTool CI`가 담당합니다.

- `test-windows`: Windows + Python 3.11 전체 pytest
- `lang-keys`: language key integrity
- `task-boards`: Task/tasks consistency
- `lint`: Ruff
- `workflow_dispatch`: 수동 실행 지원

---

## 5. 현재 Architecture

핵심 원칙은 **Single Composition Root + Passive View + explicit DI + direct Qt signal**입니다.

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

핵심 규칙:

- View -> Model 직접 import/호출 금지
- Model -> Presenter/View import 금지
- Presenter/Coordinator의 concrete QtWidgets 생성 금지
- worker -> QWidget/View 접근 금지
- Presenter 내부 hidden singleton/manager fallback 금지
- `EventRouter` 재도입 금지
- production 주요 event는 direct Qt signal

---

## 6. 주요 책임 소유권

### Connection

- `ConnectionController`: session registry, open/close/send/broadcast, lifecycle signal
- `ConnectionSessionFactory`: Transport 선택 + ConnectionWorker 생성
- `PacketParserManager`: parser lifecycle/feed/flush

### Transmission

- `CommandTransmissionService`: command processing, prefix/suffix, target resolution, validation, send

### Port / Macro / File

- `PortPresenter`: Port View 중재
- `PortScanManager`: scan worker lifecycle
- `MacroPresenter`: Macro UI
- `MacroRunner`: execution QThread
- `MacroScriptManager`: script I/O + load worker lifecycle
- `MacroExecutionCoordinator`: target snapshot/send/port-close policy
- `FileTransferManager`: transfer lifecycle/QThreadPool/progress/cancel
- `FilePresenter`: dialog/View presentation

### Logging / State

- `LoggingCoordinator`: port/system recording control
- `TrafficMonitor`: Tx/Rx logging/statistics
- `DataTrafficHandler`: RX UI batching
- `StatusCoordinator`: status timer/statistics
- `SettingsCoordinator`: Preferences/Theme/Language/Font persistence
- `ControlStateCoordinator`: Manual/Macro enable policy
- `ShutdownCoordinator`: shutdown ordering/state save

---

## 7. Shutdown Data-Preservation Rule

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

connection worker 종료 직전 queued RX가 전달되기 전에 DataLogger를 닫지 않습니다.

---

## 8. 문서 체계

| 문서 | 역할 |
|---|---|
| `AGENTS.md` | 최상위 작업/architecture 규칙 |
| `Task.MD` | 현재 작업 보드 및 post-merge backlog |
| `RULES.md` | 검증/커밋/운영 규율 |
| `CLAUDE.md` | Claude 계열 보조 지침 |
| `doc/00_overview.md` | architecture overview |
| `doc/refactoring_validation_report_20260830.md` | PR #1 리팩토링 감사/검증 기록 |
| `doc/CHANGELOG.md` | 변경 이력 |
| `doc/history/` | 세션별 작업/결정 기록 |
| `tasks/` | S-xxx 상세 작업 이력 |

`doc/refactoring_validation_report_20260830.md`는 merge 당시 검증 snapshot을 보존하는 기록 문서이며 현재 작업 상태는 `Task.MD`를 우선합니다.

---

## 9. 현재 다음 작업

현재 구조/CI gate는 Green입니다. 신규 작업 우선순위는 [`Task.MD`](Task.MD)의 **Post-merge backlog**를 따릅니다.

주요 후보:

- Windows com0com / Linux socat / 실제 USB Serial 검증
- 최신 HEAD PyInstaller smoke 재검증
- RX/Serial I/O 성능 재평가
- Plugin system
- SPI/I2C/TCP/UDP 확장
- Packet filter/annotation/export
