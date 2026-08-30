# SerialTool Post-Merge Roadmap

> 기준 브랜치: `main`
> 기준일: 2026-08-30
> 현재 architecture: Single Composition Root + Passive View + explicit DI + direct Qt signal
> 현재 검증 기준: Local Python 3.13 `643 passed`, PR/Main GitHub Actions Green

---

## 1. 목적

이 문서는 Presenter/View Boundary 리팩토링 이후 남은 P2/P3 작업을 하나의 실행 순서로 정리한다.

상세 설계는 다음 문서를 정본으로 사용한다.

- 성능: [`performance_optimization_plan.md`](performance_optimization_plan.md)
- 구조: [`architecture_cleanup_plan.md`](architecture_cleanup_plan.md)
- 확장 기능: [`extension_platform_plan.md`](extension_platform_plan.md)

`Task.MD`는 현재 상태와 우선순위만 관리하고, 구현 판단과 acceptance criteria는 본 문서군에서 관리한다.

---

## 2. 우선순위 원칙

```text
측정 가능한 성능 병목
        ↓
구조적 debt 제거
        ↓
확장 point 안정화
        ↓
Plugin / Transport 확장
        ↓
Packet / Trigger 고급 기능
```

### WHY

- 성능 문제를 구조 개편과 동시에 다루면 원인 분리가 어려워진다.
- 구조 cleanup을 Plugin system 이후에 하면 public extension API가 내부 debt에 고정된다.
- Transport 확장은 Serial contract와 connection/session ownership이 충분히 안정된 뒤 진행해야 한다.

---

## 3. 실행 Wave

### Wave A — Performance Evidence

대상:

- RxLogView `BatchRenderer` 필요성 재평가
- Serial non-blocking I/O loop 최적화

완료 조건:

- benchmark scenario 고정
- baseline/후보안 비교 수치 확보
- latency / throughput / CPU / UI responsiveness trade-off 기록
- 성능 개선이 통계적으로 의미 없으면 구현하지 않는 결정도 허용

### Wave B — Architecture Cleanup

대상:

- Coordinator package 분리 여부 결정
- `core/event_bus.py` 제거
- SettingsManager singleton 제거
- timeout/status duration 상수화

완료 조건:

- runtime behavior 무변경
- public API 변경 최소화
- architecture contract 및 full pytest Green
- hidden global state 감소를 측정 가능한 형태로 확인

### Wave C — Extension Foundation

대상:

- `PluginBase`
- `PluginLoader`
- Example plugin
- extension lifecycle/error isolation

완료 조건:

- plugin이 View/Model 내부를 직접 침범하지 않음
- plugin load 실패가 application startup을 깨지 않음
- plugin disable/unload 또는 최소한 restart-safe failure policy 정의

### Wave D — Transport Expansion

대상:

- SPI/I2C Transport
- TCP/UDP session

완료 조건:

- `BaseTransport` contract 재검토
- ConnectionSessionFactory가 protocol별 생성 책임 유지
- Serial-only UI assumption 제거
- transport별 capability 차이를 명시적으로 표현

### Wave E — Packet / Automation Features

대상:

- 구조화 packet filter
- trigger-based transmission
- packet annotation
- selected-range export

완료 조건:

- parsing / filtering / UI rendering 책임 분리
- 대량 RX에서 filter/annotation이 Fast Path를 막지 않음
- trigger loop/reentrancy 방지

---

## 4. 공통 Architecture Guardrail

모든 Wave에서 다음을 유지한다.

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

- `ApplicationBootstrapper`가 runtime composition root 유지
- EventRouter 재도입 금지
- worker/background thread → QWidget 접근 금지
- Presenter 내부 hidden singleton 생성 금지
- 새 extension 기능 때문에 MainPresenter를 Service Locator로 되돌리지 않음
- 의미 있는 cross-layer payload는 DTO 우선

---

## 5. 공통 검증 Gate

각 작업은 가장 가까운 테스트부터 full suite까지 확대한다.

```text
targeted tests
  -> architecture/lifecycle tests
  -> ruff check .
  -> full pytest
  -> language/task consistency
  -> GitHub Actions
```

성능 작업은 기능 Green만으로 완료하지 않고 benchmark 결과를 반드시 남긴다.

---

## 6. 중단 / 되돌림 기준

다음 조건이면 구현을 중단하거나 scope를 줄인다.

- 성능 개선이 측정 오차 수준
- API abstraction이 실제 두 번째 구현 없이 지나치게 일반화됨
- Plugin system 때문에 core ownership이 불명확해짐
- Transport 공통화를 위해 Serial의 안정 경로를 훼손해야 함
- UI 고급 기능이 RX Fast Path latency를 유의미하게 증가시킴

---

## 7. 권장 진행 순서

```text
P2 Performance
  1. benchmark 재설계
  2. RxLogView 후보안 비교
  3. Serial I/O 후보안 비교

P2 Architecture
  4. EventBus 제거
  5. SettingsManager singleton 제거
  6. timeout/status 상수화
  7. Coordinator package 이동 여부 최종 판단

P3 Extension
  8. Plugin foundation
  9. SPI/I2C capability model
 10. TCP/UDP session model
 11. packet filter / trigger / annotation / export
```

Coordinator package 이동은 구조상 필요성이 약하면 보류한다. 파일 이동 자체는 architecture 개선이 아니다.
