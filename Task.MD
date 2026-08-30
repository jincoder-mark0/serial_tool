# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-30  
> 작업 브랜치: `refactor/presenter-view-boundary`  
> 안정 기준: `main`  
> 리팩토링 보고서: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)  
> 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

이 문서는 **현재 완료된 것과 앞으로 해야 할 것**만 관리한다. 과거 Phase/S-xxx 상세 이력은
`doc/task.md`, `doc/CHANGELOG.md`, `tasks/`에 보존한다.

상태 표기:

- `[x]` 완료
- `[ ]` 해야 함
- `[-]` 보류 / 재개 조건 필요

---

# 1. 현재 최우선 목표

기능 추가보다 **대규모 구조 리팩토링 검증 및 안정화**가 우선이다.

현재 순서:

```text
1. stale API / constructor 전수 감사
2. ruff 실행 및 수정
3. 구조 contract test 실행
4. lifecycle / shutdown / threading 고위험 test 실행
5. 전체 pytest 실행
6. 실패 기준 마지막 구조 교정
7. 문서 정합성 재검사
8. PR/merge 준비
9. 사용자 승인 후 squash/rebase 여부 결정
```

아직 현재 리팩토링 브랜치의 전체 pytest/ruff 통과는 확인되지 않았다.
검증 전에는 `완료`, `정상 동작`, `all tests passed`라고 선언하지 않는다.

---

# 2. 구조 리팩토링 — 완료

## 2.1 Single Composition Root / DI

- [x] `application_bootstrap.py` 도입
- [x] `ApplicationBootstrapper`를 유일한 runtime object graph owner로 지정
- [x] View state restore를 Presenter 생성보다 먼저 실행
- [x] 저장된 ManualControl state를 ControlState 계산보다 먼저 적용
- [x] Bootstrapper가 Model / Service / Presenter / Coordinator / MainPresenter까지 생성
- [x] `main.py`에서 개별 Presenter/Service 조립 제거
- [x] `MainPresenter`의 `ApplicationBootstrapper` 역의존 제거
- [x] `MainPresenter` 내부 `SettingsManager()` fallback 제거
- [x] `PortPresenter` 내부 `SettingsManager()` fallback 제거
- [x] `PortPresenter` 내부 `PortScanManager()` fallback 제거
- [x] `MacroPresenter` 내부 `MacroScriptManager()` fallback 제거
- [x] 주요 runtime dependency를 constructor로 명시적 주입

## 2.2 MainPresenter 축소

- [x] command transmission 구현 제거
- [x] settings persistence 구현 제거
- [x] system/data logging 구현 제거
- [x] port scan worker lifecycle 제거
- [x] macro script file I/O/QThread 제거
- [x] file transfer lifecycle/QThreadPool 제거
- [x] traffic statistics/logger 책임 제거
- [x] status timer 책임 제거
- [x] control enable/disable 정책 제거
- [x] View collection/tab iteration 제거
- [x] shortcut connect/disconnect/clear relay 제거
- [x] file-transfer dialog relay 제거
- [x] logging compatibility delegate/alias 제거
- [x] lifecycle manager 의존 제거

현재 MainPresenter는 전역 표시 이벤트와 종료 요청 처리만 담당한다.

## 2.3 Event topology 단일화

- [x] `presenter/event_router.py` 제거
- [x] `tests/test_event_router.py` 제거
- [x] 주요 runtime event를 direct Qt signal로 통일
- [x] PacketPresenter direct controller signal 사용
- [x] Macro Expect direct RX signal 사용
- [x] File transfer 완료/오류 direct signal 사용
- [x] production 주요 runtime path에서 EventBus 제거
- [x] `connection_closing` lifecycle signal 추가
- [x] 동일 이벤트의 `Qt Signal + EventBus + Router` 이중 전달 제거

## 2.4 Command Transmission

- [x] `CommandTransmissionService` 추가
- [x] prefix/suffix 처리 단일화
- [x] CommandProcessor 사용 위치 단일화
- [x] single/broadcast target resolution 단일화
- [x] connection validation/send 결과 단일화
- [x] Manual/Macro 중복 send 로직 제거
- [x] `TransmissionErrorCode` 도입
- [x] Macro worker thread의 QWidget/current-tab 조회 제거

## 2.5 ConnectionController 분해

- [x] `PacketParserManager` 분리
- [x] `ConnectionSessionFactory` 분리
- [x] concrete Transport 선택 책임 이동
- [x] ConnectionWorker 생성 책임 이동
- [x] parser registry/feed/flush 책임 이동
- [x] FileTransfer registry 제거
- [x] Controller가 file-transfer 기능을 알지 않도록 분리

## 2.6 Macro

- [x] `MacroExecutionCoordinator` 추가
- [x] 실행 시작 시 target port 문자열 snapshot
- [x] 반복 worker send handler 분리
- [x] single Row Send 전송 조정 분리
- [x] target port close 중단 정책 분리
- [x] `MacroScriptManager` 추가
- [x] MacroPresenter의 직접 file I/O 제거
- [x] MacroPresenter의 QThread lifecycle 제거
- [x] MacroScriptManager shutdown 연동
- [x] Macro Local Echo 정책 MainPresenter에서 제거

## 2.7 File Transfer

- [x] `FileTransferManager` 추가
- [x] FilePresenter에서 `FileTransferService` 생성 제거
- [x] FilePresenter에서 `QThreadPool` scheduling 제거
- [x] speed/ETA/session lifecycle Manager로 이동
- [x] 전용 QThreadPool 사용
- [x] shutdown 시 cancel → waitForDone 순서 구현
- [x] baudrate wait를 cancel 가능한 `Event.wait()` 방식으로 변경
- [x] target port `connection_closing` 시 transfer cancel

## 2.8 Port Scan

- [x] `PortScanManager` 추가
- [x] PortPresenter에서 `PortScanWorker` 생성 제거
- [x] `_scan_worker` Presenter 상태 제거
- [x] shutdown에서 `PortScanManager.stop()` 직접 호출
- [x] worker 종료까지 기다리는 lifecycle 정리

## 2.9 Logging / Traffic / Status

- [x] `LoggingCoordinator` 추가
- [x] port/system log lifecycle 분리
- [x] 다른 listener를 제거하는 broad `.disconnect()` 패턴 제거
- [x] `TrafficMonitor` 추가
- [x] DataTrafficHandler에서 logging/statistics 제거
- [x] DataTrafficHandler를 RX UI buffer/throttling 역할로 축소
- [x] `StatusCoordinator` 추가
- [x] 상태바 timer/statistics 갱신 분리

## 2.10 Settings / Control State

- [x] `SettingsCoordinator` 추가
- [x] Preferences/Theme/Language/Font persistence MainPresenter에서 제거
- [x] Preferences runtime propagation 단일화
- [x] `ControlStateCoordinator` 추가
- [x] current-tab + connection + broadcast enable 정책 단일화
- [x] View 내부 Manual/Macro enable 정책 제거
- [x] Manual state restore 이후 ControlState 계산 순서 보장

## 2.11 Shutdown / State Persistence

- [x] `ShutdownCoordinator` 추가
- [x] S-059 순서 유지: connection close → processEvents → data logger stop
- [x] FileTransfer/MacroScript/PortScan/DataHandler/Packet/Status shutdown 포함
- [x] 시스템 로그 writer close 포함
- [x] `ShutdownStateCollector`의 View state → Settings key adapter 수정
- [x] `ports` / `macro_panel` 저장 shape mismatch 수정
- [x] Auto Tx를 transient runtime state로 정의
- [x] shutdown에서 Auto Tx를 state 저장 전에 중지/체크 해제

## 2.12 View Boundary

- [x] MainWindow의 Connect command 직접 처리 제거
- [x] Theme/Language menu persistence 직접 처리 제거
- [x] Ctrl+O/F2 command route Presenter 경로로 통일
- [x] MainLeftSection의 중복 enable 정책 제거
- [x] Port color/log presentation 책임 View/LoggingCoordinator 쪽으로 이동
- [x] Presenter가 탭 내부 위젯 collection 구현을 직접 순회하지 않도록 정리

---

# 3. 테스트/회귀 안전망 — 구현 완료, 실행 검증 필요

- [x] `test_composition_root_contract.py`
- [x] `test_architecture_policy_boundaries.py`
- [x] `test_direct_event_topology.py`
- [x] `test_command_transmission_service.py`
- [x] `test_connection_session_factory.py`
- [x] `test_control_state_coordinator.py`
- [x] `test_file_transfer_manager.py`
- [x] `test_logging_coordinator.py`
- [x] `test_macro_execution_coordinator.py`
- [x] `test_macro_script_manager.py`
- [x] `test_manual_control_transient_state.py`
- [x] `test_port_presenter_sender_contract.py`
- [x] `test_settings_coordinator.py`
- [x] `test_shutdown_coordinator.py`
- [x] `test_status_coordinator.py`
- [x] `test_traffic_monitor.py`
- [x] Presenter→View facade contract 검사 보강
- [x] stale EventRouter 테스트 제거
- [x] 일부 옛 constructor/API 테스트를 새 graph 기준으로 마이그레이션

**주의:** 테스트 파일이 존재하는 것과 실제로 통과한 것은 다르다. 아래 P0 검증이 완료되기 전에는
현재 기준선을 확정하지 않는다.

---

# 4. P0 — 지금 해야 하는 검증 작업

## 4.1 stale API / constructor 전수 감사

- [ ] `MainPresenter(...)` 직접 생성 위치 전수 검색
  - 기대: production은 Bootstrapper만 생성
  - test도 가능한 경우 `runtime.main_presenter` 사용
- [ ] `PortPresenter(...)` 옛 2-argument/optional dependency 생성 검사
- [ ] `MacroPresenter(...)`에서 `MacroScriptManager` 미주입 호출 검사
- [ ] `MacroExecutionCoordinator(...)`의 `SettingsManager` 누락 호출 검사
- [ ] 제거된 `EventRouter` import/fixture/reference 검사
- [ ] `event_router.packet_received`, `settings_changed`, `port_closed` 등 옛 signal 사용 검사
- [ ] 제거된 MainPresenter 내부 필드 검사
  - `data_handler`
  - `settings_manager`
  - `status_coordinator`
  - `file_transfer_manager`
  - `port_scan_manager`
  - `macro_script_manager`
  - `macro_presenter`
  - `packet_presenter`
  - `port_presenter`
- [ ] 제거된 logging compatibility API 검사
  - `_sys_log_writer`
  - `_on_logging_*`
  - `_on_sys_logging_*`
  - `_on_system_log_line_appended`
- [ ] `controller.parsers` 내부 registry 접근 검사
- [ ] `_active_file_transfers` / `register_file_transfer` / `unregister_file_transfer` 검사
- [ ] `_scan_worker` / `PortScanWorker` Presenter 소유 가정 검사
- [ ] `ScriptLoadWorker`를 Presenter에서 import하는 테스트 검사
- [ ] `EventBus`를 production runtime에 다시 연결한 코드가 없는지 검사

## 4.2 Ruff

- [ ] `ruff check .`
- [ ] import 정리
- [ ] unused import/variable 정리
- [ ] line length / formatting 계열 수정
- [ ] 필요한 noqa는 규칙 번호 + 이유 명시
- [ ] ruff 0건 확인

## 4.3 Architecture / contract tests

먼저 작은 구조 테스트부터 실행한다.

- [ ] `tests/test_layer_dependencies.py`
- [ ] `tests/test_composition_root_contract.py`
- [ ] `tests/test_architecture_policy_boundaries.py`
- [ ] `tests/test_direct_event_topology.py`
- [ ] `tests/test_presenter_view_contract.py`
- [ ] `tests/test_port_presenter_sender_contract.py`

Acceptance:

- [ ] layer 역방향 import 0건
- [ ] Presenter가 bootstrap/composition root를 생성하지 않음
- [ ] runtime EventRouter 의존 0건
- [ ] Presenter→View 없는 API 호출 0건

## 4.4 고위험 lifecycle/threading tests

- [ ] `tests/test_shutdown_coordinator.py`
- [ ] `tests/test_shutdown_data_logger.py`
- [ ] `tests/test_file_transfer_manager.py`
- [ ] `tests/test_port_scan_shutdown.py`
- [ ] `tests/test_macro_script_manager.py`
- [ ] `tests/test_manual_control_transient_state.py`
- [ ] `tests/test_port_tab_cleanup.py`
- [ ] Macro worker View 접근 회귀 테스트

Acceptance:

- [ ] running QThread/QRunnable 잔존 없음
- [ ] shutdown data loss 없음
- [ ] Auto Tx transient state 저장 불일치 없음
- [ ] target port close 시 file/macro lifecycle 정상 종료

## 4.5 기능 핵심 tests

- [ ] `tests/test_command_transmission_service.py`
- [ ] `tests/test_presenter_manual_control.py`
- [ ] `tests/test_auto_tx.py`
- [ ] `tests/test_macro_execution_coordinator.py`
- [ ] `tests/test_parser_and_protocol.py`
- [ ] `tests/test_presenter_packet.py`
- [ ] `tests/test_file_transfer.py`
- [ ] `tests/test_integration_refactored.py`

## 4.6 전체 검증

Windows/PowerShell CI 기준:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
ruff check .
python tools/check_language_keys.py
python tools/check_task_boards.py
```

- [ ] 전체 pytest 통과
- [ ] ruff 0건
- [ ] language key integrity 통과
- [ ] task board consistency 통과
- [ ] 실제 실행한 test count를 이 문서에 기록
- [ ] CI PR run 확인

---

# 5. P1 — 테스트 실패 기준 마지막 구조 교정

테스트가 실패하면 **옛 테스트에 맞추기 위해 production architecture를 되돌리지 않는다.**
실패 원인을 먼저 아래 유형으로 분류한다.

## 5.1 constructor/API drift

- [ ] 테스트/호출부를 새 explicit DI 계약으로 이동
- [ ] 편의를 위해 production에 optional fallback을 다시 추가하지 않음

## 5.2 removed internal field 접근

- [ ] 실제 owner (`ApplicationComponents`, Manager, Coordinator) public API를 사용하도록 수정
- [ ] MainPresenter를 service locator로 다시 만들지 않음

## 5.3 signal topology mismatch

- [ ] direct Qt signal 소유권을 기준으로 수정
- [ ] EventRouter/EventBus bridge를 복구하지 않음

## 5.4 lifecycle failure

- [ ] 실제 QThread/QRunnable owner에서 수정
- [ ] Presenter에 worker ownership을 되돌리지 않음
- [ ] shutdown ordering을 보존

## 5.5 state persistence failure

- [ ] View DTO shape와 Settings key shape를 명시적으로 adapter 처리
- [ ] `ConfigKeys.*` 문자열을 View state dict key로 직접 가정하지 않음

---

# 6. P1 — 문서 현행화

- [x] `doc/refactoring_validation_report_20260830.md` 작성
- [x] `AGENTS.md` 현재 구조 기준으로 전면 개편
- [x] `doc/00_overview.md` EventBus/EventRouter 중심 설명 제거
- [x] `Task.MD` 현재 체크리스트로 재정리
- [ ] `README.md` 아키텍처/구조/테스트 기준선 현행화
- [ ] `CLAUDE.md` EventBus/EventRouter/Fast Path 과거 설명 정리
- [ ] `RULES.md` 현재 Single Composition Root/direct signal 규칙과 충돌 여부 감사
- [ ] `doc/implementation_plan.md` 완료/현재 구조와 충돌하는 계획 문구 감사
- [ ] `doc/CHANGELOG.md` 이번 리팩토링 세션 요약 추가
- [ ] 필요 시 `doc/history/session_summary_20260830.md` 작성

---

# 7. P2 — 구조 정리 후보

다음은 검증 Green 이후 판단한다. 지금 바로 수행하지 않는다.

- [-] `presenter/` 안의 Coordinator를 별도 `application/` 또는 `coordinator/` 패키지로 이동
  - 현재 기능 경계는 명확함
  - 파일 이동은 import churn이 매우 크므로 pytest Green 이후 판단
- [-] legacy `core/event_bus.py` 완전 삭제
  - production runtime에서는 사용하지 않음
  - conftest/core refinement test 의존 제거 후 판단
- [-] `SettingsManager` singleton 자체를 non-singleton으로 재설계
  - 현재 production DI는 명시적임
  - 범위가 크므로 별도 태스크화 필요
- [-] hardcoded timeout/status message duration 상수화
  - 구조 안정화 이후 낮은 우선순위

---

# 8. Merge / PR 준비

다음 조건을 모두 만족하기 전에는 `main` merge 준비 완료로 보지 않는다.

- [ ] stale API/constructor 전수 감사 완료
- [ ] ruff 0건
- [ ] architecture contract tests Green
- [ ] lifecycle/threading tests Green
- [ ] 전체 pytest Green
- [ ] language/task consistency 검사 Green
- [ ] README/CLAUDE/RULES/doc 문서 정합 완료
- [ ] `main` 대비 최종 diff 재감사
- [ ] PR 생성 또는 기존 PR 업데이트
- [ ] GitHub Actions CI Green
- [ ] 실제 테스트 환경/Mock/실기기 여부 기록
- [ ] 알려진 제한사항 기록

## Commit history 정리

현재 리팩토링 브랜치는 `main` 대비 다수의 중간 커밋이 누적돼 있다.

- [-] squash/rebase
  - **검증 Green 이후** 수행 여부 판단
  - destructive history rewrite이므로 사용자 명시 승인 없이 수행하지 않음

---

# 9. 후속 기능 후보 — 리팩토링 검증 후

현재는 착수하지 않는다.

- [-] SPI/I2C Transport
- [-] Plugin system
- [-] 가상 시리얼 실환경(com0com) 검증
- [-] 구조화 packet filter
- [-] trigger-based transmission
- [-] packet annotation / selected range export
- [-] TCP/UDP session

---

# 10. 완료 정의

리팩토링은 코드가 나뉘었다고 완료가 아니다.

다음을 만족해야 완료다.

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

검증하지 않은 항목은 체크하지 않는다.
