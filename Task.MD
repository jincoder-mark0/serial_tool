# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-30
> 작업 브랜치: `refactor/presenter-view-boundary`
> 안정 기준: `main`
> 리팩토링 보고서: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)
> 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

이 문서는 **현재 완료된 것과 앞으로 해야 할 것**만 관리한다. 과거 Phase/S-xxx 상세 이력은
`doc/task.md`, `doc/CHANGELOG.md`, `tasks/`에 보존한다.

상태 표기: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 보류

---

# 1. 현재 최우선 목표

기능 추가보다 **대규모 구조 리팩토링 검증 및 안정화**가 우선이다.

```text
1. stale API / constructor 전수 감사
2. ruff 실행 및 수정
3. 구조 contract test 실행
4. lifecycle / shutdown / threading 고위험 test 실행
5. 핵심 feature test 실행
6. 전체 pytest 실행
7. 실패 기준 마지막 구조 교정
8. 문서/CHANGELOG 최종 동기화
9. PR/CI Green 확인
10. 사용자 승인 후 squash/rebase 여부 결정
```

2026-08-30 로컬 검증에서 전체 pytest/ruff와 저장소 정합 검사는 Green을 확인했다.
`main` 대비 전체 diff 감사와 마지막 구조 교정도 완료했다.
PR #1의 GitHub Actions Python 3.11 CI까지 4/4 job Green을 확인했다.

---

# 2. 구조 리팩토링 — 완료

## Composition Root / DI

- [x] `application_bootstrap.py` 도입
- [x] `ApplicationBootstrapper`를 유일한 runtime object graph owner로 지정
- [x] View state restore → Presenter → Coordinator → MainPresenter 생성 순서 통합
- [x] Bootstrapper가 MainPresenter까지 생성
- [x] `main.py`에서 개별 Presenter/Service 조립 제거
- [x] MainPresenter의 bootstrap/composition root 역의존 제거
- [x] Main/Port/Macro Presenter의 hidden runtime fallback 생성 제거
- [x] 주요 runtime dependency constructor 주입

## MainPresenter 축소

- [x] command transmission 구현 제거
- [x] settings persistence 구현 제거
- [x] RX/data logging/status timer 책임 제거
- [x] port scan/macro script/file transfer worker lifecycle 제거
- [x] control enable policy 제거
- [x] View collection traversal 제거
- [x] shortcut/file-dialog static relay 제거
- [x] logging compatibility API 제거
- [x] lifecycle manager 의존 제거

현재 MainPresenter는 전역 사용자 표시와 shutdown 요청 처리를 중심으로 한다.

## Event topology

- [x] `presenter/event_router.py` 제거
- [x] `tests/test_event_router.py` 제거
- [x] 주요 runtime event direct Qt signal 통일
- [x] Packet/Macro/File 이벤트 direct path 적용
- [x] production 주요 runtime path에서 EventBus 제거
- [x] `connection_closing` lifecycle signal 추가
- [x] Qt Signal + EventBus + Router 이중 전달 제거

## Command / Connection

- [x] `CommandTransmissionService` 추가
- [x] prefix/suffix/command processing/target resolution/send 단일화
- [x] Manual/Macro 중복 send 제거
- [x] `TransmissionErrorCode` 도입
- [x] Macro worker의 QWidget/current-tab 조회 제거
- [x] `PacketParserManager` 분리
- [x] `ConnectionSessionFactory` 분리
- [x] Controller의 transport/parser/file-transfer 책임 축소

## Macro / File / Port worker lifecycle

- [x] `MacroExecutionCoordinator` 추가
- [x] `MacroScriptManager` 추가
- [x] MacroPresenter file I/O/QThread 제거
- [x] `FileTransferManager` 추가
- [x] FilePresenter Service/QThreadPool lifecycle 제거
- [x] FileTransfer cancel/shutdown 및 전용 pool 적용
- [x] `PortScanManager` 추가
- [x] PortPresenter scan worker ownership 제거

## Logging / Traffic / Settings / Runtime State

- [x] `LoggingCoordinator` 추가
- [x] `TrafficMonitor` 추가
- [x] DataTrafficHandler를 RX UI batching으로 축소
- [x] `StatusCoordinator` 추가
- [x] `SettingsCoordinator` 추가
- [x] `ControlStateCoordinator` 추가
- [x] View 내부 settings/control policy 제거

## Shutdown / Persistence

- [x] `ShutdownCoordinator` 추가
- [x] connection close → processEvents → DataLogger stop 순서 보존
- [x] FileTransfer/MacroScript/PortScan/DataHandler/Packet/Status shutdown 통합
- [x] `ShutdownStateCollector` View shape → Settings path adapter 수정
- [x] ports/macro state 저장 shape mismatch 수정
- [x] Auto Tx transient state 정의 및 저장 전 stop

---

# 3. 테스트 안전망 — 로컬/PR 실행 검증 완료

- [x] composition root contract
- [x] architecture policy boundaries
- [x] direct event topology
- [x] command transmission service
- [x] connection session factory
- [x] control state coordinator
- [x] file transfer manager
- [x] logging coordinator
- [x] macro execution coordinator
- [x] macro script manager
- [x] manual control transient state
- [x] port presenter sender contract
- [x] settings coordinator
- [x] shutdown coordinator
- [x] status coordinator
- [x] traffic monitor
- [x] Presenter→View facade contract 보강
- [x] 일부 stale constructor/API 테스트 마이그레이션

---

# 4. P0 — 검증 결과

## 4.1 stale API / constructor 전수 감사

- [x] `MainPresenter(...)` 직접 생성 전수 검사
  - production은 Bootstrapper만 생성
  - test도 가능한 경우 `runtime.main_presenter` 사용
- [x] `PortPresenter(...)` 옛 optional dependency 호출 검사
- [x] `MacroPresenter(...)`의 MacroScriptManager 누락 호출 검사
- [x] `MacroExecutionCoordinator(...)` SettingsManager 누락 검사
- [x] 제거된 EventRouter import/fixture/reference 검사
- [x] `event_router.packet_received/settings_changed/port_closed` 검사
- [x] 제거된 MainPresenter 내부 필드 검사
  - `data_handler`, `settings_manager`, `status_coordinator`
  - `file_transfer_manager`, `port_scan_manager`, `macro_script_manager`
  - `macro_presenter`, `packet_presenter`, `port_presenter`
- [x] 제거된 logging compatibility API 검사
- [x] `controller.parsers` 내부 registry 접근 검사
- [x] `_active_file_transfers` 및 register/unregister API 검사
- [x] Presenter `_scan_worker` / PortScanWorker ownership 가정 검사
- [x] Presenter `ScriptLoadWorker` import 검사
- [x] EventBus production runtime 재연결 코드 검사

## 4.2 Ruff

- [x] `ruff check .`
- [x] import/unused/undefined-name 정리
- [x] 필요한 noqa에 규칙 번호 + 이유 기록
- [x] ruff 0건 확인

## 4.3 Architecture / contract tests

- [x] `tests/test_layer_dependencies.py`
- [x] `tests/test_composition_root_contract.py`
- [x] `tests/test_architecture_policy_boundaries.py`
- [x] `tests/test_direct_event_topology.py`
- [x] `tests/test_presenter_view_contract.py`
- [x] `tests/test_port_presenter_sender_contract.py`

Acceptance:

- [x] layer 역방향 import 0건
- [x] Single Composition Root 유지
- [x] runtime EventRouter 의존 0건
- [x] Presenter→View 없는 API 호출 0건

## 4.4 Lifecycle / Threading

- [x] `tests/test_shutdown_coordinator.py`
- [x] `tests/test_shutdown_data_logger.py`
- [x] `tests/test_file_transfer_manager.py`
- [x] `tests/test_port_scan_shutdown.py`
- [x] `tests/test_macro_script_manager.py`
- [x] `tests/test_manual_control_transient_state.py`
- [x] `tests/test_port_tab_cleanup.py`
- [x] Macro worker View 접근 회귀 테스트

Acceptance:

- [x] running QThread/QRunnable 잔존 없음
- [x] shutdown data loss 없음
- [x] Auto Tx 저장 상태 불일치 없음
- [x] target port close 시 file/macro 정상 종료

## 4.5 핵심 기능

- [x] `tests/test_command_transmission_service.py`
- [x] `tests/test_presenter_manual_control.py`
- [x] `tests/test_auto_tx.py`
- [x] `tests/test_macro_execution_coordinator.py`
- [x] `tests/test_parser_and_protocol.py`
- [x] `tests/test_presenter_packet.py`
- [x] `tests/test_file_transfer.py`
- [x] `tests/test_integration_refactored.py`

## 4.6 전체 검증

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

- [x] 전체 pytest Green
- [x] ruff Green
- [x] language key integrity Green
- [x] task board consistency Green
- [x] 실제 passed/failed/skipped count 기록
- [x] PR GitHub Actions Green

2026-08-30 로컬 검증 결과 (Python 3.13.15, Windows, offscreen):

```text
architecture contract: 33 passed
lifecycle/data-preservation: 45 passed
core feature: 75 passed
full pytest: 643 passed, 0 failed, 0 skipped, 2 dependency warnings
ruff: 0 errors
language keys: success (dynamic expression warnings 7건)
task board: 78 historical tasks consistent
```

2026-08-30 PR #1 GitHub Actions 결과 (Python 3.11 / GitHub-hosted runners):

```text
test-windows: success
lang-keys: success
task-boards: success
lint: success
SerialTool CI: 4/4 Green
```

---

# 5. 테스트 실패 시 교정 원칙

## constructor/API drift

- [ ] 테스트/호출부를 새 explicit DI 계약으로 이동
- [ ] production에 optional fallback 재추가 금지

## removed internal field

- [ ] 실제 owner public API / ApplicationComponents 사용
- [ ] MainPresenter service-locator화 금지

## signal topology mismatch

- [ ] direct Qt signal 기준 수정
- [ ] EventRouter/EventBus bridge 복구 금지

## lifecycle failure

- [ ] 실제 QThread/QRunnable owner에서 수정
- [ ] Presenter worker ownership 복구 금지
- [ ] shutdown ordering 보존

## state persistence failure

- [ ] View DTO shape와 Settings path explicit adapter 사용
- [ ] ConfigKeys 문자열을 View state 직접 key로 가정 금지

---

# 6. 문서 현행화

- [x] `doc/refactoring_validation_report_20260830.md`
- [x] `AGENTS.md`
- [x] `README.md`
- [x] `CLAUDE.md`
- [x] `RULES.md`
- [x] `doc/00_overview.md`
- [x] `tests/README.md`
- [x] `Task.MD`
- [x] `doc/implementation_plan.md` 감사
  - 초기 설계/역사 계획 문서로 의도적으로 보존
  - 현재 구현 기준으로 사용하지 않음
- [x] `doc/history/session_summary_20260830.md`
- [x] `doc/CHANGELOG.md`

---

# 7. P2 — Green 이후 판단할 구조 후보

- [-] Coordinator를 별도 `application/` / `coordinator/` package로 이동
  - 기능 경계는 이미 명확
  - import churn이 크므로 Green 이후 판단
- [-] legacy `core/event_bus.py` 완전 삭제
  - production runtime 미사용
  - conftest/core test 의존 제거 후 판단
- [-] SettingsManager singleton 자체 제거
  - production DI는 이미 명시적
  - 별도 대규모 태스크 필요
- [-] timeout/status duration 상수화

---

# 8. Merge / PR 준비

- [x] stale API/constructor 감사 완료
- [x] ruff Green
- [x] architecture contract Green
- [x] lifecycle/threading Green
- [x] full pytest Green
- [x] language/task consistency Green
- [x] `doc/CHANGELOG.md` 최종 기록
- [x] README/AGENTS/CLAUDE/RULES/doc 최종 정합 확인
- [x] `main` 대비 최종 diff 재감사
- [x] PR 생성/업데이트 — PR #1
- [x] GitHub Actions CI Green — 4/4 jobs
- [ ] Mock/LOOPBACK/실기기 검증 범위 기록
- [ ] 알려진 제한사항 기록

## Commit history

- [-] squash/rebase
  - 검증 Green 이후 판단
  - destructive history rewrite이므로 사용자 승인 없이 수행하지 않음

---

# 9. 후속 기능 후보

리팩토링 merge 판단 전에는 착수하지 않는다.

- [-] SPI/I2C Transport
- [-] Plugin system
- [-] com0com 실환경 검증
- [-] 구조화 packet filter
- [-] trigger-based transmission
- [-] packet annotation / selected-range export
- [-] TCP/UDP session

---

# 10. 리팩토링 완료 정의

```text
Architecture ownership clear
        +
No stale API / constructor
        +
No hidden runtime fallback
        +
No worker -> QWidget access
        +
No duplicate event topology
        +
ruff Green
        +
pytest Green
        +
CI Green
        +
Docs match code
```

자동 검증 조건은 모두 충족했다. merge 전 남은 항목은 검증 범위/제한사항 기록과 commit history 처리 여부 결정이다.
