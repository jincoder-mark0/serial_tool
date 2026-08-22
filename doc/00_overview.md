# 프로젝트 개요 (Project Overview)

**SerialTool**은 Python(PyQt5) 기반의 고성능 멀티포트 시리얼 통신 유틸리티입니다.
엄격한 **MVP 아키텍처**와 **이벤트 기반 통신(EventBus)**을 채택하여 유지보수성과 확장성을 극대화했습니다.

---

## 1. 핵심 아키텍처 (Core Architecture)

본 프로젝트는 **Strict MVP (Model-View-Presenter)** 패턴을 따릅니다.

### 1.1 계층 구조
* **View (Passive View)**: UI 렌더링 및 사용자 입력 수신. 비즈니스 로직을 포함하지 않으며, 오직 `Presenter`와 `DTO`를 통해 통신합니다. (`view/`)
* **Presenter (Supervisor)**: View와 Model 사이의 중재자. UI 이벤트를 비즈니스 로직으로 변환하고, Model의 상태 변화를 UI에 반영합니다. (`presenter/`)
* **Model (Business Logic)**: 데이터 처리, 통신 제어, 상태 관리 등 핵심 로직을 담당합니다. (`model/`)
* **Core (Infrastructure)**: 전역 설정, 이벤트 버스, 로깅, 통신 드라이버 등 기반 서비스를 제공합니다. (`core/`)
* **Common (Shared Data)**: DTO, Enum, Constants 등 계층 간 공유되는 데이터 구조입니다. (`common/`)

### 1.2 데이터 흐름
1.  **View -> Presenter**: 사용자 액션(버튼 클릭 등)을 시그널로 전달.
2.  **Presenter -> Model**: 비즈니스 메서드 호출 (예: `open_connection`).
3.  **Model -> EventBus**: 상태 변경, 패킷 및 데이터 이벤트 발행 (Publish).
4.  **EventBus -> Router -> Presenter**: 이벤트를 라우팅하여 Presenter에게 전달.
5.  **Presenter -> View**: DTO를 통해 UI 업데이트 (`apply_state`).

> **예외 (Fast Path)**: 시리얼 데이터 수신 시 `ConnectionController` -> `DataTrafficHandler` -> `MainWindow`로 직접 연결하고, 30ms 단위로 UI를 갱신합니다. 같은 데이터의 EventBus 경로는 매크로 Expect와 패킷 처리 등에 사용됩니다.

---

## 2. 주요 기능 및 모듈

| 모듈 | 설명 | 주요 클래스 |
| :--- | :--- | :--- |
| **Port Management** | 다중 포트 연결 및 설정 관리 | `PortPresenter`, `ConnectionController`, `PortSettingsWidget` |
| **Data Visualization** | 대량 로그 데이터 고속 렌더링 | `DataLogWidget`, `QSmartListView` |
| **Macro Automation** | 커맨드 리스트 순차/반복 실행 | `MacroPresenter`, `MacroRunner`, `MacroPanel` |
| **File Transfer** | 청크 기반 파일 전송 및 진행률 표시 | `FilePresenter`, `FileTransferService` |
| **Packet Inspection** | 수신 데이터 파싱 및 구조화 | `PacketPresenter`, `PacketParser` |

---

## 3. 개발 가이드 요약

* **명명 규칙**: `get/set`은 단순 접근자에만 사용하고, 무거운 작업은 `export/import`, `load/save` 등을 사용합니다.
* **상태 관리**: View의 상태는 `get_state()`와 `apply_state()` 메서드로 관리하며, 영구 저장은 `SettingsManager`가 담당합니다.
* **테스트**: `tests/conftest.py`의 공용 Fixture를 활용하여 단위/통합 테스트를 작성합니다.

## 4. 현재 상태와 제약

* 통신 구현은 `SerialTransport`만 제공하며 SPI/I2C Transport는 없습니다.
* 패킷 설정 UI는 존재하지만 연결 생성 시 현재 `RawParser`가 기본으로 사용됩니다.
* 사용자 설정은 배포(PyInstaller 번들) 시 `%APPDATA%\SerialTool\settings.json`, 개발 모드에서는 `resources/configs/settings.local.json`에 분리 저장됩니다(S-013/S-043 완료). 저장소의 `resources/configs/settings.json`은 최초 배포 시의 기본값 원본으로만 사용됩니다.
* 자동화 테스트는 Core, Model, Presenter, View 및 주요 통합 흐름 367개를 검증합니다.
* 성능 벤치마크(S-011)·패키징(S-012)·CI(S-014)는 완료되었습니다. 가상 시리얼 포트(com0com) 실환경 검증(S-010)만 후속 작업입니다.

---

## 5. 문서 구조

* `doc/00_overview.md`: 본 문서.
* `doc/history/`: 과거 세션 요약 및 변경 이력.
* `doc/implementation_plan.md`: 상세 구현 계획.
* `doc/task.md`: 작업 진행 상황 트래킹.
