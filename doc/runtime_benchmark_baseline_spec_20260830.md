# Runtime Benchmark Baseline Specification

> 날짜: 2026-08-30
> 대상: P2-B #3 benchmark scenario / baseline 재고정

## 1. 목적

기존 `tools/benchmark.py`는 RingBuffer / Queue / Parser / DataLogger의 micro benchmark로 유지한다.
P2-B 성능 작업의 실제 판단 대상인 RX UI pipeline과 `ConnectionWorker` loop는 별도
`tools/runtime_benchmark.py`에서 측정한다.

두 benchmark의 역할은 다르다.

```text
Core Micro Benchmark
  -> 자료구조/Parser/Logger 자체 처리량

Runtime-path Benchmark
  -> DataTrafficHandler batching 비용
  -> ConnectionWorker mixed RX/TX loop
  -> batch 수 / stop latency

실제 USB Serial Validation
  -> driver/USB/board latency와 reconnect/disconnect
```

Runtime benchmark 수치는 제품 성능 보장이 아니라 **같은 환경에서 변경 전후를 비교하는
의사결정 근거**다.

---

## 2. Scenario A — RX Pipeline

대상 경로:

```text
PortDataEvent
  -> DataTrafficHandler.on_fast_data_received()
  -> per-port bytearray aggregation
  -> _flush_rx_buffer_to_ui()
  -> LogDataBatch
  -> benchmark View facade
```

측정 metric:

| Metric | 단위 | 의미 |
|---|---:|---|
| `ingest_mb_s` | MB/s | RX event를 aggregation buffer에 넣는 처리량 |
| `flush_ms` | ms | 하나의 refresh tick에서 buffer를 DTO/View facade로 flush하는 시간 |
| `view_batches` | count | flush 과정에서 발생한 View batch 호출 수 |

주의:

- `QSmartListView` 실제 rendering 비용은 이 scenario에 포함하지 않는다.
- P2-B #4에서 BatchRenderer 후보를 비교할 때 별도 View benchmark를 추가한다.
- 이 분리로 DataTrafficHandler 개선과 QWidget rendering 개선의 효과를 혼동하지 않는다.

---

## 3. Scenario B — ConnectionWorker Loop

대상 경로:

```text
Synthetic BaseTransport
  <-> ConnectionWorker(QThread)
      - in_waiting/read
      - BATCH_SIZE_THRESHOLD/BATCH_TIMEOUT_MS
      - data_received signal
      - TX queue drain
      - idle/busy wait
      - stop/wait
```

Synthetic transport는 실제 Serial latency를 흉내 내지 않는다. 동일 workload에서 worker
loop policy 변경의 상대 차이를 재현하기 위한 deterministic source/sink다.

측정 metric:

| Metric | 단위 | 의미 |
|---|---:|---|
| `rx_mb_s` | MB/s | mixed workload 전체 elapsed 기준 RX 처리량 |
| `tx_mb_s` | MB/s | 동일 elapsed 기준 TX 처리량 |
| `elapsed_ms` | ms | RX/TX workload 완료까지 시간 |
| `rx_batches` | count | `data_received` batch signal 횟수 |
| `stop_ms` | ms | workload 완료 후 `ConnectionWorker.stop()` 반환까지 시간 |

이 scenario는 P2-B #5에서 다음 변경을 비교하는 기준으로 사용한다.

- idle/busy wait 조정
- adaptive read 후보
- RX/TX fairness 정책
- TX drain quota 후보
- wait primitive 후보

---

## 4. 기본 workload

`tools/runtime_benchmark.py` 기본값:

```text
repeat: 5
RX pipeline: 32 MiB / 4 KiB chunk
Worker RX: 16 MiB / 4 KiB chunk
Worker TX: 4 MiB / 4 KiB chunk
Worker timeout: 10 s
```

모든 최종 비교는 같은 commit/환경에서 최소 5회 실행 후 metric별 median을 사용한다.

---

## 5. 실행

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python tools/runtime_benchmark.py --repeat 5
python tools/runtime_benchmark.py --repeat 5 --json doc/runtime_benchmark_result.json
```

기존 micro benchmark도 함께 보존한다.

```powershell
python tools/benchmark.py --repeat 5
```

---

## 6. 비교 규칙

성능 변경 전후 비교 시 다음을 함께 본다.

```text
throughput improvement
+ batch count change
+ latency / stop responsiveness
+ full pytest / architecture contract
+ 실제 USB Serial smoke when worker loop changes
```

단일 MB/s 값만 높아졌다고 채택하지 않는다.

판정 원칙:

- 5회 median 기준 개선폭이 측정 변동 범위 수준이면 구조를 복잡하게 만들지 않는다.
- throughput이 좋아져도 `stop_ms` 또는 RX/TX fairness가 악화되면 채택하지 않는다.
- Worker loop 변경은 synthetic benchmark Green만으로 완료하지 않고 실제 USB Serial
  최소 smoke + reconnect/disconnect 확인이 필요하다.
- View rendering 변경은 P2-B #4의 별도 benchmark evidence가 필요하다.

---

## 7. CI 역할

CI는 성능 threshold를 강제하지 않는다. GitHub-hosted runner의 load 변동이 크기 때문이다.

`tests/test_runtime_benchmark_smoke.py`는 다음만 고정한다.

- 두 runtime scenario가 예외 없이 실행됨
- 결과 metric이 양수/유효 범위
- RX/TX byte-preservation contract
- JSON-compatible result schema

실제 baseline 숫자는 개발 머신에서 명시적으로 실행해 별도 결과 문서에 기록한다.
