# Extension Platform Plan

> 우선순위: P3
> 대상: Plugin, SPI/I2C, TCP/UDP, Packet Filter, Trigger, Annotation/Export

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

# 3. Transport Capability Model

SPI/I2C/TCP/UDP를 추가하기 전에 Serial 중심 PortConfig가 모든 protocol에 적합한지 재검토한다.

## 3.1 문제

Serial:

- baudrate
- bytesize
- parity
- stopbits
- flow control

TCP:

- host
- port
- connect timeout

UDP:

- local/remote endpoint
- connectionless semantics

SPI/I2C:

- bus/device/address
- clock/speed
- mode

모든 값을 하나의 거대한 PortConfig에 optional field로 넣는 것은 피한다.

## 3.2 권장 방향

공통 session identity + protocol-specific config DTO.

```text
ConnectionConfig
  + SerialConfig
  + TcpConfig
  + UdpConfig
  + SpiConfig
  + I2cConfig
```

기존 PortConfig migration 비용을 검토해 점진적으로 도입한다.

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

따라서 `BaseTransport.read/in_waiting/write` contract가 transaction protocol에 적합한지 검토해야 한다.

필요하면:

```text
StreamTransport
TransactionTransport
```

분리를 고려한다.

---

# 5. TCP / UDP Session

## TCP

- connect/disconnect lifecycle
- remote close propagation
- socket timeout
- reconnect policy는 초기 scope에서 제외 가능

## UDP

- connectionless receive
- peer metadata
- broadcast/multicast 여부

현재 `connection_name: str`만으로 peer identity가 충분한지 검토한다.

---

# 6. Structured Packet Filter

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

# 7. Trigger-Based Transmission

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

# 8. Packet Annotation / Selected-Range Export

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

# 9. Plugin과 Built-in Feature 경계

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

# 10. 단계별 Delivery

### Phase 1 — Plugin Foundation

- metadata/contract
- loader
- failure isolation
- example plugin

### Phase 2 — Transport Config Refactor

- capability/config model
- Serial compatibility

### Phase 3 — TCP first

두 번째 stream transport로 abstraction 검증.

SPI/I2C보다 TCP를 먼저 권장한다. Serial과 stream semantics가 유사해 `BaseTransport` abstraction의 실제 재사용성을 검증하기 쉽다.

### Phase 4 — UDP

connectionless semantics 반영.

### Phase 5 — SPI/I2C

transaction transport abstraction 필요 여부 최종 결정.

### Phase 6 — Filter / Trigger / Annotation / Export

Packet DTO와 transmission service가 안정된 상태에서 추가.

---

# 11. Acceptance Criteria

- 기존 Serial 기능 회귀 0
- Plugin failure가 app startup/runtime을 치명적으로 종료하지 않음
- protocol-specific config가 UI/Model에 optional field soup를 만들지 않음
- Trigger infinite loop 방지 테스트 존재
- export background I/O lifecycle 명확
- architecture contract / full pytest / CI Green
