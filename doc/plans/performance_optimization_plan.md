# Performance Optimization Plan

> 우선순위: P2
> 대상: RxLogView rendering, Serial non-blocking I/O
> 원칙: **측정 전 최적화 금지**
> Runtime baseline spec: [`../runtime_benchmark_baseline_spec_20260830.md`](../runtime_benchmark_baseline_spec_20260830.md)

---

## 1. 목표

성능 개선의 목표는 단순 throughput 최대화가 아니라 다음 균형이다.

- RX byte loss 0
- UI freeze 최소화
- command/interaction latency 유지
- CPU 사용량 안정화
- memory growth bounded
- shutdown/data-preservation invariant 유지

현재 benchmark는 역할을 분리한다.

```text
Core micro benchmark
  -> tools/benchmark.py
  -> RingBuffer / Queue / Parser / DataLogger

Runtime-path benchmark
  -> tools/runtime_benchmark.py
  -> DataTrafficHandler RX aggregation/flush
  -> ConnectionWorker mixed RX/TX loop + stop latency

Rx View benchmark
  -> tools/rx_view_benchmark.py
  -> tools/rx_view_batch_matrix.py
  -> LogModel / QSmartListView / event-loop update cost

실제 hardware validation
  -> 실제 USB Serial smoke
  -> driver / reconnect / disconnect 특성
```

GitHub-hosted runner의 성능 수치를 제품 threshold로 사용하지 않는다. CI는 benchmark
scenario 실행 가능 여부와 기능 회귀를 확인하고, 실제 성능 수치는 같은 환경에서 후보 비교 evidence로만 사용한다.

---

# 2. RxLogView `BatchRenderer` 재평가 — 완료

## 2.1 결론

**별도 `BatchRenderer`를 도입하지 않는다.**

현재 구조 유지:

```text
ConnectionController
    -> DataTrafficHandler (30 ms byte aggregation)
    -> LogDataBatch
    -> QSmartListView.append_bytes()
    -> LogModel.add_logs() (range insertion)
```

근거 문서:

- [`../rx_view_benchmark_spec_20260830.md`](../rx_view_benchmark_spec_20260830.md)
- [`../benchmarks/rx_view_baseline_20260830.md`](../benchmarks/rx_view_baseline_20260830.md)

## 2.2 측정 결과

Windows hosted runner / Python 3.11 / offscreen / repeat=3의 반복 run에서:

```text
LogModel batch vs single insert
  ~= 5.5 ~ 5.8 x

ASCII formatting cost ratio
  ~= 1.00 ~ 1.03 x

Event-loop cost ratio
  ~= 1.21 ~ 1.28 x
```

즉:

- `LogModel.add_logs()` batching은 이미 큰 효과를 제공
- ASCII decode/formatter는 dominant bottleneck 아님
- Qt View update마다 발생하는 fixed cost가 더 큼

Flush-size matrix:

```text
4 KiB   / 512 updates ->  0.813 MB/s
16 KiB  / 128 updates ->  3.191 MB/s
64 KiB  /  32 updates -> 11.935 MB/s
```

```text
update count reduction = 16.000 x
throughput improvement = 14.675 x
```

View update 횟수 감소와 처리량 개선이 거의 비례한다.

## 2.3 Architecture 판단

View update fixed cost를 줄이는 책임은 새 renderer가 아니라 이미 존재하는 `DataTrafficHandler`의 aggregation에 두는 것이 맞다.

현재 최고 지원 baudrate 4,000,000 baud를 일반적인 8N1(약 10 bit/byte)로 단순 상한 계산하면:

```text
4,000,000 / 10 ~= 400,000 byte/s
400,000 * 30 ms ~= 12 KiB / refresh
```

따라서 30 ms cadence는 최고 baudrate에서도 대략 16 KiB matrix 근처의 View update 크기를 형성한다.

별도 BatchRenderer를 추가하면:

```text
DataTrafficHandler batching
    + BatchRenderer batching
    + LogModel range insertion
```

처럼 동일 책임의 buffering/scheduling 계층이 중복되고 lifecycle/flush ownership만 복잡해질 가능성이 높다.

## 2.4 재검토 Trigger

다음이 실제로 관찰될 때만 다시 검토한다.

- 2/4 port 동시 고속 RX에서 visible UI freeze
- UI event latency/backlog 지속 증가
- 실제 display 환경에서 severe delegate paint bottleneck
- HEX mode가 실제 요구 throughput을 충족하지 못함

그 경우에도 우선순위:

1. DataTrafficHandler cadence/flush size 측정
2. autoscroll/repaint cadence
3. delegate QTextDocument layout
4. HEX conversion
5. 위 항목으로 부족할 때만 BatchRenderer

---

# 3. Serial Non-Blocking I/O Loop 최적화

현재 경로:

```text
SerialTransport
  -> ConnectionWorker QThread
     -> in_waiting
     -> read
     -> RX batch
     -> TX queue drain
     -> adaptive sleep
```

유지할 invariant:

- queue-before-open 허용
- stop 시 TX drain
- read/write error propagation
- stale worker identity guard
- final RX batch preservation

P2-B #3의 runtime benchmark는 실제 `ConnectionWorker(QThread)`와 synthetic
`BaseTransport`를 사용해 mixed RX/TX workload를 동일 조건에서 반복 비교한다.

현재 고정 metric:

- `rx_mb_s`
- `tx_mb_s`
- `elapsed_ms`
- `rx_batches`
- `stop_ms`

추가 실기기/후보 비교에서 볼 항목:

- loop iterations/s
- idle CPU
- sustained RX CPU
- RX latency p50/p95
- TX queue drain latency
- simultaneous RX/TX fairness
- 1/2/4 port scaling
- stop latency

후보안:

1. Sleep tuning
2. Read chunk adaptation
3. TX drain quota
4. QWaitCondition 등 event-driven wakeup — 1~3으로 부족할 때만

금지:

- `QThread.terminate()`
- error를 빈 bytes/0으로 숨기기
- shutdown drain 제거
- TX 개선을 위해 RX starvation 유발
- benchmark 없이 constant 임의 조정

## 3.1 실제 Serial acceptance

Serial I/O 최적화는 Mock/LOOPBACK Green만으로 완료 처리하지 않는다.

최소 확인:

```text
실제 USB Serial 장치 1종
  + open / close
  + sustained RX/TX smoke
  + disconnect / reconnect
  + application shutdown
```

WHY:

- pyserial/OS driver의 `in_waiting`, timeout, disconnect behavior는 Mock과 다를 수 있음
- 이 검증은 P4 종합 실기기 검증을 대체하지 않고, 성능 변경 직후의 최소 regression gate 역할만 수행

---

# 4. 테스트 계획

기능 회귀:

- `tests/test_runtime_benchmark_smoke.py`
- `tests/test_rx_view_benchmark_smoke.py`
- `tests/test_tx_flush.py`
- connection lifecycle tests
- file transfer tests
- high-speed parser/RX tests

Serial I/O 후보 비교 추가 권장:

- simultaneous RX/TX fairness
- 4-port sustained synthetic load
- heavy TX 중 worker stop
- heavy RX 중 worker stop

---

# 5. 산출물

```text
benchmark environment
baseline commit
candidate commit
scenario matrix
raw result summary
median/p95 comparison
CPU/memory comparison
actual USB Serial smoke result (Serial I/O 변경 시)
결론: 적용 / 보류 / 폐기
```

- benchmark 정의/비교 규칙: `doc/runtime_benchmark_baseline_spec_20260830.md`
- Rx View 판정 결과: `doc/benchmarks/rx_view_baseline_20260830.md`
- 과거 Core micro 결과: `doc/benchmark_20260822.md`
- 이후 실제 측정 결과: `doc/benchmarks/` 아래 날짜별 보존
