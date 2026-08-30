# 프로젝트 개요 (Project Overview)

**SerialTool**은 Python(PyQt5) 기반의 고성능 멀티포트 시리얼 통신 유틸리티입니다.
현재 구조는 **MVP 기반의 Passive View + 명시적 Composition Root + 역할별 Coordinator/Manager**를 중심으로 구성됩니다.

---

## 1. 핵심 아키텍처 (Core Architecture)

### 1.1 계층 구조

* **View (Passive View)**: UI 렌더링과 사용자 입력 수신을 담당합니다. Model-affecting command는 직접 처리하지 않고 public signal/facade를 통해 상위 조정 계층에 전달합니다. (`view/`)
* **Presenter**: 특정 View와 Model/Service 사이의 UI 중재를 담당합니다. 사용자 입력을 DTO/유스케이스로 변환하고 결과를 View에 반영합니다. (`presenter/`)
* **Coordinator**: 설정 적용, control enable 정책, macro 실행 조정, logging, status, shutdown처럼 여러 컴포넌트를 가로지르는 application/UI orchestration을 담당합니다. 현재 관련 클래스는 `presenter/` 패키지에 위치합니다.
* **Model / Application Service**: 연결, 전송, parser, file transfer, worker lifecycle, macro runner 등 핵심 실행 로직을 담당합니다. (`model/`)
* **Core (Infrastructure)**: 설정 저장, 로깅, transport driver, checksum 등 기반 기능을 제공합니다. (`core/`)
* **Common (Shared Contract)**: DTO, Enum, Constants, Defaults 등 계층 간 공유 계약을 정의합니다. (`common/`)
* **Composition Root**: `application_bootstrap.py`가 View 상태 복원부터 MainPresenter 생성까지 전체 runtime object graph와 고정 signal topology를 한 곳에서 조립합니다.

### 1.2 현재 데이터/명령 흐름

대표적인 흐름은 다음과 같습니다.

```text
User Action
    ↓
View signal
    ↓
Presenter / Coordinator
    ↓
Application Service / Model
    ↓
Qt signal / DTO
    ↓
Presenter / Coordinator
    ↓
View facade
```

고속 RX/TX처럼 실행 중 변하지 않는 경로는 Composition Root에서 직접 배선합니다.

```text
ConnectionController.data_received
    ├─→ DataTrafficHandler → MainWindow RX View
    ├─→ MacroRunner Expect 처리
    └─→ PacketParserManager → packet_received → PacketPresenter

ConnectionController.data_sent
    └─→ DataTrafficHandler
```

기존의 `EventBus → EventRouter → Presenter` production 경로는 제거되었습니다. `EventRouter`는 삭제되었으며, 주요 runtime 이벤트는 direct Qt signal topology를 사용합니다.

### 1.3 애플리케이션 조립 순서

```text
main.py
  ↓
ApplicationBootstrapper
  ├─ AppLifecycleManager.initialize_view()
  ├─ Model / Service 생성
  ├─ Presenter 생성
  ├─ ManualControlState 복원
  ├─ Coordinator 생성
  ├─ static signal wiring
  ├─ Shutdown graph 생성
  └─ MainPresenter 생성
```

`main.py`는 리소스, SettingsManager, UI manager, QApplication, MainWindow를 준비한 뒤 Bootstrapper를 호출하는 진입점 역할에 집중합니다.

---

## 2. 주요 기능 및 모듈

| 모듈 | 설명 | 주요 클래스 |
| :--- | :--- | :--- |
| **Composition** | 전체 runtime graph 생성/고정 signal 배선 | `ApplicationBootstrapper` |
| **Port Management** | 다중 포트 연결 및 설정 관리 | `PortPresenter`, `ConnectionController`, `PortScanManager` |
| **Connection Session** | Transport/Worker 생성, parser lifecycle | `ConnectionSessionFactory`, `PacketParserManager` |
| **Manual Transmission** | 수동/Auto Tx 명령 전송 | `ManualControlPresenter`, `CommandTransmissionService` |
| **Macro Automation** | 반복 실행, 단일 Row Send, script I/O | `MacroPresenter`, `MacroRunner`, `MacroExecutionCoordinator`, `MacroScriptManager` |
| **File Transfer** | 파일 전송 session/thread lifecycle | `FilePresenter`, `FileTransferManager`, `FileTransferService` |
| **Packet Inspection** | 수신 packet 처리 및 표시 | `PacketPresenter`, `PacketParserManager` |
| **Logging** | Port/System 로그 기록 lifecycle | `LoggingCoordinator`, `DataLoggerManager`, `TextLogWriter` |
| **Runtime State** | control enable/status bar 정책 | `ControlStateCoordinator`, `StatusCoordinator`, `TrafficMonitor` |
| **Settings** | Preferences/Theme/Language/Font 적용 | `SettingsCoordinator`, `PreferencesCoordinator` |
| **Shutdown** | background 작업 및 logger 안전 종료 | `ShutdownCoordinator`, `ShutdownStateCollector` |

---

## 3. 개발 가이드 요약

* **의존성 주입**: Presenter/Coordinator의 runtime dependency는 가능한 한 Composition Root에서 명시적으로 생성·주입합니다. 테스트 편의를 위한 hidden singleton/fallback 생성자를 다시 추가하지 않습니다.
* **View 정책**: View는 rendering/input/facade에 집중하며 연결 상태, broadcast 예외, settings persistence 같은 정책을 직접 소유하지 않습니다.
* **상태 관리**: View state는 `get_state()` / `apply_state()` 및 DTO를 사용하고, View state → Settings path 변환은 명시적 adapter를 사용합니다.
* **Cross-layer 데이터**: 계층 간 전달은 `common/dtos.py`의 DTO를 우선합니다.
* **기본값/상태 정본**: shared policy는 `constants.py`, fallback은 `defaults.py`, 유한 상태는 `enums.py`를 사용합니다.
* **Thread lifecycle**: Worker/QThread/QThreadPool을 시작하는 객체가 생명주기 종료 책임도 가져야 합니다.
* **테스트**: 구현 내부 필드보다 public contract와 architecture invariant를 검증합니다.

---

## 4. 현재 상태와 제약

* 통신 구현의 주 사용 Transport는 Serial이며 LOOPBACK transport가 테스트에 사용됩니다.
* production 주요 이벤트 경로는 direct Qt signal입니다. `core/event_bus.py`는 현재 주요 runtime 경로에서 사용하지 않으며 테스트 실행 후 완전 제거 여부를 판단할 예정입니다.
* 리팩토링 브랜치는 `main`과 큰 차이가 있으므로 merge 전 전체 stale API/constructor 감사와 실제 ruff/pytest/CI 검증이 필수입니다.
* CI는 Windows에서 `QT_QPA_PLATFORM=offscreen`으로 전체 pytest를 실행하고, 별도로 Ruff, language key, task board consistency를 검사합니다.
* 리팩토링 상세 현황과 검증 절차는 `doc/refactoring_validation_report_20260830.md`를 기준 문서로 사용합니다.

---

## 5. 문서 구조

* `doc/00_overview.md`: 현재 프로젝트/아키텍처 개요.
* `doc/refactoring_validation_report_20260830.md`: `main` 대비 리팩토링 주요 변경과 stale API/constructor 감사, ruff/pytest/CI 검증 계획.
* `doc/refactor_audit_20260822.md`: 이전 구조 감사 기록.
* `doc/history/`: 과거 세션 요약 및 변경 이력.
* `doc/implementation_plan.md`: 상세 구현 계획.
* `doc/task.md`: 작업 진행 상황 트래킹.
* `doc/CHANGELOG.md`: 변경 이력.
