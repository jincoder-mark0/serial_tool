# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-30
> 기준 브랜치: `main`
> Presenter/View Boundary 리팩토링: PR #1 squash merge 완료
> 상세 리팩토링 보고서: [`doc/refactoring_validation_report_20260830.md`](doc/refactoring_validation_report_20260830.md)
> Post-merge 상세 계획: [`doc/plans/roadmap_post_merge.md`](doc/plans/roadmap_post_merge.md)
> 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

이 문서는 **현재 완료 상태와 앞으로 해야 할 일**을 관리하는 유일한 작업 보드다.
과거 S-xxx 상세 이력은 `doc/CHANGELOG.md`, `doc/history/`, `tasks/`에 보존한다.

상태 표기: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 보류

---

# 1. 현재 상태

Presenter/View Boundary 구조 리팩토링은 완료 및 `main` 반영됐다.

```text
PR #1 squash merge: 완료
Local Windows / Python 3.13.15: 643 passed
Ruff: 0 errors
Language key integrity: Green
Task board consistency: Green
PR Python 3.11 GitHub Actions: 4/4 Green
main push CI: Green
```

현재는 **post-merge 개선 및 확장 단계**다.

---

# 2. 제품 기능 및 구조 리팩토링 — 완료

## 제품 기능 기준선

- [x] 다중 Serial port tab과 연결/해제/설정
- [x] Manual TX/RX, Local Echo, Prefix/Suffix, Newline mode, Broadcast
- [x] Manual command history와 Auto Tx scheduler
- [x] Macro list/load/save/run, Delay/Expect, 반복 실행
- [x] Packet Inspector와 Raw/AT/Delimiter/Fixed-Length parser
- [x] File Transfer chunk 전송, progress, cancel, backpressure
- [x] RX/TX/System logging과 BIN/HEX/PCAP format
- [x] QSmartListView 기반 대용량 log view와 검색
- [x] Theme, SVG icon, dual font, 한국어/영어 localization
- [x] GlobalErrorHandler, RingBuffer, ThreadSafeQueue
- [x] RX/UI benchmark (`tools/benchmark.py`, `doc/benchmark_20260822.md`)
- [x] Windows PyInstaller executable build와 smoke test
- [x] GitHub Actions Windows CI

## Architecture

- [x] Single Composition Root (`ApplicationBootstrapper`)
- [x] Passive View + explicit DI
- [x] direct Qt signal topology
- [x] EventRouter 제거
- [x] MainPresenter God-object 축소
- [x] CommandTransmissionService 분리
- [x] PacketParserManager / ConnectionSessionFactory 분리
- [x] FileTransferManager / PortScanManager / MacroScriptManager 분리
- [x] Settings / Logging / Status / Shutdown / ControlState Coordinator 분리
- [x] stale worker queued signal reconnect race 교정
- [x] shutdown/data preservation ordering 고정

---

# 3. 검증 기준선

```text
Local Windows / Python 3.13.15 / offscreen
  full pytest: 643 passed, 0 failed, 0 skipped
  ruff: 0 errors
  language key integrity: Green
  task board consistency: Green

PR #1 / GitHub Actions / Python 3.11
  test-windows: success
  lang-keys: success
  task-boards: success
  lint: success
```

검증 범위:

- 자동: Mock Serial, LoopbackTransport, offscreen Qt
- 별도 환경 검증: Windows com0com, Linux socat, 실제 USB Serial 장치

알려진 제한사항:

- blocking OS port scan / macro file load helper는 Python thread 특성상 강제 종료하지 않음
- manager가 outstanding helper를 기능별 최대 1개로 제한
- language key 동적 표현식 7건은 정적 검사 불가
- Python 3.13에서 외부 `lark` dependency warning 2건

---

# 4. Post-merge 상세 계획

통합 로드맵:

- [`doc/plans/roadmap_post_merge.md`](doc/plans/roadmap_post_merge.md)
- [`doc/plans/performance_optimization_plan.md`](doc/plans/performance_optimization_plan.md)
- [`doc/plans/architecture_cleanup_plan.md`](doc/plans/architecture_cleanup_plan.md)
- [`doc/plans/extension_platform_plan.md`](doc/plans/extension_platform_plan.md)

---

# 5. P2 — 성능

상세: [`performance_optimization_plan.md`](doc/plans/performance_optimization_plan.md)

- [-] RxLogView `BatchRenderer` 도입 필요성 benchmark 기반 재평가
- [-] Serial non-blocking I/O loop 최적화

---

# 6. P2 — 구조

상세: [`architecture_cleanup_plan.md`](doc/plans/architecture_cleanup_plan.md)

- [-] Coordinator를 별도 `application/` / `coordinator/` package로 이동
  - 실제 필요성 조건 충족 시에만 진행
- [-] legacy `core/event_bus.py` 완전 삭제
- [-] SettingsManager singleton 자체 제거
- [-] timeout/status duration 상수화

---

# 7. P3 — 확장 기능

상세: [`extension_platform_plan.md`](doc/plans/extension_platform_plan.md)

- [-] Plugin system
  - [-] `PluginBase` interface
  - [-] `PluginLoader` dynamic import
  - [-] Example plugin
- [-] SPI/I2C Transport
- [-] TCP/UDP session
- [-] 구조화 packet filter
- [-] trigger-based transmission
- [-] packet annotation / selected-range export

---

# 8. 환경 / 배포 검증

- [-] Windows com0com 가상 Serial 검증
- [-] Linux socat 가상 Serial 검증
- [-] 실제 USB Serial 장치 검증
- [-] 현재 `main` 기준 PyInstaller artifact smoke 재검증

---

# 9. 작업 공통 Gate

변경은 기능별 branch/PR에서 수행한다.

```text
targeted tests
    -> architecture/lifecycle tests
    -> ruff
    -> full pytest
    -> language/task checks
    -> GitHub Actions
```

성능 작업은 benchmark evidence가 추가 gate다.

---

# 10. 완료 정의

각 P2/P3 작업은 다음을 만족할 때 완료 처리한다.

```text
Owner/Boundary clear
+ Regression tests
+ No hidden global dependency
+ No worker -> QWidget access
+ Ruff Green
+ Full pytest Green
+ CI Green
+ Docs/Task synchronized
```
