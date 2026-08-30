# SerialTool Post-Merge Roadmap

> 기준 브랜치: `main`
> 기준일: 2026-08-30
> 현재 architecture: Single Composition Root + Passive View + explicit DI + direct Qt signal

---

## 1. 목적

이 문서는 Presenter/View Boundary 리팩토링 이후 남은 업무를 **선행 의존성·회귀 리스크·검증 비용** 기준으로 실제 실행 순서화한다.

상세 문서:

- 성능: [`performance_optimization_plan.md`](performance_optimization_plan.md)
- 구조: [`architecture_cleanup_plan.md`](architecture_cleanup_plan.md)
- 확장 기능: [`extension_platform_plan.md`](extension_platform_plan.md)
- 최종 환경/배포 검증: [`environment_validation_plan.md`](environment_validation_plan.md)

`Task.MD`는 실행 순서와 상태를 관리하고, 상세 설계/acceptance criteria는 본 문서군에서 관리한다.

---

## 2. 최종 우선순위 원칙

```text
low-risk architecture cleanup
        ↓
performance baseline / optimization
        ↓
global state cleanup
        ↓
Packet 기능 확장
        ↓
SPI/I2C extension
        ↓
Plugin system
        ↓
Trigger-based transmission
        ↓
final environment / deployment validation
```

### WHY

- PyInstaller/com0com/socat는 architecture 설계의 선행 조건보다 최종 제품 검증 성격이 강하다.
- 단, Serial I/O 최적화처럼 실제 driver/stack 특성이 중요한 작업은 해당 작업 acceptance에서 최소 실기기 smoke를 수행한다.
- 작은 dead code/policy literal 정리는 benchmark 전에 끝내도 동작 영향이 거의 없다.
- Settings singleton 제거는 범위가 넓어 baseline 측정 후 수행한다.
- Packet Filter/Annotation은 기존 구조를 이용하는 low-side-effect 확장이라 hardware/plugin보다 먼저 적합하다.
- Plugin API는 실제 extension 사례를 먼저 경험한 뒤 설계해야 내부 구조를 성급히 public contract로 고정하지 않는다.
- Trigger는 RX→TX 순환 가능성과 Macro/AutoTx/Broadcast 교차 때문에 가장 마지막 기능으로 둔다.

---

## 3. 실행 Wave

### Wave 1 — Low-Risk Architecture Cleanup

대상:

1. timeout/status/poll duration 상수화
2. legacy `core/event_bus.py` 제거

Gate:

- runtime behavior 변화 없음
- stale import/reference 0
- architecture/full pytest Green

### Wave 2 — Performance Evidence & Optimization

대상:

3. benchmark scenario/baseline 고정
4. RxLogView BatchRenderer 후보 비교
5. Serial I/O loop 후보 비교/최적화

Gate:

- CPU / throughput / latency / backlog / shutdown responsiveness 기록
- 이득이 측정 오차 수준이면 구현하지 않음
- Serial I/O 최적화 완료 전 실제 USB Serial 최소 smoke + reconnect/disconnect 확인

### Wave 3 — Global State Cleanup

대상:

6. SettingsManager singleton 제거
7. Coordinator package 이동 필요성 판단

Gate:

- test state isolation 개선
- hidden global dependency 감소
- Coordinator 이동은 dependency 명확성 개선 근거가 있을 때만 진행
- 이동하지 않는 결정도 완료로 인정

### Wave 4 — Packet Feature Expansion

대상:

8. Structured Packet Filter
9. Packet Annotation / Selected-range Export

Gate:

- Raw RX Fast Path 앞에 blocking 단계 추가 금지
- 큰 export는 UI thread file I/O 금지

### Wave 5 — SPI/I2C Expansion

대상:

10. backend 선정 / capability matrix
11. config DTO / Transport contract 결정
12. 필요한 protocol/backend부터 구현

Gate:

- backend 없는 추상화 금지
- Serial optional-field soup 금지
- transaction cancellation/shutdown path 명확
- 실제 adapter 최소 1종 검증

### Wave 6 — Plugin System

대상:

13. extension point 요구사항 정리
14. PluginBase / PluginContext
15. PluginLoader / lifecycle / failure isolation
16. Example plugin

Gate:

- MainWindow/ApplicationComponents 전체 노출 금지
- plugin failure가 app startup/runtime을 치명적으로 종료하지 않음
- 실제 사용 사례 없이 범용 API를 과도하게 일반화하지 않음

### Wave 7 — Trigger-Based Transmission

대상:

17. Trigger Engine / Action DTO / safety policy

Gate:

- cooldown / one-shot / origin tagging 또는 depth 제한
- target snapshot
- infinite-loop/reentrancy regression test
- CommandTransmissionService 경유

### Wave 8 — Final Environment / Deployment Validation

대상:

18. 현재 main PyInstaller artifact smoke
19. Windows com0com E2E
20. 실제 USB Serial 장치 종합 검증
21. Linux socat — Linux 지원 대상일 때

Gate:

- packaging/runtime dependency 누락 없음
- connect/reconnect/close/shutdown 기본 경로 정상
- 장시간 RX/TX 및 주요 feature 조합에서 data loss/crash blocker 없음
- 발견 이슈를 code defect / environment limitation으로 분류

---

## 4. 공통 Architecture Guardrail

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

- `ApplicationBootstrapper`가 runtime composition root 유지
- EventRouter 재도입 금지
- worker/background thread → QWidget 접근 금지
- Presenter 내부 hidden singleton 생성 금지
- MainPresenter를 Service Locator로 되돌리지 않음
- 의미 있는 cross-layer payload는 DTO 우선

---

## 5. 공통 검증 Gate

```text
targeted tests
  -> architecture/lifecycle tests
  -> ruff check .
  -> full pytest
  -> language/task consistency
  -> GitHub Actions
```

추가:

- performance: benchmark evidence
- Serial I/O optimization: 실제 USB Serial 최소 smoke
- SPI/I2C: 실제 backend/adapter smoke
- plugin: failure isolation
- trigger: loop/reentrancy safety
- P4: packaged artifact + virtual/physical serial E2E

---

## 6. 중단 / 보류 기준

- 성능 개선이 측정 오차 수준
- Coordinator 이동이 파일 이동 외 실제 dependency 이득을 만들지 못함
- SPI/I2C abstraction이 실제 backend 요구보다 과도하게 일반화됨
- Plugin API가 내부 object graph를 노출해야만 성립함
- Trigger가 기존 Macro/AutoTx/Broadcast semantics를 불명확하게 만듦

이 경우 scope를 축소하거나 보류를 완료 판단으로 인정한다.
