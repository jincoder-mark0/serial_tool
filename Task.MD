# Task.MD — SerialTool 현재 작업 보드

> 최종 갱신: 2026-08-30
> 현재 기준 브랜치: `main`
> Presenter/View Boundary 리팩토링: PR #1 squash merge 완료
> 에이전트 규칙: [`AGENTS.md`](AGENTS.md)

이 문서는 **현재 완료 상태와 앞으로 해야 할 일**을 관리하는 유일한 작업 보드다.
과거 S-xxx 상세 이력은 `tasks/`, `doc/history/`, `doc/CHANGELOG.md`에 보존한다.

상태 표기: `[x]` 완료 / `[ ]` 해야 함 / `[-]` 보류

---

# 1. 현재 상태

## 리팩토링 / 검증 완료

- [x] Single Composition Root / explicit DI
- [x] MainPresenter 책임 축소
- [x] EventRouter 제거 / direct Qt signal 정리
- [x] CommandTransmissionService 도입
- [x] ConnectionSessionFactory / PacketParserManager 분리
- [x] FileTransferManager / PortScanManager / MacroScriptManager 분리
- [x] Settings/Control/Logging/Status/Shutdown Coordinator 분리
- [x] stale API / constructor 감사
- [x] worker lifecycle / shutdown / data-preservation 감사
- [x] reconnect queued-signal race 수정
- [x] file transfer write-idle/error 완료 판정 보강
- [x] local full pytest / Ruff / repository consistency Green
- [x] PR #1 GitHub Actions Python 3.11 4/4 Green
- [x] PR #1 squash merge
- [x] main post-merge CI Green
- [x] 작업 보드 `Task.MD` 단일화

검증 snapshot:

```text
Local Windows / Python 3.13.15 / offscreen
  architecture contract: 33 passed
  lifecycle/data-preservation: 45 passed
  core feature: 75 passed
  full pytest: 643 passed, 0 failed, 0 skipped
  Ruff: 0 errors
  language keys: Green
  task board consistency: Green

PR #1 / GitHub Actions / Python 3.11
  test-windows: success
  lang-keys: success
  task-boards: success
  lint: success

main push CI
  squash merge commit: Green
  post-merge docs commit: Green
```

---

# 2. 제품 기능 기준선 — 완료

- [x] 다중 Serial port tab과 연결/해제/설정
- [x] Manual TX/RX, Local Echo, Prefix/Suffix, Newline, Broadcast
- [x] Manual command history / Auto Tx
- [x] Macro load/save/run, Delay/Expect, 반복/Broadcast
- [x] Packet Inspector와 주요 framing parser
- [x] File Transfer, progress, cancel, backpressure
- [x] RX/TX/System logging, BIN/HEX/PCAP
- [x] QSmartListView 기반 대용량 log view와 검색
- [x] Theme / SVG icon / dual font / ko-en localization
- [x] GlobalErrorHandler / RingBuffer / ThreadSafeQueue
- [x] RX/UI benchmark 기반선
- [x] PyInstaller onedir 구성
- [x] GitHub Actions Windows CI

---

# 3. Architecture Invariant

```text
main.py
  -> ApplicationBootstrapper
    -> Model / Service
    -> Presenter
    -> Coordinator
    -> static signal wiring
    -> MainPresenter
    -> ApplicationComponents
```

Dependency direction:

```text
Common <- Core <- Model <- Presenter/Coordinator <- View
```

유지 규칙:

- [x] `ApplicationBootstrapper` = 유일한 runtime composition root
- [x] View -> Model 직접 import 금지
- [x] Model -> Presenter/View import 금지
- [x] worker -> QWidget 접근 금지
- [x] Presenter hidden singleton/manager fallback 금지
- [x] EventRouter 재도입 금지
- [x] production 주요 event direct Qt signal 사용
- [x] shutdown data-preservation ordering 유지

---

# 4. 검증 범위 / 알려진 제한사항

## 자동 검증 범위

- [x] Mock Serial
- [x] LoopbackTransport
- [x] offscreen Qt
- [x] Windows Python 3.13 local
- [x] GitHub-hosted Windows/Ubuntu Python 3.11 CI

## 미검증 / 후속 검증

- [ ] Windows com0com virtual Serial
- [ ] Linux socat virtual Serial
- [ ] 실제 USB Serial 장치 E2E
- [ ] 최신 `main` 기준 PyInstaller artifact smoke

## 알려진 제한사항

- Port scan / Macro load의 blocking OS/file I/O는 Python helper thread 자체를 강제 종료하지 않음.
- Manager는 outstanding helper 생존 중 retry를 거부해 기능별 stuck helper를 최대 1개로 제한.
- language key 동적 표현식 일부는 정적 검사에서 warning으로 남음.
- Python 3.13 local에서 외부 `lark` dependency warning이 존재할 수 있음.
- `core/event_bus.py`는 production 주요 runtime path에는 미사용이나 legacy/core test utility로 남음.

---

# 5. Post-merge backlog

현재 신규 작업은 아래 backlog에서 우선순위를 정해 착수한다.

## P1 — 환경 / 배포 검증

- [ ] Windows com0com 가상 Serial 검증
- [ ] Linux socat 가상 Serial 검증
- [ ] 실제 USB Serial 장치 E2E 검증
- [ ] 최신 `main` PyInstaller onedir build + smoke test

## P2 — 성능

- [-] RxLogView `BatchRenderer` 도입 필요성 benchmark 기반 재평가
- [-] Serial non-blocking I/O loop 최적화

## P2 — 구조

- [-] Coordinator를 별도 `application/` / `coordinator/` package로 이동
- [-] legacy `core/event_bus.py` 완전 삭제
- [-] SettingsManager singleton 자체 제거
- [-] timeout/status duration 상수화

## P3 — 확장 기능

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

# 6. 작업 규칙

변경 후 작은 범위부터 검증을 확대한다.

```text
closest tests
  -> architecture/lifecycle tests if relevant
  -> ruff
  -> full pytest
  -> language/task consistency if relevant
  -> GitHub Actions
```

검증하지 않은 항목은 완료로 체크하지 않는다.

문서 변경 시 현재 상태를 `Task.MD`에 반영하고, 사용자 관점의 의미 있는 변경은 `doc/CHANGELOG.md`에 기록한다.
