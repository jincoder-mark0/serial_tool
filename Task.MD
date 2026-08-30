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
2. [-] legacy `core/event_bus.py` 완전 삭제

WHY:

- runtime behavior 변경이 거의 없는 작업부터 처리
- benchmark와 이후 확장에서 stale policy/dead code가 판단 노이즈가 되는 것을 방지

## P2-B — 성능 측정 및 증거 기반 최적화

상세: [`performance_optimization_plan.md`](doc/plans/performance_optimization_plan.md)

3. [-] benchmark scenario/baseline 재고정
4. [-] RxLogView `BatchRenderer` 후보안 비교
   - 측정 이득이 명확할 때만 도입
5. [-] Serial non-blocking I/O loop 후보안 비교/최적화
   - CPU / throughput / latency / shutdown responsiveness 함께 평가
   - 완료 전 실제 USB Serial 최소 smoke + reconnect/disconnect 확인

WHY:

- 구조를 크게 바꾸기 전에 성능 baseline을 고정
- 개선폭이 측정 오차 수준이면 구현하지 않는 것도 완료 판단
- Serial I/O는 Mock/LOOPBACK만으로 실제 driver/stack 특성을 충분히 검증할 수 없음

## P2-C — Global state 및 package 구조 정리

6. [-] SettingsManager singleton 제거
7. [-] Coordinator package 이동 필요성 최종 판단
   - 실제 dependency/모듈 증가 근거가 없으면 **이동하지 않는 결정도 완료**

WHY:

- Singleton 제거는 영향 범위가 커서 성능 baseline 확보 후 수행
- Coordinator 이동은 파일 이동 자체가 가치가 아니므로 마지막 구조 판단으로 유지

## P3-A — 기존 Packet 기능 확장

상세: [`extension_platform_plan.md`](doc/plans/extension_platform_plan.md)

8. [-] 구조화 packet filter
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
- [x] Logging / Theme / Localization / Settings
- [x] Single Composition Root (`ApplicationBootstrapper`)
- [x] Passive View + explicit DI
- [x] direct Qt signal topology / EventRouter 제거
- [x] MainPresenter 책임 축소
- [x] Service/Manager/Coordinator ownership 분리
- [x] reconnect stale-signal race 및 shutdown/data preservation 교정

---

# 4. 현재 자동 검증 범위 / 알려진 제한사항

자동 검증:

- Mock Serial
- LoopbackTransport
- offscreen Qt
- Windows/Ubuntu GitHub-hosted CI

알려진 제한사항:

- blocking OS port scan / macro file load helper는 Python thread 특성상 강제 종료하지 않음
- manager가 outstanding helper를 기능별 최대 1개로 제한
- language key 동적 표현식 7건은 정적 검사 불가
- Python 3.13 외부 `lark` dependency warning 2건

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