# 구현 계획 (Implementation Plan)

## 목표 (Goal)
`Implementation_Specification.md`에 정의된 **SerialManager v1.0** (Quectel QCOM V1.6 클론 및 확장)을 **Python 3.10+** 및 **PyQt5**를 사용하여 구현합니다. **Layered MVP (Model-View-Presenter)** 아키텍처와 **Worker Thread** 모델을 적용하여 고성능, 안정성, 확장성을 확보합니다.

## 사용자 검토 필요 사항 (User Review Required)
> [!IMPORTANT]
> - **UI 우선 구현**: 요청에 따라 View Layer를 먼저 구현하고 검증한 후 Core 로직을 연결합니다.
> - **README 작성**: 프로젝트 초기 설정 단계에서 `README.md`를 작성합니다.
> - **성능 목표**: Rx 2MB/s, UI 10K lines/s 처리를 목표로 최적화(RingBuffer, Batch Rendering)를 적용합니다.

## 제안된 변경 사항 (Proposed Changes)

### 1. 프로젝트 구조 (Project Structure)
`serial_manager/` 루트 하위에 계층별 모듈을 구성합니다:
- `core/`: EventBus, Utils(RingBuffer), Logger, Settings
- `model/`: SerialWorker, PortController, PacketParser, CLRunner, FileTransfer
- `view/`: MainWindow, RxLogView, PortSettings, CommandListPanel
- `presenter/`: MainPresenter, EventRouter, PortPresenter
- `plugins/`: 확장 플러그인
- `tests/`: Unit/Integration/E2E 테스트

### 2. 핵심 컴포넌트 상세 (Core Components Detail)

#### [NEW] UI Layer (View)
- **MainWindow**: QSplitter 기반 반응형 레이아웃. 좌측은 **QTabWidget**을 사용하여 포트별 탭(PortPanel)을 관리하고, 우측은 커맨드 리스트/인스펙터를 배치합니다.
- **PortPanel**: 개별 포트 제어를 위한 복합 위젯. `PortSettings`, `RxLogView`, `TxPanel`, `StatusBar`를 포함합니다.
- **RxLogView**: `QTextEdit` 기반, 배치 렌더링 및 가상 스크롤링 적용으로 고성능 로그 표시.
- **CommandListPanel**: `QTableView` + Delegate를 사용하여 복잡한 커맨드 리스트 관리 및 실행 상태 시각화.
- **Tooltips**: 모든 UI 요소에 기능 설명과 단축키를 포함한 툴팁을 제공합니다.

#### [NEW] Core & Model Layer
- **EventBus**: Publish/Subscribe 패턴으로 컴포넌트 간 느슨한 결합 보장.
- **SerialWorker**: `QThread` 상속, Non-blocking I/O 및 `RingBuffer`를 이용한 고속 데이터 수신.
- **PortController**: 포트별 상태 머신 및 리소스(Worker, Queue) 관리, 멀티포트 격리.
- **PacketParser**: Factory 패턴 적용, AT/Delimiter/Fixed/Hex 파서 지원.

#### [NEW] Automation & Features
- **CLRunner**: Command List 실행 엔진. Expect/Timeout/Repeat/Jump 로직 구현.
- **FileTransferEngine**: `QRunnable` 기반 Chunk 전송, 진행률 및 취소 지원.
- **SettingsManager**: JSON 기반 설정 저장/복원, 포트별 프로파일 지원.

### 3. 기능 구현 순서 (Implementation Order)
1.  **프로젝트 설정**: 구조 생성, `requirements.txt`, `README.md`, `main.py`.
2.  **UI 구현 (View)**: 메인 윈도우, 포트 설정, 로그 뷰, 커맨드 리스트 패널 등 위젯 구현.
3.  **UI 검증**: 레이아웃, 테마, 리사이징 동작 확인.
4.  **Core & Model**: EventBus, SerialWorker, PortController, Parser 구현.
5.  **Presenter 연동**: View와 Model 연결, 시리얼 통신 기본 기능(Open/Send/Rx) 활성화.
6.  **자동화 기능**: Command List 실행 엔진, Auto Run 구현.
7.  **고급 기능**: 파일 전송, 설정 관리, 로깅, 플러그인 시스템.
8.  **테스트 및 배포**: 단위/통합 테스트, 성능 벤치마크, PyInstaller 빌드.

## 검증 계획 (Verification Plan)

### 자동화 테스트
- **Unit Test**: `pytest`로 Core/Model 로직 검증 (커버리지 70%+).
- **Integration Test**: 가상 시리얼 포트(com0com/socat)를 이용한 송수신 및 멀티포트 테스트.
- **Performance Test**: `pytest-benchmark`로 Rx 처리량(2MB/s) 및 UI 렌더링 속도 측정.

### 수동 검증
- **UI UX**: 3-Click Rule 준수 여부, 테마 적용, 반응형 레이아웃 확인.
- **Scenario**: 실제 장비 또는 루프백 환경에서 장시간(24h+) Auto Run 테스트.
- **Deployment**: PyInstaller로 생성된 실행 파일의 클린 설치 및 실행 확인.
