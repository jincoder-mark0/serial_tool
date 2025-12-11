# 작업 목록 (Task List)

## Phase 1: 프로젝트 설정 (완료)
- [x] 프로젝트 디렉토리 구조 생성
- [x] Git 저장소 초기화
- [x] 가상 환경 생성
- [x] 의존성 설치 (PyQt5)
- [x] README.md 생성
- [x] .gitignore 생성

## Phase 2: UI 구현 및 테마 시스템 (완료)
- [x] 메인 윈도우 레이아웃 구현
    - [x] `MainWindow` 클래스 생성
    - [x] `LeftSection` 구현 (포트/제어)
    - [x] `RightSection` 구현 (커맨드/인스펙터)
- [x] 위젯 구현
    - [x] `PortSettingsWidget` (포트 설정)
    - [x] `ReceivedArea` (로그 뷰)
    - [x] `ManualControlWidget` (수동 제어)
    - [x] `MacroListWidget` (커맨드 리스트)
    - [x] `MacroCtrlWidget` (커맨드 제어)
    - [x] `PacketInspectorWidget` (패킷 인스펙터)
    - [x] `FileProgressWidget` (파일 전송 진행)
- [x] 테마 시스템 구현
    - [x] `ThemeManager` 생성
    - [x] `common.qss` 생성
    - [x] `dark_theme.qss` 생성
    - [x] `light_theme.qss` 생성
    - [x] SVG 아이콘 시스템 구현
- [x] 듀얼 폰트 시스템 구현
    - [x] `ThemeManager` 폰트 처리 업데이트
    - [x] `FontSettingsDialog` 생성
    - [x] 위젯에 폰트 적용
- [x] 디렉토리 구조 리팩토링
    - [x] 위젯을 `view/widgets`로 이동
    - [x] 패널을 `view/panels`로 이동
    - [x] 다이얼로그를 `view/dialogs`로 이동
    - [x] 좌/우 섹션을 위한 `view/sections` 생성
- [x] 다국어 지원 (Localization)
    - [x] `LanguageManager` 생성
    - [x] `en.json` 및 `ko.json` 생성
    - [x] `ManualControlWidget`에 적용
    - [x] `ReceivedArea`에 적용
    - [x] `MacroListWidget`에 적용
    - [x] `MacroCtrlWidget`에 적용
    - [x] `FileProgressWidget`에 적용
    - [x] `PacketInspectorWidget`에 적용
    - [x] `MainWindow`에 적용 (메뉴, 독 타이틀)
    - [x] `LeftSection` & `RightSection`에 적용 (탭)
    - [x] `PortSettingsWidget`에 적용
    - [x] `StatusArea`에 적용
    - [x] `FontSettingsDialog`에 적용
    - [x] `PreferencesDialog`에 적용

- [x] 리팩토링 및 안정화
    - [x] 언어 키 표준화 (`[context]_[type]_[name]`)
    - [x] 코드 스타일 가이드 업데이트 (명명 규칙)
    - [x] Preferences Dialog 접근성 수정
    - [x] Preferences Dialog 로직 구현
    - [x] Command → Macro 네이밍 리팩토링
    - [x] MVP 패턴 준수 강화 (PreferencesDialog)
    - [x] 언어 키 완성 (MainToolBar, MainMenuBar)
    - [x] TODO 주석 정리 (Note로 변경)
    - [x] 테마 메뉴 체크 표시 추가
    - [x] 우측 패널 토글 개선 (왼쪽 패널 크기 유지)
    - [x] QSS warning 클래스 추가
    - [x] ReceivedArea max_lines 동적 설정
    - [x] PortState Enum 및 QSS 통합
    - [x] Parser 탭 UI 구현 (PreferencesDialog)
    - [x] 중앙 집중식 경로 관리 (AppConfig)
    - [x] __init__.py 생성으로 import 간결화
    - [x] 네이밍 일관성 개선
    - [x] View 계층 MVP 리팩토링 (SettingsManager 의존성 제거)

## Phase 2.5: UI 기능 보완 (진행 예정)
- [ ] **송신(TX) 기능 보완**
    - [ ] Local Echo (로컬 에코) 옵션 구현
        - [ ] `ManualCtrlWidget`에 체크박스 추가
        - [ ] 전송된 데이터를 `ReceivedArea`에 표시하는 로직 구현
- [ ] **수신(RX) 기능 보완**
    - [ ] Newline 처리 옵션
        - [ ] 수신 데이터의 줄바꿈 처리 방식 설정 (Raw, Auto Wrap 등)


## Phase 3: Core 유틸리티 (진행 중)
- [x] `SettingsManager` 구현 (싱글톤, AppConfig 통합)
- [x] `AppConfig` 구현 (중앙 경로 관리)
- [x] `PortState` Enum 정의
- [x] `ITransport` 인터페이스 정의 (`core/interfaces.py`)
- [ ] `RingBuffer` 구현
    - [ ] `core/utils.py` 생성
    - [ ] 원형 버퍼 로직 구현
    - [ ] 스레드 안전성 구현
    - [ ] 오버플로우 처리
- [ ] `ThreadSafeQueue` 구현
    - [ ] `core/utils.py`에 추가
    - [ ] 블로킹/논블로킹 큐 구현
- [ ] `EventBus` 구현
    - [ ] `core/event_bus.py` 생성
    - [ ] Pub/Sub 패턴 구현
    - [ ] 표준 이벤트 타입 정의 (`core/event_types.py`)
- [ ] `LogManager` 구현
    - [ ] `core/logger.py` 생성
    - [ ] `RotatingFileHandler` 구현 (10MB 제한)
    - [ ] 성능 로거 구현 (CSV 내보내기)
- [x] `SettingsManager` 구현 (싱글톤)
    - [x] AppConfig 통합
- [x] `PortState` Enum 정의 및 PortSettingsWidget에 적용
- [x] `AppConfig` 구현 (중앙 경로 관리)

## Phase 4: Model 계층 (진행 중)
- [x] `SerialTransport` 구현 (`model/transports.py`)
- [x] `ConnectionWorker` 구현 (Transport 주입, QThread 루프)
    - [x] `ITransport` 주입 구조 적용
    - [x] QThread 기반 Loop 구현
- [ ] `PortController` 구현
    - [x] Transport 생성 및 Worker 주입 로직 구현
    - [ ] `model/port_controller.py` 생성
    - [ ] 상태 머신 구현
- [ ] `SerialManager` (PortRegistry) 구현
    - [ ] `model/serial_manager.py` 생성
    - [ ] 포트 레지스트리 및 수명 주기 관리 구현
- [ ] `PortController` 통합
    - [ ] Worker 생성 및 Transport 주입 로직
    - [ ] PacketParser 통합 (Raw Data -> Packet 변환)
    - [ ] EventBus 발행 (`port.rx_data`, `port.status` 등)
- [ ] `MacroRunner` 구현 (자동화 엔진)**
    - [ ] 상태 머신 (Idle/Running/Paused) 구현
    - [ ] Step 실행 로직 (Send -> Delay/Expect)
    - [ ] QTimer 기반 타이밍 제어
- [ ] `PacketParser` 시스템 구현
    - [ ] `model/packet_parser.py` 생성
    - [ ] `ParserFactory` 구현 (AT, Delimiter, Fixed, Hex)
    - [ ] `ExpectMatcher` 구현 (Regex 기반)
    - [ ] `IPacketParser` 인터페이스 및 `RxPacket` 데이터 클래스 정의
    - [ ] `ATParser` 구현 (AT Command 파싱)
    - [ ] `DelimiterParser`, `FixedLengthParser` 구현
- [ ] `EventRouter` 구현 (View-Model 분리)
    - [ ] EventBus 구독 및 View 업데이트 라우팅
- [ ] CI/CD 설정


## Phase 6: Presenter 계층 (아키텍처 개선)
- [ ] **Presenter 계층 세분화**
    - [ ] `MainPresenter`: 앱 생명주기 및 하위 Presenter 조율
    - [ ] `PortPresenter`: 포트 연결/해제/설정 제어 (완성)
    - [ ] `MacroPresenter`: 매크로 로드/저장/실행 제어 (신규)
    - [ ] `FilePresenter`: 파일 전송 로직 제어 (신규)
- [ ] **EventRouter 구현**
    - [ ] EventBus 구독 및 View 업데이트 라우팅
- [ ] **설정 관리 통합**
    - [ ] View의 `save_state`/`load_state`와 SettingsManager 연동

## Phase 7: 자동화 및 고급 기능 (계획됨)
- [ ] `MacroRunner` 구현 (커맨드 리스트 엔진)
    - [ ] 상태 머신 (Idle/Running/Paused)
    - [ ] 단계 실행 (Send -> Expect -> Delay)
    - [ ] Auto Run 스케줄러 (Interval/Loops)
- [ ] `FileTransferEngine` 구현
    - [ ] 청크 기반 전송 (적응형 크기)
    - [ ] 진행률 계산 및 취소 지원
    - [ ] Rx 파일 캡처 (`RxCaptureWriter`)
- [ ] `AutoTxScheduler` 구현 (주기적 전송)
- [ ] 성능 최적화
    - [ ] RxLogView를 위한 `BatchRenderer` 구현
    - [ ] `RingBuffer` 최적화 (bytearray)
    - [ ] 논블로킹 I/O 루프 최적화
    - [x] `QSmartListView` 구현 (`view/custom_widgets/smart_list_view.py`)
        - [x] QAbstractListModel 기반 로그 모델
        - [x] 검색(Find Next/Prev) 기능 구현
    - [x] `ReceivedAreaWidget`에 QSmartListView 적용
    - [x] `SystemLogWidget`에 QSmartListView 적용

## Phase 8: 플러그인 시스템 (계획됨)
- [ ] 플러그인 인프라 구현
    - [ ] `core/plugin_base.py` 생성 (인터페이스)
    - [ ] `core/plugin_loader.py` 생성 (동적 임포트)
    - [ ] `ExamplePlugin` 구현

## Phase 9: 검증 및 배포 (계획됨)
- [ ] 테스트 환경 설정
    - [ ] 가상 시리얼 포트 설정 (com0com/socat)
    - [ ] Mock Serial 클래스 생성
- [ ] 자동화 테스트
    - [ ] 단위 테스트 (Core/Model)
    - [ ] 통합 테스트 (Serial I/O)
    - [ ] 성능 벤치마크 (Rx 처리량, UI 렌더링)
- [ ] 패키징 및 배포
    - [ ] `pyinstaller.spec` 생성
    - [ ] 독립 실행형 EXE/AppImage 빌드
    - [ ] GitHub Actions CI/CD 설정
