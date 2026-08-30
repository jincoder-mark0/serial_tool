# RxLogView Benchmark Specification

> 날짜: 2026-08-30
> 대상: P2-B #4 RxLogView `BatchRenderer` 필요성 재평가
> 도구: `tools/rx_view_benchmark.py`

---

## 1. 목적

`BatchRenderer`라는 새 abstraction을 먼저 구현하지 않는다.

현재 `QSmartListView` / `LogModel` 경로에서 실제 비용이 어디에 있는지 분해하여 다음 중 어떤 결론이 맞는지 결정한다.

1. 현재 구조 유지
2. formatting 최적화
3. repaint/autoscroll cadence 최적화
4. LogModel trim/insert 최적화
5. 위 항목으로 부족할 때만 별도 `BatchRenderer` 검토

---

## 2. 현재 구조에서 이미 존재하는 batching

`DataTrafficHandler`

```text
PortDataEvent
  -> port별 bytearray aggregation
  -> UI_REFRESH_INTERVAL_MS tick
  -> LogDataBatch
  -> MainWindow.append_rx_data()
```

`QSmartListView.append()`

```text
text split
  -> optional line formatter
  -> LogModel.add_logs(lines)
       -> beginInsertRows() 1회
       -> list.extend(lines)
       -> endInsertRows() 1회
```

즉 Model layer에는 이미 row batch insertion이 있다.

따라서 새 `BatchRenderer`의 필요성은 `add_logs()` 존재 여부가 아니라 다음 구간의 병목 여부로 판단해야 한다.

- bytes -> ASCII/HEX conversion
- timestamp/color formatting
- autoscroll
- proxy model bookkeeping
- delegate `QTextDocument` layout/paint
- viewport repaint cadence
- max-line trim

---

## 3. Benchmark Scenario

### A. `model_batch_insert`

현재 production 형태와 같은 `LogModel.add_logs(lines)` batch insert.

측정:

- lines/s
- elapsed ms

### B. `model_single_insert_control`

`add_logs([line])`를 한 row씩 반복하는 대조군.

이 scenario는 production 변경 후보가 아니다.
기존 batch insert가 실제로 얼마의 이득을 주는지 판단하기 위한 control이다.

### C. `view_preformatted_text`

이미 decode/format 완료된 text를 `QSmartListView.append()`로 전달.

측정 대상:

- newline split
- LogModel insertion
- autoscroll check

### D. `view_ascii_bytes`

`append_bytes()` ASCII path.

추가 측정 대상:

- UTF-8 decode
- formatter 생성
- original-data retention

### E. `view_ascii_with_events`

ASCII append 중 주기적으로 `QApplication.processEvents()` 실행.

추가 측정 대상:

- Qt event delivery
- viewport update
- delegate layout/paint
- scrollbar/autoscroll 반영

실제 GUI/display driver 성능을 완전히 재현하지는 않지만, offscreen current/candidate 상대 비교에는 사용 가능하다.

### F. `view_hex_bytes`

HEX mode `append_bytes()`.

측정 대상:

- byte -> `XX ` string expansion
- 긴 line model insertion

---

## 4. Derived Metric

### `batch_vs_single_ratio`

```text
model_batch_insert lines/s
--------------------------
model_single_insert lines/s
```

해석:

- 높을수록 현재 `add_logs()` batching이 이미 큰 효과를 제공
- 이 값이 큰데 Model insert가 전체 병목이 아니라면 BatchRenderer가 동일한 역할을 중복할 가능성이 큼

### `ascii_formatting_cost_ratio`

```text
preformatted text MB/s
----------------------
ASCII append_bytes MB/s
```

해석:

- 1에 가까움: bytes decode/formatting 비용 작음
- 크게 증가: formatting path 우선 감사

### `event_loop_cost_ratio`

```text
ASCII append_bytes MB/s
-----------------------
ASCII + processEvents MB/s
```

해석:

- 1에 가까움: event/repaint 비용 작음
- 크게 증가: paint/autoscroll/repaint cadence가 우선 최적화 후보

---

## 5. 실행

Windows:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python tools\rx_view_benchmark.py --repeat 5 --json doc\benchmarks\rx_view_baseline.json
```

가능하면 실제 화면 환경에서도 동일 명령을 한 번 더 실행한다.

결과 비교 시 반드시 다음을 동일하게 유지한다.

- Python version
- OS
- display/offscreen 조건
- theme/font
- workload size
- repeat 수
- background load

---

## 6. BatchRenderer 도입 판단

### 먼저 도입하지 않음

다음 중 하나이면 별도 BatchRenderer를 만들지 않는다.

- `model_batch_insert`가 충분히 빠르고 전체 병목이 아님
- `event_loop_cost_ratio`가 가장 큰 병목으로 확인됨
- formatting/HEX expansion이 dominant cost
- candidate 차이가 반복 측정 분산 대비 작음

### 검토 가능

다음을 모두 만족할 때만 별도 BatchRenderer 설계를 검토한다.

1. View update scheduling 자체가 dominant bottleneck
2. 현재 `DataTrafficHandler` + `LogModel.add_logs()`로 해결하기 어려움
3. renderer 도입으로 p95 UI latency/CPU가 반복 측정에서 유의미하게 개선
4. byte/line loss 0
5. shutdown flush/data-preservation invariant 유지
6. owner/lifecycle이 명확하며 추가 QThread를 요구하지 않음

---

## 7. CI 역할

`tests/test_rx_view_benchmark_smoke.py`는 성능 threshold를 검사하지 않는다.

검증 범위:

- 실제 LogModel/QSmartListView scenario 실행 가능
- offscreen Qt path 실행 가능
- 결과 metric/schema 유지
- invalid repeat 입력 차단

GitHub-hosted runner의 절대 성능 수치를 regression threshold로 사용하지 않는다.

---

## 8. P2-B #4 완료 조건

```text
current baseline 측정
  + 반복 결과 저장
  + derived metric 분석
  + 병목 위치 판정
  + BatchRenderer 적용/보류/폐기 결정
  + 판단 근거 문서화
```

benchmark infrastructure를 만든 것만으로 P2-B #4 완료 처리하지 않는다.
