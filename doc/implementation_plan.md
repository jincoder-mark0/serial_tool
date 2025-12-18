# SerialTool 구현 계획 (Implementation Plan)

**최종 업데이트**: 2025-12-11

## 목표 (Goal)

`Implementation_Specification.md`에 정의된 **SerialTool v1.0**을 **Python 3.10+** 및 **PyQt5**를 사용하여 구현합니다. **MVP (Model-View-Presenter)** 아키텍처와 **Worker Thread** 모델을 적용하여 **고성능**, **안정성**, **확장성**을 확보하는 것이 목표입니다.

### 핵심 목표

- **멀티포트 관리**: 최대 16개 포트 동시 오픈 및 독립 제어
- **고속 데이터 처리**: 2MB/s 연속 스트림, 초당 10K 라인 로그 처리
- **자동화 엔진**: Macro List 기반 스크립트 실행, Repeat 스케줄러
- **송수신 제어**: Local Echo, RX Newline 처리
- **파일 송수신**: Chunk 기반 전송, 진행률 표시, 취소/재시도
- **확장성**: EventBus 기반 플러그인 시스템
- **MVP 패턴 준수**: View-Presenter-Model 계층 분리 및 Signal 기반 통신
- **중앙 집중식 경로 관리**: AppConfig를 통한 리소스 경로 관리

---

## 사용자 검토 필요 사항 (User Review Required)

> [!IMPORTANT]
> **프로젝트 핵심 결정 사항**
>
> - **프로젝트 명칭**: `SerialManager` → `SerialTool`로 변경 완료
> - **UI 구조**: `LeftPanel`(포트/수동제어) + `RightPanel`(커맨드/인스펙터) 구조 확정
> - **성능 목표**: Rx 2MB/s, UI 10K lines/s 처리를 위한 RingBuffer 및 Batch Rendering 적용
> - **스타일링**: 중앙 집중식 QSS 테마 시스템 (`common.qss` + 개별 테마)

> [!WARNING]
> **다음 단계 진행 전 확인 필요**
>
> - **Core 유틸리티 구현 방향**: RingBuffer 크기(512KB), ThreadSafeQueue 최대 크기(128 chunks) 확정 필요
> - **멀티포트 최대 개수**: 현재 16개로 설정, 변경 필요 시 알려주세요
> - **플러그인 시스템 범위**: v1.0에 포함할지, v1.1로 연기할지 결정 필요

---

## 제안된 변경 사항 (Proposed Changes)

### 1. 프로젝트 구조 (Project Structure)

프로젝트 루트 하위에 계층별 모듈을 구성합니다:

```
├── main.py                             # 애플리케이션 진입점
├── requirements.txt                    # 의존성 목록
│
├── common/                             # 공통 정의 (의존성 최하위)
│   ├── constants.py                    #
│   ├── dtos.py                         #
│   ├── enums.py                        #
│   └── version.py                      #
│
├── core/                               # 핵심 유틸리티
│   ├── command_processor.py            # 명령어 처리
│   ├── data_logger.py                  # 데이터 로깅
│   ├── error_handler.py                # 에러 핸들러
│   ├── event_bus.py                    # 이벤트 버스
│   ├── device_transport.py             #
│   ├── logger.py                       # 로깅 시스템 (Singleton)
│   ├── port_state.py                   # 포트 상태 관리
│   ├── resource_path.py                # 경로 관리
│   ├── settings_manager.py             # 설정 관리 (Singleton)
│   └── utils.py                        # 유틸리티 함수
│
├── model/                              # 비즈니스 로직
│   ├── connection_controller.py        #
│   ├── connection_manager.py           #
│   ├── connection_worker.py            # 연결 워커
│   ├── file_transfer.py                # 파일 전송
│   ├── macro_runner.py                 # 매크로 실행
│   ├── packet_parser.py                # 패킷 파싱
│   └── serial_transport.py             # 전송 관리
│
├── presenter/                          # MVP Presenter 계층
│   ├── event_router.py                 # 이벤트 라우터
│   ├── file_presenter.py               # 파일 프레젠터
│   ├── macro_presenter.py              # 매크로 프레젠터
│   ├── main_presenter.py               # 메인 프레젠터
│   ├── manual_control_presenter.py     # 수동 제어 프레젠터
│   ├── packet_presenter.py             # 패킷 프레젠터
│   └── port_presenter.py               # 포트 프레젠터
│
├── view/                               # UI 계층
│   ├── main_window.py                  # 메인 윈도우
│   │
│   ├── managers/                       # 관리자 계층
│   │   ├── color_manager.py            # 로그 색상 규칙
│   │   ├── language_manager.py         # 다국어 관리
│   │   └── theme_manager.py            # 테마 관리
│   │
│   ├── custom_qt/                      # PyQt5 커스텀 위젯
│   │   ├── smart_number_edit.py        # 스마트 숫자 편집 위젯
│   │   ├── smart_list_view.py          # 스마트 리스트 뷰 위젯
│   │   └── smart_plain_text_edit.py    # 스마트 plain 텍스트 편집 위젯
│   │
│   ├── sections/                       # 섹션 (대 분할)
│   │   ├── main_left_section.py        # 메인 왼쪽 섹션
│   │   ├── main_menu_bar.py            # 메인 메뉴 바
│   │   ├── main_right_section.py       # 메인 오른쪽 섹션
│   │   ├── main_status_bar.py          # 메인 상태 바
│   │   └── main_tool_bar.py            # 메인 도구 바
│   │
│   ├── panels/                         # 패널 (중 단위)
│   │   ├── macro_panel.py              # 매크로 패널
│   │   ├── manual_control_panel.py     # 수동 제어 패널
│   │   ├── packet_inspector_panel.py   # 패킷 인스펙터 패널
│   │   ├── port_panel.py               # 포트 패널
│   │   └── port_tab_panel.py           # 포트 탭 패널
│   │
│   ├── widgets/                        # 위젯 (소 단위)
│   │   ├── data_log.py                 # 수신 로그 위젯
│   │   ├── file_progress.py            # 파일 진행률 위젯
│   │   ├── macro_control.py            #
│   │   ├── macro_list.py               # 매크로 리스트 위젯
│   │   ├── manual_control.py           # 수동 제어 위젯
│   │   ├── packet_inspector.py         # 패킷 인스펙터 위젯
│   │   ├── port_settings.py            # 포트 설정 위젯
│   │   ├── port_stats.py               # 포트 통계 위젯
│   │   └── system_log.py               # 시스템 로그 위젯
│   │
│   └── dialogs/                        # 대화상자
│       ├── about_dialog.py             # 정보 대화상자
│       ├── file_transfer_dialog.py     # 파일 전송 대화상자
│       ├── font_settings_dialog.py     # 폰트 설정 대화상자
│       └── preferences_dialog.py       # 설정 대화상자
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

#### [진행 필요] `core/utils.py`

**RingBuffer 구현**

- 크기: 512KB (설정 가능)
- 고속 데이터 수신 처리
- 오버플로우 시 오래된 데이터를 덮어쓰며, `memoryview`를 사용하여 복사를 최소화합니다.
- 고속 데이터 수신 처리 및 스레드 안전성 보장.

**ThreadSafeQueue 구현**

- TX 큐 관리 (최대 128 chunks)
- `collections.deque` 기반
- Lock-free 또는 최소 Lock 전략
- 우선순위 큐 지원 (선택)
- memoryview

#### [진행 필요] `core/event_bus.py`

**EventBus 아키텍처**

- **기능**: 컴포넌트 간 결합도를 낮추기 위한 Pub/Sub 시스템.
- Publish/Subscribe 패턴
- 표준 이벤트 타입 정의
  - `PORT_OPENED`, `PORT_CLOSED`, `DATA_RECEIVED`, `DATA_SENT`
  - `MACRO_STARTED`, `MACRO_COMPLETED`, `MACRO_FAILED`
  - `FILE_TRANSFER_STARTED`, `FILE_TRANSFER_PROGRESS`, `FILE_TRANSFER_COMPLETED`
- 플러그인 연동 인터페이스
- 이벤트 필터링 및 우선순위
- PyQt Signal/Slot을 활용한 스레드 안전한 이벤트 디스패치.

#### [진행 필요] `core/logger.py`

**로깅 계층 (Logging Layers)**

- **UI Log**: `QSmartListView` (메모리), 실시간 표시
- **File Log**: `RotatingFileHandler` (10MB x 5개), `logs/app_YYYY-MM-DD.log`
- **Performance Log**: CSV 형식 (`logs/perf_YYYY-MM-DD.csv`), 지표(Rx/Tx 속도, 버퍼 점유율)

#### [진행 필요] `core/plugin_base.py` & `core/plugin_loader.py`

**플러그인 시스템 (Plugin System)**

- **Interface**: `PluginBase` (name, version, register, unregister)
- **Loader**: `importlib` 기반 동적 로딩 (`plugins/` 디렉토리 스캔)
- **EventBus Integration**: `register(bus, context)` 필수 구현

#### [진행 예정] `core/error_handler.py`

**전역 에러 핸들러 (Global Error Handler)**

- **기능**: 처리되지 않은 예외(Uncaught Exception) 포착 및 로깅
- **구현**: `sys.excepthook` 오버라이딩
- **UI 연동**: 치명적 오류 시 `QMessageBox`로 사용자 알림 및 로그 파일 위치 안내
- **안전 모드**: 반복적인 크래시 발생 시 설정 초기화 또는 안전 모드 진입 제안

---

### 3. Model 계층 (Model Layer) - Domain Logic

#### [완료] `model/transports.py`

**통신 추상화 및 Worker 구현**

- **ITransport**: 통신 인터페이스 정의 (`open`, `close`, `read`, `write`)
- **SerialTransport**: PySerial을 래핑하여 ITransport 구현

#### [완료] `model/connection_worker.py`

- **ConnectionWorker**:
- **Non-blocking I/O**: `timeout=0` + 반복 읽기 최적화
- **RingBuffer Integration**: 고속 송/수신 데이터 버퍼링
- **Signals**: `rx_data(bytes)`, `tx_complete(int)`, `port_error(str)`, `data_received`, `error_occurred`, `connection_opened/closed`
- `ITransport`를 주입받아 하드웨어 독립적인 I/O 루프 수행.
- Controller로부터 Transport 객체를 주입받아 동작 (Dependency Injection)

**성능 목표**

- 수신 처리량: 2MB/s
- TX 큐 지연: 10ms 이하
- CPU 사용률: 단일 포트 기준 5% 이하

#### [완료] `model/port_controller.py`

**포트 라이프사이클 관리**

- **역할**: `SerialTransport`와 `ConnectionWorker`의 생명주기 관리
- **EventBus 통합**: 수신된 데이터를 직접 시그널로 보내는 대신, `EventBus`에 `port.rx_data` 이벤트를 발행하여 디커플링
- 상태 머신: `DISCONNECTED` ↔ `CONNECTING` ↔ `CONNECTED` ↔ `ERROR`
- 역할: Worker 스레드 관리 및 Transport 객체 생성/주입
- 설정 변경 처리 (baudrate, parity 등)
- 에러 복구 정책
  - 자동 재연결 (설정)
  - 에러 로그 기록

**멀티포트 격리**

- 포트별 독립 RingBuffer
- 포트별 독립 TX 큐
- 포트별 독립 Worker 스레드

#### [완료] `model/serial_manager.py`

**PortRegistry 구현 (싱글톤)**

- **역할**: 애플리케이션 전체의 `PortController` 인스턴스를 관리하는 중앙 레지스트리
- **기능**:
  - `get_port(port_name) -> PortController`: 포트 컨트롤러 조회 또는 생성
  - `get_all_ports() -> List[PortController]`: 활성 포트 목록 반환
  - `close_all_ports()`: 애플리케이션 종료 시 모든 포트 정리
  - `active_ports` 속성: 현재 열려있는 포트 이름 목록 관리

#### [진행 예정] `model/packet_parser.py` (보완)

**패킷 파서 시스템**

- **IPacketParser**: 파싱 인터페이스 (`parse(buffer) -> List[Packet]`)
- **Implementations**:
  - `ATParser`: `\r\n` 구분 및 OK/ERROR 응답 처리
  - `RawParser`: 바이너리 데이터를 그대로 패스
  - `DelimiterParser`: 사용자 정의 구분자(예: STX/ETX, Comma) 처리
  - `FixedLengthParser`: 고정 길이 패킷 처리
- **ParserFactory**: 설정(`AT`, `Hex` 등)에 따라 적절한 파서 인스턴스 생성 (전략 패턴)
- **ExpectMatcher**: 정규식 기반 응답 대기 및 매칭 기능 구현
- **PortController 통합**: Raw Data 수신 시 Parser를 거쳐 Packet 객체로 변환 후 EventBus 발행

#### [완료] `model/macro_runner.py`

**매크로 실행 엔진**

- **구조**: 매크로 실행을 담당하는 **상태 머신** (QObject).
- **State Machine**: `Idle` → `Running` → `Paused` → `Stopped`
- **Step Execution**: Send → Expect Match (Regex) → Delay → Next/Jump/Repeat
- **Auto Run**: `AutoTxScheduler` (Global Interval + Loop Count)
- **Signals**: `step_started`, `step_completed`, `macro_finished`, `error_occurred`
- **기능**:
  - `load_macro(entries)`: 매크로 리스트 로드
  - `start()`: 실행 시작
  - `stop()`: 실행 중지
  - `pause()` / `resume()`: 일시 정지 및 재개
  - `set_interval(ms)`: 반복 간격 설정

#### [완료] `model/macro_entry.py`

**MacroEntry DTO**

```python
@dataclass
  class MacroEntry:
      enabled: bool
      command: str
      is_hex: bool
      prefix: bool
      suffix: bool
      delay_ms: int
      expect: str = ""
      timeout_ms: int = 5000
```

**JSON 직렬화**

- 스크립트 저장/로드
- 검증 규칙 (필수 필드, 타입 체크)

#### [진행 예정] `model/file_transfer.py`

**FileTransferEngine(QRunnable)**

- **구조**: `QRunnable`을 상속받아 별도 스레드 풀에서 실행
- **Chunk 기반 전송**: 기본 1KB ~ 4KB (Baudrate에 따라 적응형 조절 가능)
- **진행률 계산**: 전송된 바이트 / 전체 바이트
- **취소 메커니즘**: `cancel()` 플래그 체크
- **재시도 정책**: 전송 실패 시 최대 3회 재시도
- **EventBus 연동**: `file.progress`, `file.completed`, `file.error` 이벤트 발행

**시그널**

- `progress_updated(int, int)`: 현재/전체 바이트
- `transfer_completed(bool)`: 성공 여부
- `error_occurred(str)`: 에러 메시지

---

### 4. Presenter 계층 (Presenter Layer)

#### [진행 필요] `presenter/main_presenter.py`

**중앙 제어 로직**

- 애플리케이션 초기화
  - SettingsManager 로드
  - EventBus 초기화
  - 플러그인 로드
- View ↔ Model 연결
- 종료 시퀀스
  - 모든 포트 닫기
  - 설정 저장
  - 스레드 정리

#### [진행 필요] `presenter/port_presenter.py`

**포트 제어**

- `PortSettingsWidget` <-> `PortController` 연결
- 포트 열기/닫기
  - View 시그널 수신 (`port_open_requested`)
  - 상태 업데이트 (`port_opened`, `port_closed`)
- 설정 변경 처리
  - baudrate, parity 등 변경 시 포트 재시작
- 데이터 송수신
  - View → Model: TX 데이터 전달
  - Model → View: RX 데이터 표시
- 연결 상태 변화에 따라 UI 업데이트

#### [진행 필요] `presenter/macro_presenter.py`

**Macro List 제어**

- `MacroPanel` <-> `MacroRunner` 연결
- 스크립트 저장/로드
  - JSON 파일 I/O
  - MacroEntry 직렬화/역직렬화
- Run/Stop/Pause 로직
  - MacroRunner 제어
  - 실행 상태 UI 업데이트
  - QTimer 기반 주기 실행
  - 최대 실행 횟수 체크

#### [진행 필요] `presenter/file_presenter.py`

**파일 전송 제어**

- `ManualCtrlWidget`(파일 탭) <-> `FileTransferEngine` 연결
- 파일 선택 처리
- FileTransferEngine 시작
- 진행률 업데이트
  - ProgressBar 업데이트
  - 전송 속도 계산 (KB/s)
- 취소 처리
  - Engine 중단
  - UI 정리

#### [진행 필요] `presenter/event_router.py`

**EventRouter (View-Model Decoupling)**

- **Role**: View 이벤트를 Domain 메서드로 라우팅, Domain 시그널을 View 업데이트로 변환
- **Benefit**: View와 Model 간의 직접 의존성 제거 (MVP 준수)

---

### 5. Performance Strategy (성능 최적화 전략)

#### 1. Tx/Rx Data Pipeline

- **RingBuffer**: 메모리 할당 최소화 (O(1))
- **Non-blocking I/O**: `serial.read()` 타임아웃 0ms 설정 및 루프 최적화

#### 2. UI Rendering (RxLogView)

- **Batch Renderer**: 50ms 주기로 로그 묶어서 업데이트 (`appendHtml` 호출 횟수 감소)
- **Virtual Scrolling**: 대량 로그(10K+ 라인) 표시 시 렌더링 부하 분산
- **Trim Policy**: 2000라인 초과 시 상단 제거 (메모리 관리)

#### 3. Threading Model

- **SerialWorker**: 포트별 독립 QThread (I/O 격리)
- **FileTransfer**: `QRunnable` + `QThreadPool` (UI 스레드 영향 최소화)
- **Lock-free Queue**: `collections.deque` 활용 (GIL 의존)

---

### 6. View 계층 (View Layer) - ✅ 완료

#### [완료] UI 구조

- `MainWindow`: 메인 레이아웃, 메뉴, 툴바, 스플리터 관리
- `MainLeftSection`: 포트 탭 + 수동 제어 (화면 좌측)
- `MainRightSection`: 매크로 리스트 + 패킷 인스펙터 (화면 우측)
- `Panels`: 기능 단위 그룹 (PortPanel, MacroPanel, ManualControlPanel 등)
- `Sections`: 화면 분할 (MainMenuBar, MainStatusBar 포함)

#### [완료] 위젯

- `PortSettingsWidget`: 컴팩트 2줄 레이아웃, 연결 상태 관리
- `RxLogWidget`: 로그 뷰, 색상 규칙, 타임스탬프, Trim, 검색
- `ManualControlWidget`: 수동 전송, 파일 선택, Prefix/Suffix
- `MacroListWidget`: Prefix/Suffix, 3단계 체크박스, 행별 Send 버튼
- `MacroCtrlWidget`: 스크립트 저장/로드, Repeat 실행
- `PacketInspectorWidget`: 패킷 상세 뷰
- `StatusWidget`: RX/TX 통계, 에러 카운트, 업타임
- `StatusAreaWidget`: 상태 로그 표시
- `FileProgressWidget`: 파일 전송 진행률
- `MainToolBar`: 빠른 액션 버튼 (Open, Close, Clear, Save, Settings)
- `SmartNumberEdit`: HEX 모드 입력 필드 (자동 대문자 변환)

#### [완료] 테마 시스템

- `ThemeManager`: QSS 로딩 및 동적 전환
- `common.qss`: 공통 스타일
- `dark_theme.qss`, `light_theme.qss`: 개별 테마
- SVG 아이콘 시스템 (테마별 색상 자동 변경)
- 테마별 아이콘 로딩 (`get_icon()` 메서드)

#### [완료] 듀얼 폰트 시스템

**목적**: UI 가독성 향상을 위한 폰트 분리

**Proportional Font (가변폭 폰트)**

- 적용 대상: 메뉴, 툴바, 상태바, 레이블, 버튼, 그룹박스, 탭 등
- 기본 폰트: "Segoe UI" (Windows), "Ubuntu" (Linux)
- 크기: 9pt (기본), 설정 가능
- 특징: 자연스러운 텍스트 표시, UI 요소에 최적화

**Fixed Font (고정폭 폰트)**

- 적용 대상: TextEdit, LineEdit, MacroList의 Command 컬럼, 패킷 인스펙터
- 기본 폰트: "Consolas" (Windows), "Monospace" (Linux)
- 크기: 9pt (기본), 설정 가능
- 특징: 정렬된 텍스트 표시, 코드/데이터 가독성 향상

#### [완료] 다국어 지원

- `LanguageManager`: 한국어/영어 실시간 전환
- CommentJSON 기반 번역 파일 (`config/languages/ko.json`, `en.json`)
- `text_matches_key()` 헬퍼: 언어 확장성 개선
- 모든 UI 컴포넌트 다국어 적용 완료

#### [완료] MVP 패턴 준수

- View 계층에서 Model 직접 접근 제거
- Signal 기반 통신 (View → Presenter)
- 명확한 책임 분리: View는 UI만, Presenter는 로직 처리

#### [완료] Packet Inspector 설정 UI 구현

- **위치**: `view/dialogs/preferences_dialog.py` 내부에 새로운 탭으로 구현
- **필수 요소**:
  - 파서 타입 선택 (AT Command, Delimiter, Fixed Length)
  - Delimiter 문자열 입력 필드
  - Fixed Length 숫자 입력 필드
  - AT Color Rules 설정 체크박스 및 색상 규칙 편집 버튼
  - Inspector Options (버퍼 크기 설정, 실시간 추적 활성화)
- **Task**: `PreferencesDialog`의 `create_parser_tab` 메서드 구현

#### [완료] Port Connect 버튼 QSS 보완

- **위치**: `resources/themes/*.qss`
- **필수 요소**:
  - `QPushButton[state="error"]` 속성에 대한 스타일 정의 (배경색, 글꼴 색상 등)
  - 포트 연결 실패 시 사용자에게 명확한 시각적 피드백 제공 (예: 배경색을 빨간색 계열로 변경)
- **Task**: 다크/라이트 테마 QSS 파일에 `error` 상태 스타일 추가

#### [완료] Main Status Bar 동적 업데이트 통합

- **위치**: `view/sections/main_status_bar.py`
- **필수 요소**:
  - RX/TX 속도, 버퍼 사용량, 현재 시간, 전역 에러 카운트 표시를 위한 View 통합 로직 구현
- **Task**: `MainPresenter`와 `PortPresenter`에서 발행하는 EventBus 데이터를 받아와 상태바 위젯을 갱신하는 슬롯 메서드 구현

#### [완료] 전역 단축키 시스템 (Global Shortcuts)

- **목표**: 키보드 중심의 빠른 제어 지원
- **단축키 목록**:
  - `F2`: 포트 연결 (Open)
  - `F3`: 포트 연결 해제 (Close)
  - `F5`: 수신 로그 지우기 (Clear)
  - `Ctrl+S`: 로그 저장
  - `Ctrl+,`: 설정 다이얼로그
- **구현**: `MainWindow`의 `keyPressEvent` 또는 `QShortcut` 활용

---

### 7. 플러그인 시스템 (Plugin System)

#### [진행 필요] `core/plugin_base.py`

**PluginBase 인터페이스**

```python
  class PluginBase(ABC):
      @abstractmethod
      def register(self, app_context: AppContext) -> None:
          pass

      @abstractmethod
      def unregister(self) -> None:
          pass
```

**AppContext**

- EventBus 접근
- SettingsManager 접근
- UI 확장 API (메뉴, 패널 추가)

#### [진행 필요] `core/plugin_loader.py`

**동적 로딩**

- `plugins/` 디렉터리 스캔
- 부팅 시 자동 로드
- 핫 리로딩 지원
- 예외 격리 (플러그인 에러 시 앱 중단 방지)

#### [진행 필요] `plugins/example_plugin/`

**샘플 플러그인**

- EventBus 연동 예제
- UI 확장 예제 (메뉴 추가)
- 설정 관리 예제

---

## 검증 계획 (Verification Plan)

### 자동화 테스트

#### 단위 테스트 (Unit Tests)

**Core 모듈**

- `test_ringbuffer.py`: 오버플로우, 스레드 안전성
- `test_queue.py`: TX 큐 동작, 우선순위
- `test_event_bus.py`: Pub/Sub, 필터링
- `test_settings_manager.py`: 저장/로드, 마이그레이션

**Model 모듈**

- `test_packet_parser.py`: 각 파서 동작, Expect/Timeout
- `test_macro_runner.py`: 순차 실행, 반복, 에러 처리
- `test_file_transfer.py`: Chunk 전송, 취소, 재시도

**목표 커버리지**: 70%+

#### 통합 테스트 (Integration Tests)

**Virtual Serial Port 환경**

- Windows: com0com
- Linux: socat

**테스트 시나리오**

1. 포트 열기/닫기 시퀀스
2. 데이터 송수신 루프백 (1Mbps, 10분)
3. 멀티포트 동시성 (4개 포트)
4. Macro List 실행 (10개 명령, 5회 반복)
5. 파일 전송 (10MB 파일, 115200bps)

#### E2E 테스트 (pytest-qt)

**UI 워크플로우**

1. 앱 시작 → 포트 선택 → 열기
2. 수동 명령 송신 → 로그 확인
3. Macro List 로드 → 실행 → 결과 확인
4. 파일 전송 → 진행률 확인 → 완료
5. 설정 변경 → 저장 → 재시작 → 복원 확인

#### 성능 벤치마크

**측정 지표**

- Rx 처리량: 2MB/s 목표 (pytest-benchmark)
- UI 렌더링: 10K lines/s (QTextEdit 업데이트)
- 패킷 파서 지연: 1ms 이하 (1KB 패킷)
- 파일 전송 속도: 100KB/s+ (115200bps)

**도구**

- `pytest-benchmark`
- `cProfile` + `SnakeViz`
- `tracemalloc` (메모리 프로파일)

---

### 수동 검증

#### UI/UX 검증

- [ ] 버튼 활성/비활성 상태 확인
- [ ] 탭 동작 (추가, 닫기, 전환)
- [ ] 툴팁 및 단축키 확인
- [ ] 테마 전환 (Dark ↔ Light)
- [ ] 폰트 변경 확인
- [ ] 레이아웃 리사이징

#### 기능 검증

- [ ] 실제 장비 연결 후 데이터 송수신
- [ ] Macro List 자동 실행 (AT 명령)
- [ ] 파일 전송 (펌웨어 다운로드)
- [ ] 설정 저장/복원
- [ ] 로그 내보내기

#### 장기 런 테스트

- [ ] 24시간 연속 실행 (Auto Run)
- [ ] 메모리 누수 체크 (Windows Task Manager)
- [ ] CPU 사용률 모니터링
- [ ] 로그 파일 크기 확인 (Rotation 동작)

#### 플랫폼별 검증

- [ ] Windows 10/11 (x64)
- [ ] Ubuntu 20.04+ (x64)
- [ ] Debian 11+ (x64)
- [ ] macOS 12.0+ (선택)

---

## 배포 계획 (Deployment Plan)

### PyInstaller 빌드

#### Windows

```bash
pyinstaller --onefile --windowed \
  --name SerialTool \
  --icon resources/icons/app_icon.ico \
  --add-data "resources;resources" \
  --add-data "config;config" \
  main.py
```

**결과물**

- `dist/SerialTool.exe` (단일 실행 파일)
- 크기 목표: 50MB 이하

#### Linux

```bash
pyinstaller --onefile \
  --name SerialTool \
  --add-data "resources:resources" \
  --add-data "config:config" \
  main.py
```

**AppImage 생성**

- `appimagetool` 사용
- 결과물: `SerialTool-x86_64.AppImage`

### 배포 아티팩트 구성

```
serial_tool_v1.0.0/
├── SerialTool.exe (Windows) / AppImage (Linux)
├── config/
│   ├── default_settings.json
│   └── color_rules.json
├── plugins/
│   └── example_plugin/
├── README.md
├── CHANGELOG.md
├── LICENSE
└── docs/
    └── UserManual.pdf (or .md)
```

### CI/CD 파이프라인 (GitHub Actions)

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest
      - run: pyinstaller pyinstaller.spec
      - uses: actions/upload-artifact@v3
        with:
          name: SerialTool-Windows
          path: dist/SerialTool.exe

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest
      - run: pyinstaller pyinstaller.spec
      - run: appimagetool dist/SerialTool
      - uses: actions/upload-artifact@v3
        with:
          name: SerialTool-Linux
          path: SerialTool-x86_64.AppImage

  release:
    needs: [build-windows, build-linux]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v3
      - uses: softprops/action-gh-release@v1
        with:
          files: |
            SerialTool-Windows/SerialTool.exe
            SerialTool-Linux/SerialTool-x86_64.AppImage
```

---

## 구현 순서 (Implementation Order)

### Phase 1 & 2: Project Setup & UI (In Progress)

**View 보완**: Packet Inspector 설정 UI 및 Port 버튼 QSS 통합

### Phase 3: Core Utilities (In Progress)

1. `core/utils.py`: RingBuffer, ThreadSafeQueue
2. `core/event_bus.py`: EventBus, EventTypes
3. `core/logger.py`: LogManager, RotatingFileHandler
4. `core/plugin_base.py`: Plugin Interface

### Phase 4: Model Layer (Planned)

1. `model/serial_worker.py`: SerialWorker (Non-blocking I/O)
2. `model/port_controller.py`: PortController (State Machine)
3. `model/serial_manager.py`: PortRegistry
4. `model/packet_parser.py`: ParserFactory, ExpectMatcher
5. `presenter/event_router.py`: EventRouter

### Phase 5: Presenter Layer (Planned)

1. `presenter/port_presenter.py`: Port Control Logic
2. `presenter/main_presenter.py`: App Lifecycle
3. `presenter/macro_presenter.py`: Macro Logic
4. `presenter/file_presenter.py`: File Transfer Logic

### Phase 6: Automation & File I/O (Planned)

1. `model/macro_runner.py`: Macro Engine, Auto Run
2. `model/file_transfer.py`: FileTransferEngine, RxCaptureWriter
3. `model/auto_tx.py`: AutoTxScheduler
4. **Performance Optimization**: BatchRenderer, RingBuffer Tuning

### Phase 7: Plugin System (Planned)

1. `core/plugin_loader.py`: Dynamic Loading
2. `plugins/example_plugin.py`: Reference Implementation
3. Plugin Management UI

### Phase 8: Verification & Deployment (Planned)

1. Virtual Serial Port Setup (com0com/socat)
2. Unit/Integration Tests
3. Performance Benchmarks
4. PyInstaller Build & CI/CD

**총 예상 기간**: 12주 (약 3개월)

---

## 현재 상태 및 다음 단계

### 완료된 작업 (2025-12-11 기준)

- ✅ **프로젝트 구조**: 폴더 구조, 문서, 설정 파일

### Phase 2: UI 구현 및 테마 시스템 (✅ 완료)

- [x] UI 기본 골격 구현
- [x] 위젯 구현 및 리팩토링
- [x] 테마 및 스타일링 시스템
- [x] 듀얼 폰트 시스템 구현
- [x] 디렉토리 구조 재정리
- [x] 코드 품질 개선
- [x] 견고성 개선
- [x] View 계층 보완 (Spec 10, 11, 17)
- [x] View 계층 마무리 및 다국어 지원 (Phase 1)
- [x] View 계층 위젯 다국어 적용 (Phase 2)
  - [x] LanguageManager 개선 (Fallback 로직)
  - [x] MainWindow "Tools" 메뉴 수정
  - [x] ManualControlWidget 다국어 적용
  - [x] ReceivedArea 다국어 적용
  - [x] MacroListWidget 다국어 적용
  - [x] MacroCtrlWidget 다국어 적용
  - [x] FileProgressWidget 다국어 적용
  - [x] PacketInspectorWidget 다국어 적용
  - [x] MainWindow 다국어 적용 (메뉴, 타이틀)
  - [x] LeftPanel/RightPanel 다국어 적용 (탭)
  - [x] PortSettingsWidget 다국어 적용
  - [x] StatusArea 다국어 적용
  - [x] FontSettingsDialog 다국어 적용
- [x] Macro List Persistence (자동 저장)
- [x] Refactoring & Stabilization
  - [x] UI Architecture Refactoring (Sections/Panels/Widgets)
  - [x] Language Key Standardization (`[context]_[type]_[name]`)
  - [x] Code Style Guide Update
  - [x] Preferences Dialog Implementation & Fix
  - [x] Documentation Updates (CHANGELOG, Session Summary)
  - [x] Path Management Refactoring (`ResourcePath` class)
  - [x] Color Manager Improvements (System Log, Timestamp Rules)
  - [x] Local Echo Implementation

### Phase 2.5: UI 기능 보완 (✅ 완료)

- [x] **송신(TX) 기능 보완**
  - [x] Local Echo 구현 (송신 데이터를 RX 창에 표시)
  - [x] Command Prefix/Suffix 설정 및 적용
  - [x] ManualCtrl UI 정리 (중복 버튼 제거)
- [x] **수신(RX) 기능 보완**
  - [x] Newline 처리 옵션 (Raw, LF, CR, CRLF) 콤보박스 추가 및 로직 구현
  - [x] 로그 저장 기능 개선 (토글 방식, 파일명 포맷팅)
- [x] **Packet Inspector 설정 UI 구현**
  - [x] `PreferencesDialog`에 Packet 탭 추가
  - [x] Parser Type, Delimiter, Fixed Length, AT Color Rules 설정 UI 구현
- [x] **UI 스타일링 및 피드백 강화**
  - [x] Port Connect 버튼 Error 상태 QSS 추가 (테마 파일 확인 완료)
- [x] **Main StatusBar 동적 업데이트 연동**
  - [x] RX/TX 속도, 버퍼 상태, 에러 카운트 표시 구현
  - [x] `PortController` -> `MainPresenter` -> `MainStatusBar` 데이터 흐름 연결
- [x] **사용성 개선**
  - [x] 전역 단축키 시스템 구현 (F2: Connect, F3: Disconnect, F5: Clear)
  - [x] MacroList 컨텍스트 메뉴 추가
  - [x] ManualCtrl 히스토리 기능 추가

### Phase 3: Core 유틸리티 (✅ 완료)

- [x] `SettingsManager` 구현 (싱글톤, AppConfig 통합)
- [x] `AppConfig` 구현 (중앙 경로 관리)
- [x] `PortState` Enum 정의
- [x] `ITransport` 인터페이스 정의
- [x] `RingBuffer` 구현 (512KB, memoryview 최적화)
- [x] `ThreadSafeQueue` 구현 (Lock-free 전략)
- [x] `EventBus` 구현 (Pub/Sub 시스템)
- [x] `LogManager` 구현 (RotatingFileHandler)

### Phase 4: Model 계층 (진행 중)

- [x] `SerialTransport` 구현
- [x] `ConnectionWorker` 구현 (Non-blocking I/O)
- [x] `PortController` 구현 (상태 머신, 멀티포트 지원)
- [ ] `SerialManager` (PortRegistry) 구현
- [ ] `MacroRunner` 구현
- [ ] `PacketParser` 시스템 구현

### 다음 단계 (우선순위)

1. **Model 계층 완성** (Phase 4)
   - `SerialManager` (PortRegistry) 구현
   - `MacroRunner` 구현
   - `PacketParser` 시스템 구현
2. **Presenter 연동** (Phase 5)
   - `PortPresenter` 구현
   - `MacroPresenter` 구현
   - `FilePresenter` 구현
   - View ↔ Model 연결
   - 실제 포트 송수신 확인
3. **자동화 및 고급 기능** (Phase 6)
   - `MacroRunner` 연동
   - `FileTransferEngine` 구현

---

## 리스크 및 대응 방안

### 기술적 리스크

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|-----------|
| 고속 데이터 처리 시 UI 프리징 | 높음 | RingBuffer + Batch Rendering, Worker Thread 격리 |
| 멀티포트 동시성 이슈 | 중간 | 포트별 독립 스레드, Lock-free 큐 사용 |
| PyInstaller 빌드 크기 과다 | 낮음 | UPX 압축, 불필요한 모듈 제외 |
| 플랫폼별 포트 스캔 차이 | 중간 | OS별 분기 처리, 충분한 테스트 |

### 일정 리스크

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|-----------|
| Core 유틸리티 구현 지연 | 높음 | 우선순위 집중, 단순화 |
| 테스트 환경 구축 어려움 | 중간 | Virtual Serial Port 사전 준비 |
| 플러그인 시스템 복잡도 | 낮음 | v1.1로 연기 가능 |

---

## 성공 기준 (Success Criteria)

### 기능적 성공 기준

- [ ] 16개 포트 동시 오픈 및 독립 제어
- [ ] 2MB/s 연속 스트림 안정 처리
- [ ] Macro List 자동 실행 (반복, 지연, Expect)
- [ ] 파일 전송 (10MB+, 진행률 표시)
- [ ] 설정 저장/복원 (포트, UI, 명령 리스트)
- [ ] 플러그인 로드 및 실행

### 비기능적 성공 기준

- [ ] UI 반응성: 60fps 스크롤, Freeze 0
- [ ] 단위 테스트 커버리지: 70%+
- [ ] 통합 테스트: 주요 시나리오 100% 통과
- [ ] 장기 런 안정성: 24시간 무중단 실행
- [ ] 배포 패키지 크기: 50MB 이하 (Windows)

### 사용자 경험 성공 기준

- [ ] 3-Click Rule 준수 (주요 작업 3번 클릭 이내)
- [ ] 직관적인 UI (툴팁, 단축키, 상태 표시)
- [ ] 에러 메시지 명확성 (원인 및 해결 방법 제시)
- [ ] 문서 완성도 (사용자 가이드, API 레퍼런스)

---

**문서 버전**: v1.0
**최종 업데이트**: 2025-12-09
