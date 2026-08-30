# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-31
> 기준 브랜치: `main`
> 현재 실행 순서: **P2 잔여 hardware gate → P3 확장 → P4 최종 환경/배포 검증**
> Post-merge 로드맵: [`doc/plans/roadmap_post_merge.md`](doc/plans/roadmap_post_merge.md)
> SPI/I2C 결정: [`doc/plans/spi_i2c_backend_decision_20260831.md`](doc/plans/spi_i2c_backend_decision_20260831.md)
> SPI/I2C wrapper: [`doc/plans/spi_i2c_adapter_architecture.md`](doc/plans/spi_i2c_adapter_architecture.md)

상태: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 일부 완료·외부 gate 대기

---

# 1. P2 — 구조 / 성능

## P2-A — Low-risk 구조 정리

1. [x] timeout/status duration/poll interval 상수화
   - MainPresenter status duration 포함 canonical constant 정리
   - literal regression contract 추가
   - PR #2 CI 4/4 Green

2. [x] legacy EventBus 완전 삭제
   - `core/event_bus.py`, `EventTopics`, EventBus fixture/test 제거
   - direct Qt signal topology 재도입 방지 contract
   - PR #3: Python 3.11 `639 passed, 2 warnings`, CI 4/4 Green

## P2-B — 증거 기반 성능 최적화

3. [x] benchmark scenario/baseline 재고정
   - Core micro benchmark 유지
   - `tools/runtime_benchmark.py`: RX pipeline + ConnectionWorker mixed RX/TX
   - PR #4: Python 3.11 `643 passed, 2 warnings`, CI 4/4 Green

4. [x] RxLogView `BatchRenderer` 필요성 재평가
   - 결론: **별도 BatchRenderer 미도입**
   - 현재 DataTrafficHandler + LogModel batching 유지
   - 기준: [`doc/benchmarks/rx_view_baseline_20260830.md`](doc/benchmarks/rx_view_baseline_20260830.md)

5. [-] Serial non-blocking I/O loop 최적화
   - software 변경 완료, 실제 USB Serial acceptance 미완료
   - Candidate B: active I/O → `yieldCurrentThread()`, pending-only → busy wait, idle → 1 ms wait
   - synthetic repeat=3: RX `226.700 MB/s`, TX `56.675 MB/s`, elapsed `70.578 ms`, stop `0.913 ms`
   - PR #7: Python 3.11 `652 passed, 2 warnings`, CI Green
   - 남은 gate: 실제 USB Serial open/close + sustained RX/TX + disconnect/reconnect + shutdown

## P2-C — Global state / package 구조

6. [x] SettingsManager singleton 제거
   - class-level singleton 제거
   - production 생성은 `main.py` composition root 1곳
   - hidden constructor / stale test reset 제거
   - PR #8: Python 3.11 `655 passed, 2 warnings`, CI 4/4 Green

7. [x] Coordinator package 이동 판단
   - 결론: **현재 이동하지 않음**
   - 현재 DI/ownership이 명확하고 import churn 대비 실익 부족
   - SPI/I2C/Plugin 확장으로 application orchestration이 실제 증가할 때 재평가

---

# 2. P3-A — Packet 기능 확장

8. [x] Structured Packet Filter
   - 완결 `PacketEvent` 이후 pure `PacketFilterEngine` 적용
   - declarative AND DSL: port/type/length/HEX/ASCII/byte-mask/checksum
   - arbitrary Python expression 미지원
   - malformed rule은 직전 valid filter 유지
   - PR #10: Python 3.11 `678 passed, 2 warnings`, CI 4/4 Green

9. [x] Packet Annotation / Selected-range Export
   - immutable `PacketRecord` + runtime `PacketAnnotationStore`
   - CSV / JSON / HEX / RAW selected export
   - background QThread + atomic replace
   - composition-root ownership / shutdown lifecycle
   - PR #11: Python 3.11 `695 passed, 2 warnings`, CI 4/4 Green

---

# 3. P3-B — SPI/I2C Multi-backend Transaction Platform

상세:

- [`doc/plans/spi_i2c_backend_decision_20260831.md`](doc/plans/spi_i2c_backend_decision_20260831.md)
- [`doc/plans/spi_i2c_adapter_architecture.md`](doc/plans/spi_i2c_adapter_architecture.md)

## 10. [x] Backend family / capability / wrapper architecture

결정:

```text
Transaction layer
  -> SpiController / I2cController
  -> AdapterHandle
  -> AdapterProvider / AdapterBackendRegistry
      -> PyFtdi backend: FT232H + FT2232H
      -> CH347 backend: 후속
      -> MCP2210 backend: 후속, SPI-only
      -> future backend
```

- chip/vendor-neutral capability-driven wrapper
- Tier-1 hardware: **FT232H + FT2232H**
- FT2232H A/B channel identity/lifecycle을 첫 구현에서 검증
- CH347는 SPI+I2C 확장 target
- MCP2210은 SPI-only capability target
- persistent USB enumeration index 금지
- stable identity: `backend_id + stable_id + optional channel_id`
- vendor library object/DLL/PyFtdi URL은 backend 밖으로 노출 금지
- PR #12: CI 4/4 Green, squash merge 완료

## 11. [x] Protocol config DTO + Adapter Wrapper / Transaction contract

구현 위치: `core/transport/transaction/`

### Vendor-neutral DTO / capability

- `AdapterIdentity`
- `AdapterDescriptor`
- `AdapterCapabilities`
- `SpiCapabilities` / `I2cCapabilities`
- `SpiConfig` / `I2cConfig`
- `SpiTransactionRequest` / `SpiTransactionResult`
- `I2cTransactionRequest` / `I2cTransactionResult`
- `TransactionConnectionConfig`

### Wrapper contract

- `AdapterProvider`
- `AdapterHandle`
- `AdapterBackendRegistry`
- `SpiController`
- `I2cController`

### Common control / error surface

- `TransactionOptions(timeout_ms)`
- thread-safe cooperative `CancellationToken`
- `BackendUnavailableError`
- `AdapterNotFoundError`
- `AdapterBusyError`
- `UnsupportedCapabilityError`
- `ProtocolConfigurationError`
- `TransactionTimeoutError`
- `TransactionIoError`
- `AdapterDisconnectedError`

### Legacy migration policy

기존 `PortConfig`는 현재 Serial runtime 호환을 위해 즉시 제거하지 않는다.

```text
legacy PortConfig(SPI)
  speed/mode -------------------+
                                v
new AdapterIdentity --------> LegacyPortConfigAdapter
                                |
                                v
                     TransactionConnectionConfig
```

- 기존 SPI `speed/mode`만 재사용
- adapter backend/stable identity/channel은 **사용자가 새 UI에서 선택한 값을 반드시 주입**
- 기존 설정에서 FTDI/CH347/MCP2210 identity를 추측하지 않음
- Serial `PortConfig`를 SPI로 암묵 변환하지 않음

### Architecture regression

Fake provider로 다음 조합을 동일 registry에서 검증:

- FT2232H channel A/B
- CH347 SPI+I2C
- MCP2210 SPI-only
- unavailable optional backend isolation
- capability mismatch
- duplicate backend registration
- vendor import leakage 금지

최신 PR #13 contract HEAD 검증:

```text
Windows / Python 3.11
  full pytest: 711 passed, 2 external lark warnings
  lint: success
  lang-keys: success
  task-boards: success
```

## 12. [ ] SPI/I2C backend / runtime / UI 구현

Tier-1:

- [ ] PyFtdi optional backend loader/provider
- [ ] FT232H enumerate/open
- [ ] FT232H SPI transaction
- [ ] FT232H I2C transaction
- [ ] FT2232H stable device + channel A/B enumeration
- [ ] FT2232H SPI transaction
- [ ] FT2232H I2C transaction
- [ ] FT2232H dual-channel lifecycle
- [ ] transaction worker/service + timeout/cancellation 실제 적용
- [ ] adapter discovery / protocol settings UI
- [ ] Settings persistence migration
- [ ] disconnect/reopen/shutdown
- [ ] actual accepted bus frequency 표시/보고
- [ ] 실제 FT232H + FT2232H hardware smoke

Architecture requirements:

- PyFtdi import는 backend implementation 내부에만 존재
- PyFtdi 미설치/driver unavailable이어도 SerialTool startup 유지
- CH347/MCP2210 provider 추가 시 Presenter/View/transaction contract 변경 금지
- SPI/I2C를 기존 Serial `read/in_waiting/write` worker loop에 억지로 통합하지 않음

---

# 4. P3-C — Plugin System

13. [ ] Plugin extension point 요구사항 확정
14. [ ] `PluginBase` / `PluginContext`
15. [ ] `PluginLoader` dynamic import / lifecycle / failure isolation
16. [ ] Example plugin

원칙:

- Packet/SPI-I2C의 실제 확장 사례를 경험한 뒤 public extension API를 고정
- MainWindow / ApplicationComponents / raw SettingsManager / ConnectionController registry 노출 금지

---

# 5. P3-D — Trigger-based Transmission

17. [ ] trigger-based transmission

마지막 수행 이유:

```text
RX -> Trigger -> TX -> Echo/RX -> Trigger
```

Macro / AutoTx / Broadcast / Local Echo / Packet Parser와 교차하므로 side effect가 가장 큼.

필수:

- origin tagging 또는 max depth
- cooldown
- one-shot
- target snapshot
- loop/reentrancy regression

---

# 6. P4 — 최종 환경 / 배포 검증

상세: [`doc/plans/environment_validation_plan.md`](doc/plans/environment_validation_plan.md)

18. [ ] 최신 `main` PyInstaller artifact build + smoke
19. [ ] Windows com0com Serial E2E
20. [ ] 실제 USB Serial 종합 검증
21. [ ] Linux socat 검증 — Linux가 실제 지원 대상일 때 필수

P4는 개별 feature hardware acceptance를 대체하지 않는다.

---

# 7. 현재 자동 검증 / 알려진 제한

자동 검증:

- Mock Serial / LoopbackTransport
- synthetic runtime benchmark
- offscreen Qt
- Windows/Ubuntu GitHub-hosted CI
- SPI/I2C fake multi-backend contract tests

제한:

- Serial worker 실제 USB hardware acceptance 미완료
- Packet annotation은 runtime-only
- PyFtdi Windows 사용은 공식 보장 대상이 아니며 libusb setup 필요 가능
- FT2232H I2C clock stretching hardware wiring 검증 필요
- PyFtdi I2C medium/high-speed write는 초기 성능 목표에서 제외
- CH347/MCP2210 production backend는 아직 구현 전

---

# 8. 공통 Gate / 완료 정의

```text
Owner / Boundary clear
+ Regression tests
+ No hidden global dependency
+ No worker -> QWidget access
+ Optional backend failure isolation
+ Ruff Green
+ Full pytest Green
+ Language / Task checks Green
+ GitHub Actions Green
+ Docs/Task synchronized
```

추가:

- 성능: benchmark evidence
- Serial I/O: 실제 USB Serial smoke
- SPI/I2C Tier-1: 실제 **FT232H + FT2232H** smoke
- SPI/I2C wrapper: vendor import leakage / capability mismatch tests
- Plugin: load failure isolation
- Trigger: loop/reentrancy tests
