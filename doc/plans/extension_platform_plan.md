# Extension Platform Plan

> 우선순위: P3
> 대상: Plugin, SPI/I2C, Packet Filter, Trigger, Annotation/Export

---

## 1. 목표

확장 기능을 추가하면서 현재 안정화된 ownership을 깨지 않는 것이 최우선이다.

핵심 원칙:

```text
새 기능 = 새 owner / capability
새 기능 != MainPresenter/ConnectionController 비대화
```

---

# 2. Plugin System

## 2.1 목표

Plugin은 내부 객체에 임의 접근하는 Python hook이 아니라 제한된 extension contract를 사용한다.

## 2.2 1차 Scope

- `PluginBase`
- metadata
- lifecycle: load/start/stop
- capability declaration
- `PluginLoader`
- Example plugin
- load failure isolation

## 2.3 제외

초기 버전에서 제외:

- hot reload
- arbitrary UI injection
- pip marketplace
- remote plugin install
- untrusted sandbox execution

## 2.4 후보 Contract

```python
class PluginBase(ABC):
    @property
    def metadata(self) -> PluginMetadata: ...

    def start(self, context: PluginContext) -> None: ...
    def stop(self) -> None: ...
```

`PluginContext`는 필요한 facade만 제공한다.

금지:

```text
MainWindow 전체 노출
ApplicationComponents 전체 노출
SettingsManager raw 노출
ConnectionController internal registry 노출
```

## 2.5 Loader

책임:

- discovery
- import
- metadata validation
- duplicate ID 차단
- lifecycle ownership
- error isolation/logging

PluginLoader는 composition root에서 생성하고 strong reference를 유지하는 것이 자연스럽다.

---

# 3. SPI / I2C Capability Model

SPI/I2C를 추가하기 전에 Serial 중심 `PortConfig`와 `BaseTransport`가 transaction protocol에 적합한지 재검토한다.

## 3.1 문제

Serial:

- baudrate
- bytesize
- parity
- stopbits
- flow control
- continuous stream semantics

SPI/I2C:

- bus/device/address
- clock/speed
- mode
- transaction/request-response semantics
- backend별 capability 차이

모든 값을 하나의 거대한 `PortConfig`에 optional field로 넣는 것은 피한다.

## 3.2 권장 방향

공통 session identity + protocol-specific config DTO.

```text
ConnectionConfig
  + SerialConfig
  + SpiConfig
  + I2cConfig
```

기존 `PortConfig` migration 비용을 검토해 점진적으로 도입한다.

---

# 4. SPI / I2C Transport

## 4.1 선행 결정

Desktop PC에서 SPI/I2C backend가 무엇인지 명시해야 한다.

후보:

- USB bridge
- FTDI
- vendor adapter
- Linux `/dev/spidev` / `/dev/i2c-*`

backend 없이 abstract transport만 먼저 만들지 않는다.

## 4.2 Capability 차이

Serial처럼 continuous RX stream이 아닐 수 있다.

따라서 `BaseTransport.read/in_waiting/write` contract가 transaction protocol에 적합한지 먼저 검토한다.

필요하면:

```text
StreamTransport
TransactionTransport
```

분리를 고려한다.

## 4.3 구현 순서

1. 실제 backend 선정
2. backend capability 표 작성
3. `SpiConfig` / `I2cConfig` DTO 정의
4. 기존 `BaseTransport` 재사용 가능성 평가
5. 필요하면 transaction-oriented interface 분리
6. `ConnectionSessionFactory`에 protocol 생성 경로 추가
7. UI에서 Serial-only 설정과 SPI/I2C 설정을 명확히 분리
8. Mock backend + 실제 adapter 검증

## 4.4 완료 조건

- Serial 안정 경로 회귀 0
- Serial optional field soup를 만들지 않음
- backend 미존재/분리/timeout 오류가 명확히 surface됨
- transaction cancellation/shutdown path 정의
- 실제 지원 backend 최소 1개 검증

---

# 5. Structured Packet Filter

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

Filter 후보:

- field equality
- numeric range
- mask/bit condition
- contains/prefix
- checksum validity

초기에는 declarative rule을 우선하고 arbitrary Python expression은 피한다.

---

# 6. Trigger-Based Transmission

## 위험

RX가 TX를 발생시키고 TX echo가 다시 RX trigger를 만들면 loop가 생길 수 있다.

필수 정책:

- cooldown
- max trigger depth 또는 origin tagging
- one-shot
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

---

# 7. Packet Annotation / Selected-Range Export

## Annotation

Packet DTO 자체를 mutation하지 않고 별도 annotation store/model을 권장한다.

정보:

- packet/session identity
- timestamp
- note/tag
- optional color/category semantic

## Selected Range Export

export 입력은 View selection을 DTO snapshot으로 변환해 Service에 넘긴다.

지원 후보:

- raw bytes
- hex text
- CSV
- JSON packet metadata

큰 selection에서 UI thread file I/O 금지.

---

# 8. Plugin과 Built-in Feature 경계

모든 새 기능을 Plugin으로 만들 필요는 없다.

Built-in 권장:

- core Transport
- packet filter engine
- trigger engine

Plugin 적합:

- vendor-specific decoder
- custom exporter
- device-specific command pack
- optional analysis panel

안정적인 core abstraction이 생기기 전에 Plugin API에 노출하지 않는다.

---

# 9. 단계별 Delivery

### Phase 1 — Plugin Foundation

- metadata/contract
- loader
- failure isolation
- example plugin

### Phase 2 — SPI/I2C Backend & Config Decision

- 실제 backend 선정
- capability 표 작성
- protocol-specific config model
- Serial compatibility 영향 분석

### Phase 3 — Transport Contract Decision

- `BaseTransport` 재사용 가능성 검증
- 필요 시 `StreamTransport` / `TransactionTransport` 분리
- ConnectionSessionFactory ownership 유지

### Phase 4 — SPI/I2C Implementation

- 최소 1개 실제 backend 지원
- Mock backend 기반 unit/integration test
- 실제 adapter smoke test

### Phase 5 — Filter / Trigger / Annotation / Export

Packet DTO와 transmission service가 안정된 상태에서 추가.

---

# 10. Acceptance Criteria

- 기존 Serial 기능 회귀 0
- Plugin failure가 app startup/runtime을 치명적으로 종료하지 않음
- protocol-specific config가 UI/Model에 optional field soup를 만들지 않음
- SPI/I2C backend 및 transaction lifecycle이 명확함
- Trigger infinite loop 방지 테스트 존재
- export background I/O lifecycle 명확
- architecture contract / full pytest / CI Green
