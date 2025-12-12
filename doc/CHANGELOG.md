# 변경 이력 (CHANGELOG)

## [미배포] (Unreleased)

---

### 아키텍처 안정화 및 핵심 기능 고도화 (2025-12-12)

#### 추가 사항 (Added)

- **설정 키 상수화 (ConfigKeys)**
  - `constants.py`에 `ConfigKeys` 클래스 추가 및 설정 경로 중앙 관리
  - 모든 설정 접근 로직(`SettingsManager.get/set`)에 상수 적용 완료

- **핵심 기능 로직 보강**
  - **매크로**: `ExpectMatcher` 구현 및 `_wait_for_expect` 응답 대기 로직 추가
  - **파일 전송**: 송신 큐 모니터링을 통한 Backpressure(역압) 제어 로직 추가
  - **성능**: `QSmartListView` 검색 입력에 디바운싱(300ms) 타이머 추가

#### 변경 사항 (Changed)

- **명명 규칙 및 구조 개선 (Renaming & Refactoring)**
  - **Data Logger**: `LogRecorder`를 `DataLogger`로 명칭 변경 (시스템 로그와 데이터 로깅의 역할 분리 명확화)
  - **Event System**: `PortController`의 중복된 이벤트 발행 구조를 제거하고 Signal-EventBus 자동 브리지 구현
  - **Macro Engine**: `QTimer` 기반 루프를 `QThread` + `QWaitCondition` 기반으로 전면 교체 (Windows 타이머 정밀도 문제 해결)
  - **Font Settings**: 폰트 설정 저장 로직을 View(`MainWindow`)에서 Presenter(`MainPresenter`)로 이관하고, 동적 키 생성(`f-string`) 대신 `ConfigKeys` 매핑 딕셔너리를 사용하여 MVP 원칙 준수 및 안전성 강화

- **코드 품질 및 테스트 안정성 (Quality & Stability)**
  - **Documentation**: `model/macro_runner.py` 등 핵심 모듈에 Google Style Docstring 가이드(WHY/WHAT/HOW, Logic)를 엄격히 적용하여 가독성 향상
  - **Thread Safety**: `MacroRunner`의 `_on_data_received` 및 `run` 루프 내 Mutex 잠금 범위를 최적화하여 경쟁 상태(Race Condition) 방지
  - **Test Reliability**: `test_model.py`의 비동기 시그널 대기 타임아웃을 연장(1s → 5s)하고 스레드 초기화 대기(`qtbot.wait`)를 보강하여 간헐적인 `TimeoutError` 해결

- **로직 최적화 및 수정**
  - **Flow Control**: 하드웨어 흐름 제어 설정에 따라 전송 지연(Sleep)을 조건부로 적용하도록 변경
  - **Error Handler**: `KeyboardInterrupt` 발생 시 기존 훅(`_old_excepthook`)을 호출하여 호환성 유지

#### 이점 (Benefits)

- **안정성 확보**: 대량 데이터 전송 및 고속 매크로 실행 시의 메모리 폭증 및 데이터 유실 방지
- **유지보수성 향상**: 문자열 리터럴 제거, 이벤트 흐름 단일화, 표준화된 주석 적용으로 코드 복잡도 감소
- **성능 개선**: 정규식 필터링 시 UI 프리징 현상 해결 및 매크로 타이밍 정밀도(1ms) 확보
- **신뢰성 높은 테스트**: 비동기 테스트 시나리오의 안정화로 CI/CD 신뢰도 향상
- **명확성 증대**: 시스템 로그와 데이터 로깅의 용어 분리로 개발자 혼동 방지

---

### Presenter 계층 구조화 및 MVP 리팩토링 (2025-12-12)

#### 추가 사항 (Added)

- **신규 Presenter 도입**
  - **`ManualCtrlPresenter`**: 수동 명령어 전송, Prefix/Suffix 처리, Hex 변환 로직을 전담
  - **`PacketPresenter`**: 패킷 데이터의 포맷팅(Timestamp, Hex/ASCII 변환) 및 설정 적용 로직 전담
  - **`FilePresenter`**: 파일 전송 진행률, 속도(Speed), 잔여 시간(ETA) 계산 로직 전담

- **View 인터페이스 강화 (Passive View)**
  - **Interface Methods**: Presenter가 View의 내부 위젯에 직접 접근하지 않도록 공개 메서드(`set_connected`, `append_local_echo_data`, `update_progress`) 구현
  - **Signal Bubbling**: 하위 위젯(`ManualCtrlWidget`)의 이벤트를 패널(`ManualCtrlPanel`)과 섹션(`MainLeftSection`)을 거쳐 최상위(`MainWindow`)로 전달하는 구조 구현

#### 변경 사항 (Changed)

- **MainPresenter 대규모 리팩토링**
  - View 내부 계층(`view.left_section.manual_ctrl...`)에 대한 직접 접근 코드를 전면 제거
  - `ManualCtrl`, `Packet`, `File` 관련 로직을 각 전담 Presenter로 이관하여 코드 비대화 해소
  - `EventRouter`와 `MainWindow`의 공개 인터페이스만을 사용하여 로직 조율

- **MVP 원칙 적용**
  - **PortPresenter**: `connect_btn` 등 위젯 직접 제어를 제거하고 시그널 구독 및 상태 변경 요청 방식으로 전환
  - **FileTransferDialog**: 내부의 계산 로직을 모두 제거하고, Presenter가 전달하는 데이터만 표시하는 수동적인 뷰로 전환
  - **Local Echo**: `MainPresenter` 내 하드코딩된 로직을 제거하고, View 인터페이스(Callback)를 통해 유연하게 처리

#### 이점 (Benefits)

- **결합도 감소**: Presenter가 View의 구체적인 구현(위젯 계층 구조)을 알 필요가 없어져 유지보수성 향상 (디미터 법칙 준수)
- **책임 분리 명확화**: 각 Presenter가 특정 도메인 로직만 담당하여 단일 책임 원칙(SRP) 강화
- **테스트 용이성 증대**: View의 로직이 제거되고 Presenter로 이동함에 따라, UI 없이 비즈니스 로직에 대한 단위 테스트 가능

---

### 코드 문서화 강화 (2025-12-12)

#### 추가 사항 (Added)

- **주석 가이드 준수 문서화**
  - 25개 핵심 파일에 WHY/WHAT/HOW 섹션 추가
  - Google Style Docstring 형식 100% 준수
  - Logic 섹션으로 복잡한 알고리즘 설명 강화

- **모듈별 문서화 완료**
  - **Core 모듈 (3개)**: event_bus, logger, settings_manager
  - **Model 모듈 (8개)**: macro_runner, file_transfer, port_controller, serial_manager, connection_worker, serial_transport, packet_parser, macro_entry
  - **Presenter 모듈 (5개)**: macro_presenter, main_presenter, port_presenter, file_presenter, event_router
  - **View 모듈 (5개)**: lang_manager, theme_manager, smart_plain_text_edit, smart_number_edit
  - **Entry/Config/Resource (4개)**: main.py, constants.py, resource_path.py
  - **Test 모듈 (1개)**: test_ui_translations_dynamic.py

#### 변경 사항 (Changed)

- **주석 간결성 개선**
  - "~합니다" → "~" 형태로 간결화
  - 불필요한 조사 제거
  - 명사형 종결로 통일

- **기술 용어 일관성 확보**
  - PyQt, PySerial, pathlib 등 영어 유지
  - Signal, Slot, Thread, Worker 등 PyQt 용어 영어 유지
  - Singleton, MVP, Pub/Sub, Factory 등 디자인 패턴 용어 영어 유지

- **Logic 섹션 추가 (17개 파일)**
  - 복잡한 알고리즘 흐름 명확화
  - 조건 분기 의도 설명
  - 에러 처리 로직 문서화
  - 버퍼 관리 및 메모리 보호 로직 설명

#### 이점 (Benefits)

- **가독성 향상**: 코드 의도를 명확히 전달하여 이해도 증대
- **유지보수성 개선**: 일관된 문서화 형식으로 코드 수정 용이
- **온보딩 효율화**: 신규 개발자가 코드베이스를 빠르게 이해 가능
- **자동 문서화 준비**: mkdocstrings 플러그인으로 자동 문서 생성 가능

---

### EventBus 싱글톤 수정 및 Presenter 계층 구조화 (2025-12-12)

#### 추가 사항 (Added)

- **EventRouter (이벤트 라우터)**
  - `presenter/event_router.py`: EventBus 이벤트를 PyQt 시그널로 변환하는 라우터 클래스
  - Port Events: `port_opened`, `port_closed`, `port_error`, `data_received`
  - Macro Events: `macro_started`, `macro_finished`, `macro_progress`
  - File Transfer Events: `file_transfer_progress`, `file_transfer_completed`
  - 스레드 안전한 UI 업데이트 보장

- **MacroPresenter (매크로 프레젠터)**
  - `presenter/macro_presenter.py`: MacroPanel과 MacroRunner를 연결하는 Presenter
  - 매크로 시작/정지, 단일 명령 전송 요청 처리
  - MacroRunner 시그널과 UI 연동

- **FilePresenter (파일 전송 프레젠터)**
  - `presenter/file_presenter.py`: 파일 전송 로직을 전담하는 Presenter
  - FileTransferEngine 관리 및 진행률 UI 업데이트
  - 전송 완료/에러 상태 처리

- **Core Refinement 테스트**
  - `tests/test_core_refinement.py`: ExpectMatcher 및 ParserType 상수 테스트
  - 문자열 매칭, 정규식 매칭, 버퍼 크기 제한, 파서 팩토리 생성 테스트

#### 수정 사항 (Fixed)

- **EventBus 싱글톤 패턴**
  - `core/event_bus.py`: 전역 `event_bus` 인스턴스 도입
  - `__new__` 메서드 제거, 모듈 레벨 싱글톤으로 단순화
  - `PortController`, `MacroRunner`, `FileTransferEngine`, `EventRouter`에서 전역 인스턴스 사용

- **PortController 시그널 복구**
  - 실수로 제거된 시그널 정의 복구
  - `port_opened`, `port_closed`, `error_occurred`, `data_received`, `data_sent`, `packet_received`

- **MacroRunner 시그널 불일치 수정**
  - `send_requested` 시그널 (4개 인자)과 `on_manual_cmd_send_requested` (5개 인자) 불일치 해결
  - `on_macro_cmd_send_requested` 중간 핸들러 추가

- **테스트 파라미터 수정**
  - `ExpectMatcher` 테스트: `feed()` → `match()` 메서드명 수정
  - `ExpectMatcher` 테스트: `timeout_ms` 파라미터 제거 (구현에 없음)
  - `ParserType` 테스트: 상수값 수정 (`"raw"` → `"Raw"` 등)

#### 변경 사항 (Changed)

- **MainPresenter 리팩토링**
  - `MacroPresenter`, `FilePresenter`, `EventRouter` 초기화 추가
  - `EventRouter` 시그널을 통한 포트 이벤트 처리로 변경
  - 파일 전송 로직을 `FilePresenter`로 위임

- **Model 계층 EventBus 통합**
  - `PortController`: 포트 상태 변경 시 EventBus 이벤트 발행
  - `MacroRunner`: 매크로 생명주기 이벤트 발행
  - `FileTransferEngine`: 파일 전송 진행률/완료 이벤트 발행

---

### Core 및 Model 기능 강화 (2025-12-11 - 심야 세션)

#### 추가 사항 (Added)

- **Global Error Handler (전역 에러 핸들러)**
  - `core/error_handler.py`: 처리되지 않은 예외(Uncaught Exception)를 포착하여 로깅하고 사용자에게 알림
  - `sys.excepthook` 오버라이딩을 통해 구현
  - `main.py`에 통합하여 애플리케이션 안정성 확보

- **ExpectMatcher (응답 대기 매처)**
  - `model/packet_parser.py`: 정규식(Regex) 및 문자열 리터럴 기반 매칭 클래스 구현
  - 매크로 실행 시 특정 응답을 대기하는 기능의 기반 마련

- **PacketParser 통합**
  - `model/port_controller.py`: `PacketParser`를 통합하여 수신된 Raw 데이터를 Packet 객체로 변환
  - `packet_received` 시그널 추가 및 `parsers` 딕셔너리를 통한 포트별 파서 관리
  - 설정(`parser_type`, `delimiter` 등)에 따른 파서 자동 초기화

- **FileTransferEngine (파일 전송 엔진)**
  - `model/file_transfer.py`: `QRunnable` 기반의 파일 전송 엔진 구현
  - 별도 스레드에서 실행되어 UI 블로킹 방지
  - Baudrate 기반 적응형 청크 전송 및 진행률(Progress) 시그널링
  - 전송 취소 기능 지원

#### 개선 사항 (Refinement & Hardening)

- **GlobalErrorHandler 스레드 안전성 확보**
  - `QObject` 상속 및 시그널/슬롯 패턴 적용
  - 워커 스레드에서 발생한 예외도 메인 UI 스레드에서 안전하게 다이얼로그 표시

- **ExpectMatcher 안정성 강화**
  - `max_buffer_size` 도입으로 메모리 무한 증가 방지 (기본 1MB)
  - 버퍼 초과 시 오래된 데이터 자동 삭제

- **PortController 캡슐화 및 확장**
  - `send_data_to_port` 메서드 추가로 특정 포트 대상 전송 지원
  - `FileTransferEngine`이 내부 `workers`에 직접 접근하지 않도록 개선

- **PacketParser 코드 품질 개선**
  - `ParserType` 상수 클래스 도입으로 하드코딩 문자열 제거
  - `ParserFactory` 및 `PortController`에서 상수 사용으로 유지보수성 향상

---

### UI 기능 보완 및 사용성 개선 (2025-12-11)

#### 추가 사항 (Added)

- **Packet Inspector 설정 UI**
  - `PreferencesDialog`에 `Packet` 탭 추가
  - Parser Type (Auto, AT, Delimiter, Fixed, Raw), Delimiter 설정, Fixed Length, AT Color Rules, Inspector Options UI 구현
  - 관련 설정 로드/저장 로직 구현

- **RX Newline 처리 옵션**
  - `RxLogWidget`에 Newline 모드 선택 콤보박스 (Raw, LF, CR, CRLF) 추가
  - 수신 데이터 줄바꿈 처리 로직 구현
  - 관련 언어 키 추가 (`ko.json`, `en.json`)

- **Main Status Bar 동적 업데이트**
  - `PortController`에 `data_sent` 시그널 추가
  - `MainPresenter`에서 1초 주기로 RX/TX 속도(KB/s) 계산 및 상태바 업데이트
  - 포트 연결/해제/에러 상태 실시간 표시 연동

- **전역 단축키 시스템**
  - `MainWindow`에 전역 단축키 등록
  - F2: 현재 포트 연결 (Connect)
  - F3: 현재 포트 연결 해제 (Disconnect)
  - F5: 현재 포트 로그 지우기 (Clear Log)
  - `MainPresenter`와 `PortPresenter` 연동하여 동작 구현

- **전이중 레코딩 (Full Duplex Recording)**
  - 송신(TX) 데이터와 수신(RX) 데이터를 모두 로그 파일에 기록하는 기능 구현
  - `MainPresenter`에서 데이터 송수신 이벤트를 캡처하여 `DataLoggerManager`로 전달
  - `RxLogWidget`의 로그 저장 버튼을 토글 방식으로 변경하고, 파일명에 탭 이름 포함

#### 변경 사항 (Changed)

- **문서 업데이트**
  - `doc/task.md`: Phase 2.5 완료 상태 반영

---

### 기능 개선 및 버그 수정 (2025-12-11)

#### 추가 사항 (Added)

- **MacroListWidget 컨텍스트 메뉴**
  - 우클릭 메뉴 추가: Add, Delete, Up, Down 기능 제공
  - 키보드 단축키 외에 마우스 조작 편의성 향상
  - **MacroListWidget 추가 기능 개선**
  - 매크로 추가 시 선택된 행 바로 아래에 삽입되도록 변경 (기존: 항상 맨 뒤 추가)
- **ManualControlWidget 히스토리 기능**
  - 최근 전송된 명령어 50개 기억 (MRU 방식)
  - 전송 버튼 상단에 히스토리 탐색(▲, ▼) 버튼 추가
  - Ctrl+Up/Down 키로도 히스토리 탐색 가능

- **리팩토링 (Refactoring)**
  - `PortController.open_port`: 개별 인자 대신 `config` 딕셔너리를 받도록 변경하여 확장성 확보
  - `MainWindow` 종료 로직을 `MainPresenter`로 이동하여 역할 분리 (MVP 패턴 강화)
  - `PortController`: 멀티포트 지원을 위해 다중 `ConnectionWorker` 관리 구조로 리팩토링

#### 변경 사항 (Changed)

- **에러 핸들링 및 로깅 개선**
  - `PortPresenter` 및 `MacroPanel`에서 `print` 문을 `logger`와 `QMessageBox`로 대체
  - 포트 미선택 시 Warning, 에러 발생 시 Critical 팝업 표시
  - 에러 상황을 로그 파일에 기록하여 디버깅 용이성 확보

- **PortSettingsWidget 로직 복원**
  - `get_current_config` 메서드 추가 및 `PortPresenter` 연동
  - 누락되었던 `on_protocol_changed`, `on_connect_clicked`, `on_port_scan_clicked` 메서드 복원
  - `set_connected` 메서드 추가로 호환성 확보
  - 포트 설정 및 연결 로직 정상화

- **ManualCtrlWidget UI 정리**
  - `RxLogWidget`과 중복되는 `Clear` 및 `Save Log` 버튼 제거
  - UI 레이아웃 재구성

- **RingBuffer 최적화**
  - `core/utils.py`: `memoryview` 슬라이싱을 사용하여 `write` 메서드 성능 개선
  - 불필요한 데이터 복사 최소화

#### 수정 사항 (Fixed)

- **QSmartListView 테두리 스타일**
  - `QSmartListView`에 객체 이름(`SmartListView`) 부여
  - `common.qss`, `dark_theme.qss`, `light_theme.qss`에서 ID 선택자(`#SmartListView`)를 사용하여 테두리 스타일 적용
  - `QGroupBox` 스타일과의 간섭 제거로 올바른 테두리 표시

- **RxLogWidget 버그 수정**
  - 존재하지 않는 `add_logs_batch` 메서드 호출을 `append_batch`로 수정하여 대량 로그 처리 오류 해결

#### 추가 사항 (Added) - 오후 세션

- **Local Echo (로컬 에코)**
  - `ManualCtrlWidget`에 로컬 에코 체크박스 추가
  - 송신 데이터를 수신창(`RxLogWidget`)에 표시하는 기능 구현
- **시스템 로그 및 타임스탬프 색상 규칙**
  - `ColorManager`에 `SYS_INFO`, `SYS_ERROR` 등 시스템 로그 규칙 추가
  - `TIMESTAMP` 규칙 추가 및 `get_rule_color` 메서드 구현
  - `SystemLogWidget` 및 `RxLogWidget`이 `ColorManager`를 통해 색상을 적용하도록 개선

#### 변경 사항 (Changed) - 오후 세션

- **경로 관리 리팩토링 (Path Management)**
  - `ResourcePath` 클래스 도입으로 리소스 경로 관리 일원화
  - `Paths` 클래스 대체 및 테마 아이콘 경로 처리 로직 개선
  - 주요 모듈(`main.py`, `settings_manager.py` 등) 업데이트
- **QSmartListView 리팩토링**
  - 타임스탬프 색상 처리 로직을 제거하고 순수 뷰어 역할로 변경
  - 색상 처리는 `RxLogWidget` 및 `SystemLogWidget`에서 수행

#### 수정 사항 (Fixed) - 오후 세션

- **RxLogWidget 버그 수정**
  - 존재하지 않는 `add_logs_batch` 메서드 호출을 `append_batch`로 수정하여 대량 로그 처리 오류 해결

#### 변경 사항 (Changed) - 저녁 세션

- **System Log 위치 변경**
  - `PortPanel` 내부에서 `MainLeftSection` 하단(전역)으로 이동
  - 탭별로 분산된 시스템 로그를 한곳에서 통합 관리하도록 개선
  - 공간 효율성 증대 및 포트 간 이벤트 순서 파악 용이성 확보
- **Manual Control UI 개선**
  - 불필요한 그룹박스(`manual_options_grp`, `manual_send_grp`) 제거
  - 레이아웃 재배치: 입력창/전송 버튼을 상단에, 옵션 체크박스를 하단에 배치하여 사용성 향상
  - 옵션 체크박스 레이아웃을 3열 2행으로 변경하여 가로 폭 절약
- **하단 UI 레이아웃 변경**
  - `ManualCtrlWidget`과 `SystemLogWidget`을 `MainLeftSection` 하단에 수직(`QVBoxLayout`)으로 배치
  - `SystemLogWidget`의 전체 높이를 100px로 고정(리스트 높이 고정 제거)하여 우측 패널(`MacroCtrlWidget`)과의 수평 라인 정렬 유도
  - `MacroCtrlWidget`의 `execution_settings_grp` 높이를 100px로 고정하여 좌측 패널(`SystemLogWidget`)과 높이 일치
  - 좌측 패널 구성: `PortTabs(Stretch)` - `ManualCtrl` - `SystemLog(Fixed)`

- **Model 계층 강화 (Phase 4)**
  - `SerialManager`: 싱글톤 스레드 안전성 강화 (QMutex 적용) 및 포트 관리 로직 개선
  - `ConnectionWorker`: TX 큐(`ThreadSafeQueue`) 도입으로 비동기 전송 구현, `time.monotonic()` 적용으로 타이밍 정밀도 향상
  - `SerialTransport`: 예외 처리 강화 (연결 끊김 감지 및 에러 전파)
  - `PacketParser`: `ATParser`, `DelimiterParser` 버퍼 크기 제한 추가 (메모리 보호), 임포트 최적화
  - `MacroRunner`: Expect 처리 구조 마련 및 비동기 실행 로직 개선

---

### View 계층 완성, 중앙 경로 관리, 아키텍처 및 리팩토링 (2025-12-10)

#### 리팩토링 (Refactoring)

- **통신 계층 추상화 (Transport Abstraction)**
  - `core/interfaces.py`: 모든 통신 드라이버가 구현해야 할 `ITransport` 인터페이스 정의
  - `model/transports.py`: PySerial을 감싸는 `SerialTransport` 구현체 작성
  - **목적**: SPI, I2C 등 향후 프로토콜 확장을 위한 기반 마련

#### 추가 사항 (Added)

- **로그 검색 기능 강화**
  - `QSmartListView` 내부에 검색 탐색(`find_next`, `find_prev`) 로직 구현
  - 검색어 일치 항목 하이라이트 및 자동 스크롤 이동 기능 추가

- **Parser 탭 구현 (PreferencesDialog)**
  - Parser Type 선택: Auto Detect, AT Parser, Delimiter Parser, Fixed Length Parser, Raw Parser
  - Delimiter 설정: 구분자 리스트 관리 (추가/삭제)
  - Fixed Length 설정: 패킷 길이 지정 (1-4096 바이트)
  - Inspector Options: 버퍼 크기, 실시간 추적, 자동 스크롤
  - 22개의 새로운 언어 키 추가 (en.json, ko.json)

- **중앙 집중식 경로 관리 (AppConfig)**
  - `config.py`: 모든 리소스 경로를 중앙에서 관리하는 `AppConfig` 클래스 생성
  - 개발 모드와 PyInstaller 번들 환경 자동 감지
  - 경로 검증 메서드 (`validate_paths()`)
  - `SettingsManager`, `LangManager`, `ThemeManager`에 AppConfig 통합

- **Package-level Imports**
  - `view/sections/__init__.py`: 섹션 클래스 export
  - `view/dialogs/__init__.py`: 다이얼로그 클래스 export
  - `main_window.py` import 구문 간결화

- **QSS 스타일 개선**
  - `section-title` 클래스 추가: QGroupBox::title과 유사한 스타일
  - `RxLogWidget.recv_log_title`, `StatusAreaWidget.status_log_title`에 적용
  - Dark/Light 테마별 색상 지정 (녹색/파란색)
  - `QSmartTextEdit` 스타일 추가 (공통, 다크, 라이트 테마)

- **수동 제어 (ManualCtrl) 개선**
  - `QSmartTextEdit` 도입: 라인 번호가 표시되는 멀티라인 에디터
  - 여러 줄 입력 지원 (Enter: 새 줄, Ctrl+Enter: 전송)
  - 플레이스홀더 텍스트 업데이트 ("Ctrl+Enter to send")

#### 버그 수정 (Fixed)

- **UI 레이아웃**
  - 우측 패널 토글 시 좌측 패널 크기가 변경되는 문제 수정
  - 스플리터 스트레치 팩터 조정 (좌: 0, 우: 1) 및 패널 너비 저장/복원 로직 개선
  - 윈도우 리사이즈 시 System Log 높이를 고정하고 Received Area만 늘어나도록 수정 (`setFixedHeight`)

#### 변경 사항 (Changed)

- **테마 및 스타일 (QSS)**
  - `QSmartListView` 및 `QSmartTextEdit`에 다크/라이트 테마 완벽 지원
  - `QSmartTextEdit`에 `Q_PROPERTY`를 추가하여 QSS에서 라인 번호 색상 제어 가능
  - `common.qss`에 `QSmartListView` 기본 스타일 추가
- **MVP 아키텍처 적용**
  - View 계층(`MacroPanel`, `MainLeftSection` 등)에서 `SettingsManager` 의존성을 완전히 제거했습니다.
  - View는 이제 스스로 파일을 저장하지 않고, `save_state() -> dict`와 `load_state(dict)` 메서드를 통해 상태 데이터만 주고받습니다.
  - 데이터의 영구 저장 및 복원 책임이 `MainWindow`(향후 `MainPresenter`)로 이관되어, UI와 비즈니스 로직(설정 관리)의 결합도가 낮아졌습니다.
  - `MainRightSection`에 하위 패널들의 상태를 집계하는 로직을 추가했습니다.

- **네이밍 일관성 개선**
  - `rx` → `recv`: RxLogWidget의 모든 변수 및 메서드명 변경
    - `on_clear_rx_log_clicked()` → `on_clear_recv_log_clicked()`
    - `rx_search_input` → `recv_search_input`
    - `rx_hex_chk` → `recv_hex_chk` 등
  - `manual_control` → `manual_ctrl`:
    - 파일명: `manual_control.py` → `manual_ctrl.py`
    - 클래스명: `ManualControlWidget` → `ManualCtrlWidget`
    - 설정 키: `"manual_control"` → `"manual_ctrl"`
  - 언어 키 통일:
    - `recv_lbl_log` → `recv_title`
    - `status_lbl_log` → `system_title`
    - `right_tab_inspector` → `right_tab_packet`
    - `pref_tab_parser` → `pref_tab_packet`

- **DTR/RTS 제거**
  - `PortSettingsWidget`에서 DTR/RTS 체크박스 제거
  - 포트 설정 2행 레이아웃 간소화 (Data | Parity | Stop | Flow)
  - 설정 저장/로드 로직에서 DTR/RTS 제거

- **파일 이동**
  - `view/widgets/main_toolbar.py` → `view/sections/main_tool_bar.py`
  - 섹션 관련 파일은 `sections/`에 통합

#### 수정 사항 (Fixed)

- **싱글톤 패턴 수정**
  - `SettingsManager`, `LangManager`의 `__new__` 메서드에 `*args, **kwargs` 추가
  - `TypeError: takes 1 positional argument but 2 were given` 오류 해결

- **경로 계산 수정**
  - `LangManager`의 하위 호환성 경로 계산 오류 수정
  - `view/tools/lang_manager.py`에서 3단계 상위 디렉토리로 이동하도록 수정

- **우측 패널 표시 상태 복원**
  - `MainWindow.init_ui()`에서 설정값 읽어서 메뉴 체크 상태 복원
  - `right_panel_visible` 설정 적용

- **clear_log() 메서드 개선**
  - `isinstance(current_widget, PortPanel)` 체크 제거
  - PortPanel import 제거로 의존성 감소

#### 아키텍처 개선 (Architecture)

- **Worker 구조 개선**
  - 파일명 변경: `model/serial_worker.py` → `model/connection_worker.py`
  - 클래스명 변경: `SerialWorker` → `ConnectionWorker`
  - **의존성 주입**: Worker가 특정 라이브러리(pyserial) 대신 `ITransport` 인터페이스에 의존하도록 변경
  - `PortController`: `SerialTransport`를 생성하여 `ConnectionWorker`에 주입하는 구조로 변경

- **ReceivedArea 동적 설정**
  - `set_max_lines(max_lines)` 메서드 추가
  - `MainPresenter`에서 설정 변경 시 모든 ReceivedArea 업데이트
  - `PortPresenter`에서 초기화 시 설정값 적용

- **PortState Enum 통합**
  - `core/port_state.py`: `DISCONNECTED`, `CONNECTED`, `ERROR` 상태 정의
  - `PortSettingsWidget.set_connection_state(PortState)` 구현
  - QSS 동적 속성 (`QPushButton[state="..."]`) 활용

- **SettingsManager 개선**
  - `_get_config_path`를 `@property`로 변경
  - AppConfig 통합으로 경로 관리 일원화

- **고성능 로그 뷰어 도입 (`QSmartListView`)**
  - 기존 `QTextEdit` 기반 로그 뷰를 `QListView` 기반의 `QSmartListView`로 교체
  - 대량의 로그 데이터 처리 시 메모리 사용량 감소 및 렌더링 성능 대폭 향상
  - `view/widgets/received_area.py` 및 `view/widgets/system_log.py`에 적용

#### 문서 업데이트 (Documentation)

- **doc/task.md**
  - Phase 2 완료 항목 추가 (ReceivedArea, PortState, Parser 탭, AppConfig)
  - Phase 3 상태를 "진행 중"으로 변경

- **doc/implementation_plan.md**
  - 최종 업데이트 날짜: 2025-12-10
  - 프로젝트 구조 업데이트 (AppConfig, **init**.py, 파일명 수정)

- **README.md**
  - 주요 기능 업데이트 (PortState, AppConfig, Package-level imports)
  - 용어 통일 (커맨드 → 매크로)

---

### 버그 수정 및 UI/UX 개선 (2025-12-09)

#### 수정 사항 (Fixed)

- **초기화 및 Import 오류 수정**
  - `MainWindow` 초기화 시 `AttributeError` (left_section 미생성 상태에서 시그널 연결) 수정
  - `PortController`에서 `SerialWorker` import 경로 오류 (`ModuleNotFoundError`) 수정
  - 애플리케이션 실행 안정성 확보

- **툴바 동작 로직 개선**
  - 'Close' 버튼이 토글 방식으로 동작하여 닫힌 포트를 여는 문제 수정
  - `close_current_port` 메서드 추가 및 `is_connected` 상태 확인 로직 도입
  - 명시적인 닫기 동작 보장

#### 변경 사항 (Changed)

- **시그널 네이밍 일관성 강화**
  - `MacroCtrlWidget`: `cmd_run_single` → `cmd_run_once`, `cmd_auto_start` → `cmd_repeat_start` 등
  - `PortSettingsWidget`: `scan_requested` → `port_scan_requested`
  - 버튼 텍스트 및 기능과 일치하도록 시그널 이름 직관화

- **테스트 코드 최신화**
  - `test_view.py`, `test_ui_translations.py`를 최신 위젯 클래스명(`RxLogWidget` 등) 및 시그널로 업데이트

- **네이밍 리팩토링 (Command -> Macro)**
  - `CommandListWidget` → `MacroListWidget`
  - `CommandControlWidget` → `MacroControlWidget`
  - `CommandListPanel` → `MacroPanel`
  - 관련 파일명 및 변수명 일괄 변경 (`command_list.py` → `macro_list.py` 등)
  - "Command" 용어의 모호성(시스템 명령 등) 해소 및 "Macro"로 명확화

- **설정 키 구조 정리**
  - `PreferencesDialog`에서 `port_baudrate`, `port_newline`, `port_scan_interval` 추가
  - `main_presenter.py`에서 설정 키 매핑 업데이트
  - 설정 로드/저장 로직 일관성 확보

#### 추가 사항 (Added)

- **동적 윈도우 리사이징**
  - 우측 패널(Right Panel) 토글 시 윈도우 크기가 자동으로 조정되는 기능 구현
  - 패널 숨김/표시 시 자연스러운 윈도우 크기 변화 제공
  - 좌측 패널 크기 유지: 스플리터 크기 설정으로 좌측 패널이 변경되지 않도록 수정

#### 아키텍처 개선 (Architecture)

- **MVP 패턴 준수 강화**
  - `PreferencesDialog`에서 `SettingsManager` 직접 접근 제거
  - Presenter(`MainWindow`)를 통해 설정을 전달받아 사용하도록 변경
  - `_get_setting()` 헬퍼 메서드 추가: 중첩된 설정 키 안전 접근
  - View 계층이 Model 계층에 직접 접근하지 않도록 개선

#### 완성도 개선 (Polish)

- **언어 키 완성**
  - `MainToolBar`: 모든 액션에 언어 키 적용 (`toolbar_open`, `toolbar_close` 등)
  - `MainMenuBar`: 메뉴 액션에 언어 키 적용 (`main_menu_open_port`, `main_menu_close_tab` 등)
  - `MacroCtrlWidget`: Pause 버튼 언어 키 추가 (`macro_ctrl_btn_repeat_pause`)
  - `PreferencesDialog`: Newline 설정 언어 키 추가 (`pref_lbl_newline`)

- **TODO 주석 정리**
  - 모든 TODO 주석을 Note로 변경하고 향후 구현 계획 명시
  - `macro_panel.py`: Repeat 파라미터 전달 방식 설명 추가
  - `port_presenter.py`, `main_presenter.py`: 상태바 에러 표시 계획 명시
  - `received_area.py`: 정규식 검색 지원 계획 명시

- **테마 메뉴 개선**
  - View -> Theme 메뉴에 현재 선택된 테마 체크 표시 추가
  - `MainMenuBar.set_current_theme()` 메서드 추가
  - 테마 전환 시 자동으로 체크 표시 업데이트

- **우측 패널 토글 개선**
  - 패널 숨김 시 왼쪽 패널 너비 저장
  - 패널 표시 시 저장된 왼쪽 패널 너비 복원
  - `_saved_left_width` 인스턴스 변수 추가

- **QSS 스타일 확장**
  - `warning` 클래스 추가 (노란색 버튼 스타일)
  - Pause 버튼에 warning 스타일 적용

---

### 언어 확장성 개선 및 아이콘 수정 (2025-12-08)

#### 추가 사항 (Added)

- **LanguageManager 확장성 개선**
  - `get_text()` 메서드에 optional `lang_code` 파라미터 추가
  - `get_supported_languages()` 메서드 추가: 지원되는 모든 언어 코드 목록 반환
  - `text_matches_key()` 헬퍼 메서드 추가: 텍스트가 특정 키의 어떤 언어 번역과 일치하는지 확인
  - 새 언어 추가 시 코드 수정 없이 자동 지원 가능

#### 수정 사항 (Fixed)

- **UI 아이콘 표시 문제**
  - `dark_theme.qss`, `light_theme.qss`에서 아이콘 선택자 수정
  - 버튼 objectName 불일치 해결: `add_btn` → `add_cmd_btn`, `del_btn` → `del_cmd_btn` 등
  - Command List 및 검색 버튼 아이콘이 정상적으로 표시됨

#### 변경 사항 (Changed)

- **언어 비교 로직 개선**
  - `manual_control.py`, `main_status_bar.py`, `file_progress.py`에서 하드코딩된 언어별 비교 제거
  - `== lang_manager.get_text("key", "en") or == lang_manager.get_text("key", "ko")` 패턴을
  - `lang_manager.text_matches_key(text, "key")` 호출로 변경
  - 일본어, 중국어 등 새 언어 추가 시 코드 수정 불필요

#### 이점 (Benefits)

- **확장성 향상**: 새 언어 추가 시 JSON 파일만 추가하면 자동 지원
- **유지보수성 개선**: 언어별 하드코딩 제거로 코드 간소화
- **UI 일관성**: 모든 아이콘 버튼이 테마에 맞게 정상 표시

---

### UI 요소 및 시그널/메서드 네이밍 리팩토링 (2025-12-08)

#### 변경 사항 (Changed)

- **UI 요소 이름 구체화**
  - `send_btn` → `send_manual_cmd_btn`, `clear_btn` → `clear_manual_options_btn` 등
  - `manual_control.py`, `received_area.py`, `tx_panel.py`, `command_control.py` 전체 적용
  - 모호한 변수명을 제거하고 컨텍스트와 기능을 명확히 함

- **시그널 및 메서드 네이밍 표준화**
  - 시그널: `[context]_[action]_requested` 패턴 적용 (예: `manual_cmd_send_requested`)
  - 핸들러: `on_[widget]_[event]` 패턴 적용 (예: `on_send_manual_cmd_clicked`)
  - `guide/naming_convention.md` 업데이트

#### 이점 (Benefits)

- **가독성 향상**: 코드만 보고도 어떤 UI 요소가 어떤 동작을 하는지 즉시 파악 가능
- **유지보수성 개선**: 명확한 네이밍으로 버그 발생 가능성 감소 및 협업 효율 증대

### 설정 다이얼로그 리팩토링 (2025-12-08)

#### 변경 사항 (Changed)

- **PreferencesDialog MVP 패턴 적용 및 리팩토링**
  - `load_settings`: `SettingsManager` 직접 사용하여 의존성 제거
  - `apply_settings`: 데이터 변환 로직(lower(), int() 등)을 View에서 제거하고 원본 데이터 전송
  - `MainWindow`에 `preferences_save_requested` 시그널 추가하여 이벤트 전달
  - `MainPresenter`에 `on_preferences_save_requested` 핸들러 구현하여 비즈니스 로직 처리

#### 이점 (Benefits)

- **아키텍처 준수**: View는 UI 로직만 담당하고, 데이터 검증 및 변환은 Presenter가 담당하여 MVP 패턴 강화
- **데이터 일관성**: `SettingsManager`를 단일 진실 공급원(SSOT)으로 사용
- **유지보수성**: 설정 로드/저장 로직이 명확하게 분리됨

### UI/UX 개선 및 버그 수정 (2025-12-08)

#### 추가 사항 (Added)

- **SmartNumberEdit 위젯**
  - `view/widgets/common/smart_number_edit.py` 신규 생성
  - HEX 모드와 일반 텍스트 모드 지원
  - HEX 모드 시 0-9, A-F, 공백만 입력 허용
  - 자동 대문자 변환 기능
  - `ManualControlWidget` 입력 필드에 적용

- **PortTabPanel 위젯**
  - `view/panels/port_tab_panel.py` 신규 생성 (기존 `PortTabWidget` 리네임)
  - 포트 탭 관리 로직 캡슐화 (추가/삭제/플러스 탭)
  - `LeftSection`에서 `QTabWidget` 대신 `PortTabPanel` 사용
  - 코드 재사용성 및 유지보수성 향상

- **테마별 SVG 아이콘 지원**
  - `ThemeManager.get_icon()` 메서드 추가
  - 테마에 따라 `resources/icons/{name}_{theme}.svg` 로드
  - `add_dark.svg`, `add_light.svg` 아이콘 생성
  - 플러스 탭에 테마별 아이콘 적용

- **포트 탭 이름 수정 기능**
  - 탭 이름 형식: `[커스텀명]:포트명`
  - 탭 더블클릭 시 커스텀 이름 수정 다이얼로그 표시
  - 포트 변경 시 자동으로 탭 제목 업데이트
  - 커스텀 이름 저장/복원 기능
  - `PortPanel`에 `tab_title_changed` 시그널 추가

#### 수정 사항 (Fixed)

- **MacroListWidget Send 버튼 상태 버그**
  - 행 이동 시 Send 버튼 활성화 상태가 초기화되는 문제 수정
  - `_move_row` 메서드에서 이동 전 버튼 상태 저장 후 복원

- **포트 탭 닫기 버튼 문제**
  - `insertTab` 사용 시 닫기 버튼이 사라지는 버그 수정
  - 플러스 탭 제거 → 새 탭 추가 → 플러스 탭 재추가 방식으로 변경
  - 모든 탭의 닫기 버튼이 정상적으로 표시됨

- **포트 탭 삭제 시 새 탭 생성 버그**
  - 탭 삭제 시 `on_tab_changed` 시그널로 인해 새 탭이 생성되는 문제 수정
  - `close_port_tab`에서 시그널 차단 및 적절한 탭으로 포커스 이동
  - 최소 1개의 포트 탭 유지 로직 추가

- **순환 import 문제**
  - `PortTabWidget`과 `PortPanel` 간 순환 import 해결
  - `TYPE_CHECKING`을 사용한 타입 힌트 분리
  - 런타임에만 필요한 곳에서 import 수행

#### 변경 사항 (Changed)

- **설정 키 일관성 확보**
  - `SettingsManager`, `PreferencesDialog`, `MainWindow`에서 `menu_theme`, `menu_language` 키 통일
  - `settings.json`의 `global.theme`, `global.language`와 내부 키 간 명확한 매핑 확립

- **LeftSection 리팩토링**
  - `PortTabWidget` 사용으로 탭 관리 코드 간소화
  - `add_new_port_tab`, `close_port_tab`, `on_tab_changed` 등 메서드 제거 (캡슐화)

#### 이점 (Benefits)

- **사용자 경험 향상**: HEX 모드 입력 제한으로 오류 방지, 탭 이름 수정으로 사용자 정의 가능
- **코드 품질 개선**: 위젯 캡슐화로 재사용성 및 유지보수성 향상
- **테마 일관성**: 모든 UI 요소에 테마가 올바르게 적용됨
- **안정성 향상**: 버튼 상태 및 탭 닫기 버그 수정으로 사용자 경험 개선

---

### 문서화 및 가이드 개선 (2025-12-05)

### 문서화 및 가이드 개선 (2025-12-05)

#### 추가 사항 (Added)

- **주석 가이드 문서**
  - `guide/comment_guide.md` 신규 생성: Google Style Docstring 표준 가이드
  - Google Style 정의 및 공식 문서 링크 추가
  - 모듈/클래스/함수 Docstring 작성 규칙 상세화
  - 인라인 주석 작성 규칙 (블록 주석, 분기문, 수식, TODO/FIXME/NOTE 태그)
  - MkDocs 자동 문서화 설정 가이드
  - 체크리스트 제공

- **Git 관리 가이드 문서**
  - `guide/git_guide.md` 신규 생성
  - 커밋 메시지 규칙 (Header/Body/Footer, 태그별 예시)
  - PR 및 이슈 템플릿 가이드
  - 실무 Git 레시피 (Amend, Stash, Reset/Revert 등 복구 명령어)
  - 브랜치 전략 상세

- **View 구현 계획 보강**
  - `view/doc/implementation_plan.md`에 Packet Inspector 설정 섹션 추가
  - Parser 타입 선택 (Auto/AT/Delimiter/Fixed Length/Raw)
  - Delimiter 설정 (기본값 + 사용자 정의)
  - AT Parser 색상 규칙 설정
  - Inspector 동작 옵션 (버퍼 크기, 실시간 추적, 자동 스크롤)
  - Preferences 다이얼로그 탭 UI 레이아웃 정의

#### 변경 사항 (Changed)

- **README.md 업데이트**
  - 프로젝트 설명: "시리얼 통신 유틸리티" → "통신 유틸리티" (SPI, I2C 확장 예정 명시)
  - 폴더 구조 정리: `guide/` 폴더 분리, 중복 파일 제거
  - 향후 계획 상세화: 단기/중장기 구분, FT4222/SPI/I2C 지원 로드맵 추가
  - 문서 참조 표 보강: 코딩 규칙, 명명 규칙 추가
  - Git 관리 가이드 강화: 지속적 백업 권장 명시

- **코드 스타일 가이드 간소화**
  - `guide/code_style_guide.md`에서 Docstring 상세 내용 제거 (117줄 → 31줄)
  - 주석 관련 내용을 `guide/comment_guide.md` 참조로 대체
  - 기본 원칙과 간단한 예시만 유지

- **구현 계획 우선순위 조정**
  - `view/doc/implementation_plan.md` 우선순위 섹션에서 일정 표기 제거
  - Packet Inspector 설정을 선택적 항목으로 추가

#### 이점 (Benefits)

- **문서 체계화**: 주석 가이드를 독립 문서로 분리하여 관리 용이
- **확장성 명시**: README에 향후 프로토콜 확장 계획 명확히 전달
- **개발 가이드 강화**: Google Style Docstring 표준 및 작성 규칙 상세화
- **View 계층 완성도**: Packet Inspector UI 설정 요구사항 문서화

### MVP 아키텍처 리팩토링 및 코드 품질 개선 (2025-12-05)

#### 변경 사항 (Changed)

- **MVP 아키텍처 준수**
  - `ManualControlWidget`에서 `SettingsManager` 직접 호출 제거
  - `send_command_requested` 시그널 변경: 3개 파라미터 → 4개 파라미터 (text, hex_mode, use_prefix, use_suffix)
  - View는 원본 사용자 입력과 체크박스 상태만 전달
  - prefix/suffix 처리 로직을 `MainPresenter.on_send_command_requested()`로 이동
  - View 계층에서 비즈니스 로직 40+ 라인 제거

- **네이밍 규칙 문서 통합**
  - `docs/naming_convention.md`에 모든 네이밍 규칙 통합 (클래스, 함수, 변수, 상수, 언어 키 등)
  - `doc/code_style_guide.md`에서 중복 내용 제거, 참조 링크로 대체
  - 단일 문서로 일관성 및 유지보수성 향상

- **Logger 싱글톤 패턴 개선**
  - 예외 발생 방식에서 `__new__` + `_initialized` 패턴으로 변경
  - `SettingsManager`와 동일한 구현 방식 적용
  - 다중 인스턴스 생성 시도 시 안전하게 동일 인스턴스 반환

- **설정 구조 리팩토링**
  - 평탄한 `global.*` 네임스페이스에서 논리적 그룹으로 재구조화
  - 새로운 그룹: `serial.*`, `command.*`, `logging.*`, `ui.*`
  - `main_window.py` `apply_preferences()` 메서드에 settings_map 추가
  - `main_presenter.py`에서 `global.command_prefix` → `command.prefix` 경로 변경
  - `settings.json` 구조 개선

#### 이점 (Benefits)

- **아키텍처 개선**: View와 Presenter 책임 분리 명확화, MVP 패턴 준수
- **문서 통합**: 단일 소스로 네이밍 규칙 참조, 문서 관리 일원화
- **안정성 향상**: Logger 싱글톤 패턴 개선으로 애플리케이션 안정성 증대
- **설정 관리**: 논리적 그룹화로 장기 유지보수 용이

### 문서 및 Preferences 다이얼로그 개선 (2025-12-04)

#### 변경 사항 (Changed)

- **코딩 스타일 가이드 업데이트**
  - `doc/code_style_guide.md`에 언어 키 네이밍 규칙 섹션(5.1) 추가
  - `[context]_[type]_[name]` 형식 엄격히 정의
  - UI 요소 타입별 분류 (`btn`, `lbl`, `chk`, `combo`, `input`, `grp`, `col`, `tab`, `dialog`, `txt`, `tooltip`)
  - 올바른/잘못된 예시 제공
  - 특수 케이스 문서화 (다이얼로그 타이틀, 상태 메시지, 필터 문자열)

- **설정 키 일관성 확보**
  - `SettingsManager`의 Fallback 설정 키를 `menu_theme`, `menu_language`로 통일
  - `PreferencesDialog`와 `MainWindow` 간의 설정 키 매핑 불일치 해결
  - `settings.json`의 `global.theme`, `global.language`와 내부 키(`menu_theme`, `menu_language`) 간의 명확한 매핑 로직 확립

- **Preferences 다이얼로그 접근성 수정**
  - `view/main_window.py`에서 `preferences_requested` 시그널 연결
  - `open_preferences_dialog()` 및 `apply_preferences()` 메서드 추가
  - 메뉴바 → View → Preferences 정상 작동
  - 테마 및 언어 변경 즉시 적용

#### 이점 (Benefits)

- 언어 키 네이밍에 대한 명확한 가이드라인 제공
- 신규 개발자 온보딩 시 참고 자료 확보
- Preferences 다이얼로그 접근성 개선
- 일관성 있는 코드베이스 유지

### UI 아키텍처 리팩토링 (2025-12-04)

#### 변경 사항 (Changed)

- **4단계 계층 구조 확립 (Window → Section → Panel → Widget)**
  - 기존 `LeftPanel`, `RightPanel`을 `LeftSection`, `RightSection`으로 리팩토링
  - 새 디렉토리 `view/sections/` 생성
  - `ManualControlPanel`, `PacketInspectorPanel` 래퍼 추가
  - 각 계층의 역할 명확화:
    - **Window**: 최상위 애플리케이션 셸 (`MainWindow`)
    - **Section**: 화면 구획 분할, Panel만 포함 (`LeftSection`, `RightSection`)
    - **Panel**: 기능 단위 그룹, Widget만 포함 (`PortPanel`, `MacroListPanel`, `ManualControlPanel` 등)
    - **Widget**: 실제 UI 요소 및 로직 (`PortSettingsWidget`, `ManualControlWidget` 등)
  - Presenter 계층 업데이트 (`port_presenter.py`, `main_presenter.py`)

#### 이점 (Benefits)

- 코드 구조의 일관성 및 가독성 향상
- 컴포넌트 책임 범위 명확화
- 유지보수 및 확장성 개선

### UI 개선 및 기능 강화 (2025-12-04)

#### 추가 사항 (Added)

- **ManualControlWidget 기능 확장**
  - 접두사(Prefix) 및 접미사(Suffix) 입력 필드 및 체크박스 추가
  - 데이터 전송 시 포맷팅 옵션 적용 기능

- **스크립트 저장/로드**
  - Command List 및 실행 설정을 JSON 파일로 저장/로드하는 기능 구현 (`MacroListPanel`)
  - `save_script_to_file`, `load_script_from_file` 메서드 추가

- **아이콘**
  - 검색 탐색 버튼용 아이콘 추가 (`find_prev`, `find_next`)

#### 수정 사항 (Fixed)

- **UI 아이콘 표시**
  - `MacroListWidget` 버튼의 objectName 불일치 수정 (`btn_add` → `add_btn` 등)으로 아이콘 미표시 문제 해결
- **테마 스타일**
  - 다크 테마에서 Placeholder 텍스트 색상 문제 수정 (`placeholder-text-color` 추가)

### 언어 키 표준화 및 로깅 프레임워크 (2025-12-03)

#### 추가 사항 (Added)

- **로깅 프레임워크**
  - `core/logger.py` 구현: 싱글톤 패턴 기반 Logger 클래스
  - 로그 레벨: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - 파일 로깅: RotatingFileHandler (10MB x 5개 파일)
  - 콘솔 로깅: 색상 구분 출력
  - 타임스탬프 자동 추가

- **자동화 테스트**
  - `tests/test_ui_translations.py`: UI 컴포넌트 번역 자동 검증
  - 8개 위젯/패널 언어 전환 테스트 (6개 통과)

- **도구**
  - `tools/manage_lang_keys.py` 개선: 자동 모듈 탐지 기능

#### 변경 사항 (Changed)

- **언어 키 표준화**
  - 모든 언어 키를 `[context]_[type]_[name]` 규칙으로 리팩토링
  - `en.json`, `ko.json` 업데이트 (192개 키)
  - 모든 UI 컴포넌트의 `get_text()` 호출 수정
  - 주석 제거 및 JSON 구조 정리

- **MainWindow 구조 개선**
  - `MainMenuBar`를 별도 위젯으로 분리 (`view/widgets/main_menu_bar.py`)
  - `MainStatusBar`를 별도 위젯으로 분리 (`view/widgets/main_status_bar.py`)
  - 코드 재사용성 및 가독성 향상

- **로깅 개선**
  - `ThemeManager`, `LanguageManager`의 print 문을 logger 호출로 교체
  - 구조화된 로그 메시지 형식

#### 수정 사항 (Fixed)

- **About Dialog**: `MainWindow`에서 시그널 연결 누락 수정
- **manage_lang_keys.py**: 하드코딩된 모듈 리스트 제거, 자동 탐지로 개선

### View 계층 마무리 및 다국어 지원 (2025-12-02)

#### 추가 사항 (Added)

- **다국어 지원 (Phase 1)**
  - LanguageManager 확장: 50+ UI 문자열 추가 (한국어/영어)
  - MainWindow 메뉴 시스템 한글화 (파일, 보기, 도움말 메뉴)
  - 윈도우 제목 및 상태바 한글화
  - 언어 동적 변경 핸들러 구현 (on_language_changed)
  - PortSettingsWidget 부분 한글화 (포트, 스캔, 보레이트 버튼)
  - **리팩토링**: 언어 리소스를 코드에서 JSON 파일로 분리 (`config/languages/*.json`)

- **commentjson 지원**
  - 모든 JSON 파일 처리에 commentjson 라이브러리 적용
  - JSON 파일에 주석 사용 가능 (가독성 향상)
  - 설정 파일 및 언어 파일에 설명 주석 추가 가능

- **설정 관리 개선**
  - 설정 저장 위치를 `config/settings.json`으로 변경 (프로젝트 루트에서 config 폴더로)
  - SettingsManager에 싱글톤 패턴 적용하여 설정 동기화 문제 해결

- **위젯 상태 저장/복원 구현**
  - ManualControlWidget: 입력 텍스트, HEX 모드, RTS/DTR 상태 저장/복원
  - ReceivedArea: 검색어, HEX 모드, 타임스탬프, 일시정지 상태 저장/복원
  - CommandControl: 초기화 문제 수정 및 상태 저장/복원 안정화
  - MacroListPanel: 초기화 순서 변경으로 load_state 오류 해결

#### 수정 사항 (Fixed)

- **ThemeManager**: `load_theme()` 메서드의 `@staticmethod` 데코레이터 제거 (NameError 방지)
- **ColorRulesManager**: 설정 파일 경로 계산 오류 수정 (`parent.parent.parent` → `parent.parent`)
- **MainWindow**:
  - Import 구문을 파일 상단으로 이동 (코드 스타일 가이드 준수)
  - `on_language_changed` 및 `_save_window_state` 메서드 복구
- **PortSettingsWidget**: 필수 메서드 복원 (`set_port_list`, `set_connected`)
- **CommandControl**: SyntaxError 수정 (중복 코드 제거)
- **MacroListPanel**: 초기화 순서 변경으로 상태 복원 시 오류 해결
- **탭 관리**:
  - 포트 탭 증식 문제 수정 (재시작 시 탭이 계속 추가되던 버그)
  - LeftPanel의 탭 추가 로직 개선
- **About Dialog**: 구현 완료 및 manage_lang_keys.py JSON 주석 처리 개선
- **manage_lang_keys.py**: JSON 파싱 오류 처리 추가

#### 변경 사항 (Changed)

- **test_view.py**: PreferencesDialog, AboutDialog, FileProgressWidget, Language 테스트 케이스 추가
- **디버그 로깅**:
  - 모든 주요 컴포넌트에 저장/복구 디버그 로그 추가 (개발 중)
  - 검증 완료 후 디버그 로그 제거

### 듀얼 폰트 시스템 (2025-12-01)

#### 추가 사항 (Added)

- **폰트 시스템 개선**
  - Proportional Font (가변폭): UI 요소 (메뉴, 상태바, 레이블, 버튼 등)에 적용
  - Fixed Font (고정폭): TextEdit, CommandList 등 데이터 표시 영역에 적용
  - 폰트 설정 대화상자 구현

- **테마 시스템**
  - 중앙 집중식 QSS 기반 테마 관리 구현 (`view/theme_manager.py`)
  - 다크 테마 (`resources/themes/dark_theme.qss`) 및 라이트 테마 (`resources/themes/light_theme.qss`) 생성
  - View 메뉴를 통한 동적 테마 전환
  - 폰트 커스터마이징 메뉴 (사전 정의 폰트 및 커스텀 폰트 대화상자)

- **SVG 아이콘 시스템**
  - 아이콘 리소스 디렉토리 생성 (`resources/icons/`)
  - 테마 인식 SVG 아이콘 구현 (다크 테마용 흰색, 라이트 테마용 검은색)
  - 아이콘: Add, Delete, Up, Down, Close, ComboBox 화살표
  - objectName 선택자를 통한 QSS 기반 아이콘 로딩 적용

- **UI 컴포넌트**
  - `PortSettingsWidget`: 컴팩트한 2줄 레이아웃
    - 1행: 포트 | 스캔 | 보레이트 | 열기
    - 2행: 데이터 | 패리티 | 정지 | 흐름 | DTR | RTS
  - `MacroListWidget`:
    - Prefix/Suffix 컬럼 추가 (이전 Head/Tail에서 변경)
    - 3단계 Select All 체크박스 (선택 안함, 부분 선택, 전체 선택)
    - 세로 스크롤바 항상 표시
    - 행별 Send 버튼
  - `MacroCtrlWidget`:
    - 전역 명령 수정을 위한 Prefix/Suffix 입력 필드 추가
    - 스크립트 저장/로드 버튼
    - 자동 실행 설정 (지연시간, 최대 실행 횟수)

#### 변경 사항 (Changed)

- **디렉토리 구조 재정리**
  - `view/resources/` → `resources/` (루트로 이동)
  - `view/styles/` → `resources/themes/` (테마 파일 통합)
  - `view/styles/theme_manager.py` → `view/theme_manager.py`
  - 모든 QSS 파일 내 아이콘 경로 업데이트 (`view/resources/` → `resources/`)

- **레이아웃 최적화**
  - `CommandControl`에서 `CommandList` 헤더로 Select All 체크박스 이동
  - 일관성을 위한 컴포넌트 크기 조정
  - Port combo 너비를 Baud combo와 동일하게 맞춤
  - 명확성을 위해 UI 요소 간 간격 추가

- **명명 규칙**
  - `CommandList` 및 `CommandControl` 전체에서 "Head/Tail"을 "Prefix/Suffix"로 변경
  - 관련된 모든 레이블, 툴팁 및 변수명 업데이트

#### 수정 사항 (Fixed)

- 두 테마 모두에서 ComboBox 드롭다운 화살표가 이제 표시됨
- 탭 닫기 버튼 아이콘이 올바르게 테마 적용됨
- Select All 체크박스가 이제 개별 행 체크박스 변경에 반응함
- Import 오류 수정 (QCheckBox, QSizePolicy)

### View 계층 개선 및 설정 관리 (2025-12-01)

#### 추가 사항 (Added)

- **View 기능 강화**
  - **색상 규칙 (Color Rules)**: `ReceivedArea`에 특정 패턴(OK, ERROR 등) 강조 기능 추가 (`config/color_rules.json`)
  - **로그 최적화 (Log Trim)**: 2000줄 초과 시 자동 삭제 기능으로 메모리 관리
  - **타임스탬프**: 수신 데이터에 타임스탬프(`[HH:MM:SS]`) 표시 옵션 추가
  - **파일 전송 UI**: ManualControlWidget에 파일 선택 및 전송 UI 추가

- **설정 관리 시스템**
  - `SettingsManager` 구현: `config/settings.json` 및 사용자 설정 관리
  - 상태 저장: 창 크기, 위치, 테마 설정을 종료 시 자동 저장 및 시작 시 복원

- **테스트 도구**
  - 독립 테스트 앱 (`tests/test_view.py`): View 컴포넌트(위젯)를 메인 로직 없이 독립적으로 테스트 가능

#### 수정 사항 (Fixed)

- `ManualControlWidget`: `file_selected` 시그널 누락 수정
- `LeftPanel`: 탭 추가 로직(`add_plus_tab`) 오류 수정
- `PortPresenter`: 파일 손상 복구 및 안정화
- `MainPresenter`: 문법 오류 수정

### UI/UX 개선 및 테마 리팩토링 (2025-12-01)

#### 변경 사항 (Changed)

- **ManualControlWidget 개선**:
  - 레이아웃을 컴팩트하게 조정 (불필요한 여백 제거)
  - 입력창을 `QTextEdit`에서 `QLineEdit`으로 변경하여 높이 축소
  - Send 버튼 높이 조정 및 스타일 적용
  - Flow Control (RTS/DTR) 체크박스 추가
- **MacroCtrlWidget 개선**:
  - 레이아웃 정리 및 버튼 배치 최적화
  - Start Auto Run (녹색), Stop (붉은색) 버튼에 강조 스타일 적용
- **MainWindow 개선**:
  - 좌우 패널 스플리터 비율을 2:1에서 1:1로 조정하여 균형 개선
- **테마 시스템 리팩토링**:
  - `common.qss` 도입으로 공통 스타일 통합 관리
  - `ThemeManager`가 공통 스타일과 개별 테마를 병합하여 로드하도록 개선
  - 라이트 테마에서 비활성화된 버튼의 시인성 개선 (틴트 색상 적용)

### 프로젝트 구조 (2025-11-30)

#### 추가 사항 (Added)

- MVP 아키텍처 확립
- 모듈식 폴더 구조 생성:
  - `view/panels/`: LeftPanel, RightPanel, PortPanel, MacroListPanel
  - `view/widgets/`: PortSettings, CommandList, CommandControl, ManualControl
  - `resources/themes/`: 테마 관리자 및 QSS 파일
  - `resources/icons/`: SVG 아이콘
  - `doc/`: 문서 및 계획 파일

#### 변경 사항 (Changed)

- 프로젝트 이름을 "SerialManager"에서 "SerialTool"로 변경
- UI를 LeftPanel(포트 + 수동 제어) 및 RightPanel(커맨드 리스트 + 패킷 인스펙터)을 사용하도록 리팩토링
- 미사용 파일 제거 (rx_log_view.py, status_bar.py 등)

## 버전 이력 (Version History)

### [1.0.0] - 개발 중

#### 완료 (Completed)

- ✅ 프로젝트 설정 및 구조
- ✅ UI 골격 구현
- ✅ 테마 및 스타일링 시스템
- ✅ UI 레이아웃 최적화
- ✅ SVG 아이콘 시스템
- ✅ 위젯 개선 및 다듬기
- ✅ 디렉토리 구조 재정리
- ✅ View 계층 마무리 (다이얼로그, 다국어 지원)
- ✅ Command List 영속성 구현

#### 진행 중 (In Progress)

- 🔄 Core 유틸리티 (RingBuffer, ThreadSafeQueue)
- 🔄 Model 계층 (SerialWorker, PortController)
- 🔄 Presenter 통합

#### 계획 (Planned)

- ⏳ Command List 자동화 엔진
- ⏳ 파일 전송 기능
- ⏳ 플러그인 시스템
- ⏳ 테스트 및 배포

---

**범례:**

- ✅ 완료
- 🔄 진행 중
- ⏳ 계획됨
- 🐛 버그 수정
- ⚡ 성능 개선
- 🎨 UI/UX 향상
