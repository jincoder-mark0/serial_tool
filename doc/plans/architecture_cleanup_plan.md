# Architecture Cleanup Plan

> 우선순위: P2
> 목표: runtime behavior를 바꾸지 않고 residual architecture debt 제거

---

## 1. 범위

- [x] timeout/status duration/poll interval 상수화
- [x] legacy `core/event_bus.py` 완전 삭제
- [-] SettingsManager singleton 제거
- [-] Coordinator package 분리 여부 판단

이 네 항목은 영향 범위가 다르므로 한 번에 묶지 않는다.

---

## 2. Stage A — Performance 전에 처리할 Low-Risk Cleanup

### 2.1 Timeout / Status Duration 상수화 — 완료

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

완료 결과:

- 기존 worker/background/file-transfer polling 값의 canonical constant 사용 확인
- MainPresenter status message duration `0/3000/5000 ms`를 의미별 named constant로 정리
- literal contract regression test 추가
- PR #2 GitHub Actions 4/4 Green

### 2.2 `core/event_bus.py` 완전 삭제 — 완료

목표:

production 주요 runtime에서 이미 사용하지 않던 EventBus를 repository에서도 제거하여 event topology 정본을 direct Qt signal 하나로 만든다.

수행 결과:

1. `core/event_bus.py` 삭제
2. `common.constants.EventTopics` 삭제
3. `tests/conftest.py`의 EventBus autouse reset 제거
4. EventBus 자체 unit tests 제거
5. stale `EventTopics` constants contract 제거
6. direct event topology test에 EventBus module / EventTopics 재도입 방지 조건 추가

역사 문서 정책:

- `doc/history/`, `tasks/S-xxx`의 EventBus 언급은 당시 구조와 결정 기록이므로 보존
- 현재 architecture 문서는 direct Qt signal만 정본으로 설명

검증:

```text
PR #3 / Python 3.11 / Windows
  full pytest: 639 passed, 2 external lark warnings
  lint: success
  lang-keys: success
  task-boards: success
```

테스트 수가 이전보다 5개 감소한 이유는 EventBus 전용 테스트 4개와 EventTopics 전용 테스트 1개를 의도적으로 제거했기 때문이다.

Acceptance:

- production/test EventBus import 0
- `core/event_bus.py` 없음
- `EventTopics` 없음
- direct signal topology contract Green
- full pytest / CI Green

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
timeout/status 상수화 [완료]
  -> EventBus 제거 [완료]
  -> P2 성능 baseline/최적화
  -> SettingsManager singleton 제거
  -> Coordinator package 이동 여부 판단
```

구조 작업을 한 묶음으로 연속 수행하지 않는다. 영향이 작은 cleanup은 성능 측정 전에, 영향이 큰 global-state refactor는 측정 기준 확보 후 수행한다.

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
