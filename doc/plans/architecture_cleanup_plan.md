# Architecture Cleanup Plan

> 우선순위: P2
> 목표: runtime behavior를 바꾸지 않고 residual architecture debt 제거

---

## 1. 범위

- Coordinator package 분리 여부
- legacy `core/event_bus.py` 완전 삭제
- SettingsManager singleton 제거
- timeout/status duration 상수화

---

# 2. `core/event_bus.py` 완전 삭제

## 2.1 목표

production 주요 runtime에서 이미 사용하지 않는 EventBus를 repository에서 완전히 제거하여 event topology의 정본을 direct Qt signal 하나로 만든다.

## 2.2 선행 감사

검색 대상:

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

## 2.3 실행 단계

1. test-only consumer 파악
2. architecture contract로 대체 가능한 테스트 제거/이관
3. EventBus-specific test 삭제
4. `core/event_bus.py` 삭제
5. import/stale string 감사
6. docs 업데이트

## 2.4 Acceptance

- repository production/test import 0건
- direct signal contract tests Green
- full pytest Green

---

# 3. SettingsManager Singleton 제거

## 3.1 WHY

production DI는 명시적으로 개선됐지만 Singleton이 남아 있으면 테스트 간 global state leakage와 hidden dependency 재도입 가능성이 남는다.

## 3.2 목표 구조

```text
main.py
  -> SettingsManager instance
  -> ApplicationBootstrapper
     -> SettingsCoordinator
     -> Presenter/Coordinator dependencies
```

하나의 application instance가 하나의 SettingsManager를 소유하지만, 이를 class-level Singleton으로 강제하지 않는다.

## 3.3 감사 대상

- `SettingsManager()` direct construction
- `get_instance()` / class `_instance`
- tests fixture singleton reset
- module-level settings lookup

## 3.4 단계

1. current construction graph 수집
2. production hidden call 제거
3. tests fixture를 explicit instance로 이동
4. singleton mechanism 제거
5. constructor type hints/public contract 정리
6. parallel test/state isolation 검증

## 3.5 Acceptance

- production composition root 외 ad-hoc construction 최소화
- tests 간 settings state leak 없음
- 기존 settings migration/schema behavior 동일

---

# 4. Timeout / Status Duration 상수화

## 4.1 대상 분류

모든 숫자를 상수로 만드는 것이 목적이 아니다.

상수화 대상:

- lifecycle timeout
- user-visible status duration
- polling interval
- retry/backoff
- batch cadence

로컬 계산식/명백한 UI spacing은 제외한다.

## 4.2 위치 원칙

- cross-module runtime contract -> `common/constants.py`
- feature-local policy -> 해당 module의 named constant
- user-configurable value -> settings/default/schema

## 4.3 Naming

예:

```python
PORT_SCAN_STOP_TIMEOUT_MS
STATUS_MESSAGE_DURATION_MS
MACRO_STOP_WAIT_MS
```

단위 suffix를 반드시 포함한다.

---

# 5. Coordinator Package 이동

## 5.1 현재 상태

Coordinator들이 `presenter/` 아래 있으나 책임 경계 자체는 이미 분리돼 있다.

따라서 **파일 위치만 바꾸는 refactor는 기본적으로 보류**한다.

## 5.2 이동을 정당화하는 조건

다음 중 2개 이상이 명확할 때 진행 권장:

- Presenter와 Coordinator import direction이 반복적으로 혼동됨
- application orchestration module 수가 더 증가
- Plugin/Transport 확장으로 application-level coordinator가 늘어남
- package-level public API가 필요

## 5.3 목표 후보

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

단, `application_bootstrap.py` 이동은 import churn이 크므로 별도 결정.

## 5.4 Acceptance

- 기능 변경 0
- dependency direction 더 명확
- import churn 대비 유지보수 이득 문서화

---

# 6. 실행 순서 권장

```text
1. EventBus 제거
2. SettingsManager singleton 제거
3. timeout/status 상수화
4. Coordinator package 이동 필요성 재평가
```

이 순서는 low-risk dead code 제거 -> hidden global state 제거 -> policy literal 정리 -> package churn 순이다.

---

# 7. 공통 검증

- architecture policy tests
- composition root contract
- settings tests
- shutdown/lifecycle tests
- full pytest
- ruff
- GitHub Actions

구조 cleanup은 테스트 수 증가보다 dependency 단순화와 hidden state 감소가 성공 기준이다.
