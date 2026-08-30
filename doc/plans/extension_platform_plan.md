# Extension Platform Plan

> 우선순위: P3
> 대상: Packet Filter, Annotation/Export, SPI/I2C, Plugin, Trigger
> SPI/I2C backend decision: [`spi_i2c_backend_decision_20260831.md`](spi_i2c_backend_decision_20260831.md)
> SPI/I2C adapter architecture: [`spi_i2c_adapter_architecture.md`](spi_i2c_adapter_architecture.md)

---

# 1. 공통 원칙

```text
새 기능 = 새 owner / capability
새 기능 != MainPresenter / ConnectionController 비대화
```

- Raw RX Fast Path와 UI thread blocking 최소화
- vendor-specific API를 Core/Application contract로 승격하지 않음
- optional backend failure가 SerialTool startup을 막지 않음
- 실제 extension use-case를 먼저 구현한 뒤 Plugin API를 고정

---

# 2. Phase 1 — Structured Packet Filter — 완료

최종 경계:

```text
Raw RX
 -> PacketParserManager
 -> PacketEvent
 -> PacketPresenter
 -> PacketFilterEngine
 -> PacketViewData
 -> PacketPanel
```

주요 결정:

- 완결 Packet 이후 filtering
- semicolon-separated AND DSL
- port/type/length/HEX/ASCII/byte-mask/checksum 지원
- arbitrary Python expression 미지원
- malformed expression은 직전 valid filter 유지
- Filter off 시 기존 packet path 동일

검증:

```text
PR #10 / Windows / Python 3.11
  678 passed, 2 external warnings
  CI 4/4 Green
```

---

# 3. Phase 2 — Packet Annotation / Selected Export — 완료

최종 경계:

```text
PacketEvent
 -> PacketPresenter
 -> immutable PacketRecord
 -> PacketModel / selection

Annotation
 -> PacketAnnotationStore

Export
 -> PacketExportManager
 -> QThread
 -> temp file
 -> atomic replace
```

주요 결정:

- parser Packet / display DTO mutation 없음
- stable runtime packet identity
- annotation은 runtime-only
- CSV / JSON / HEX / RAW export
- immutable selection snapshot
- UI thread file I/O 없음

검증:

```text
PR #11 / Windows / Python 3.11
  695 passed, 2 external warnings
  CI 4/4 Green
```

---

# 4. Phase 3 — SPI/I2C Multi-backend Architecture — 완료

## 4.1 Target

Tier-1:

```text
FT232H
  SPI Master
  I2C Master

FT2232H
  SPI Master
  I2C Master
  channel A/B identity + lifecycle
```

후속 architecture target:

```text
CH347   -> SPI + I2C
MCP2210 -> SPI only
future  -> FT4232H / FT4222H / native Linux / vendor adapters
```

## 4.2 Wrapper

```text
Application / Transaction Service
        |
        v
SpiController / I2cController
        |
        v
AdapterHandle
        |
        v
AdapterProvider + AdapterBackendRegistry
        |
        +-- PyFtdi backend -> FT232H / FT2232H
        +-- CH347 backend   -> 후속
        +-- MCP2210 backend -> 후속
```

상위 계층은 chip name, vendor DLL handle, HID handle, PyFtdi URL을 알지 않는다.

## 4.3 Stable Identity

```text
AdapterIdentity
  backend_id
  stable_id
  channel_id?     # FT2232H A/B 등
```

USB enumeration index는 persistent identity로 사용하지 않는다.

## 4.4 Capability-driven 정책

```text
MCP2210 + SPI -> allowed
MCP2210 + I2C -> UnsupportedCapabilityError

FT2232H channel A + SPI -> capability에 따라 allowed
FT2232H channel B + I2C -> capability에 따라 allowed
```

Core에 `if chip == ...` 분기를 추가하지 않는다.

PR #12: architecture/docs CI 4/4 Green, squash merge 완료.

---

# 5. Phase 4 — Transaction Contract — 완료

구현 위치:

```text
core/transport/transaction/
  __init__.py
  config.py
  contracts.py
  control.py
  dto.py
  errors.py
  registry.py
```

## 5.1 DTO / Capability

구현 완료:

- `TransactionProtocol`
- `AdapterIdentity`
- `AdapterDescriptor`
- `AdapterCapabilities`
- `SpiCapabilities`
- `I2cCapabilities`
- `SpiConfig`
- `I2cConfig`
- `SpiTransactionRequest` / `SpiTransactionResult`
- `I2cTransactionRequest` / `I2cTransactionResult`
- `TransactionConnectionConfig`

`TransactionConnectionConfig`는 adapter identity와 protocol config를 분리한다.

```text
TransactionConnectionConfig
  name
  protocol
  adapter: AdapterIdentity
  spi: SpiConfig | None
  i2c: I2cConfig | None
```

SPI/I2C config를 하나의 optional-field soup로 만들지 않는다.

## 5.2 Backend / Controller Contract

구현 완료:

- `AdapterProvider`
- `AdapterHandle`
- `AdapterBackendRegistry`
- `SpiController`
- `I2cController`

Provider 책임:

- backend prerequisite availability
- enumeration
- stable identity resolution
- vendor handle 생성

Registry 책임:

- provider 등록
- duplicate backend ID 차단
- unavailable optional provider isolation
- adapter resolve/open
- SPI/I2C capability validation

## 5.3 Timeout / Cancellation

구현 완료:

- `TransactionOptions(timeout_ms)`
- thread-safe `CancellationToken`
- controller `transact()` contract에 options/cancellation 전달

Cancellation은 cooperative 방식이다.

```text
cancel request
  -> CancellationToken.cancel()
  -> backend/worker가 vendor call 전후 또는 chunk/retry 경계에서 확인
```

실행 중 native vendor call을 Python에서 강제 종료하지 않는다.

## 5.4 Error Surface

구현 완료:

- `BackendUnavailableError`
- `AdapterNotFoundError`
- `AdapterBusyError`
- `UnsupportedCapabilityError`
- `ProtocolConfigurationError`
- `TransactionTimeoutError`
- `TransactionIoError`
- `AdapterDisconnectedError`

Vendor exception은 #12 backend에서 위 오류로 변환하고 cause로 원본을 보존한다.

## 5.5 Legacy PortConfig Migration

현재 `PortConfig`는 Serial runtime의 live contract라 즉시 제거하지 않는다.

현재 SPI UI에 `speed/mode` field가 존재하지만 `ConnectionProtocol.SUPPORTED=(Serial,)`이고 실제 SPI session은 아직 생성되지 않는다.

따라서 migration은 명시적으로 수행한다.

```text
Legacy PortConfig(SPI)
  speed / mode --------------------+
                                   v
New AdapterIdentity ----------> LegacyPortConfigAdapter
                                   |
                                   v
                        TransactionConnectionConfig
```

정책:

- legacy `speed/mode` 재사용 가능
- adapter identity는 새 adapter discovery/UI에서 선택한 값 필수
- FTDI/CH347/MCP2210 identity 추측 금지
- Serial PortConfig를 SPI로 암묵 변환 금지

## 5.6 Multi-backend Regression

Fake provider로 실제 contract를 검증한다.

```text
Registry
  pyftdi -> FT2232H A/B
  ch347  -> CH347 SPI+I2C
  mcp2210 -> MCP2210 SPI-only
```

검증 항목:

- FT2232H A/B stable channel identity
- 3 backend 동시 registry
- MCP2210 I2C capability mismatch
- frequency / clock-stretching capability validation
- unavailable optional provider isolation
- duplicate backend registration 차단
- vendor import leakage 금지
- legacy migration 명시성
- timeout/cancellation contract

최신 PR #13 contract HEAD:

```text
Windows / Python 3.11
  full pytest: 711 passed, 2 external lark warnings
  lint: success
  lang-keys: success
  task-boards: success
```

#11 완료 기준은 **hardware 동작이 아니라 backend-independent contract가 코드와 regression test로 고정된 것**이다.

---

# 6. Phase 5 — Tier-1 SPI/I2C Backend / Runtime / UI — 다음 작업

## 6.1 PyFtdi Backend

첫 production backend:

```text
PyFtdiAdapterProvider
  -> FT232H
  -> FT2232H
```

중요:

- `pyftdi` import는 backend implementation 안에만 존재
- package 미설치 / libusb unavailable 시 provider만 unavailable
- SerialTool startup 및 Serial 기능은 유지

## 6.2 FT232H Acceptance

- enumerate by stable identity
- open/close/reopen
- SPI transaction
- I2C transaction
- actual frequency reporting
- disconnect/shutdown

## 6.3 FT2232H Acceptance

- physical stable identity
- channel A/B descriptor
- channel A/B independent selection
- SPI transaction
- I2C transaction
- dual-channel lifecycle
- disconnect/reopen/shutdown

대표 target:

```text
FT2232H
  channel A -> SPI
  channel B -> I2C
```

## 6.4 Runtime Service

필요 owner:

- adapter discovery manager/service
- transaction session lifecycle
- worker/thread execution
- timeout/cancellation 적용
- request/result signal/DTO boundary

SPI/I2C transaction을 기존 Serial `read/in_waiting/write` polling worker에 억지로 넣지 않는다.

## 6.5 UI

기존 SPI placeholder UI를 실제 adapter-aware UI로 전환한다.

필요 항목:

```text
Protocol
Adapter
Channel

SPI:
  Frequency
  Mode
  Chip Select
  Bit Order / Duplex where supported

I2C:
  Frequency
  Address
  Address width
  Clock stretching request
```

지원 여부/범위는 `AdapterCapabilities`에서 가져온다.

## 6.6 Persistence

- stable `AdapterIdentity` 저장
- legacy SPI speed/mode migration
- backend가 없거나 adapter가 사라진 경우 설정 파일을 파괴하지 않음
- stale identity는 사용자에게 unavailable state로 표시

## 6.7 Dependency / Hardware Gate

- optional PyFtdi dependency 정책
- Windows libusb/Zadig setup 문서
- Linux udev/libusb policy
- **FT232H + FT2232H 실제 hardware smoke 필수**

CH347/MCP2210은 #12 Tier-1 구현 범위에 넣지 않지만, 이들을 나중에 추가할 때 upper contract를 바꾸지 않아야 한다.

---

# 7. Phase 6 — Plugin System

SPI/I2C backend registry와 일반 Plugin API를 동일 개념으로 섞지 않는다.

Plugin 1차 scope:

- `PluginBase`
- `PluginMetadata`
- `PluginContext`
- load/start/stop lifecycle
- `PluginLoader`
- duplicate ID 차단
- failure isolation
- Example plugin

노출 금지:

- MainWindow 전체
- ApplicationComponents 전체
- raw SettingsManager
- ConnectionController internal registry

실제 Packet/SPI/I2C extension 경험을 기준으로 facade를 정의한다.

---

# 8. Phase 7 — Trigger-based Transmission

P3 마지막 작업.

```text
Packet/Event
 -> TriggerEngine
 -> TriggerAction DTO
 -> CommandTransmissionService
```

필수 정책:

- cooldown
- one-shot
- origin tagging 또는 max depth
- target snapshot
- disable 즉시 신규 action 차단
- Macro/AutoTx 동시 실행 ownership
- loop/reentrancy regression

---

# 9. Delivery 순서

```text
1. Structured Packet Filter                         [완료]
2. Packet Annotation / Selected Export              [완료]
3. SPI/I2C multi-backend architecture               [완료]
4. SPI/I2C vendor-neutral transaction contract      [완료]
5. FT232H + FT2232H PyFtdi runtime/backend/UI       [다음]
6. Plugin system
7. Trigger-based transmission
8. P4 final environment/deployment validation
```

---

# 10. 공통 Acceptance

- 기존 Serial 회귀 0
- architecture/full pytest/Ruff/CI Green
- vendor dependency가 contract/Application/View로 누출되지 않음
- optional backend missing isolation
- transaction timeout/cancellation lifecycle 명확
- Tier-1 SPI/I2C는 실제 FT232H + FT2232H smoke
- Plugin failure isolation
- Trigger loop/reentrancy prevention
