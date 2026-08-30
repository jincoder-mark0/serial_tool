# SPI/I2C Backend Decision — 2026-08-31

> Task: P3-B #10
> 상태: **Backend family / wrapper architecture 결정 완료, Transport contract 구현 전**
> 상세 구조: [`spi_i2c_adapter_architecture.md`](spi_i2c_adapter_architecture.md)

---

## 1. 결정 요약

SerialTool의 SPI/I2C 구조는 특정 chip/library에 고정하지 않는다.

```text
Application
  -> Transaction Protocol Contract
  -> Adapter Wrapper / Backend Registry
      -> PyFtdi Backend
          -> FT232H
          -> FT2232H
      -> CH347 Backend          # 후속
      -> MCP2210 Backend        # 후속, SPI only
      -> future backend
```

### 1차 구현 Target

```text
Tier 1
  -> FT232H
  -> FT2232H

Reference Python backend
  -> PyFtdi 0.57.x

Initial protocol
  -> SPI Master
  -> I2C Master
```

**FT2232H는 secondary/deferred adapter가 아니라 첫 구현 및 acceptance target에 포함한다.**

WHY:

- FT232H single-channel과 FT2232H multi-channel을 함께 지원해야 adapter identity/channel contract를 초기에 검증 가능
- CH347, MCP2210 등 vendor/library가 다른 bridge를 후속 추가할 수 있도록 상위 contract를 vendor-neutral하게 고정
- MCP2210처럼 SPI만 지원하는 chip도 capability model로 자연스럽게 표현 가능
- Serial stream semantics와 SPI/I2C transaction semantics를 분리

---

# 2. Architecture 원칙

Chip name이나 vendor library object를 Presenter/View/Session 상위 계층에 노출하지 않는다.

상위에서 사용하는 정본 개념:

```text
AdapterIdentity
AdapterDescriptor
AdapterCapabilities
AdapterProvider
AdapterHandle
AdapterBackendRegistry
SpiController
I2cController
```

Backend implementation만 다음을 안다.

```text
PyFtdi URL / controller object
CH347 DLL/API handle
MCP2210 HID handle
OS driver / USB selector
```

자세한 contract는 [`spi_i2c_adapter_architecture.md`](spi_i2c_adapter_architecture.md) 참조.

---

# 3. 1차 Target Hardware

## 3.1 FT232H

지원 목표:

- SPI Master
- I2C Master
- dedicated single MPSSE interface

장점:

- single channel이라 초기 bring-up과 wiring이 단순
- PyFtdi SPI/I2C API 검증용 reference로 적합

## 3.2 FT2232H — 첫 Target 포함

지원 목표:

- SPI Master
- I2C Master
- channel/interface selector
- dual-channel capability 표현

대표 acceptance topology:

```text
FT2232H
  channel A -> SPI
  channel B -> I2C
```

중요:

- channel A/B identity와 physical adapter identity를 분리해 표현
- Windows composite/libusb driver 정책을 backend가 캡슐화
- I2C clock stretching은 hardware wiring limitation을 명시

PyFtdi는 FT2232H를 SPI/I2C 지원 MPSSE device로 명시한다. SPI는 최대 30 MHz class interface이며 I2C도 지원한다. Mode 1/3은 MPSSE workaround라 신호 품질 제약이 있다.

---

# 4. 후속 Backend 후보

## 4.1 CH347

WCH 공식 자료 기준:

- USB 2.0 High Speed 480 Mbps
- active SPI host
- I2C host
- JTAG/SWD 계열 기능
- SPI 최대 60 MHz class
- I2C 최대 1 MHz class
- Windows/Linux driver/API 제공

의미:

- FTDI와 다른 vendor API 계열
- SPI/I2C를 한 chip에서 지원
- wrapper가 실제로 vendor-neutral한지 검증하기 좋은 2차 backend

## 4.2 MCP2210

Microchip 공식 자료 기준:

- USB HID 기반 SPI Master
- OS 표준 HID driver 사용 가능
- SPI mode 0/1/2/3
- 최대 12 Mbps class
- 최대 9 CS/GPIO line
- I2C 지원 없음

의미:

- **SPI-only capability backend** 사례
- I2C 없는 backend를 special-case 없이 `AdapterCapabilities`로 표현하는 검증 대상

## 4.3 기타

후속 후보:

- FT4232H/HA/HP
- FT4222H
- MCP2221A (I2C 중심)
- Aardvark/vendor adapter
- Linux native `spidev` / `smbus2`

이들을 추가할 때 Protocol/Presenter/UI contract를 변경하지 않는 것이 목표다.

---

# 5. Backend Capability 비교

| Backend/Chip | SPI | I2C | Multi-channel | Host/Driver 특징 | 초기 정책 |
| --- | --- | --- | --- | --- | --- |
| PyFtdi + FT232H | O | O | X | libusb/PyUSB | Tier 1 |
| PyFtdi + FT2232H | O | O | O, 2 channel | libusb/PyUSB | **Tier 1** |
| CH347 | O | O | device dependent | WCH vendor API/driver | Tier 2 |
| MCP2210 | O | X | X | USB HID | Tier 2 |
| Linux spidev/smbus2 | O | O | OS/device dependent | kernel native | deferred |

핵심 판단:

```text
backend 이름으로 feature 분기하지 않음
        |
        v
capability로 feature enable/validation
```

---

# 6. 공통 Capability Model

초기 `AdapterCapabilities`에서 최소 다음을 표현한다.

## 공통

- supported protocol set
- channel count / channel identity
- stable device identity 지원 여부
- concurrent channel capability

## SPI

- supported mode set
- min/max frequency
- half/full duplex
- chip-select count
- CS hold/continuation
- optional GPIO coexistence

## I2C

- 7-bit address
- optional 10-bit address
- repeated-start
- clock stretching
- min/max frequency

Backend가 capability를 광고하지 않으면 UI/Session은 connection/transaction 생성 전에 차단한다.

---

# 7. FTDI / PyFtdi 제한사항

## SPI

PyFtdi 공식 문서 기준:

- FT232H/FT2232H 등 MPSSE에서 SPI Master 지원
- half/full duplex 지원
- Mode 0/2는 native path
- Mode 1/3은 workaround이며 duty-cycle/signalling 제약 존재
- USB/MPSSE 특성상 precise time-controlled sequence에는 부적합

따라서 `spi_modes={0,1,2,3}`만 저장하지 않고 backend capability/quality note를 문서와 UI tooltip 수준에서 보존한다.

## I2C

- FT232H/FT2232H 모두 I2C Master 지원
- FT2232H는 open-collector 특성 때문에 clock stretching 시 추가 wiring/diode 고려 필요
- byte ACK마다 USB round trip이 개입해 medium/high-speed write throughput에 구조적 한계

초기 I2C use-case:

```text
register access
configuration read/write
board bring-up
production/test automation control transaction
```

대용량/high-throughput I2C write는 acceptance 성능 목표가 아니다.

---

# 8. Windows / Linux 정책

## Windows

FTDI/PyFtdi:

- PyFtdi는 Windows를 공식 지원 대상으로 보장하지 않음
- libusb/Zadig setup 필요 가능
- 기존 Serial VCP 장치 driver를 자동 교체하지 않음
- protocol adapter는 dedicated device로 운영

CH347/MCP2210 등 후속 backend는 각 provider가 자체 driver dependency를 관리한다.

앱은 driver를 자동 설치/교체하지 않는다.

## Linux

- PyFtdi: libusb + udev permission
- CH347/native backend 등은 provider별 setup policy
- OS-specific requirement는 provider metadata로 분리

---

# 9. Stable Adapter Identity

USB enumeration index를 persistent identity로 사용하지 않는다.

정본 DTO 방향:

```text
AdapterIdentity
  backend_id
  stable_id
  channel_id
```

예:

```text
FT2232H
  backend_id = pyftdi
  stable_id = FT9ABC12
  channel_id = 1

CH347
  backend_id = ch347
  stable_id = vendor serial/device identity

MCP2210
  backend_id = mcp2210
  stable_id = HID serial/path identity
```

vendor-specific selector parsing은 provider 내부 책임이다.

---

# 10. #11 Config 방향

기존 `PortConfig`에 vendor-specific optional field를 추가하지 않는다.

```text
ConnectionConfig
  protocol
  adapter: AdapterIdentity

SerialConfig
  port
  baudrate
  bytesize
  parity
  stopbits
  flow_control

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

FTDI URL, CH347 index, MCP2210 HID path는 상위 protocol config에 들어가지 않는다.

---

# 11. #11 Transport / Wrapper 방향

```text
StreamTransport
  -> Serial

Transaction Layer
  -> SpiController
  -> I2cController
       ^
       |
AdapterHandle
       ^
       |
AdapterProvider / Registry
       |
       +-- PyFtdiProvider
       +-- Ch347Provider
       +-- Mcp2210Provider
```

SPI/I2C를 Serial의 `read/in_waiting/write` loop에 맞추지 않는다.

---

# 12. Dependency Policy

#10 단계에서는 production dependency를 추가하지 않는다.

1차 구현 #12에서:

```text
PyFtdi 0.57.x
PyUSB/libusb runtime requirement
```

을 optional backend dependency로 추가하는 방식을 우선 검토한다.

향후 CH347/MCP2210 backend package/DLL이 없어도 SerialTool 전체 startup은 유지해야 한다.

---

# 13. Acceptance

P3-B #10 완료 조건:

- [x] chip/vendor-neutral wrapper 방향 확정
- [x] FT232H Tier 1 target
- [x] **FT2232H Tier 1 target**
- [x] CH347 follow-up backend capability 정리
- [x] MCP2210 SPI-only backend capability 정리
- [x] stable adapter/channel identity 방향
- [x] capability-driven feature validation 방향
- [x] Windows/Linux driver risk 분리
- [x] P3-B #11 config/wrapper contract 입력 확정

P3-B #12 hardware acceptance 최소 범위:

```text
FT232H
  -> enumerate/open
  -> SPI transaction
  -> I2C transaction
  -> disconnect/reopen

FT2232H
  -> enumerate by stable identity
  -> channel A/B 구분
  -> SPI transaction
  -> I2C transaction
  -> dual-channel lifecycle
  -> disconnect/reopen
```

---

# 14. Source References

- PyFtdi overview/features: https://eblot.github.io/pyftdi/
- PyFtdi SPI API: https://eblot.github.io/pyftdi/api/spi.html
- PyFtdi I2C API: https://eblot.github.io/pyftdi/api/i2c.html
- WCH CH347 datasheet/resources: https://www.wch-ic.com/downloads/CH347DS1_PDF.html
- Microchip MCP2210: https://www.microchip.com/en-us/product/mcp2210
