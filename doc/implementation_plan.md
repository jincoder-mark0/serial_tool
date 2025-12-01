# 구현 계획 (Implementation Plan)

## 목표 (Goal)

`Implementation_Specification.md`에 정의된 **SerialTool v1.0** 을 **Python 3.10+** 및 **PyQt5**를 사용하여 구현합니다. **Layered MVP (Model-View-Presenter)** 아키텍처와 **Worker Thread** 모델을 적용하여 고성능, 안정성, 확장성을 확보합니다.

## 사용자 검토 필요 사항 (User Review Required)
>
> [!IMPORTANT]
>
> - **프로젝트 명칭 변경**: `SerialManager`에서 `SerialTool`로 변경되었습니다.
> - **UI 구조 확정**: `LeftPanel`(포트/수동제어) + `RightPanel`(커맨드/인스펙터) 구조로 리팩토링 완료되었습니다.
> - **성능 목표**: Rx 2MB/s, UI 10K lines/s 처리를 목표로 최적화(RingBuffer, Batch Rendering)를 적용합니다.
> - **스타일링**: 개별 `setStyleSheet` 대신 중앙 집중식 QSS 테마 시스템을 사용합니다.

## 제안된 변경 사항 (Proposed Changes)

### 1. 프로젝트 구조 (Project Structure)

`serial_manager/` 루트 하위에 계층별 모듈을 구성합니다:

- `core/`: EventBus, Utils(RingBuffer, ThreadSafeQueue), Logger, Settings
- `model/`: SerialWorker, PortController, PacketParser, CLRunner, FileTransfer
- `view/`:
  - `panels/`: LeftPanel, RightPanel, PortPanel, CommandListPanel
  - `widgets/`: ManualControl, CommandControl, PortSettings, PacketInspector
- `presenter/`: PortPresenter, MainPresenter, EventRouter
- `plugins/`: 확장 플러그인
- `tests/`: Unit/Integration/E2E 테스트
- `doc/`: 문서 (CHANGELOG, 명세서 등)

### 2. 핵심 컴포넌트 상세 (Core Components Detail)

#### [COMPLETED] UI Layer (View)

- **MainWindow**: `LeftPanel`과 `RightPanel`로 구성된 깔끔한 레이아웃.
- **LeftPanel**:
  - **PortTabs**: 다중 포트 탭 관리 (`PortPanel` 인스턴스).
  - **ManualControl**: 수동 명령 입력, 파일 전송, 로그 제어.
- **RightPanel**:
  - **CommandListPanel**: 커맨드 리스트 관리 및 실행 제어 (`CommandControl` 포함).
  - **PacketInspector**: 상세 패킷 분석 뷰.
- **Styling**: [완료] `common.qss` 도입 및 다크/라이트 테마 리팩토링. `.accent`/`.danger` 스타일 적용.
- **Font System**: [진행 중] Proportional/Fixed 폰트 분리 시스템 구현 중.

#### [COMPLETED] Core & Model Layer

- **EventBus**: Publish/Subscribe 패턴으로 컴포넌트 간 느슨한 결합 보장.
- **SerialWorker**: `QThread` 상속, Non-blocking I/O 및 `RingBuffer`를 이용한 고속 데이터 수신.
- **Utils**: `RingBuffer`, `ThreadSafeQueue` 구현.
- **PortPresenter**: View와 Model 연결, 포트 제어 로직 구현.
- **PortController**: 포트별 상태 머신 및 리소스(Worker, Queue) 관리, 멀티포트 격리.

#### [IN-PROGRESS] Automation & Features

- **SettingsManager**: [완료] 설정 저장/로드 (JSON).
- **PacketParser**: Factory 패턴 적용, AT/Delimiter/Fixed/Hex 파서 지원.
- **CLRunner**: Command List 실행 엔진 (순차 실행, 반복, 지연).
- **FileTransferEngine**: 파일 청크 전송 로직.
- **PluginSystem**: 확장 플러그인 로더.

### 3. 기능 구현 순서 (Implementation Order)

1. **[완료] 프로젝트 설정**: 구조 생성, `requirements.txt`, `README.md`, `main.py`.
2. **[완료] UI 구현 (View)**: 메인 윈도우, 패널/위젯 분리 및 리팩토링, 레이아웃 최적화.
3. **[완료] UI 검증**: 초기 실행 시 버튼 비활성화, 탭 동작, 리사이징 확인.
4. **[완료] Core & Model**: EventBus, SerialWorker, PortPresenter 구현 및 연동.
5. **[완료] Presenter 연동**: 실제 시리얼 포트 연결, 데이터 송수신(Tx/Rx) 활성화.
6. **[완료] 설정 관리**: SettingsManager 구현 및 View 연동.
7. **[진행중] 자동화 기능**: Command List 실행 엔진, Auto Run 구현.
8. **고급 기능**: 파일 전송, 로깅, 플러그인 시스템.
9. **테스트 및 배포**: 단위/통합 테스트, 성능 벤치마크, PyInstaller 빌드.

## 검증 계획 (Verification Plan)

### 자동화 테스트

- **Unit Test**: `pytest`로 Core/Model 로직 검증 (커버리지 70%+).
- **Integration Test**: 가상 시리얼 포트(com0com/socat)를 이용한 송수신 및 멀티포트 테스트.
- **Performance Test**: `pytest-benchmark`로 Rx 처리량(2MB/s) 및 UI 렌더링 속도 측정.

### 수동 검증

- **UI UX**: 버튼 활성/비활성 상태, 탭 동작, 툴팁 확인.
- **Functional**: 실제 장비 연결 후 데이터 송수신, 커맨드 리스트 자동 실행 확인.
- **Scenario**: 실제 장비 또는 루프백 환경에서 장시간(24h+) Auto Run 테스트.
- **Deployment**: PyInstaller로 생성된 실행 파일의 클린 설치 및 실행 확인.
