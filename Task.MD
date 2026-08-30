# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-30
> 기준 브랜치: `main`
> Presenter/View Boundary 리팩토링: PR #1 squash merge 완료
> Post-merge 통합 로드맵: [`doc/plans/roadmap_post_merge.md`](doc/plans/roadmap_post_merge.md)
> 최종 환경 검증 계획: [`doc/plans/environment_validation_plan.md`](doc/plans/environment_validation_plan.md)
> 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

이 문서는 **현재 완료 상태와 앞으로 해야 할 일을 실제 권장 착수 순서대로 관리하는 유일한 작업 보드**다.
상태 표기: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 보류·판단 필요

---

# 1. 현재 기준선

```text
PR #1 squash merge: 완료
Local Windows / Python 3.13.15: 643 passed
Ruff: 0 errors
Language key integrity: Green
Task board consistency: Green
PR Python 3.11 GitHub Actions: 4/4 Green
main push CI: Green
```

현재 단계는 **P2 debt/성능 정리 → P3 기능 확장 → P4 최종 환경/배포 검증**이다.

---

# 2. 앞으로 해야 할 업무 — 권장 실행 순서

아래 번호가 실제 권장 착수 순서다. P2/P3/P4 명칭보다 **선행 의존성, 회귀 리스크, 검증 비용**을 우선한다.

## P2-A — Low-risk 구조 정리

상세: [`architecture_cleanup_plan.md`](doc/plans/architecture_cleanup_plan.md)

1. [x] timeout/status duration/poll interval 상수화
   - worker/background/file-transfer polling은 기존 canonical constant 사용 확인
   - MainPresenter status message duration `0/3000/5000 ms`를 의미별 named constant로 정리
   - literal contract regression test 추가, PR #2 GitHub Actions 4/4 Green
2. [x] legacy `core/event_bus.py` 완전 삭제
   - `core/event_bus.py` 및 `common.constants.EventTopics` 제거
   - EventBus 전용 autouse fixture / unit tests / stale constants contract 제거
   - direct event topology test가 EventBus/EventTopics 재도입을 차단
   - PR #3 Python 3.11 full pytest: `639 passed, 2 warnings`, GitHub Actions 4/4 Green

WHY:

- runtime behavior 변경이 거의 없는 작업부터 처리
- benchmark와 이후 확장에서 stale policy/dead code가 판단 노이즈가 되는 것을 방지

## P2-B — 성능 측정 및 증거 기반 최적화

상세: [`performance_optimization_plan.md`](doc/plans/performance_optimization_plan.md)

3. [x] benchmark scenario/baseline 재고정
   - 기존 `tools/benchmark.py` Core micro benchmark는 유지
   - `tools/runtime_benchmark.py` 신규: DataTrafficHandler RX pipeline + 실제 ConnectionWorker QThread mixed RX/TX scenario
   - metric: RX/TX throughput, elapsed, RX batch count, stop latency
   - synthetic transport는 benchmark fixture 자체가 병목이 되지 않도록 immutable bytes + offset 소비
   - CI는 성능 threshold가 아니라 scenario 실행/byte-preservation/result schema만 검증
   - 기준 문서: [`doc/runtime_benchmark_baseline_spec_20260830.md`](doc/runtime_benchmark_baseline_spec_20260830.md)
   - PR #4 최신 검증: Python 3.11 `643 passed, 2 warnings`, GitHub Actions 4/4 Green
4. [x] RxLogView `BatchRenderer` 필요성 benchmark 기반 재평가
   - 결론: **별도 BatchRenderer 도입하지 않음 / 현재 DataTrafficHandler + LogModel batching 유지**
   - `LogModel.add_logs()` batch insert는 single-row control 대비 약 `5.5~5.8x` 처리량
   - ASCII decode/formatting overhead는 약 `0~3%`로 dominant bottleneck 아님
   - event-loop/paint servicing overhead는 약 `21~28%`
   - flush-size matrix: `4 KiB=0.813 MB/s`, `16 KiB=3.191 MB/s`, `64 KiB=11.935 MB/s`
   - update 횟수 `16x` 감소 시 처리량 `14.675x` 증가 -> 병목은 update fixed cost이며 upstream batching이 올바른 해결 위치
   - 기준 결과: [`doc/benchmarks/rx_view_baseline_20260830.md`](doc/benchmarks/rx_view_baseline_20260830.md)
   - 실제 2/4-port 고속 RX, 실제 화면/HEX bottleneck이 확인될 때만 재검토
5. [-] Serial non-blocking I/O loop 후보안 비교/최적화
   - **software optimization 완료 / 실제 USB Serial acceptance 미완료**
   - baseline: Windows synthetic mixed RX/TX에서 16 MiB RX를 10 s 내 완료하지 못함 (`3,301,376 / 16,777,216 bytes`)
   - Candidate A (`usleep(100 us)` activity-aware): 동일하게 timeout -> 폐기
   - Candidate B: 실제 I/O activity가 있으면 `yieldCurrentThread()`, pending-only는 busy wait, 완전 idle은 1 ms wait -> 채택
   - Candidate B synthetic repeat=3: RX `226.700 MB/s`, TX `56.675 MB/s`, elapsed `70.578 ms`, stop `0.913 ms`
   - Python 3.11 full pytest `652 passed, 2 warnings`, CI/benchmark Green 확인
   - benchmark 결과: [`doc/benchmarks/worker_loop_optimization_20260830.md`](doc/benchmarks/worker_loop_optimization_20260830.md)
   - TX drain quota / adaptive read / QWaitCondition은 현재 evidence로 불필요하여 도입하지 않음
   - **남은 완료 조건:** 실제 USB Serial open/close + sustained RX/TX + disconnect/reconnect + shutdown smoke

WHY:

- 구조를 크게 바꾸기 전에 성능 baseline을 고정
- 개선폭이 측정 오차 수준이면 구현하지 않는 것도 완료 판단
- Serial I/O는 Mock/LOOPBACK/synthetic transport만으로 실제 driver/stack 특성을 충분히 검증할 수 없음

## P2-C — Global state 및 package 구조 정리

6. [x] SettingsManager singleton 제거
   - `SettingsManager.__new__`, class `_instance`, `_initialized` 제거
   - application runtime에서는 `main.py`가 instance를 한 번 생성하고 `ApplicationBootstrapper`에 명시적으로 주입
   - `ThemeManager` 내부의 사용되지 않던 hidden `SettingsManager()` 생성 제거
   - production direct constructor는 `main.py`만 허용하는 AST architecture contract 추가
   - test fixture/migration/durability test를 독립 instance 방식으로 전환하고 stale singleton reset 제거
   - load/save/migration/fallback/backup/atomic replace contract 보존
   - PR #8 Windows Python 3.11 full pytest `655 passed, 2 external warnings`, GitHub Actions 4/4 Green
7. [x] Coordinator package 이동 필요성 최종 판단 — **현재는 이동하지 않음**
   - `ApplicationBootstrapper`가 Presenter/Coordinator를 한 composition root에서 명시적으로 import/조립
   - Presenter/Coordinator import direction 혼동이나 순환 dependency 문제의 반복 evidence 없음
   - SPI/I2C/Plugin 확장 전이라 application-level orchestration module 증가 조건 미충족
   - 별도 coordinator package public API 요구 없음
   - 계획의 이동 조건 4개 중 2개 이상 충족하지 않으므로 package move는 import churn만 증가한다고 판단
   - 향후 SPI/I2C/Plugin 확장으로 coordinator 수/의존성이 실제 증가하면 재평가

WHY:

- SettingsManager ownership을 class global state가 아니라 Composition Root DI로 단일화
- Coordinator의 책임 경계는 이미 class/DI 수준에서 분리되어 있어 현재는 파일 위치 변경의 실익이 없음

## P3-A — 기존 Packet 기능 확장

상세: [`extension_platform_plan.md`](doc/plans/extension_platform_plan.md)

8. [x] 구조화 packet filter
   - `model/packet_filter.py`에 pure `PacketFilterEngine` / immutable filter context 추가
   - Raw RX Fast Path와 parser 내부는 건드리지 않고 완결 `PacketEvent` 이후 `PacketPresenter`에서 filtering
   - semicolon-separated declarative DSL, 모든 rule은 AND 조건
   - 지원: `port/type` equality, `len` range, HEX/ASCII contains/prefix, byte/range/mask, checksum state
   - arbitrary Python expression 미지원
   - malformed rule은 compile 단계에서 `PacketFilterSyntaxError`; 직전 valid filter 유지 + PacketPanel 오류 feedback
   - PacketPanel에 Filter enable checkbox + expression input 추가
   - filter off 시 기존 packet 표시 path 유지
   - PR #10 구현 HEAD: Windows Python 3.11 full pytest `678 passed, 2 external warnings`, GitHub Actions 4/4 Green
9. [-] packet annotation / selected-range export

WHY:

- 현재 Packet DTO / parser 구조 위에 추가 가능하며 신규 hardware abstraction보다 리스크가 낮음
- Trigger보다 side effect가 적어 먼저 안정화하기 적합

## P3-B — SPI/I2C Transport 확장

10. [-] 실제 SPI/I2C backend 선정 및 capability 표 작성
11. [-] protocol-specific config DTO 및 Transport contract 결정
12. [-] SPI/I2C Transport 구현
   - 실제 필요한 protocol/backend 하나부터 시작
   - 필요 시 `StreamTransport` / `TransactionTransport` 분리
   - 구현 단계 자체에서 실제 adapter 검증 필수

WHY:

- backend 없이 추상화부터 만들지 않음
- Serial stream semantics를 transaction protocol에 억지로 맞추지 않음

## P3-C — Plugin system

13. [-] Plugin extension point 요구사항 확정
14. [-] `PluginBase` / `PluginContext` interface
15. [-] `PluginLoader` dynamic import / lifecycle / failure isolation
16. [-] Example plugin

WHY:

- Packet/SPI-I2C 확장 사례를 먼저 경험한 뒤 Plugin API를 설계해야 과도한 일반화를 피할 수 있음
- 내부 architecture debt를 public extension contract로 고정하지 않도록 함

## P3-D — Trigger-based transmission

17. [-] trigger-based transmission

마지막에 수행하는 이유:

```text
RX -> Trigger -> TX -> Echo/RX -> Trigger
```

순환 가능성이 있으며 Macro / AutoTx / Broadcast / Packet Parser / Local Echo와 교차하므로 현재 backlog 중 runtime side effect가 가장 크다.

필수 선행 정책:

- origin tagging 또는 max trigger depth
- cooldown
- one-shot
- target snapshot
- loop/reentrancy regression tests

## P4 — 최종 환경 / 배포 검증

상세: [`environment_validation_plan.md`](doc/plans/environment_validation_plan.md)

18. [-] 현재 `main` 기준 PyInstaller artifact 재빌드 및 smoke test
19. [-] Windows com0com 가상 Serial E2E
20. [-] 실제 USB Serial 장치 종합 검증
21. [-] Linux socat 검증
   - Linux가 실제 지원 대상일 때 필수화

WHY:

- PyInstaller/com0com/socat는 architecture 설계의 선행 조건보다 최종 제품 검증 성격이 강함
- 각 기능 개발 중 필요한 실기기 smoke는 해당 작업 acceptance에서 수행하고, P4에서는 전체 제품 관점으로 재검증

---

# 3. 완료된 제품/Architecture 기준선

- [x] 다중 Serial port tab과 연결/해제/설정
- [x] Manual TX/RX, Auto Tx, Macro, File Transfer
- [x] Packet Inspector 및 주요 parser
- [x] Structured Packet Filter
- [x] Logging / Theme / Localization / Settings
- [x] Single Composition Root (`ApplicationBootstrapper`)
- [x] Passive View + explicit DI
- [x] direct Qt signal topology / EventRouter / EventBus 제거
- [x] MainPresenter 책임 축소
- [x] Service/Manager/Coordinator ownership 분리
- [x] SettingsManager class-level Singleton 제거 / composition-root ownership
- [x] Coordinator package 이동 현재 보류 결정 / 재평가 trigger 명시
- [x] reconnect stale-signal race 및 shutdown/data preservation 교정

---

# 4. 현재 자동 검증 범위 / 알려진 제한사항

자동 검증:

- Mock Serial
- LoopbackTransport
- synthetic runtime benchmark
- offscreen Qt
- Windows/Ubuntu GitHub-hosted CI

알려진 제한사항:

- blocking OS port scan / macro file load helper는 Python thread 특성상 강제 종료하지 않음
- manager가 outstanding helper를 기능별 최대 1개로 제한
- language key 동적 표현식 7건은 정적 검사 불가
- 외부 `lark` dependency warning 2건
- Serial worker scheduling 변경은 실제 USB Serial 장치 acceptance 미완료

---

# 5. 작업 공통 Gate

변경은 기능별 branch/PR을 원칙으로 한다.

```text
targeted tests
    -> architecture/lifecycle tests
    -> ruff
    -> full pytest
    -> language/task checks
    -> GitHub Actions
```

추가 gate:

- 성능 작업: benchmark evidence 필수
- Serial I/O 최적화: 실제 USB Serial 최소 smoke 필수
- SPI/I2C: 실제 backend/adapter 검증 필수
- Plugin: load failure isolation test 필수
- Trigger: loop/reentrancy test 필수

---

# 6. 완료 정의

각 작업은 다음을 만족할 때 완료 처리한다.

```text
Owner / Boundary clear
+ Regression tests
+ No hidden global dependency
+ No worker -> QWidget access
+ Ruff Green
+ Full pytest Green
+ CI Green
+ Docs/Task synchronized
```
