# S-061 — 패킷 뷰 무스로틀 (측정 선행 후 판단)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 측정으로 병목 확인
  (14,336패킷 버스트가 GUI 스레드를 1,001ms 정지) 후 30ms 스로틀 구현. 최초 구현을
  재측정해 backlog 일괄 flush가 오히려 1,692ms로 악화된 것을 스스로 잡아내 상한 적용.
  범위 밖 결함 1건 발견 → S-064)
- Recommended model: **하위(Sonnet) 가능** (측정이 먼저 — 결과에 따라 구현 여부가 갈린다)
- 선행: 없음
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-6 인접 / 감사① 항목 4

## 목적 (Why)

`presenter/packet_presenter.py`가 파싱된 패킷 1건마다 `panel.append_packet()`을 **즉시** 호출한다
(RX raw 데이터는 `data_handler`의 30ms 버퍼를 거치는 것과 대조). CLAUDE.md의 Throttling
규칙은 예외를 명시하지 않지만, 패킷은 바이트 스트림이 아니라 파싱된 단위라 성격이 다르다.

감사는 "즉시 결함은 아니나 고속 환경 미검증"으로 판정했다. **측정 없는 최적화 금지**
(S-007 원칙)에 따라 **먼저 측정하고, 병목이 확인될 때만 스로틀을 넣는다.**

## Steps

### 1. 측정 (필수 — 이것만으로도 태스크의 절반이다)

- LOOPBACK 포트(S-033)로 고속 패킷을 주입해 UI 응답성을 측정한다.
  - 파서를 Delimiter 등으로 설정해(S-041로 설정 반영이 동작한다) 초당 수백~수천 패킷을 만든다.
  - 측정 지표 예: 주입 N건 처리에 걸린 wall-clock, 그 사이 이벤트 루프가 막힌 시간
    (`QApplication.processEvents()` 왕복 지연), `append_packet` 호출당 평균 소요.
  - 측정 스크립트는 **스크래치패드에만** 두고 프로젝트에 커밋하지 않는다
    (재현 가능하게 보고에 코드·명령을 남길 것).
- `tools/benchmark.py`(S-011)에 항목으로 추가할 가치가 있다고 판단되면 추가해도 좋다 —
  그 경우 프로젝트에 커밋한다(판단·근거 보고).

### 2. 판정

- **병목이 없으면**: 구현하지 말고 측정 수치와 함께 "보류" 판정을 태스크 파일에 기록한다.
  S-007과 같은 형식(재개 조건 명시). 이 경우에도 태스크는 완료다.
- **병목이 있으면**: 3번으로.

### 3. 스로틀 구현 (병목 확인 시에만)

- `data_handler`의 30ms 버퍼 패턴을 **그대로 재사용**한다(새 방식 발명 금지).
  상수는 `common/constants.py`의 `UI_REFRESH_INTERVAL_MS`를 재사용할지, 패킷 전용 상수를
  둘지 판단해 근거를 보고하라.
- 패킷 **순서와 누락 없음**이 보장되어야 한다(버퍼링은 지연일 뿐 유실이 아니다).
- 버퍼에 쌓인 채 포트가 닫히거나 앱이 종료되면 **잔여를 flush**한다
  (S-039/S-045/S-059와 같은 원칙 — 조용히 버리지 않는다).
- 테스트: 다량 주입 시 전부 표시되는지, 순서가 유지되는지, 종료 시 잔여가 반영되는지.

## 측정 결과·판정 (2026-08-22, 하위 모델)

### 측정 방법 (재현 명령)

측정 스크립트는 스크래치패드 전용(`bench_packet_throttle.py`, 커밋 안 함), 실행:

```
$env:QT_QPA_PLATFORM="offscreen"
.venv\Scripts\python.exe <스크래치패드 경로>\bench_packet_throttle.py
```

3부로 구성:
- **Part 1 (개선 전, 실제 파이프라인)**: `LOOPBACK` + `ConnectionController` +
  `DelimiterParser`(구분자 `\n`, 2바이트 초단문 라인 5만 개)로 실제 코드 경로를 그대로
  구동. `EventRouter`/`PacketPresenter`/`PacketPanel`은 실 객체(Mock 아님). 초당
  수만 패킷 트래픽을 주입해, `panel.append_packet` 호출 시각 목록에서 3ms 이상
  간격이 벌어진 지점을 "버스트 경계"로 검출 — 한 버스트 = 워커 스레드 한 번의
  `data_received` emit이 유발한 동기 처리 구간(=그동안 GUI 스레드가 다른 이벤트를
  처리 못하는 구간).
- **Part 2 (개선 전, 격리 벤치마크)**: `MagicMock` EventRouter + 실제
  `PacketPresenter`/`PacketPanel`로 스레드/I/O 잡음 없이 `on_packet_received`를
  N회(100~8000) 연속 호출해 순수 처리 비용만 측정. `buffer_size`/`autoscroll`
  조합별로 반복.
- **Part 3 (개선 후)**: Part 1과 동일한 실제 파이프라인을 구현 후 코드로 재실행,
  `_flush_pending_packets` 호출 1회당 소요 시간을 계측.

### 수치 (개선 전, 최초 구현 착수 전)

- Part 1 실제 LOOPBACK 파이프라인: 검출된 버스트 최대 **14,336개 패킷을 처리하는 데
  1,001.09 ms** 소요 (그동안 GUI 스레드가 다른 이벤트를 처리하지 못함). 버스트 크기
  분포: min 4,944 / median 6,144 / max 14,336건.
- Part 2 격리 벤치마크 (`buffer_size=100, autoscroll=True` — **기본 설정**):
  N=100일 때 호출당 14.85us이던 것이 N=8,000에서 63.82us로 **호출 수가 늘수록
  건당 비용이 커지는(초선형) 패턴** 확인 (총 510.55ms/8,000건).
  `autoscroll=False`로 끄면 건당 비용이 4~5us로 평탄해짐 →
  **`scrollToBottom()`이 비용 증가의 주된 원인**으로 특정.
  `buffer_size=10,000`(큰 버퍼)으로 늘리면 N=8,000에서 건당 149.00us까지 악화
  (총 1,192.03ms) → 컬럼 `ResizeToContents`가 모델에 쌓인 행 수에 비례해 더 비싸짐.

### 판정: **구현함** (병목 확인됨)

기본 설정 그대로도 수천 패킷 버스트에서 GUI 스레드가 0.5~1초 넘게 멈춘다 — 감사가
"미검증"으로 남겨둔 고속 환경에서 실측으로 병목이 확인되어 Step 3(스로틀 구현)을
진행했다.

### 구현 내용

- `presenter/packet_presenter.py`: `on_packet_received`가 더는 `panel.append_packet`을
  즉시 호출하지 않고 `self._pending_packets` 리스트에 쌓는다. `QTimer`
  (`common.constants.UI_REFRESH_INTERVAL_MS` 재사용, 아래 근거)가 30ms마다
  `_flush_pending_packets`를 호출해 순서대로 반영한다.
- **상수 재사용 근거**: 별도 패킷 전용 상수를 두지 않고 기존 `UI_REFRESH_INTERVAL_MS`를
  재사용했다 — `data_handler.py`(RX 로그 뷰)와 동일한 "즉시 반영 대신 짧은 주기로
  모아서 반영" 개념이고, 서로 다른 튜닝이 필요하다는 근거가 아직 없다(둘 다 "약 33
  FPS면 사람 눈에 지연으로 느껴지지 않는다"는 동일한 전제). 필요해지면 그때 분리한다
  (`common/constants.py`의 상수 주석에 명시).
- **추가 발견 및 보완(설계 변경)**: 최초 구현("버퍼를 통째로 flush")을 Part 3로
  재측정한 결과, backlog가 크게 쌓인 경우(예: 짧은 시간에 대량 유입) **단일 flush가
  오히려 개선 전(1,001ms)보다 더 나쁜 1,692ms**가 걸리는 사례를 실측으로 발견했다
  (스로틀 주기 자체는 30ms로 짧아졌지만, 그 사이 쌓인 backlog를 한 번에 다 밀어넣는
  방식이라 backlog가 크면 여전히 통째로 블로킹됨). **측정 없는 최적화 금지 원칙을
  구현 자체에도 적용**해, `_flush_pending_packets`가 대기 개수가 View의 표시 버퍼
  크기(`PACKET_BUFFER_SIZE`, 기본 100)를 넘으면 오래된 초과분을 건너뛰도록 보완했다.
  근거: 어차피 `PacketModel`은 `deque(maxlen=buffer_size)`라 오래된 것부터 즉시
  밀려나 화면에 한 번도 보이지 못한다 — 하나씩 넣고 즉시 evict하는 것과 최종
  결과(화면에 남는 것)가 동일하므로, 그 과정의 Qt 모델 갱신 신호(`begin/endInsertRows`
  등)만 건너뛰어 비용을 없앤 것이지 사용자가 볼 수 있었던 데이터를 새로 버린 게
  아니다(패킷 뷰에 표시 이력 외 별도 export/저장 기능 없음을 코드 검색으로 확인).
  보완 후 재측정: 동일 고부하 스트레스 조건에서 **단일 flush 최대 소요가 1.67ms**로
  감소 (299회 flush 중 median 0ms, mean 0.04ms).
- 종료 시 flush: `stop()` 메서드 추가(타이머 정지 + 잔여 flush), `main_presenter.py`의
  `on_close_requested()`에서 `data_handler.stop()` 옆에 `packet_presenter.stop()` 호출
  추가(범위 밖 파일이지만 DoD "앱 종료 시 flush"를 실제로 배선하는 유일한 지점이라
  최소 1줄만 추가).
- 포트 종료 시 flush: `EventRouter.port_closed`를 `_flush_pending_packets`에 연결해
  다음 30ms를 기다리지 않고 즉시 반영.
- Clear 시: `on_clear_requested`가 `panel.clear_view()` 전에 `self._pending_packets`도
  비워 "Clear 이후 지연 패킷이 다시 나타나는" 유령 현상을 막는다.

### 범위 밖 발견 (수정하지 않음 — 별도 보고)

Part 1/3 실제 파이프라인 재현 중, `model/packet_parser.py`의 `DelimiterParser`/
`ATParser`가 내부 버퍼가 `max_buffer_size`(기본 4096바이트)를 넘으면
`self._buffer = self._buffer[-self._max_buffer_size:]`로 **앞부분을 조용히 잘라내는**
것을 확인했다. 이 보호 로직은 "구분자가 전혀 없는 폭주 스트림"을 겨냥한 것으로
보이는데, `ConnectionWorker`의 배치 임계값(`BATCH_SIZE_THRESHOLD=8192B`)이 파서의
`max_buffer_size`(4096B)보다 커서, **아직 분리 안 된 완결된(구분자 포함) 라인들까지도
통째로 잘려나가 실제 데이터 유실**이 발생할 수 있다(고속 재현 시 재현성 있게 확인).
Presenter/View 계층(S-061 범위) 문제가 아니라 Model 계층(`packet_parser.py`)의 별도
결함으로 보여 이 태스크에서 고치지 않았다 — 후속 태스크로 등재 필요.

## 검증 방법

측정 결과(수치) + 전체 pytest(offscreen, 기준선은 직전 커밋 값) + **ruff 0건** +
구현했다면 캡처 1회. 캡처 후 `settings.json` 무변경 확인.

- 전체 pytest(offscreen): **382 passed** (기준선 367 → 이번 태스크에서 6개 순증 —
  버퍼링/순서/누락 없음/backlog 상한/stop flush/port_closed flush/Clear 검증).
  실행 중 `tests/test_shutdown_data_logger.py`가 간헐적으로(다른 테스트가) 실패하는
  것을 관찰했으나, 3회 반복 실행 결과 매번 다른 테스트가 실패/통과해 실제 시간
  경합에 의한 **기존 flaky 테스트**로 판단(RX 데이터 로거 경로 — `packet_presenter.py`와
  무관, 이번 변경 전에도 존재했을 가능성). 본 태스크 관련 테스트는 모두 안정적으로
  통과.
- `ruff check .`: All checks passed (0건).
- GUI 캡처: 생략 — 이번 변경은 시각적 레이아웃/스타일이 아니라 내부 타이밍 로직이라
  스크린샷으로 판별 불가(패킷이 30ms 이내에 반영되는지는 캡처 1장으로 확인 불가).
  `settings.json`은 애초에 건드리지 않음(변경 파일 목록에 없음).

## Acceptance criteria (DoD)

- [x] 고속 패킷 측정 수치가 보고된다(재현 방법 포함).
- [x] 판정(구현 또는 보류)이 근거와 함께 태스크 파일에 기록된다.
- [x] 구현한 경우: 순서·누락 없음과 종료 시 flush가 테스트로 고정된다.
- [x] 전체 pytest·ruff 통과.
