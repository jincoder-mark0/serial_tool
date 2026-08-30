# Session Summary — 2026-08-30

## 목적

`refactor/presenter-view-boundary` 브랜치에서 진행한 구조 리팩토링을 정리하고,
`main` 대비 변경 내용을 문서화한 뒤 **stale API/constructor 감사 → ruff/pytest → CI** 단계로 전환한다.

---

## 이번 세션의 핵심 구조 변경

### Composition Root

- `application_bootstrap.py` 도입
- `ApplicationBootstrapper`가 전체 runtime object graph를 생성
- View 초기 state restore부터 MainPresenter 생성까지 조립 순서를 한 곳으로 통합
- `main.py`는 resource/UI application 준비와 bootstrap 호출만 담당

### Event topology

- production 주요 runtime 이벤트를 direct Qt signal로 통일
- `presenter/event_router.py` 제거
- `tests/test_event_router.py` 제거
- EventBus + EventRouter + Qt Signal 이중 경로 제거

### MainPresenter

God Presenter 성격을 해체했다.

MainPresenter에서 제거한 주요 책임:

- Settings persistence
- command processing/transmission
- RX UI buffer/throttling
- data/system logging implementation
- status timer/statistics
- port scan worker lifecycle
- macro script I/O/QThread
- file-transfer service/QThreadPool lifecycle
- control enable policy
- port-tab collection traversal
- static shortcut/file-dialog relay
- composition/bootstrap fallback

현재 MainPresenter는 connection/macro/file/manual 결과의 전역 사용자 표시와 shutdown 요청 처리를 중심으로 한다.

### 신규/분리된 Model / Service

- `CommandTransmissionService`
- `ConnectionSessionFactory`
- `PacketParserManager`
- `FileTransferManager`
- `MacroScriptManager`
- `PortScanManager`
- `TrafficMonitor`

### 신규/분리된 Coordinator

- `MacroExecutionCoordinator`
- `LoggingCoordinator`
- `SettingsCoordinator`
- `ControlStateCoordinator`
- `StatusCoordinator`
- `ShutdownCoordinator`

### Thread / Lifecycle

- worker를 생성하는 owner가 종료 책임도 갖도록 정리
- FileTransfer cancel/shutdown 및 전용 QThreadPool 적용
- PortScanManager가 scan QThread 수명 소유
- MacroScriptManager가 load worker 수명 소유
- shutdown data-preservation 순서 유지
- Auto Tx를 transient runtime state로 정의하고 저장 전에 중지

### State persistence

`ShutdownStateCollector`의 View state shape와 Settings key path가 혼용되던 문제를 수정했다.

```text
View ports -> ConfigKeys.PORTS_TABS_STATE
View macro_panel.commands -> ConfigKeys.MACRO_COMMANDS
View macro_panel.control_state -> ConfigKeys.MACRO_CONTROL_STATE
```

---

## 테스트/안전망 변경

신규 또는 강화된 주요 테스트:

- `test_composition_root_contract.py`
- `test_architecture_policy_boundaries.py`
- `test_direct_event_topology.py`
- `test_command_transmission_service.py`
- `test_connection_session_factory.py`
- `test_control_state_coordinator.py`
- `test_file_transfer_manager.py`
- `test_logging_coordinator.py`
- `test_macro_execution_coordinator.py`
- `test_macro_script_manager.py`
- `test_manual_control_transient_state.py`
- `test_port_presenter_sender_contract.py`
- `test_settings_coordinator.py`
- `test_shutdown_coordinator.py`
- `test_status_coordinator.py`
- `test_traffic_monitor.py`

일부 기존 테스트의 EventRouter/옛 constructor/옛 내부 필드 의존도 새 구조로 마이그레이션했다.

**중요:** 이번 세션 환경에서는 전체 pytest/ruff를 실제 실행하지 못했다.
따라서 테스트 Green 또는 통과 개수를 아직 확정하지 않는다.

---

## 문서 현행화

현재 코드와 직접 연결되는 문서를 현행화했다.

- `AGENTS.md`
  - 현재 architecture/branch/검증 규칙의 최상위 에이전트 지침으로 전면 개편
- `Task.MD`
  - 과거 이력 중심 문서에서 현재 완료/잔여 체크리스트로 재구성
- `README.md`
  - EventBus/EventRouter 중심 구조 삭제
  - Single Composition Root/direct Qt signal/Coordinator 구조 반영
  - 과거 고정 test baseline 제거
- `CLAUDE.md`
  - 현재 AGENTS.md를 정본으로 사용하도록 전환
  - EventRouter/MainPresenter Fast Path 과거 규칙 제거
- `RULES.md`
  - 현재 검증 규율과 direct signal/composition root 기준으로 갱신
  - 과거 `497 passed` 고정 baseline 제거
- `doc/00_overview.md`
  - current architecture와 문서 source-of-truth 관계 정리
- `tests/README.md`
  - 현재 stale audit/ruff/architecture/lifecycle/full pytest 검증 순서 반영
- `doc/refactoring_validation_report_20260830.md`
  - main 대비 주요 변경과 검증 계획 신규 작성

### 의도적으로 역사 문서로 유지

- `doc/implementation_plan.md`
  - 초기 설계와 과거 계획을 보존하는 문서
  - 현재 architecture 정본으로 사용하지 않음
- `doc/task.md`
  - 과거 Phase별 완료 이력
- 과거 `tasks/S-xxx-*.md`
  - 당시 작업의 상세 근거/검증 기록

---

## 현재 다음 작업

`Task.MD` P0 순서에 따라 진행한다.

1. stale API / constructor 전수 감사
2. `ruff check .`
3. architecture contract tests
4. lifecycle/threading tests
5. 핵심 feature tests
6. full pytest
7. language-key/task-board 검사
8. 실패 기준 마지막 구조 교정
9. `doc/CHANGELOG.md`에 검증 결과 포함 최종 리팩토링 항목 기록
10. PR CI Green 확인

---

## Merge 전 조건

- stale API/constructor 0건
- ruff Green
- architecture contract Green
- lifecycle/threading Green
- full pytest Green
- language/task consistency Green
- PR GitHub Actions Green
- 문서와 현재 코드 정합

커밋 history squash/rebase는 위 검증 완료 후 사용자 승인 시에만 수행한다.
