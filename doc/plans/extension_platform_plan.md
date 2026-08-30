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

# 2. Phase 1 — Structured Packet Filter — 완료

## 최종 구조

PacketParser 이후의 완결 Packet/Event만 filtering한다.

```text
Raw RX
 -> PacketParserManager
 -> PacketEvent
 -> PacketPresenter
 -> PacketFilterEngine
 -> PacketViewData
 -> PacketPanel
```

Raw RX Fast Path와 parser 내부에는 filter를 넣지 않는다.

## Owner / Boundary

`model/packet_filter.py`:

- `PacketFilterEngine`: expression compile 책임
- `CompiledPacketFilter`: immutable compiled rule collection
- `PacketFilterContext`: filter가 읽는 packet snapshot
- `PacketFilterSyntaxError`: malformed expression의 단일 오류 surface

`PacketPresenter`:

- 현재 valid compiled filter 보유
- filter enable 상태 보유
- `PacketEvent`에서 context 생성 후 match 판정
- malformed expression이면 기존 valid filter 유지

`PacketPanel`:

- Filter enable checkbox
- expression input
- syntax error feedback
- filter 자체의 parsing/matching logic은 소유하지 않음

## DSL

semicolon(`;`)으로 분리된 모든 clause를 AND 조건으로 평가한다.

```text
port=COM3
 type=AT
len=8
len=8..32
hex*=DE AD
hex^=AA55
ascii*=OK
ascii^=AT+
byte[0]=0xAA
byte[1]=10..20
byte[0]&0xF0=0xA0
checksum=ok
checksum=fail
checksum=none
```

지원 범위:

- port/type equality
- packet length equality/range
- raw byte sequence contains/prefix
- latin-1 text contains/prefix
- byte offset equality/range
- masked byte condition
- checksum state

초기 제외:

- arbitrary Python expression
- regex
- OR / nested boolean group
- user-defined callback
- raw RX filtering

WHY:

- arbitrary expression은 execution/sandbox/error surface를 불필요하게 확대
- 1차 목표는 predictable, compile-time validated, testable filtering
- 복잡한 boolean DSL은 실제 요구가 확인될 때 확장

## Malformed Rule Policy

```text
사용자 expression 편집
 -> compile 성공
    -> active compiled filter 교체
    -> error feedback clear

 -> compile 실패
    -> 직전 valid compiled filter 유지
    -> PacketPanel에 error 표시
    -> RX/Parser runtime에는 예외 전달 안 함
```

## Checksum 공유

`checksum=...` filtering과 CHK 컬럼 표시가 서로 다른 결과를 만들지 않도록
`PacketPresenter`가 checksum을 한 번 계산하고 FilterContext와 PacketViewData가 같은 값을 공유한다.

## 검증

- pure engine DSL unit tests
- filter off 기존 path regression
- matching/non-matching packet integration
- invalid expression이 직전 valid filter를 유지하는지 검증
- language key integrity
- full pytest / Ruff / task-board checks

PR #10 구현 HEAD 검증:

```text
Windows / Python 3.11
  full pytest: 678 passed, 2 external lark warnings
  lint: success
  lang-keys: success
  task-boards: success
```

Acceptance:

- filter off 시 기존 경로와 behavior 동일 — 완료
- Raw RX Fast Path 영향 없음 — 완료
- malformed rule runtime isolation — 완료
- View가 filter parsing logic을 소유하지 않음 — 완료
- full CI Green — 완료

---

# 3. Phase 2 — Packet Annotation / Selected-Range Export — 완료

## 3.1 최종 구조

Parser가 만든 Packet 객체나 표시용 `PacketViewData`를 annotation 때문에 mutation하지 않는다.

```text
PacketEvent
 -> PacketPresenter
 -> PacketRecord immutable snapshot
    - packet_id
    - port
    - timestamp/display time
    - packet type
    - raw bytes
    - HEX / ASCII
    - checksum state
    - annotation snapshot
 -> PacketModel
 -> selection
```

Annotation:

```text
selected packet_id(s)
 -> PacketPresenter
 -> PacketAnnotationStore
 -> PacketPanel cached PacketRecord update
```

Export:

```text
selected PacketRecord tuple
 -> PacketPresenter
 -> PacketExportManager
 -> QThread export worker
 -> temporary file
 -> os.replace()
```

## 3.2 Owner / Boundary

`common/packet_records.py`:

- `PacketRecord`: annotation/export용 immutable packet snapshot
- export 시작 이후 View selection/row eviction과 독립적인 data contract

`model/packet_annotation_store.py`:

- `packet_id -> note` runtime state owner
- empty note는 annotation 삭제
- Parser Packet / View DTO mutation 없음

`model/packet_export_manager.py`:

- export worker lifecycle owner
- CSV / JSON / HEX text / RAW binary 지원
- background QThread file I/O
- temporary file + atomic `os.replace`
- 실패 시 temporary file cleanup

`PacketPresenter`:

- stable runtime packet identity 발급 (`<port>:<sequence>`)
- annotation use-case orchestration
- selected immutable record snapshot을 export manager로 전달
- shutdown 시 export manager bounded stop

`PacketPanel / PacketModel`:

- Extended row selection
- Note column / tooltip
- Note dialog / Export save dialog
- display DTO와 `PacketRecord`를 parallel bounded deque로 정렬 유지
- selection을 immutable record tuple로 반환
- file write / annotation source-of-truth 소유하지 않음

`ApplicationBootstrapper`:

- `PacketAnnotationStore`, `PacketExportManager` 생성
- `PacketPresenter`에 explicit injection
- `ApplicationComponents`에서 strong reference 유지

## 3.3 Annotation 정책

현재 annotation은 **runtime session state**로 한정한다.

```text
앱 실행 중 annotation 유지
Clear Packet View -> annotation store clear
앱 종료 -> annotation 소멸
SettingsManager에 저장하지 않음
```

WHY:

- persistent annotation을 도입하려면 session/file identity, stale record migration, 저장 위치 정책이 추가로 필요
- 우선 분석 workflow의 note 기능을 안정화하고 실제 persistence 요구가 확인될 때 별도 feature로 설계

## 3.4 Selected Export 형식

CSV:

```text
time, port, type, hex, ascii, checksum, annotation
```

JSON:

```text
packet_id / time / port / type / raw_hex / ascii / checksum / annotation
```

HEX Text:

- selected packet당 1 line
- time / port / type / HEX / optional annotation

RAW Binary:

- selected packet raw bytes를 selection order대로 concatenate
- 별도 delimiter는 삽입하지 않음

## 3.5 File I/O 정책

큰 selection에서 UI thread file I/O를 하지 않는다.

```text
View selection
 -> immutable tuple snapshot
 -> background QThread
 -> temp write
 -> atomic replace
```

Worker가 실행된 뒤 View가 clear/scroll/annotation 변경되어도 현재 export snapshot에는 영향이 없다.

## 3.6 검증

- AnnotationStore가 Packet snapshot과 독립인지 검증
- empty annotation removal
- CSV/JSON/HEX/RAW output contract
- raw byte preservation
- atomic replace / failed temp cleanup
- PacketModel buffer eviction/resize 시 display-record alignment
- row selection dedupe/order
- annotation column update
- PacketPresenter stable packet identity
- Presenter annotation/store/View sync
- export request immutable snapshot 전달
- presenter stop -> export owner stop

PR #11 구현 HEAD 검증:

```text
Windows / Python 3.11
  full pytest: 695 passed, 2 external lark warnings
  lint: success
  lang-keys: success
  task-boards: success
```

Acceptance:

- Packet DTO mutation 없음 — 완료
- stable selection/export snapshot — 완료
- selected-range export 4 format — 완료
- UI thread file I/O 없음 — 완료
- export failure가 기존 target file을 훼손하지 않음 — 완료
- View bounded-buffer와 record alignment 유지 — 완료
- composition-root ownership / shutdown lifecycle 명시 — 완료
- full CI Green — 완료

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
1. Structured Packet Filter [완료]
2. Packet Annotation / Selected-range Export [완료]
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
