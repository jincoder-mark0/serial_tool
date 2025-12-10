### 아키텍처 리팩토링 및 성능 최적화 (2025-12-10)

#### 리팩토링 (Refactoring)
- **통신 계층 추상화 (Transport Abstraction)**
  - `core/interfaces.py`: 모든 통신 드라이버가 구현해야 할 `ITransport` 인터페이스 정의
  - `model/transports.py`: PySerial을 감싸는 `SerialTransport` 구현체 작성
  - **목적**: SPI, I2C 등 향후 프로토콜 확장을 위한 기반 마련

- **Worker 구조 개선**
  - 파일명 변경: `model/serial_worker.py` → `model/connection_worker.py`
  - 클래스명 변경: `SerialWorker` → `ConnectionWorker`
  - **의존성 주입**: Worker가 특정 라이브러리(pyserial) 대신 `ITransport` 인터페이스에 의존하도록 변경
  - `PortController`: `SerialTransport`를 생성하여 `ConnectionWorker`에 주입하는 구조로 변경

#### 성능 개선 (Performance)
- **고성능 로그 뷰어 도입 (`QSmartListView`)**
  - 기존 `QTextEdit` 기반 로그 뷰를 `QListView` 기반의 `QSmartListView`로 교체
  - 대량의 로그 데이터 처리 시 메모리 사용량 감소 및 렌더링 성능 대폭 향상
  - `view/widgets/received_area.py` 및 `view/widgets/system_log.py`에 적용

#### 기능 추가 (Added)
- **로그 검색 기능 강화**
  - `QSmartListView` 내부에 검색 탐색(`find_next`, `find_prev`) 로직 구현
  - 검색어 일치 항목 하이라이트 및 자동 스크롤 이동 기능 추가
