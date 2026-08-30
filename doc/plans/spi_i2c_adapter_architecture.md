# SPI/I2C Adapter Wrapper Architecture

> 대상: P3-B #10~#12
> 목적: FT232H / FT2232H를 1차 지원하면서 CH347, MCP2210 등 신규 USB bridge를 상위 구조 변경 없이 추가

---

## 1. 핵심 결정

SPI/I2C 확장은 특정 chip/library 중심 Transport가 아니라 **capability-driven adapter wrapper**로 설계한다.

```text
Application / Presenter
        |
        v
Transaction Service
        |
        v
Protocol Contract
  +-------------------+
  | SpiController     |
  | I2cController     |
  +-------------------+
        |
        v
Adapter Wrapper Layer
  +-------------------+
  | AdapterProvider   |
  | AdapterHandle     |
  | Capability Model  |
  | Backend Registry  |
  +-------------------+
        |
        +-------------------+-------------------+-------------------+
        |                   |                   |
        v                   v                   v
   FTDI Backend        CH347 Backend       MCP2210 Backend
   - FT232H            - SPI               - SPI only
   - FT2232H           - I2C
   - future FT4232H
        |
        v
Vendor library / OS driver / USB device
```

상위 계층은 chip name, DLL handle, PyFtdi URL, USB endpoint를 직접 알지 않는다.

---

## 2. WHY

지원 가능한 bridge는 하나의 계열로 고정되지 않는다.

예:

- FT232H: SPI + I2C, single MPSSE channel
- FT2232H: SPI + I2C, dual MPSSE channel
- CH347: SPI + I2C + JTAG 계열 capability
- MCP2210: SPI 중심, I2C 없음
- 향후 FT4232H / FT4222H / Aardvark / native Linux backend 등

따라서 다음 형태는 피한다.

```text
SpiTransport
  -> if FTDI ...
  -> elif CH347 ...
  -> elif MCP2210 ...
```

또한 다음 형태도 피한다.

```text
PortConfig
  ftdi_url
  ch347_index
  mcp_vid
  mcp_pid
  ...
```

이 구조는 backend가 추가될 때마다 Core DTO와 UI가 vendor-specific field soup로 변한다.

---

## 3. Layer 책임

### 3.1 AdapterProvider

backend plugin이 구현하는 discovery/factory 경계.

개념 contract:

```python
class AdapterProvider(Protocol):
    backend_id: str

    def enumerate(self) -> list[AdapterDescriptor]: ...
    def open(self, identity: AdapterIdentity) -> AdapterHandle: ...
```

책임:

- 해당 vendor/library device enumeration
- 안정적인 adapter identity 생성
- backend unavailable와 device unavailable 구분
- vendor API object 생성/해제

상위 계층에 vendor object를 반환하지 않는다.

### 3.2 AdapterDescriptor / AdapterIdentity

UI와 설정에 전달 가능한 vendor-neutral DTO.

```text
AdapterDescriptor
  backend_id       # pyftdi / ch347 / mcp2210
  device_family    # FT2232H / CH347 / MCP2210
  display_name
  identity
  channels
  capabilities

AdapterIdentity
  backend_id
  stable_id        # serial number 우선
  channel_id       # FT2232H A/B 등 optional
  vendor_data      # backend 내부용 opaque selector 최소화
```

원칙:

- USB enumeration index만 영구 저장하지 않음
- serial number 또는 backend가 보장하는 stable selector 우선
- UI는 `display_name`을 사용하고 internal selector를 조립하지 않음

### 3.3 Capability Model

backend 종류가 아니라 capability로 기능 사용 가능 여부를 판단한다.

```text
AdapterCapabilities
  protocols: {SPI, I2C}
  spi_modes
  spi_min_hz / spi_max_hz
  spi_full_duplex
  spi_cs_count
  spi_cs_hold
  i2c_7bit
  i2c_10bit
  i2c_repeated_start
  i2c_clock_stretching
  gpio_count
  multi_channel
```

예:

```text
FT2232H
  SPI = yes
  I2C = yes
  channels = 2

CH347
  SPI = yes
  I2C = yes

MCP2210
  SPI = yes
  I2C = no
```

MCP2210 provider는 I2C capability를 광고하지 않으면 된다. 별도 special-case가 필요 없다.

### 3.4 AdapterHandle

열린 physical adapter의 lifecycle owner.

개념 contract:

```python
class AdapterHandle(Protocol):
    @property
    def descriptor(self) -> AdapterDescriptor: ...

    def open_spi(self, config: SpiBusConfig) -> SpiController: ...
    def open_i2c(self, config: I2cBusConfig) -> I2cController: ...
    def close(self) -> None: ...
```

지원하지 않는 protocol은 capability validation 단계에서 차단한다.

### 3.5 SpiController / I2cController

상위 Transaction layer가 의존하는 protocol contract.

SPI:

```text
configure bus
exchange(tx, rx_length, chip_select, flags)
write(data, chip_select, flags)
read(length, chip_select, flags)
close
```

I2C:

```text
write(address, data, flags)
read(address, length, flags)
write_read(address, write_data, read_length, flags)
close
```

vendor-specific method 이름은 여기서 흡수한다.

---

## 4. Backend Registry

Composition Root가 provider를 등록한다.

```text
AdapterBackendRegistry
  register(PyFtdiAdapterProvider)
  register(Ch347AdapterProvider)      # 후속
  register(Mcp2210AdapterProvider)    # 후속
```

초기 production:

```text
Registry
  -> PyFtdiAdapterProvider
       -> FT232H
       -> FT2232H
```

후속 추가:

```text
Registry
  -> PyFtdiAdapterProvider
  -> Ch347AdapterProvider
  -> Mcp2210AdapterProvider
```

상위 `ConnectionSessionFactory`나 UI는 provider 수가 늘어도 변경하지 않는 것을 목표로 한다.

---

## 5. 1차 Target

### Tier 1 — 반드시 구현/검증

```text
FT232H
  -> SPI Master
  -> I2C Master

FT2232H
  -> SPI Master
  -> I2C Master
  -> interface/channel selector
```

FT2232H는 2차 후보가 아니라 **첫 release target**에 포함한다.

특히 FT2232H는 multi-channel capability가 wrapper 설계를 실제로 검증하므로 중요하다.

Acceptance 예:

```text
FT2232H channel A -> SPI
FT2232H channel B -> I2C
```

이 topology가 가능하더라도 동일 physical chip의 channel lifecycle/driver 제약은 backend가 관리한다.

### Tier 2 — wrapper 확장성 검증 후보

CH347:

- USB 2.0 High Speed
- SPI + I2C를 하나의 chip에서 지원
- WCH 공식 자료상 SPI 최대 60 MHz, I2C 최대 1 MHz class
- Windows/Linux vendor driver/API 존재

MCP2210:

- USB HID 기반 SPI Master
- OS 기본 HID driver 활용 가능
- SPI 4 mode, 최대 12 Mbps class
- I2C capability 없음

MCP2210은 **SPI-only backend가 구조에 자연스럽게 들어오는지 검증하기 좋은 사례**다.

---

## 6. Dependency Isolation

vendor package를 Core top-level import로 두지 않는다.

권장:

```text
core/transport/
  transaction/
    contracts.py
    dto.py
    registry.py
    backends/
      pyftdi_backend.py
      ch347_backend.py       # 후속
      mcp2210_backend.py     # 후속
```

실제 package 위치는 #11 current-code audit 후 확정하되 dependency direction은 다음을 고정한다.

```text
Protocol Contract
       ^
       |
Backend Implementation
       |
Vendor Library
```

금지:

```text
Protocol Contract -> pyftdi import
Protocol Contract -> CH347 DLL import
Presenter -> vendor library
View -> vendor library
```

backend package가 설치되지 않았거나 native DLL이 없으면 해당 provider만 unavailable 처리하고 SerialTool 전체 startup은 유지한다.

---

## 7. Config 방향

설정은 protocol과 adapter identity를 분리한다.

```text
ConnectionConfig
  protocol
  adapter: AdapterIdentity

SpiConfig
  frequency_hz
  mode
  chip_select
  bit_order
  duplex policy

I2cConfig
  frequency_hz
  address
  address_bits
  clock_stretching request
```

vendor-specific selector는 `AdapterIdentity` backend implementation 내부에서 해석한다.

예:

```text
FT2232H
  backend_id = pyftdi
  stable_id = FT9ABC12
  channel_id = 1

CH347
  backend_id = ch347
  stable_id = <vendor serial/device id>

MCP2210
  backend_id = mcp2210
  stable_id = <HID serial/path identity>
```

---

## 8. Capability Negotiation

사용자가 config를 적용할 때 두 단계로 검증한다.

```text
1. Static validation
   -> mode/address/frequency 범위 등 DTO validation

2. Backend capability validation
   -> 실제 adapter가 요청 capability를 지원하는지 확인
```

예:

```text
MCP2210 + I2C request
  -> capability mismatch
  -> connection 생성 전 실패

FT2232H + unsupported frequency
  -> requested/actual frequency policy에 따라 reject 또는 clamp
```

backend가 값을 조용히 바꾸지 않고 accepted/actual value를 상위에 반환하는 것을 원칙으로 한다.

---

## 9. Error Surface

vendor exception을 application 전체로 노출하지 않는다.

공통 오류 분류 후보:

```text
BackendUnavailableError
AdapterNotFoundError
AdapterBusyError
UnsupportedCapabilityError
ProtocolConfigurationError
TransactionTimeoutError
TransactionIoError
AdapterDisconnectedError
```

원본 vendor exception은 logging/debug cause로 보존한다.

---

## 10. Lifecycle / Concurrency

- physical adapter open/close owner는 AdapterHandle
- SPI/I2C transaction은 worker/thread service에서 실행
- QWidget에서 vendor call 금지
- 동일 adapter/channel 동시 transaction serialization 정책 필요
- FT2232H channel A/B는 backend capability가 independent channel로 광고할 때 별도 session 허용
- shutdown은 신규 transaction 차단 -> pending transaction 정리 -> controller close -> adapter close 순서

---

## 11. #11 구현 전 확정할 세부 contract

다음 단계에서 코드로 고정한다.

1. `AdapterIdentity` / `AdapterDescriptor`
2. `AdapterCapabilities`
3. `AdapterProvider` / `AdapterHandle`
4. `AdapterBackendRegistry`
5. `SpiConfig` / `I2cConfig`
6. SPI/I2C Request / Result DTO
7. Transaction cancellation / timeout model
8. current `PortConfig` migration strategy
9. `ConnectionSessionFactory`와 transaction session의 경계

---

## 12. Architecture Acceptance

- FT232H/FT2232H를 같은 PyFtdi provider가 처리
- FT2232H channel identity가 vendor-neutral DTO로 표현 가능
- CH347 backend 추가 시 Presenter/View/Protocol contract 수정 불필요
- MCP2210 SPI-only backend 추가 시 I2C special-case 불필요
- vendor library import가 backend implementation 밖으로 누출되지 않음
- missing optional backend가 앱 startup을 막지 않음
- capability mismatch가 transaction 전 deterministic하게 실패
- actual accepted bus setting을 상위에 보고 가능
