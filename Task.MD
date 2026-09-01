# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-09-01 (코드 대조 기준 커밋 `9de58c3`)
> 기준 브랜치: `main`
> 현재 실행 순서: **P2 잔여 hardware gate → P3 확장 → P4 최종 환경/배포 검증**
> Post-merge 로드맵: [`doc/plans/roadmap_post_merge.md`](doc/plans/roadmap_post_merge.md)
> SPI/I2C 결정: [`doc/plans/spi_i2c_backend_decision_20260831.md`](doc/plans/spi_i2c_backend_decision_20260831.md)
> SPI/I2C wrapper: [`doc/plans/spi_i2c_adapter_architecture.md`](doc/plans/spi_i2c_adapter_architecture.md)

상태: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 일부 완료·외부 gate 대기

> 이 보드는 **코드와 대조한 시점**을 위에 적는다. 2026-09-01 대조에서 12번 하위 14개가
> 전부 `[ ]`였으나 실제로는 13개가 병합·테스트되어 있었다(PR #15·#16·#17, 67커밋 격차).
> 병합 후 보드를 갱신하지 않으면 다음 세션이 완료된 작업을 다시 만든다 —
> `doc/mistakes.md` #6·#8과 같은 양상이며, `tools/check_task_boards.py`는
> 인덱스 정합성만 보므로 이 종류의 어긋남은 잡지 못한다.

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

## 12. [-] SPI/I2C backend / runtime / UI 구현

소프트웨어는 PR #15·#16·#17로 병합됐고, 남은 gate는 **실제 하드웨어 acceptance** 하나다.

`[x]` = 하드웨어 없이 완결되는 항목 / `[-]` = 소프트웨어 완료·실기기 gate 대기

Tier-1:

- [x] PyFtdi optional backend loader/provider
  - `test_provider_is_unavailable_when_optional_backend_prerequisite_is_missing`
  - `test_provider_is_unavailable_when_optional_package_import_fails`
  - `test_pyftdi_backend_is_lazy_imported`
- [-] FT232H enumerate/open
  - `test_enumerates_ft232h_and_ft2232h_channels_with_stable_identity`
  - `test_missing_serial_uses_explicit_non_persistent_usb_locator`
- [-] FT232H SPI transaction — `test_manager_executes_spi_transaction_and_emits_result`
- [-] FT232H I2C transaction — `test_i2c_repeated_start_and_split_transactions_map_to_pyftdi_port`
- [-] FT2232H stable device + channel A/B enumeration
  - `test_registry_supports_ft2232h_channel_identity_without_vendor_special_case`
- [-] FT2232H SPI transaction
  - `test_ft2232h_channel_b_spi_transaction_is_wrapped_without_vendor_leakage`
- [-] FT2232H I2C transaction — I2C wrapper는 채널 공통 경로. FT2232H 전용 I2C 테스트는 없음
- [-] FT2232H dual-channel lifecycle
  - `test_handle_prevents_two_protocol_owners_on_same_ftdi_interface`
  - `test_duplicate_session_name_is_rejected_until_close`
- [x] transaction worker/service + timeout/cancellation 실제 적용
  - `test_transaction_options_rejects_non_positive_timeout`
  - `test_cancellation_token_is_thread_safe_cooperative_state`
  - `test_cancel_active_transaction_is_thread_safe`
  - `test_cancellation_is_checked_before_vendor_io`
- [x] adapter discovery / protocol settings UI
  - `test_async_discovery_emits_vendor_neutral_descriptors`
  - `tests/test_transaction_manual_control.py` (Serial/SPI/I2C 옵션 노출)
- [x] Settings persistence migration
  - `test_legacy_spi_migration_requires_explicit_adapter_identity`
  - `test_legacy_serial_config_is_not_silently_converted_to_spi`
- [-] disconnect/reopen/shutdown
  - `test_usb_disconnect_error_is_translated_to_common_error`
  - `TransactionManager.close_session/stop_discovery/shutdown` + manager 테스트
- [-] actual accepted bus frequency 표시/보고
  - 백엔드가 `actual_frequency_hz`로 보고, `ManualControlPresenter`가 표시
  - `test_pyftdi_backend.py` 실측 assert (`4_000_000`)
- [ ] 실제 FT232H + FT2232H hardware smoke
  - **유일하게 남은 실질 gate.** 현재 개발 환경에는 PyFtdi가 설치조차 되어 있지 않다
    (그 상태로 전체 테스트가 통과하는 것이 optional backend 격리의 증거이기도 하다)

런타임 점검(2026-09-01, 실패·경합 경로를 실제로 돌림):

- 고침 — 세션 종료 시 **큐에 남은 transaction이 결과 신호 없이 사라졌다**.
  request ID 4건 발급 후 close/shutdown하면 실행 중 1건만 `transaction_failed`를
  받고 나머지는 2초를 기다려도 무응답이었다. 결과를 기다리는 호출자는 영원히
  기다리고 사용자에게 오류 표시도 없다 — S-080이 매크로에서 없앤 것과 같은 침묵.
  `run()` finally에서 큐를 비우며 통지하도록 고쳤다.
  회귀: `test_queued_transactions_are_answered_when_session_closes`,
  `test_pending_failures_are_reported_before_session_closed`
- 확인했고 정상이던 것 — 열지 않은/닫힌 세션 `execute()`는 None 반환,
  진행 중 shutdown/close는 협조적 취소로 즉시 정리, `controller.close()` 예외는
  격리되어 같은 이름 재오픈 가능, discovery+session 동시 종료 후 스레드 누수 없음

추가 점검(2026-09-02) — **위 S-084 수정만으로는 침묵이 다 없어지지 않았다**:

- 고침 — 큐에서 **꺼낸 뒤** stop()이 도착하면 그 1건이 여전히 사라졌다 (S-085).
  worker는 `get()`으로 command를 꺼낸 다음 lock을 잡고 `_stop_requested`를 확인해
  `break` 하는데, 그 command는 이미 큐 밖이라 `_fail_pending_transactions()`의
  큐 드레인도 잡지 못한다. 인터리빙을 고정해 재현하면 발급 3건 중 1번이 완료도
  실패도 없이 사라졌다. break 전에 통지하도록 고쳤다.
  회귀: `test_dequeued_transaction_is_answered_when_stop_arrives_mid_loop`
- 교훈 — "큐를 비우며 통지"는 큐에 **남아 있는** 것만 덮는다. 큐에서 꺼낸 뒤
  실행 전까지의 구간도 소유자가 있어야 한다

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
- **보드가 인용한 PR 번호(#2·#3·#4·#7·#8·#10·#11·#15·#16·#17)가 현재 origin
  (`jincoder-mark0/serial_tool`)의 PR과 대응하지 않는다.** 그 저장소의 merged PR은
  2025-12자 #1~#17이고 head branch 이름도 전혀 다르다. 근거 추적 시 PR 번호 대신
  커밋 해시를 쓸 것. 원격 브랜치 23개의 병합 여부도 이 때문에 확인이 안 되어
  정리를 보류했다

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
