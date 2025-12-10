serial_tool2/
├── config.py                # 중앙 경로 관리 (AppConfig) [완료]
├── core/                    # 핵심 유틸리티 및 인프라
│   ├── interfaces.py       # ITransport 인터페이스 [신규]
│   ├── event_bus.py        # EventBus (Pub/Sub)
│   ├── utils.py            # RingBuffer, ThreadSafeQueue
│   ├── logger.py           # 로깅 시스템 [완료]
│   ├── settings_manager.py # 설정 관리 [완료]
│   └── port_state.py       # PortState Enum [완료]
├── model/                   # 비즈니스 로직 및 Worker
│   ├── transports.py       # SerialTransport 등 통신 구현체 [신규]
│   ├── connection_worker.py # 범용 통신 Worker (구 serial_worker) [리팩토링]
│   ├── port_controller.py  # 포트 라이프사이클 관리 [수정]
│   ├── serial_manager.py   # 멀티포트 레지스트리
│   ├── packet_parser.py    # 패킷 파싱
│   ├── macro_runner.py     # Macro List 실행 엔진
│   └── file_transfer.py    # 파일 전송 엔진
├── view/                    # UI 계층 [완료]
│   ├── custom_widgets/     # 커스텀 위젯
│   │   ├── smart_list_view.py # 고성능 로그 뷰어 [신규]
... (나머지는 동일)

### 4. Model 계층 (Model Layer)

#### [완료] `model/transports.py` & `model/connection_worker.py`
**통신 추상화 및 Worker 구현**
- **ITransport**: 통신 인터페이스 정의 (`open`, `close`, `read`, `write`)
- **SerialTransport**: PySerial을 래핑하여 ITransport 구현
- **ConnectionWorker**:
    - 하드웨어에 독립적인 통신 루프 구현
    - Controller로부터 Transport 객체를 주입받아 동작 (Dependency Injection)
    - 시그널: `data_received`, `error_occurred`, `connection_opened/closed`

#### [진행 중] `model/port_controller.py`
**포트 라이프사이클 관리**
- 역할: Worker 스레드 관리 및 Transport 객체 생성/주입
- 상태 머신: `DISCONNECTED` ↔ `CONNECTING` ↔ `CONNECTED` ↔ `ERROR`