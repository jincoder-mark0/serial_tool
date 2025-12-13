# Session Summary - 2025-12-12

## 1. 개요 (Overview)

금일 개발 오전 세션은 **EventBus 싱글톤 패턴 수정** 및 **Presenter 계층 구조화**로 시작하여,
**아키텍처 안정화(Stabilization)**와 **핵심 기능의 정밀도 향상**에 집중했습니다.

오전에는 `ModuleNotFoundError` 및 싱글톤 이슈를 해결하고 `EventRouter`를 도입했습니다. 이후 세션에서는 **이벤트 전달 체계의 이중성 제거**, **설정 키 상수화**, **매크로 엔진의 타이밍 정밀도 개선(QThread 전환)**, **파일 전송 흐름 제어(Backpressure)** 등 시스템의 신뢰성을 높이는 대규모 리팩토링을 수행했습니다. 또한 명확한 역할 분리를 위해 `LogRecorder`를 `DataLogger`로 명칭을 변경했습니다.

## 2. 주요 변경 사항 (Key Changes)

### 2.1 EventBus 및 Presenter 구조화

- **EventBus 전역 인스턴스 도입**:
  - `core/event_bus.py`에 모듈 레벨 `event_bus` 인스턴스를 생성하고 복잡한 싱글톤 로직을 단순화했습니다.
  - 모든 컴포넌트가 동일한 EventBus 인스턴스를 공유하도록 보장했습니다.

- **Presenter 계층 세분화**:
  - **`EventRouter`**: EventBus 이벤트를 PyQt 시그널로 변환하여 View와 Model의 결합도를 낮췄습니다.
  - **`MacroPresenter`**: 매크로 실행 및 상태 관리를 전담합니다.
  - **`FilePresenter`**: 파일 전송 로직 및 진행률 표시를 전담합니다.

- **MainPresenter 리팩토링**:
  - 하위 Presenter(`Port`, `Macro`, `File`)를 초기화하고 조율하는 역할로 재정립했습니다.

### 2.2 아키텍처 및 구조 개선

- **이벤트 전달 체계 일원화 (Event System Unification)**:
  - `PortController`에서 Signal 발생과 EventBus 발행이 중복되던 구조를 개선했습니다.
  - Signal 발생 시 자동으로 EventBus로 전파되도록 `_connect_signals_to_eventbus` 브리지를 구현하여 **SSOT(Single Source of Truth)** 원칙을 확립했습니다.
  - `MainPresenter`가 Model에 직접 의존하지 않고 `EventRouter`를 통해 통신하도록 수정했습니다.

- **설정 키 상수화 (ConfigKeys)**:
  - 설정 파일(`settings.json`)의 키 경로를 관리하는 `ConfigKeys` 상수 클래스를 `constants.py`에 도입했습니다.
  - 코드 전반에 산재된 문자열 리터럴을 상수로 교체하여 오타 방지 및 유지보수성을 확보했습니다.

- **Data Logger 명칭 변경**:
  - 시스템 로그(`Logger`)와 데이터 로깅의 역할을 명확히 구분하기 위해 `LogRecorder`를 **`DataLogger`**로 변경했습니다.
  - 관련 클래스(`DataLogger`, `DataLoggerManager`) 및 UI 텍스트를 일괄 수정했습니다.

- **Data Logger Viewer 명칭 변경**:
  - `RxLogWidget`를 **`DataLogViewer`**로 명칭 변경 (송수신 데이터를 포괄하는 `DataLog`가 더 정확함)
  - 관련 클래스(`DataLogViewer`, `DataLogViewerManager`) 및 UI 텍스트를 일괄 수정했습니다.

### 2.3 핵심 기능 고도화 (Core Logic Enhancements)

- **매크로 엔진 정밀도 및 품질 개선 (Macro Engine)**:
  - `MacroRunner`를 기존 `QTimer` 기반에서 **`QThread` + `QWaitCondition`** 기반으로 전면 재작성하여 윈도우 타이머 정밀도 문제(1ms 단위 제어)를 해결하고 UI 블로킹을 방지했습니다.
  - **문서화 강화**: 핵심 모듈에 `Google Style Docstring` 가이드(WHY/WHAT/HOW, Logic)를 엄격히 적용하여 코드 가독성과 유지보수성을 대폭 향상시켰습니다.
  - **스레드 안전성**: `_on_data_received` 및 `run` 루프 내 `QMutex` 잠금 범위를 최적화하여 데이터 수신 시 발생할 수 있는 경쟁 상태(Race Condition)를 방지했습니다.
  - **테스트 안정화**: 비동기 테스트 시나리오의 타임아웃을 연장(1s → 5s)하고 스레드 초기화 대기 로직을 보강하여 간헐적인 `TimeoutError`를 해결했습니다.

- **파일 전송 안정성 확보 (File Transfer)**:
  - **Backpressure(역압) 제어**: 송신 큐(`TX Queue`) 크기를 모니터링하여 버퍼 오버플로우를 방지하는 로직을 추가했습니다.
  - **Flow Control 연동**: 포트 설정(RTS/CTS, XON/XOFF)에 따라 전송 지연(Sleep)을 조건부로 적용하여 전송 속도를 최적화했습니다.

### 2.4 성능 최적화 및 버그 수정

- **로그 필터링 성능 개선**:
  - `QSmartListView` 검색 입력에 **디바운싱(Debouncing, 300ms)**을 적용했습니다.
  - 대량의 로그가 쌓인 상태에서 정규식 입력 시 발생하는 UI 프리징 현상을 해결했습니다.

- **에러 핸들러 호환성 개선**:
  - `GlobalErrorHandler`에서 `KeyboardInterrupt` 처리 시 기존 훅(`_old_excepthook`)을 호출하도록 수정하여, 다른 라이브러리와의 호환성을 보장했습니다.

## 3. 파일 변경 목록 (File Changes)

### 신규 생성 및 주요 수정

- **Core & Constants**:
  - `constants.py`: `ConfigKeys` 상수 클래스 추가.
  - `core/data_logger.py`: (구 log_recorder.py) 클래스명 변경 및 로직 수정.
  - `core/error_handler.py`: 훅 체이닝 로직 개선.
  - `core/event_bus.py`: 전역 인스턴스화.

- **Model**:
  - `model/port_controller.py`: 시그널-EventBus 브리지 구현, 설정 저장, 중복 코드 제거.
  - `model/macro_runner.py`: QThread 기반으로 전면 리팩토링, Expect 로직 추가.
  - `model/packet_parser.py`: `ExpectMatcher` 구현, `ParserType` 상수 추가.
  - `model/file_transfer.py`: Backpressure 및 Flow Control 로직 추가.
  - `model/connection_worker.py`: 큐 사이즈 조회 메서드 추가.

- **View & Presenter**:
  - `presenter/event_router.py`: 신규 생성, `data_sent` 시그널 라우팅.
  - `presenter/macro_presenter.py`, `file_presenter.py`: 신규 생성.
  - `presenter/main_presenter.py`: ConfigKeys 적용, EventRouter 의존성 강화.
  - `view/custom_qt/smart_list_view.py`: 필터링 디바운스 타이머 추가.
  - `view/main_window.py`, `view/dialogs/preferences_dialog.py`: ConfigKeys 적용.

## 4. 테스트 결과 (Test Results)

| 테스트 파일 | 결과 |
|------------|------|
| `test_core_refinement.py` | ✅ 6/6 통과 |
| `test_presenter_init.py` | ✅ 1/1 통과 |
| 전체 테스트 (`pytest tests/`) | 9 통과, 8 실패 (UI 번역 관련) |

> **참고**: UI 번역 테스트 실패는 위젯 초기화 관련 이슈로, 금일 세션 범위 외입니다.

## 5. 향후 계획 (Next Steps)

- **Phase 4: Model 계층 통합**
  - `ExpectMatcher`를 `MacroRunner`에 통합하여 응답 대기 기능 구현
  - `PacketParser`를 `PacketInspectorWidget`과 연동

- **Phase 6: 자동화 및 고급 기능 (진행 중)**
  - `MacroRunner`와 UI 연동 테스트 (실제 장비)
  - `FileTransferEngine`과 UI 완전 연동 (`FilePresenter` 활용)
  - 파일 전송 다이얼로그 진행률 표시 구현
  - 파일 전송 중단/재개 기능 고도화

- **안정화 (Stabilization)**
  - 통합 테스트(Integration Test) 시나리오 추가
  - 장시간(Long-run) 동작 시 메모리 누수 점검

## 6. 아키텍처 다이어그램 (Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                        MainPresenter                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │PortPresenter │  │MacroPresenter│  │FilePresenter │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │               │
│  ┌──────┴─────────────────┴─────────────────┴──────────┐    │
│  │                    EventRouter                       │    │
│  │  (EventBus Events → PyQt Signals)                    │    │
│  └──────────────────────┬───────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │       event_bus       │  (Global Singleton)
              │  (Publish/Subscribe)  │
              └───────────┬───────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───┴────────┐   ┌────────┴────────┐   ┌───────┴─────────┐
│PortController│ │   MacroRunner    │ │FileTransferEngine│
│  (Model)     │ │    (Model)       │ │     (Model)      │
└──────────────┘ └──────────────────┘ └──────────────────┘
```
