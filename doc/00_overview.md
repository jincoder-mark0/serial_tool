# 프로젝트 개요 (Project Overview)

**SerialTool**은 Python(PyQt5) 기반의 고성능 멀티포트 시리얼 통신 유틸리티입니다.
현재 구조는 **MVP 기반 Passive View + Single Composition Root + explicit DI + direct Qt signal + 역할별 Coordinator/Manager**를 중심으로 구성됩니다.

> 현재 작업 상태와 우선순위는 `Task.MD`를 우선 확인합니다.

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

Dependency direction:

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

### 1.2 현재 데이터/명령 흐름

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

기존 `EventBus -> EventRouter -> Presenter` relay 구조는 완전히 제거됐습니다.

- `presenter/event_router.py` 없음
- `core/event_bus.py` 없음
- `common.constants.EventTopics` 없음
- production 주요 이벤트의 정본은 direct Qt signal
- `tests/test_direct_event_topology.py`가 relay 계층 재도입을 회귀로 차단

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

* **의존성 주입**: Presenter/Coordinator의 runtime dependency는 Composition Root에서 명시적으로 생성·주입합니다. 테스트 편의를 위한 hidden singleton/fallback 생성자를 다시 추가하지 않습니다.
* **View 정책**: View는 rendering/input/facade에 집중하며 연결 상태, broadcast 예외, settings persistence 같은 정책을 직접 소유하지 않습니다.
* **상태 관리**: View state는 `get_state()` / `apply_state()` 및 DTO를 사용하고, View state → Settings path 변환은 명시적 adapter를 사용합니다.
* **Cross-layer 데이터**: 계층 간 전달은 `common/dtos.py`의 DTO를 우선합니다.
* **기본값/상태 정본**: shared policy는 `constants.py`, fallback은 `defaults.py`, 유한 상태는 `enums.py`를 사용합니다.
* **Event topology**: 전역 Pub/Sub bus를 두지 않고 명확한 owner의 Qt signal을 사용합니다.
* **Thread lifecycle**: Worker/QThread/QThreadPool을 시작하는 객체가 생명주기 종료 책임도 가져야 합니다.
* **테스트**: 구현 내부 필드보다 public contract와 architecture invariant를 검증합니다.

---

## 4. 현재 상태와 제약

* 통신 구현의 주 사용 Transport는 Serial이며 LOOPBACK transport가 테스트에 사용됩니다.
* production 및 test 정본 event topology는 direct Qt signal입니다. EventRouter/EventBus/EventTopics는 제거됐습니다.
* Presenter/View Boundary 리팩토링은 PR #1에서 squash merge 완료됐습니다.
* P2-A timing policy 상수화는 PR #2에서 완료됐습니다.
* P2-A EventBus 완전 삭제는 PR #3에서 Python 3.11 full pytest `639 passed, 2 warnings` 및 CI 4/4 Green으로 검증됐습니다.
* CI는 Windows에서 `QT_QPA_PLATFORM=offscreen`으로 전체 pytest를 실행하고, 별도로 Ruff, language key, task board consistency를 검사합니다.
* 현재 backlog와 검증 범위는 `Task.MD`를 기준으로 합니다.

---

## 5. 문서 구조

* `README.md`: 사용자/개발자용 현재 기능·실행·아키텍처 안내.
* `AGENTS.md`: AI/코딩 에이전트 최상위 실행 규칙.
* `Task.MD`: **현재** 완료/잔여 작업 체크리스트.
* `RULES.md`: 검증/커밋/운영 규율.
* `CLAUDE.md`: Claude 계열 보조 작업 지침.
* `doc/00_overview.md`: 현재 프로젝트/아키텍처 개요.
* `doc/plans/`: P2/P3/P4 상세 실행 계획.
* `doc/refactoring_validation_report_20260830.md`: PR #1 merge 당시 감사/검증 snapshot.
* `doc/implementation_plan.md`: 초기 설계/과거 구현 계획 보존 문서.
* `tasks/`: 과거 S-xxx 상세 작업 이력.
* `doc/CHANGELOG.md`: 변경 이력.
* `doc/history/`: 세션별 작업/결정 기록.
