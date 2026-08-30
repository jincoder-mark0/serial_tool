# Extension Platform Plan

> 우선순위: P3
> 대상: Packet Filter, Annotation/Export, SPI/I2C, Plugin, Trigger

---

## 1. 목표

현재 안정화된 ownership을 깨지 않고 기능을 확장한다.

핵심 원칙:

```text
새 기능 = 새 owner / capability
새 기능 != MainPresenter / ConnectionController 비대화
```

P3에서는 **실제 사용 사례가 분명한 기능부터** 진행하고, 범용 extension API는 뒤로 미룬다.

---

# 2. Phase 1 — Structured Packet Filter

## 목표

PacketParser 이후의 완결 Packet DTO를 대상으로 filtering한다.

```text
Raw RX
 -> Parser
 -> Packet DTO
 -> Filter Engine
 -> Packet Presenter/View
```

Raw RX Fast Path 앞에 filter를 넣지 않는다.

초기 rule 후보:

- field equality
- numeric range
- mask/bit condition
- contains/prefix
- checksum validity

초기에는 declarative rule을 우선하고 arbitrary Python expression은 피한다.

Acceptance:

- filter off 시 기존 경로와 behavior 동일
- 대량 packet에서 UI/RX Fast Path blocking 없음
- malformed rule이 runtime을 깨지 않음

---

# 3. Phase 2 — Packet Annotation / Selected-Range Export

## Annotation

Packet DTO 자체 mutation보다 별도 annotation store/model을 권장한다.

정보 후보:

- packet/session identity
- timestamp
- note/tag
- optional category semantic

## Selected Range Export

View selection을 DTO snapshot으로 변환해 Service에 전달한다.

지원 후보:

- raw bytes
- hex text
- CSV
- JSON packet metadata

큰 selection에서 UI thread file I/O 금지.

WHY:

- Packet Filter와 동일한 Packet DTO 경계를 활용 가능
- Trigger처럼 TX side effect가 없어 먼저 안정화하기 적합

---

# 4. Phase 3 — SPI/I2C Backend & Capability Model

SPI/I2C는 Serial과 transaction semantics가 다르므로 backend를 먼저 확정한다.

## 4.1 Backend 후보

- USB bridge
- FTDI
- vendor adapter
- Linux `/dev/spidev` / `/dev/i2c-*`

실제 사용할 backend 없이 abstract transport만 먼저 만들지 않는다.

## 4.2 Config 방향

하나의 거대한 `PortConfig`에 optional field를 계속 추가하지 않는다.

```text
ConnectionConfig
  + SerialConfig
  + SpiConfig
  + I2cConfig
```

기존 `PortConfig` migration 비용을 검토해 점진적으로 도입한다.

## 4.3 Transport contract

기존:

```text
read / in_waiting / write
```

이 contract가 transaction protocol에 부적합하면 억지로 확장하지 않는다.

필요하면:

```text
StreamTransport
TransactionTransport
```

분리를 고려한다.

---

# 5. Phase 4 — SPI/I2C Transport 구현

권장 순서:

1. 실제 필요한 protocol/backend 하나 선정
2. backend capability 표 확정
3. config DTO
4. Transport interface 결정
5. ConnectionSessionFactory 생성 경로
6. protocol-specific UI settings
7. Mock backend tests
8. 실제 adapter smoke

SPI와 I2C를 동시에 구현하는 것을 목표로 하지 않는다. 실제 제품/업무 요구가 높은 쪽부터 구현한다.

Acceptance:

- 기존 Serial 회귀 0
- optional field soup 없음
- backend missing/disconnect/timeout error surface 명확
- transaction cancellation/shutdown path 정의
- 실제 지원 backend 최소 1개 검증

---

# 6. Phase 5 — Plugin System

## WHY 이 시점인가

Plugin API를 가장 먼저 만들면 아직 존재하지 않는 extension point를 추측해 과도하게 일반화할 가능성이 크다.

Packet 확장과 SPI/I2C 같은 실제 사례를 먼저 경험한 뒤 다음 질문에 답할 수 있을 때 Plugin contract를 만든다.

```text
무엇을 확장해야 하는가?
어떤 facade가 안전하게 필요한가?
어떤 lifecycle이 반복되는가?
어떤 failure isolation이 실제로 필요한가?
```

## 6.1 1차 Scope

- `PluginBase`
- `PluginMetadata`
- `PluginContext`
- lifecycle: load/start/stop
- `PluginLoader`
- duplicate ID 차단
- failure isolation/logging
- Example plugin

초기 제외:

- hot reload
- arbitrary UI injection
- marketplace
- remote install
- untrusted sandbox execution

## 6.2 Context 제한

노출 금지:

```text
MainWindow 전체
ApplicationComponents 전체
SettingsManager raw instance
ConnectionController internal registry
```

필요한 facade만 제공한다.

PluginLoader는 composition root에서 생성하고 strong reference를 유지한다.

Acceptance:

- plugin failure가 startup/runtime을 치명적으로 종료하지 않음
- plugin이 내부 object graph를 임의 탐색하지 않음
- unload 또는 최소 restart-safe failure policy 존재
- 실제 example use-case가 contract를 검증

---

# 7. Phase 6 — Trigger-Based Transmission

Trigger는 P3의 마지막에 진행한다.

## 위험

```text
RX
 -> Trigger
 -> TX
 -> Echo / RX
 -> Trigger
```

Macro / AutoTx / Broadcast / Local Echo / Packet Parser와 교차하므로 side effect가 가장 크다.

필수 정책:

- cooldown
- one-shot
- origin tagging 또는 max trigger depth
- enable scope
- target snapshot

권장 흐름:

```text
Packet/Event
 -> TriggerEngine
 -> TriggerAction DTO
 -> CommandTransmissionService
```

TriggerEngine이 ConnectionController를 직접 호출하지 않는다.

Acceptance:

- infinite loop 방지 regression test
- reconnect/port-close 중 action 안전
- Macro/AutoTx와 동시에 동작할 때 ownership 명확
- trigger disable 즉시 신규 action 차단

---

# 8. Built-in vs Plugin 경계

모든 기능을 Plugin으로 만들 필요는 없다.

Built-in 권장:

- core Transport
- packet filter engine
- trigger engine

Plugin 적합 후보:

- vendor-specific decoder
- custom exporter
- device-specific command pack
- optional analysis extension

안정적인 core abstraction이 생기기 전에 Plugin API에 내부 세부사항을 노출하지 않는다.

---

# 9. 최종 Delivery 순서

```text
1. Structured Packet Filter
2. Packet Annotation / Selected-range Export
3. SPI/I2C backend & capability model
4. SPI/I2C Transport implementation
5. Plugin system
6. Trigger-based transmission
```

이 순서는 low-side-effect 기능 → hardware abstraction → 실제 사례 기반 extension API → high-side-effect automation 순이다.

---

# 10. 공통 Acceptance

- 기존 Serial 기능 회귀 0
- architecture contract / full pytest / CI Green
- hardware 기능은 실제 backend smoke 포함
- Plugin failure isolation test 존재
- Trigger loop/reentrancy 방지 test 존재
- background file I/O lifecycle 명확
