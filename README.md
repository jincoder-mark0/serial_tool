# SerialTool v1.0

**최종 업데이트**: 2025-12-10

**SerialTool**은 Python과 PyQt5로 개발된 강력한 통신 유틸리티입니다.
**Strict MVP (Model-View-Presenter)** 아키텍처를 기반으로 설계되어 유지보수성과 확장성이 뛰어나며,
Serial 통신뿐만 아니라 향후 SPI, I2C 등 다양한 프로토콜로의 확장을 고려한 현대적인 구조를 갖추고 있습니다.

---
## 1. 주요 기능 (Key Features)

### 1.1 핵심 기능

* **멀티 프로토콜(시리얼, SPI, I2C) 지원**: 탭 인터페이스로 여러 프로토콜(시리얼, SPI, I2C) 포트 동시 제어
* **송신**:
  * HEX/ASCII 모드
  * Prefix/Suffix
  * 여러 줄 입력 지원 (라인 번호 표시, Ctrl+Enter 전송)
  * 파일 전송 기능
  * Local Echo (송신 데이터 표시) 지원
  * 테스트를 위한 브로드캐스팅 지원
* **매크로 자동화**:
  * 여러 명령어를 리스트로 관리
  * 순차 명령 실행
  * Repeat 및 Delay 설정
  * 스크립트 저장 및 불러오기 (JSON 형식)
* **수신**:
  * HEX/ASCII 모드
  * Tx/Rx 바이트 카운트
  * 실시간 모니터링
  * 색상 규칙 기반 로그 강조 (OK=녹색, ERROR=빨강)
  * 타임스탬프 표시
  * 로그 저장 및 화면(newline 설정, max line 수 설정) 클리어

### 1.2 UI/UX 특징

* **현대적 인터페이스**:
  * 다크/라이트 테마 전환
  * 듀얼 폰트 시스템 (Proportional/Fixed)
  * SVG 기반 테마 적응형 아이콘
  * 컴팩트한 2줄 포트 설정 레이아웃
  * 3단계 Select All 체크박스
  * PortState Enum 기반 연결 상태 표시
* **사용성**:
  * 모든 기능 툴팁 제공
  * 설정 자동 저장 (창 크기, 테마, 폰트)
  * 견고한 폴백 메커니즘 (설정 파일 누락 시 복구)
  * 중앙 집중식 경로 관리 (AppConfig)
  * Package-level imports (**init**.py)

### 1.3 다국어 지원

* **한국어/영어** 실시간 전환
* CommentJSON 기반 번역 관리
* 언어 키 자동 추출 도구 (`tools/manage_lang_keys.py`)

---

## 2. 설치 및 실행 가이드

### 2.1 요구 사항 (Requirements)

* Python 3.8+
* PyQt5, pyserial, commentjson

### 2.2 설치 방법 (Installation)

```bash
# 1. 저장소 클론
git clone https://github.com/yourusername/SerialTool.git
cd SerialTool

# 2. 가상 환경 생성 (권장)
python -m venv .venv

# 3. 가상 환경 활성화
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. 패키지 설치
pip install -r requirements.txt
```

### 실행

```bash
# 가상 환경 활성화 후
python main.py
```

---

## 3. 프로젝트 구조 (Project Structure)

본 프로젝트는 역할과 책임에 따라 엄격하게 디렉토리가 구분되어 있습니다.

```
serial_tool/
├── main.py                             # 애플리케이션 진입점
├── requirements.txt                    # 의존성 목록
│
├── common/                             # 공통 데이터 및 상수 (의존성 최하위, 로직 없음)
│   ├── constants.py                    # 전역 상수 및 설정 키(ConfigKeys) 정의
│   ├── dtos.py                         # 데이터 전송 객체 (ManualCommand, PortConfig 등)
│   ├── enums.py                        # 열거형 (PortState, ParserType 등)
│   └── version.py                      # 버전 정보 관리
│
├── core/                               # 인프라 및 유틸리티 (비즈니스 로직과 무관한 기능)
│   ├── command_processor.py            # 명령어 처리
│   ├── data_logger.py                  # 데이터 로깅
│   ├── device_transport.py             # 하드웨어 통신 추상화 인터페이스
│   ├── error_handler.py                # 에러 핸들러
│   ├── event_bus.py                    # 이벤트 버스
│   ├── logger.py                       # 로깅 시스템 (Singleton)
│   ├── resource_path.py                # 경로 관리
│   ├── settings_manager.py             # 설정 관리 (Singleton)
│   └── utils.py                        # 유틸리티 함수
│
├── model/                              # [Model] 비즈니스 로직 및 상태 관리
│   ├── connection_controller.py        # 연결 세션 제어, 데이터 흐름 중재, Worker 관리
│   ├── connection_manager.py           # 전체 연결 인스턴스 관리 (Registry)
│   ├── connection_worker.py            # 실제 I/O를 수행하는 워커 스레드 (QThread)
│   ├── file_transfer.py                # 파일 전송 엔진 (QRunnable, Backpressure 포함)
│   ├── macro_runner.py                 # 매크로 실행 엔진 (QThread, 정밀 타이밍)
│   ├── packet_parser.py                # 패킷 파싱 전략 및 Expect 매처 구현
│   └── serial_transport.py             # PySerial 기반 DeviceTransport 구현체
│
├── presenter/                          # [Presenter] View와 Model의 중재자
│   ├── event_router.py                 # EventBus 이벤트를 PyQt Signal로 변환하여 라우팅
│   ├── file_presenter.py               # 파일 전송 로직, 진행률 계산, UI 업데이트 요청
│   ├── macro_presenter.py              # 매크로 로드/저장/실행 제어
│   ├── main_presenter.py               # 메인 화면 로직, 앱 수명주기, 하위 Presenter 조율
│   ├── manual_control_presenter.py     # 수동 제어(입력/전송) 로직 처리
│   ├── packet_presenter.py             # 패킷 뷰 데이터 포맷팅 및 업데이트
│   └── port_presenter.py               # 포트 스캔, 연결/해제 설정 처리
│
├── view/                               # [View] 사용자 인터페이스 (Passive View)
│   ├── main_window.py                  # 메인 윈도우 셸
│   │
│   ├── custom_qt/                      # PyQt5 커스텀 위젯
│   │   ├── smart_list_view.py          # 고성능 로그 뷰어 (QListView 확장)
│   │   ├── smart_number_edit.py        # 스마트 숫자 입력기 (자릿수 증감, Alt 코드)
│   │   └── smart_plain_text_edit.py    # 라인 번호가 있는 텍스트 에디터
│   │
│   ├── dialogs/                        # 팝업 대화상자
│   │   ├── about_dialog.py             # 정보창
│   │   ├── file_transfer_dialog.py     # 파일 전송 진행창
│   │   ├── font_settings_dialog.py     # 폰트 설정창
│   │   └── preferences_dialog.py       # 환경 설정창
│   │
│   ├── managers/                       # 관리자 계층
│   │   ├── color_manager.py            # 로그 색상 규칙 관리
│   │   ├── language_manager.py         # 다국어 리소스 관리
│   │   └── theme_manager.py            # 테마 및 폰트 관리
│   │
│   ├── panels/                         # 위젯을 그룹화한 패널 (중 단위)
│   │   ├── macro_panel.py              # 매크로 패널
│   │   ├── manual_control_panel.py     # 수동 제어 패널
│   │   ├── packet_panel.py             # 패킷 인스펙터 패널
│   │   ├── port_panel.py               # 포트 패널
│   │   └── port_tab_panel.py           # 포트 탭 패널
│   │
│   ├── sections/                       # 메인 윈도우 레이아웃 구획 (대 분할)
│   │   ├── main_left_section.py        # 메인 왼쪽 섹션
│   │   ├── main_right_section.py       # 메인 오른쪽 섹션
│   │   ├── main_menu_bar.py            # 메인 메뉴 바
│   │   └── main_status_bar.py          # 메인 상태 바
│   │
│   └─── widgets/                       # 개별 기능 단위 위젯 (소 단위)
│       ├── data_log.py                 # (구 RxLogWidget) 데이터 로그 뷰어
│       ├── file_progress.py            # 파일 전송 프로그레스바
│       ├── macro_control.py            # 매크로 제어 위젯
│       ├── macro_list.py               # 매크로 리스트 위젯
│       ├── manual_control.py           # (구 ManualControlWidget) 수동 제어 위젯
│       ├── packet.py                   # 패킷 트리 뷰
│       ├── port_settings.py            # 포트 설정 위젯
│       ├── port_stats.py               # 통계 위젯
│       └── system_log.py               # 시스템 로그 위젯
│
├── resources/                          # 리소스 파일
│   ├── languages/                      # 다국어 리소스
│   │   ├── ko.json                     # 한국어
│   │   └── en.json                     # 영어
│   │
│   ├── configs/                        # 설정 파일
│   │   ├── settings.json               # 앱 설정 (논리 그룹: serial, command, logging, ui)
│   │   └── color_rules.json            # 로그 색상 규칙
│   │
│   ├── icons/                          # SVG 아이콘
│   │   ├── light/                      # 라이트 테마용
│   │   └── dark/                       # 다크 테마용
│   │
│   └── themes/                         # QSS 스타일시트
│       ├── common.qss                  # 공통 스타일시트
│       ├── dark_theme.qss              # 다크 테마 스타일시트
│       └── light_theme.qss             # 라이트 테마 스타일시트
│
├── doc/                                # 프로젝트 문서
│   ├── changelog.md                    # 변경 이력
│   └── session_summary_YYYYMMDD.md     # 작업 세션 요약
│
├── .agent/                             # 개발 가이드
│   └── rules/                          # 규칙
│       ├── code_style_guide.md         # 코드 스타일 가이드
│       ├── comment_guide.md            # 주석 가이드
│       ├── git_guide.md                # git 가이드
│       └── naming_convention.md        # 명명 규칙 (언어 키, 변수명 등)
│
├── tools/                              # 유틸리티 도구
│   ├── check_language_keys.py          # 언어 키 검사 도구
│   └── manage_language_keys.py         # 언어 키 관리 도구
│
└── tests/                              # 테스트 코드
    ├── test_core_refinement.py         # Core Refinement 테스트
    ├── test_core_utiles.py             # Core Utils 테스트
    ├── test_model_packet_parsers.py    # Model Packet Parsers 테스트
    ├── test_model.py                   # Model 테스트
    ├── test_presenter_init.py          # Presenter Init 테스트
    ├── test_presenter_manual_contol.py # Presenter Manual Ctrl 테스트
    ├── test_presenter_packet.py        # Presenter Packet 테스트
    ├── test_view_translations.py       # View Translations 테스트
    └── test_view.py                    # View 테스트
```

---

## 4. 아키텍처 (Architecture)


### 4.1 MVP 패턴 & 데이터 흐름 (Data Flow)

본 프로젝트는 **Strict MVP (Model-View-Presenter)** 패턴을 준수합니다.
View와 Model은 서로 직접 통신하지 않으며,
**DTO(Data Transfer Object)**를 통한 데이터 교환과
**EventBus**를 통한 느슨한 결합(Decoupling)을 지향합니다.
데이터 흐름은 단방향성을 유지하며, 각 계층은 정의된 인터페이스(DTO)를 통해서만 소통합니다.


```
┌─────────────┐  (DTO)   ┌────────────────┐  (DTO)   ┌──────────────┐
│    View     │─────────►│    Presenter   │─────────►│     Model    │
│ (Passive)   │          │    (Logic)     │          │ (Biz/State)  │
└─────────────┘◄─────────└────────────────┘◄─────────└──────┬───────┘
       ▲                                                    │
       │ (UI Update via Interface Methods)                  │ (EventBus Publish)
       │                                                    ▼
┌──────┴───────┐                                   ┌────────────────┐
│ EventRouter  │◄────────(Subscribe/Route)─────────┤    EventBus    │
└──────────────┘                                   └────────────────┘
```

### 4.2 계층 구조 (Layers)

| 계층 | 역할 | 주요 구성 요소 | 비고 |
| :--- | :--- | :--- | :--- |
| **View** | **UI 표시 및 사용자 입력** | `MainWindow`, `PortSettingsWidget`, `RxLogWidget` | 비즈니스 로직 없음. 오직 시그널(`pyqtSignal`)만 발생시킴. `ConfigKeys` 상수 사용. |
| **Presenter** | **중재자 (Mediator)** | `MainPresenter`, `PortPresenter`, `MacroPresenter` | View의 시그널을 받아 Model을 제어하고, Model의 이벤트를 View에 반영. |
| **Model** | **비즈니스 로직 및 데이터** | `PortController`, `MacroRunner`, `FileTransferEngine` | 실제 통신, 파싱, 자동화 로직 수행. UI를 전혀 모르며 `EventBus`로 상태 전파. |
| **Core** | **인프라 및 유틸리티** | `EventBus`, `DataLogger`, `SettingsManager`, `ResourcePath` | 전역에서 사용되는 공통 기능 제공. |

### 4.3 컴포넌트 관계도 (Component Diagram)

```mermaid
graph TD
    %% 스타일 정의
    classDef view fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef presenter fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef model fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef core fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;

    subgraph VIEW_LAYER [View Layer (UI & Input)]
        direction TB
        MW[MainWindow]
        
        subgraph WIDGETS [Key Widgets]
            DataLog[DataLogViewer]
            PortSettings[PortSettingsWidget]
            ManualCtrl[ManualCtrlWidget]
        end
        
        MW --> PortSettings
        MW --> DataLog
        MW --> ManualCtrl
    end

    subgraph PRESENTER_LAYER [Presenter Layer (Mediator)]
        direction TB
        MainP[MainPresenter]
        PortP[PortPresenter]
        ManualP[ManualCtrlPresenter]
        Router[EventRouter]
    end

    subgraph CORE_LAYER [Core Layer (Infrastructure)]
        Bus((EventBus))
        Logger[DataLogger]
        Settings[SettingsManager]
    end

    subgraph MODEL_LAYER [Model Layer (Business Logic & Data)]
        direction TB
        PortCtrl[ConnectionController]
        MacroRun[MacroRunner]
        
        subgraph WORKERS [Background Threads]
            ConnWorker[ConnectionWorker]
            Transport[SerialTransport]
        end
    end

    %% 연결 관계
    PortSettings -- "signal: open_requested (DTO)" --> PortP
    ManualCtrl -- "signal: send_requested (DTO)" --> ManualP
    
    MainP o--o PortP
    MainP o--o ManualP
    MainP o--o Router

    PortP -- "open_connection(config)" --> PortCtrl
    ManualP -- "send_data(cmd)" --> PortCtrl

    PortCtrl o--o ConnWorker
    ConnWorker o--o Transport

    ConnWorker -- "emit: data_received" --> PortCtrl
    PortCtrl -- "publish: port.data_received" --> Bus

    Bus -- "subscribe" --> Router
    Bus -- "subscribe" --> Logger
    Bus -- "subscribe" --> MacroRun

    Router -- "signal: port_data" --> MainP
    MainP -- "append_data()" --> DataLog

    %% Class Styling
    class MW,DataLog,PortSettings,ManualCtrl view;
    class MainP,PortP,ManualP,Router presenter;
    class PortCtrl,ConnWorker,Transport,MacroRun model;
    class Bus,Logger,Settings core;
```

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                       VIEW LAYER                                        │
│  ┌───────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────┐  │
│  │      MainWindow       │   │      PortSettingsWidget   │   │     RxLogWidget       │  │
│  └───────────┬───────────┘   └──────────────┬────────────┘   └───────────▲───────────┘  │
│              │ (Owns)                       │ (Signal: Connect)          │ (Update)     │
└──────────────┼──────────────────────────────┼────────────────────────────┼──────────────┘
               │                              │                            │
               ▼                              ▼                            │
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PRESENTER LAYER                                      │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                   MainPresenter                                   │  │
│  │ ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐  │  │
│  │ │ PortPresenter │  │MacroPresenter │  │ FilePresenter │  │     EventRouter     │  │  │
│  │ └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └──────────▲──────────┘  │  │
│  └─────────┼──────────────────┼──────────────────┼─────────────────────┼─────────────┘  │
└────────────┼──────────────────┼──────────────────┼─────────────────────┼────────────────┘
             │ (Method Call)    │ (Method Call)    │ (Method Call)       │ (Signals)
             ▼                  ▼                  ▼                     │
┌────────────────────────────────────────────────────────────────────────┼────────────────┐
│                                    MODEL LAYER                         │                │
│                                                                        │                │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐    │                │
│  │  PortController  │   │   MacroRunner    │   │FileTransferEngine│    │                │
│  │ (Manages Ports)  │   │    (QThread)     │   │   (QRunnable)    │    │                │
│  └─────────┬────────┘   └────────┬─────────┘   └─────────┬────────┘    │                │
│            │ (Owns)              │ (Publish)             │ (Publish)   │                │
│            ▼                     │                       │             │                │
│  ┌──────────────────┐            │                       │             │                │
│  │ ConnectionWorker │            │                       │             │                │
│  │    (QThread)     │────────────┼───────────────────────┼─────────────┘                │
│  └──────────────────┘            │                       │                              │
└──────────────────────────────────┼───────────────────────┼──────────────────────────────┘
                                   │                       │
                                   ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                     CORE LAYER                                          │
│                                                                                         │
│           ┌─────────────────────────────────────────────────────────────┐               │
│           │                          EventBus                           │               │
│           │  (Publish / Subscribe Mechanism for Decoupling Layers)      │               │
│           └──────┬───────────────────────┬──────────────────────────────┘               │
│                  │ (Subscribe)           │ (Subscribe)                                  │
│                  ▼                       ▼                                              │
│        ┌──────────────────┐    ┌──────────────────┐                                     │
│        │    DataLogger    │    │ SettingsManager  │                                     │
│        │  (Raw File I/O)  │    │   (Config I/O)   │                                     │
│        └──────────────────┘    └──────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

```

---

## 데이터 흐름 시나리오 (Data Flow Scenarios)

### A. 포트 연결 및 데이터 수신 (RX Flow)
>
> **핵심**: `Worker Thread`와 `EventBus`를 통한 비동기 UI 업데이트

1. **User**: `PortSettingsWidget`에서 'Connect' 버튼 클릭.
2. **View**: `port_open_requested(config)` 시그널 발생.
3. **Presenter**: `PortPresenter`가 시그널을 수신하고 `PortController.open_port(config)` 호출.
4. **Model**: `PortController`가 `SerialTransport`를 생성하고, 이를 `ConnectionWorker`(QThread)에 주입하여 시작.
5. **Worker**: 백그라운드 스레드에서 `SerialTransport.read()` 루프 실행 (Non-blocking).
6. **Bridge**: 데이터 수신 시 `PortController`가 Signal을 발생시키고, 이는 자동으로 `EventBus`의 `port.data_received` 토픽으로 발행됨 (SSOT 원칙).
7. **Routing**:
    * `DataLogger`: Raw 데이터를 파일에 기록.
    * `EventRouter`: 이벤트를 감지하여 `data_received` 시그널로 변환.
8. **UI Update**: `MainPresenter`가 시그널을 받아 `RxLogWidget`(`QSmartListView`)에 데이터를 전달하여 렌더링.

### B. 수동 명령어 전송 (Manual TX Flow)
>
> **핵심**: Presenter에서의 비즈니스 로직(Prefix/Suffix) 처리

1. **User**: `ManualCtrlWidget`에서 명령어 입력 후 'Send' 클릭.
2. **View**: `manual_cmd_send_requested` 시그널 발생 (입력값, 옵션 상태 전달).
3. **Presenter**: `MainPresenter`가 설정(`ConfigKeys`)을 조회하여 Prefix/Suffix를 조합하고 HEX 변환을 수행.
4. **Model**: `PortController.send_data()`를 호출하여 활성 포트로 데이터 전송.
5. **Feedback**: 전송된 데이터는 `Local Echo` 옵션에 따라 `RxLogWidget`에 표시되고, `DataLogger`에 기록됨.

### C. 매크로 자동화 실행 (Automation Flow)
>
> **핵심**: `QThread` 기반 정밀 타이밍 및 `Expect` 대기

1. **User**: `MacroCtrlWidget`에서 'Repeat Start' 클릭.
2. **Presenter**: `MacroPresenter`가 선택된 항목들을 `MacroEntry` 객체로 변환하여 `MacroRunner`에 로드.
3. **Model (`MacroRunner`)**:
    * `QThread` 내부 루프 시작.
    * **Send**: `send_requested` 시그널 → `MainPresenter` → `PortController`.
    * **Expect**: `ExpectMatcher`를 설정하고 `QWaitCondition`으로 대기. `EventBus`로 들어오는 수신 데이터를 실시간 검사.
    * **Delay**: 정밀 타이밍을 위해 `QWaitCondition.wait()` 사용 (Windows Timer 오차 해결).
4. **Completion**: 루프 종료 시 `macro_finished` 이벤트 발생 → UI 상태 복구.

### D. 파일 전송 (File Transfer Flow)
>
> **핵심**: `Backpressure` 제어 및 스레드 풀 사용

1. **User**: `ManualCtrlWidget` 파일 탭에서 'Send File' 클릭.
2. **Presenter**: `FilePresenter`가 `FileTransferEngine`(`QRunnable`)을 생성하고 `QThreadPool`에서 실행.
3. **Model (`FileTransferEngine`)**:
    * 파일을 Chunk 단위로 읽음.
    * **Backpressure**: `PortController`의 송신 큐(`TX Queue`) 크기를 모니터링하여 오버플로우 방지.
    * **Flow Control**: RTS/CTS 설정에 따라 전송 지연(Sleep) 최적화.
4. **Update**: 진행률(`progress`) 이벤트를 `EventBus`로 발행 → `FileProgressWidget` 갱신.

---

**설계 원칙**:

* **View**: UI 표시와 사용자 입력만 처리 (시그널 emit)
* **Presenter**: 비즈니스 로직 처리 (View ↔ Model 중재)
* **Model**: 데이터 및 시리얼 통신 담당

**최근 리팩토링 사례**:

* ManualCtrlWidget: Prefix/Suffix 로직 → Presenter로 이동
* PortSettingsWidget: 설정 접근 → SettingsManager 활용

### 설정 구조

**논리적 그룹 기반** (`config/settings.json`):

```json
{
  "serial": { "baudrate": 115200, ... },
  "command": { "prefix": "AT", "suffix": "\r\n" },
  "logging": { "log_path": "logs/", ... },
  "ui": { "theme": "dark", "font": {...} }
}
```

---

## 5. 개발 가이드 (Development Guide)

### 5.1 문서 참조

| 문서 | 목적 | 위치 |
|------|------|------|
| Implementation Specification | 전체 설계 및 명세 | `doc/Implementation_Specification.md` |
| View 구현 계획 | View 계층 구현 가이드 | `view/doc/implementation_plan.md` |
| 코딩 규칙 | 코드 스타일 | `guide/code_style_guide.md` |
| 명명 규칙 | 코드/언어 키 네이밍 | `guide/naming_convention.md` |
| 주석 가이드 | 주석/Docstring 작성법 | `guide/comment_guide.md` |
| Git 가이드 | 커밋/PR/이슈 규칙 | `guide/git_guide.md` |
| 변경 이력 | 세션별 변경 사항 | `doc/changelog.md` |
| 세션 요약 | 2025-12-09 작업 요약 | `doc/session_summary_20251209.md` |

### 5.2 코드 스타일

* **PEP 8** 준수
* **한국어** 주석 및 Docstring
* **타입 힌트** 필수
* **MVP 패턴** 준수 (View는 시그널만 emit)

### 5.3 네이밍 규칙 (Naming Convention)
* **클래스**: `PascalCase` (e.g., `DataLogWidget`)
* **함수/변수**: `snake_case` (e.g., `connect_port`)
* **언어 키**: `[context]_[type]_[name]` (e.g., `port_btn_connect`)
* **DTO**: `PascalCase` (e.g., `ManualCommand`)

### 5.4 Git 버전 관리

* 본 프로젝트는 **Git을 통한 지속적인 백업**을 권장합니다:
* 모든 메시지는 **한국어**로 작성합니다.

```bash
# 커밋 메시지 형식 (한국어)
Feat: 기능 추가
Fix: 버그 수정
Docs: 문서 수정
Refactor: 리팩토링
Style: 스타일 변경
```

**브랜치 전략**:

* `main`: 안정 버전
* `feature/기능명`: 개발 브랜치

**권장 사항**:

* 기능 단위로 자주 커밋 (최소 하루 1회)
* 세션 종료 시 `doc/session_summary_YYYYMMDD.md` 작성

---

## 6. 도구 및 테스트 (Tools & Tests)

### 6.1 유틸리티 도구
```bash
# 소스 코드에서 언어 키 추출 및 JSON 업데이트
python tools/manage_lang_keys.py extract

# 누락되거나 사용되지 않는 언어 키 검사
python tools/manage_lang_keys.py check
```

### 6.2 테스트 실행
```bash
# 전체 테스트 실행
pytest

# 특정 모듈 테스트
pytest tests/test_model.py

# 상세 출력 모드
pytest -v -s
```
