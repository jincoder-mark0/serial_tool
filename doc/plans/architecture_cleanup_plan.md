# Architecture Cleanup Plan

> 우선순위: P2
> 목표: runtime behavior를 바꾸지 않고 residual architecture debt 제거

---

## 1. 범위

- timeout/status duration/poll interval 상수화
- legacy `core/event_bus.py` 완전 삭제
- SettingsManager singleton 제거
- Coordinator package 분리 여부 판단

이 네 항목은 영향 범위가 다르므로 한 번에 묶지 않는다.

---

## 2. Stage A — Performance 전에 처리할 Low-Risk Cleanup

### 2.1 Timeout / Status Duration 상수화

상수화 대상:

- lifecycle timeout
- user-visible status duration
- polling interval
- retry/backoff
- batch cadence

제외:

- 로컬 계산식
- 명백한 UI spacing
- 한 함수 안에서만 의미가 분명한 일회성 값

위치 원칙:

- cross-module runtime contract -> `common/constants.py`
- feature-local policy -> 해당 module named constant
- user-configurable -> settings/default/schema

Naming 예:

```python
PORT_SCAN_STOP_TIMEOUT_MS
STATUS_MESSAGE_DURATION_MS
MACRO_STOP_WAIT_MS
```

단위 suffix를 명시한다.

WHY:

- 동작을 바꾸지 않으면서 benchmark/리뷰에서 policy 의미를 명확히 함
- 이후 최적화 중 timeout literal을 성능 tuning 값과 혼동하는 것을 방지

### 2.2 `core/event_bus.py` 완전 삭제

목표:

production 주요 runtime에서 이미 사용하지 않는 EventBus를 repository에서도 제거하여 event topology 정본을 direct Qt signal 하나로 만든다.

선행 감사:

```text
EventBus
get_event_bus
subscribe(
publish(
reset_event_bus
```

분류:

- production runtime
- test fixture
- legacy/core unit test
- docs/comments

실행:

1. test-only consumer 파악
2. architecture contract로 대체 가능한 테스트 이관
3. EventBus-specific test 제거
4. `core/event_bus.py` 삭제
5. stale import/string 감사
6. docs 업데이트

Acceptance:

- production/test import 0건
- direct signal contract Green
- full pytest Green

---

## 3. Stage B — Performance Baseline 이후 Global State Cleanup

### SettingsManager Singleton 제거

WHY:

production DI는 명시적으로 개선됐지만 Singleton이 남아 있으면 test global state leakage와 hidden dependency 재도입 가능성이 남는다.

다만 singleton 제거는 construction/test fixture 전반에 영향을 줄 수 있으므로 **성능 baseline을 먼저 고정한 뒤** 수행한다.

목표 구조:

```text
main.py
  -> SettingsManager instance
  -> ApplicationBootstrapper
     -> SettingsCoordinator
     -> Presenter/Coordinator dependencies
```

하나의 application instance가 하나의 SettingsManager를 소유하지만 class-level Singleton으로 강제하지 않는다.

감사 대상:

- `SettingsManager()` direct construction
- `get_instance()` / class `_instance`
- singleton reset fixture
- module-level settings lookup

단계:

1. current construction graph 수집
2. production hidden call 제거
3. tests fixture explicit instance화
4. singleton mechanism 제거
5. constructor/public contract 정리
6. test/state isolation 검증

Acceptance:

- hidden global settings access 0
- tests 간 settings state leak 없음
- migration/schema behavior 동일
- composition root ownership 유지

---

## 4. Stage C — Coordinator Package 이동은 조건부

현재 Coordinator가 `presenter/` 아래 있지만 책임 경계 자체는 이미 분리돼 있다.

따라서 파일 위치만 바꾸는 refactor는 기본적으로 보류한다.

진행 조건 — 다음 중 2개 이상이 명확할 때:

- Presenter/Coordinator import direction 혼동 반복
- application orchestration module 수 증가
- SPI/I2C/Plugin 확장으로 application-level coordinator 증가
- package-level public API 필요

후보:

```text
application/
  bootstrap.py
  coordinators/
    settings.py
    shutdown.py
    logging.py
    control_state.py
    status.py
    macro_execution.py
```

Acceptance:

- 기능 변경 0
- dependency direction이 실제로 더 명확
- import churn 대비 유지보수 이득 문서화

조건을 충족하지 못하면 **이동하지 않는 것이 완료 판단**이다.

---

## 5. 전체 Roadmap에서의 위치

```text
P1 실환경 baseline
  -> timeout/status 상수화
  -> EventBus 제거
  -> P2 성능 baseline/최적화
  -> SettingsManager singleton 제거
  -> Coordinator package 이동 여부 판단
```

즉 구조 작업을 한 묶음으로 연속 수행하지 않는다. 영향이 작은 cleanup은 성능 측정 전에, 영향이 큰 global-state refactor는 측정 기준 확보 후 수행한다.

---

## 6. 공통 검증

- architecture policy tests
- composition root contract
- settings tests
- shutdown/lifecycle tests
- full pytest
- ruff
- GitHub Actions

구조 cleanup의 성공 기준은 파일 이동량이 아니라 dependency 단순화와 hidden state 감소다.
