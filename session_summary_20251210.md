---

## 추가 세션: 아키텍처 및 성능 고도화 (Refactoring & Optimization)

### 1. 통신 구조 리팩토링 (Protocol Agnostic Architecture)
**목표**: Serial 통신에만 종속된 구조를 탈피하여, 향후 SPI/I2C 등 다양한 프로토콜을 수용할 수 있는 유연한 구조로 변경.

- **인터페이스 분리**: `ITransport` (core/interfaces.py) 인터페이스를 정의하여 통신 규약을 추상화함.
- **Transport 계층 구현**: `pyserial` 의존성을 `SerialTransport` (model/transports.py) 클래스로 격리함.
- **Worker 일반화**:
  - `SerialWorker`를 `ConnectionWorker` (model/connection_worker.py)로 이름을 변경하고 리팩토링.
  - Worker는 더 이상 Serial 객체를 직접 생성하지 않고, 외부에서 주입받은 `ITransport` 객체를 사용.
- **Controller 수정**: `PortController`가 `SerialTransport`를 생성하여 Worker에 주입(Dependency Injection)하도록 수정.

### 2. UI 성능 최적화 (QSmartListView)
**목표**: 대량의 로그 데이터(초당 수천 라인) 수신 시 발생하는 UI 버벅임(Freezing) 해결.

- **QSmartListView 도입**:
  - 기존 `QTextEdit` 대신 `QListView`와 `QAbstractListModel`을 활용한 커스텀 위젯 구현.
  - 화면에 보이는 부분만 렌더링하여 성능을 극대화함.
  - `view/custom_widgets/smart_list_view.py` 생성.
- **검색 기능 내장**:
  - 리스트 뷰 내부에서 정규식 기반의 `find_next`, `find_prev` 메서드 구현.
  - 검색 결과 하이라이트 및 자동 스크롤 기능 포함.
- **적용**: `ReceivedAreaWidget` 및 `SystemLogWidget`의 로그 뷰어를 `QSmartListView`로 교체 완료.