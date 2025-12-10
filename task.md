## Phase 3: Core 유틸리티 (진행 중)
- [x] `SettingsManager` 구현 (싱글톤, AppConfig 통합)
- [x] `AppConfig` 구현 (중앙 경로 관리)
- [x] `PortState` Enum 정의
- [x] `ITransport` 인터페이스 정의 (`core/interfaces.py`)
- [ ] `RingBuffer` 구현
    - [ ] `core/utils.py` 생성
    - [ ] 원형 버퍼 로직 구현
    - [ ] 스레드 안전성 구현
- [ ] `ThreadSafeQueue` 구현
    - [ ] `core/utils.py`에 추가
    - [ ] 블로킹/논블로킹 큐 구현
- [ ] `EventBus` 구현
    - [ ] `core/event_bus.py` 생성
    - [ ] Pub/Sub 패턴 구현

## Phase 4: Model 계층 (진행 중)
- [x] `SerialTransport` 구현 (`model/transports.py`)
- [x] `ConnectionWorker` 구현 (구 SerialWorker 리팩토링)
    - [x] `ITransport` 주입 구조 적용
    - [x] QThread 기반 Loop 구현
- [x] `PortController` 구조 개선
    - [x] Transport 생성 및 Worker 주입 로직 구현
- [ ] `SerialManager` (PortRegistry) 구현
    - [ ] `model/serial_manager.py` 생성
    - [ ] 포트 레지스트리 및 수명 주기 관리 구현
- [ ] `PacketParser` 시스템 구현
    - [ ] `model/packet_parser.py` 생성
    - [ ] `ParserFactory` 구현

## Phase 5: UI 성능 최적화 (추가됨, 완료)
- [x] `QSmartListView` 구현 (`view/custom_widgets/smart_list_view.py`)
    - [x] QAbstractListModel 기반 로그 모델
    - [x] 검색(Find Next/Prev) 기능 구현
- [x] `ReceivedAreaWidget`에 QSmartListView 적용
- [x] `SystemLogWidget`에 QSmartListView 적용