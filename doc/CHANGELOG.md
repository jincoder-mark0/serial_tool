# 변경 이력 (Changelog)

이 프로젝트의 모든 주요 변경 사항은 이 파일에 기록됩니다.

이 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 기반으로 하며,
이 프로젝트는 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 준수합니다.

## [Unreleased]

## [0.1.0] - 2025-11-30

### 추가됨 (Added)
- **멀티 포트 탭 지원**: `LeftPanel`에 `QTabWidget`을 구현하여 여러 시리얼 포트 연결을 관리할 수 있도록 했습니다.
- **동적 탭 이름**: 탭 이름이 연결된 COM 포트 이름 또는 자리 표시자("-")로 동적으로 업데이트됩니다.
- **수동 제어 위젯 (ManualControlWidget)**: 수동 명령 입력, 파일 전송, 로그 저장을 위한 위젯을 추가했습니다 (구 `OperationArea`).
- **커맨드 제어 위젯 (CommandControlWidget)**: 커맨드 리스트 실행(실행, 중지, 자동 실행)을 관리하는 위젯을 추가했습니다 (구 `RunControl`).
- **커맨드 리스트 위젯 (CommandListWidget)**:
    - 행 관리(추가, 삭제, 위로 이동, 아래로 이동)를 위한 버튼을 추가했습니다.
    - HEX/CR 옵션 및 행별 Send 버튼을 실제 체크박스와 버튼으로 구현했습니다.
    - 레이아웃 및 선택 동작(행 단위 선택)을 개선했습니다.
- **패널 구조**: UI 구성을 개선하기 위해 `LeftPanel`(포트/수동 제어)과 `RightPanel`(커맨드/인스펙터) 컨테이너를 도입했습니다.
- **핵심 인프라 (Core Infrastructure)**:
    - `EventBus`: 시그널 기반의 전역 이벤트 처리 시스템.
    - `SerialWorker`: 스레드 기반 시리얼 통신 워커.
    - `ThreadSafeQueue`, `RingBuffer`: 데이터 처리를 위한 유틸리티 클래스.

### 변경됨 (Changed)
- **UI 리팩토링**:
    - `OperationArea` -> `ManualControlWidget`으로 이름 변경.
    - `RunControl` -> `CommandControlWidget`으로 이름 변경.
    - 패널 클래스들을 `view/panels/` 디렉토리로 이동.
    - 위젯 클래스들을 `view/widgets/` 디렉토리로 이동.
- **레이아웃 개선**:
    - `MainWindow`를 단순화하고 레이아웃 관리를 `LeftPanel`과 `RightPanel`에 위임했습니다.
    - `CommandListWidget`의 컬럼 렌더링 및 버튼 레이아웃을 개선했습니다.
- **UX 향상**:
    - 모든 UI 요소에 툴팁을 추가했습니다.
    - 포트 연결 전 제어 버튼들의 초기 비활성화 상태를 구현했습니다.

### 제거됨 (Removed)
- 사용하지 않는 파일 삭제: `rx_log_view.py`, `status_bar.py`, `run_control.py`, `operation_area.py`.
