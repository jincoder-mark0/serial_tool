# SerialTool 구현 계획 (Implementation Plan)

## 목표 (Goal)

`Implementation_Specification.md`에 정의된 **SerialTool v1.0**을 **Python 3.10+** 및 **PyQt5**를 사용하여 구현합니다. **Layered MVP (Model-View-Presenter)** 아키텍처와 **Worker Thread** 모델을 적용하여 **고성능**, **안정성**, **확장성**을 확보하는 것이 목표입니다.

### 핵심 목표
- **멀티포트 관리**: 최대 16개 포트 동시 오픈 및 독립 제어
- **고속 데이터 처리**: 2MB/s 연속 스트림, 초당 10K 라인 로그 처리
- **자동화 엔진**: Command List 기반 스크립트 실행, Auto Run 스케줄러
- **파일 송수신**: Chunk 기반 전송, 진행률 표시, 취소/재시도
- **확장성**: EventBus 기반 플러그인 시스템

---

## 사용자 검토 필요 사항 (User Review Required)

> [!IMPORTANT]
> **프로젝트 핵심 결정 사항**
> - **프로젝트 명칭**: `SerialManager` → `SerialTool`로 변경 완료
> - **UI 구조**: `LeftPanel`(포트/수동제어) + `RightPanel`(커맨드/인스펙터) 구조 확정
> - **성능 목표**: Rx 2MB/s, UI 10K lines/s 처리를 위한 RingBuffer 및 Batch Rendering 적용
> - **스타일링**: 중앙 집중식 QSS 테마 시스템 (`common.qss` + 개별 테마)

> [!WARNING]
> **다음 단계 진행 전 확인 필요**
> - **Core 유틸리티 구현 방향**: RingBuffer 크기(512KB), ThreadSafeQueue 최대 크기(128 chunks) 확정 필요
> - **멀티포트 최대 개수**: 현재 16개로 설정, 변경 필요 시 알려주세요
> - **플러그인 시스템 범위**: v1.0에 포함할지, v1.1로 연기할지 결정 필요

---

## 제안된 변경 사항 (Proposed Changes)

### 1. 프로젝트 구조 (Project Structure)

프로젝트 루트 하위에 계층별 모듈을 구성합니다:

```
serial_tool2/
├── core/                    # 핵심 유틸리티 및 인프라
│   ├── event_bus.py        # EventBus (Pub/Sub)
│   ├── utils.py            # RingBuffer, ThreadSafeQueue
│   ├── logger.py           # 로깅 시스템
│   └── settings_manager.py # 설정 관리 [완료]
├── model/                   # 비즈니스 로직 및 Worker
│   ├── serial_worker.py    # QThread 기반 시리얼 I/O
│   ├── port_controller.py  # 포트 라이프사이클 관리
│   ├── serial_manager.py   # 멀티포트 레지스트리
│   ├── packet_parser.py    # 패킷 파싱 (AT/Delimiter/Fixed/Hex)
│   ├── command_entry.py    # Command DTO
│   ├── cl_runner.py        # Command List 실행 엔진
│   └── file_transfer.py    # 파일 전송 엔진
├── view/                    # UI 계층
│   ├── main_window.py      # 메인 윈도우 [완료]
│   ├── theme_manager.py    # 테마 관리 [완료]
│   ├── panels/             # 패널 컴포넌트
│   │   ├── left_panel.py   # 좌측 패널 (포트 탭) [완료]
│   │   ├── right_panel.py  # 우측 패널 (커맨드/인스펙터) [완료]
│   │   ├── port_panel.py   # 포트 패널 [완료]
│   │   └── command_list_panel.py # 커맨드 리스트 패널 [완료]
│   └── widgets/            # 위젯 컴포넌트
│       ├── port_settings.py       # 포트 설정 [완료]
│       ├── received_area.py       # 로그 뷰 [완료]
│       ├── manual_control.py      # 수동 제어 [완료]
│       ├── command_list.py        # 커맨드 리스트 [완료]
│       ├── command_control.py     # 커맨드 제어 [완료]
│       └── packet_inspector.py    # 패킷 인스펙터 [완료]
├── presenter/               # Presenter 계층
│   ├── main_presenter.py   # 중앙 제어
│   ├── port_presenter.py   # 포트 제어
│   ├── command_presenter.py # 커맨드 제어
│   ├── file_presenter.py   # 파일 전송 제어
│   └── event_router.py     # 이벤트 라우팅
├── plugins/                 # 확장 플러그인
│   └── example_plugin/     # 샘플 플러그인
├── resources/               # 리소스 파일 [완료]
│   ├── themes/             # QSS 테마 [완료]
│   │   ├── common.qss
│   │   ├── dark_theme.qss
│   │   └── light_theme.qss
│   └── icons/              # SVG 아이콘 [완료]
├── config/                  # 설정 파일
│   ├── default_settings.json
│   └── color_rules.json
├── tests/                   # 테스트
│   ├── test_view.py        # View 독립 테스트 [완료]
│   ├── test_core.py
│   ├── test_model.py
│   └── test_integration.py
├── doc/                     # 문서
│   ├── Implementation_Specification.md [완료]
│   ├── CHANGELOG.md        [완료]
│   ├── implementation_plan.md
│   ├── task.md
│   └── session_summary_*.md
├── main.py                  # 진입점 [완료]
├── version.py              # 버전 정보 [완료]
├── requirements.txt        # 의존성 [완료]
└── README.md               # 프로젝트 개요 [완료]
```

---

### 2. Core 계층 (Core Layer)

#### [완료] `core/settings_manager.py`
- ✅ JSON 기반 설정 저장/로드
- ✅ 전역 설정 및 포트별 프로파일 관리
- ✅ 백업/복원 기능

#### [진행 필요] `core/utils.py`
**RingBuffer 구현**
- 크기: 512KB (설정 가능)
- 고속 데이터 수신 처리
- 오버플로우 시 자동 덮어쓰기
- 스레드 안전성 보장

**ThreadSafeQueue 구현**
- TX 큐 관리 (최대 128 chunks)
- `collections.deque` 기반
- Lock-free 또는 최소 Lock 전략
- 우선순위 큐 지원 (선택)

#### [진행 필요] `core/event_bus.py`
**EventBus 아키텍처**
- Publish/Subscribe 패턴
- 표준 이벤트 타입 정의
  - `PORT_OPENED`, `PORT_CLOSED`, `DATA_RECEIVED`, `DATA_SENT`
  - `COMMAND_STARTED`, `COMMAND_COMPLETED`, `COMMAND_FAILED`
  - `FILE_TRANSFER_STARTED`, `FILE_TRANSFER_PROGRESS`, `FILE_TRANSFER_COMPLETED`
- 플러그인 연동 인터페이스
- 이벤트 필터링 및 우선순위

#### [진행 필요] `core/logger.py`
**로깅 계층**
- UI 로그: ReceivedArea에 표시
- 파일 로그: RotatingFileHandler (10MB x 5개)
- 성능 로그: CSV 형식 (perf_YYYY-MM-DD.csv)

**기능**
- 색상 규칙 (OK/ERROR/URC)
- 타임스탬프 프리픽스
- 로그 레벨 (DEBUG/INFO/WARNING/ERROR)
- 민감 정보 마스킹

---

### 3. Model 계층 (Model Layer)

#### [진행 필요] `model/serial_worker.py`
**SerialWorker(QThread) 구현**
- Non-blocking I/O 루프
- RingBuffer 연동 (수신 데이터)
- ThreadSafeQueue 연동 (송신 데이터)
- 시그널 발행
  - `data_received(bytes)`
  - `data_sent(int)`
  - `error_occurred(str)`
  - `port_closed()`
- 안전 종료 시퀀스 (타임아웃 3초)

**성능 목표**
- 수신 처리량: 2MB/s
- TX 큐 지연: 10ms 이하
- CPU 사용률: 단일 포트 기준 5% 이하

#### [진행 필요] `model/port_controller.py`
**포트 라이프사이클 관리**
- 상태 머신: `Closed` → `Opening` → `Open` → `Error` → `Closed`
- 포트별 Worker 인스턴스 관리
- 설정 변경 처리 (baudrate, parity 등)
- 에러 복구 정책
  - 자동 재연결 (선택)
  - 에러 로그 기록

**멀티포트 격리**
- 포트별 독립 RingBuffer
- 포트별 독립 TX 큐
- 포트별 독립 Worker 스레드

#### [진행 필요] `model/serial_manager.py`
**PortRegistry 구현**
- 포트 목록 관리 (최대 16개)
- 포트 스캔 기능 (OS별 구현)
  - Windows: `COM1`~`COM256`
  - Linux: `/dev/ttyUSB*`, `/dev/ttyACM*`
- 포트 상태 모니터링
- 통계 수집 (Rx/Tx 바이트, 에러 카운트)

#### [진행 필요] `model/packet_parser.py`
**Parser Factory 패턴**
- `ParserBase` 추상 클래스
- 구체 파서 구현
  - `DelimiterParser`: 개행, 커스텀 구분자
  - `FixedLengthParser`: 고정 길이 패킷
  - `ATParser`: AT 명령 응답 (OK, ERROR, +URC)
  - `HexParser`: 바이너리 데이터

**Expect/Timeout 처리**
- 정규식 기반 매칭
- 타임아웃 설정 (기본 5초)
- 매칭 실패 시 재시도 정책

#### [진행 필요] `model/command_entry.py`
**CommandEntry DTO**
```python
@dataclass
class CommandEntry:
    enabled: bool
    command: str
    is_hex: bool
    prefix: str
    suffix: str
    delay_ms: int
    expect: str = ""
    timeout_ms: int = 5000
```

**JSON 직렬화**
- 스크립트 저장/로드
- 검증 규칙 (필수 필드, 타입 체크)

#### [진행 필요] `model/cl_runner.py`
**Command List 실행 엔진**
- 상태 머신: `Idle` → `Running` → `Paused` → `Stopped`
- 순차 실행 로직
  1. 명령 송신
  2. Expect 매칭 대기 (타임아웃 체크)
  3. Delay 대기
  4. 다음 명령
- 반복 실행 (최대 횟수 설정)
- 실행 결과 리포트 (JSON)

**시그널**
- `step_started(int)`: 현재 행 번호
- `step_completed(int, bool)`: 행 번호, 성공 여부
- `run_completed(bool)`: 전체 성공 여부

#### [진행 필요] `model/file_transfer.py`
**FileTransferEngine(QRunnable)**
- Chunk 기반 전송 (기본 1KB)
- 적응형 Chunk Size (baudrate 기반)
- 진행률 계산 (바이트 단위)
- 취소 메커니즘 (플래그 체크)
- 재시도 정책 (최대 3회)

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
  - 플러그인 로드 (선택)
- View ↔ Model 연결
- 종료 시퀀스
  - 모든 포트 닫기
  - 설정 저장
  - 스레드 정리

#### [진행 필요] `presenter/port_presenter.py`
**포트 제어 로직**
- 포트 열기/닫기
  - View 시그널 수신 (`port_open_requested`)
  - PortController 호출
  - 상태 업데이트 (`port_opened`, `port_closed`)
- 설정 변경 처리
  - baudrate, parity 등 변경 시 포트 재시작
- 데이터 송수신
  - View → Model: TX 데이터 전달
  - Model → View: RX 데이터 표시

#### [진행 필요] `presenter/command_presenter.py`
**Command List 제어**
- 스크립트 저장/로드
  - JSON 파일 I/O
  - CommandEntry 직렬화/역직렬화
- Run/Stop/Pause 로직
  - CLRunner 제어
  - 실행 상태 UI 업데이트
- Auto Run 스케줄링
  - QTimer 기반 주기 실행
  - 최대 실행 횟수 체크

#### [진행 필요] `presenter/file_presenter.py`
**파일 전송 제어**
- 파일 선택 처리
- FileTransferEngine 시작
- 진행률 업데이트
  - ProgressBar 업데이트
  - 전송 속도 계산 (KB/s)
- 취소 처리
  - Engine 중단
  - UI 정리

#### [진행 필요] `presenter/event_router.py`
**EventBus 기반 라우팅**
- View 이벤트 → Model 이벤트 변환
- Model 이벤트 → View 업데이트
- 플러그인 이벤트 처리

---

### 5. View 계층 (View Layer) - ✅ 완료

#### [완료] UI 구조
- `MainWindow`: 메인 레이아웃, 메뉴, 툴바
- `LeftPanel`: 포트 탭 + 수동 제어
- `RightPanel`: 커맨드 리스트 + 패킷 인스펙터

#### [완료] 위젯
- `PortSettingsWidget`: 컴팩트 2줄 레이아웃
- `ReceivedArea`: 로그 뷰, 색상 규칙, 타임스탬프, Trim
- `ManualControlWidget`: 수동 전송, 파일 선택
- `CommandListWidget`: Prefix/Suffix, 3단계 체크박스
- `CommandControlWidget`: 스크립트 저장/로드, Auto Run
- `PacketInspectorWidget`: 패킷 상세 뷰

#### [완료] 테마 시스템
- `ThemeManager`: QSS 로딩 및 동적 전환
- `common.qss`: 공통 스타일
- `dark_theme.qss`, `light_theme.qss`: 개별 테마
- SVG 아이콘 시스템 (테마별 색상 자동 변경)

#### [완료] 듀얼 폰트 시스템
**목적**: UI 가독성 향상을 위한 폰트 분리

**Proportional Font (가변폭 폰트)**
- 적용 대상: 메뉴, 툴바, 상태바, 레이블, 버튼, 그룹박스, 탭 등
- 기본 폰트: "Segoe UI" (Windows), "Ubuntu" (Linux)
- 크기: 9pt (기본), 설정 가능
- 특징: 자연스러운 텍스트 표시, UI 요소에 최적화

**Fixed Font (고정폭 폰트)**
- 적용 대상: TextEdit, LineEdit, CommandList의 Command 컬럼, 패킷 인스펙터
- 기본 폰트: "Consolas" (Windows), "Monospace" (Linux)
- 크기: 9pt (기본), 설정 가능
- 특징: 정렬된 텍스트 표시, 코드/데이터 가독성 향상

**구현 사항** (완료)
- `ThemeManager`에 폰트 관리 기능 추가
  - `set_proportional_font(family: str, size: int)`
  - `set_fixed_font(family: str, size: int)`
  - `get_proportional_font() -> QFont`
  - `get_fixed_font() -> QFont`
- 폰트 설정 대화상자 구현
  - Proportional Font 선택 (프리뷰 포함)
  - Fixed Font 선택 (프리뷰 포함)
  - 크기 조절 (6pt ~ 16pt)
  - 기본값 복원 버튼
- QSS에 폰트 클래스 추가
  - `.proportional-font`: 가변폭 폰트 적용
  - `.fixed-font`: 고정폭 폰트 적용
- 설정 저장/복원
  - `settings.json`에 폰트 정보 저장
  - 앱 재시작 시 폰트 복원

---

### 6. 플러그인 시스템 (Plugin System) - 선택 기능

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
- 핫 리로딩 지원 (선택)
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
- `test_cl_runner.py`: 순차 실행, 반복, 에러 처리
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
4. Command List 실행 (10개 명령, 5회 반복)
5. 파일 전송 (10MB 파일, 115200bps)

#### E2E 테스트 (pytest-qt)
**UI 워크플로우**
1. 앱 시작 → 포트 선택 → 열기
2. 수동 명령 송신 → 로그 확인
3. Command List 로드 → 실행 → 결과 확인
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
- [ ] Command List 자동 실행 (AT 명령)
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
└── LICENSE
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

### Phase 1: Core 유틸리티 (1주)
1. `core/utils.py`: RingBuffer, ThreadSafeQueue
2. `core/event_bus.py`: EventBus 구현
3. `core/logger.py`: 로깅 시스템
4. 단위 테스트 작성 및 실행

### Phase 2: Model 계층 (2주)
1. `model/serial_worker.py`: SerialWorker 구현
2. `model/port_controller.py`: PortController 구현
3. `model/serial_manager.py`: PortRegistry 구현
4. Virtual Serial Port 통합 테스트

### Phase 3: Presenter 연동 (1주)
1. `presenter/port_presenter.py`: 포트 제어 로직
2. `presenter/main_presenter.py`: 중앙 제어
3. View ↔ Model 연결
4. 실제 포트 송수신 테스트

### Phase 4: 자동화 기능 (2주)
1. `model/packet_parser.py`: 패킷 파서
2. `model/command_entry.py`: Command DTO
3. `model/cl_runner.py`: Command List 엔진
4. `presenter/command_presenter.py`: 커맨드 제어
5. Command List E2E 테스트

### Phase 5: 파일 전송 (1주)
1. `model/file_transfer.py`: FileTransferEngine
2. `presenter/file_presenter.py`: 파일 제어
3. 대용량 파일 전송 테스트

### Phase 6: 고급 기능 (1주)
1. Preferences Dialog 구현
2. 로그 내보내기 기능
3. 패킷 인스펙터 고도화

### Phase 7: 플러그인 시스템 (1주, 선택)
1. `core/plugin_base.py`, `core/plugin_loader.py`
2. `plugins/example_plugin/`
3. 플러그인 관리 UI

### Phase 8: 테스트 및 최적화 (1주)
1. 단위/통합 테스트 커버리지 70%+
2. 성능 벤치마크 실행
3. 메모리 프로파일링 및 최적화

### Phase 9: 배포 준비 (1주)
1. PyInstaller 빌드 스크립트
2. CI/CD 파이프라인 구축
3. 플랫폼별 빌드 테스트
4. 사용자 문서 작성

### Phase 10: 최종 검증 및 릴리스 (1주)
1. 수락 기준 검증
2. 플랫폼별 수동 테스트
3. 장기 런 테스트 (24시간)
4. v1.0.0 릴리스

**총 예상 기간**: 12주 (약 3개월)

---

## 현재 상태 및 다음 단계

### 완료된 작업 (2025-12-01 기준)
- ✅ **프로젝트 구조**: 폴더 구조, 문서, 설정 파일
- ✅ **UI 구현**: 모든 패널 및 위젯 완성
- ✅ **테마 시스템**: Dark/Light 테마, SVG 아이콘
- ✅ **듀얼 폰트 시스템**: Proportional/Fixed 폰트 분리 및 적용
- ✅ **설정 관리**: SettingsManager 구현

### 진행 중인 작업
- 🔄 **Core 유틸리티**: RingBuffer, ThreadSafeQueue, EventBus 구현 필요
- 🔄 **Model 계층**: SerialWorker, PortController 구현 필요

### 다음 단계 (우선순위)
1. **Core 유틸리티 완성** (Phase 3)
   - RingBuffer 구현 및 테스트
   - ThreadSafeQueue 구현 및 테스트
   - EventBus 구현 및 테스트
3. **Model 계층 구현** (Phase 4)
   - SerialWorker 구현
   - PortController 구현
   - Virtual Serial Port 테스트
3. **Presenter 연동** (Phase 3)
   - PortPresenter 구현
   - View ↔ Model 연결
   - 실제 포트 송수신 확인

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
- [ ] Command List 자동 실행 (반복, 지연, Expect)
- [ ] 파일 전송 (10MB+, 진행률 표시)
- [ ] 설정 저장/복원 (포트, UI, 명령 리스트)
- [ ] 플러그인 로드 및 실행 (선택)

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
**최종 업데이트**: 2025-12-01
**작성자**: AI Assistant (Antigravity)
