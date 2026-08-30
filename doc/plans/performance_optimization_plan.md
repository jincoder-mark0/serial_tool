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

# 3. Serial Non-Blocking I/O Loop 최적화 — Software 완료 / Hardware Acceptance 대기

현재 경로:

```text
SerialTransport
  -> ConnectionWorker QThread
     -> in_waiting
     -> read
     -> RX batch
     -> TX queue drain
     -> activity-aware scheduling
```

유지할 invariant:

- queue-before-open 허용
- stop 시 TX drain
- read/write error propagation
- stale worker identity guard
- final RX batch preservation

P2-B #3의 runtime benchmark는 실제 `ConnectionWorker(QThread)`와 synthetic
`BaseTransport`를 사용해 mixed RX/TX workload를 동일 조건에서 반복 비교한다.

고정 metric:

- `rx_mb_s`
- `tx_mb_s`
- `elapsed_ms`
- `rx_batches`
- `stop_ms`

## 3.1 발견된 Bottleneck

기존 loop는 batch emit 후 `batch_buffer`가 비면 transport에 다음 RX가 계속 대기 중이어도 idle로 판단할 수 있었다.

더 중요한 실측 결과는 Windows에서 `QThread.usleep(100)` 같은 sub-millisecond sleep이 기대한 0.1 ms 수준의 scheduling primitive로 동작하지 않았다는 점이다.

동일 synthetic workload:

```text
RX       16 MiB
TX        4 MiB
chunk     4 KiB
repeat    3
```

Baseline:

```text
10 s timeout
RX 3,301,376 / 16,777,216 bytes
TX 4,194,304 / 4,194,304 bytes
```

Candidate A — activity-aware `usleep(100 us)`:

```text
10 s timeout
RX 3,252,224 / 16,777,216 bytes
TX 4,194,304 / 4,194,304 bytes
```

즉 activity를 정확히 분류해도 sub-ms sleep을 계속 사용하면 sustained RX 병목은 해결되지 않았다.

## 3.2 채택안 — Active I/O Yield

최종 scheduling policy:

```text
실제 RX/TX activity 있음
    -> QThread.yieldCurrentThread()

새 I/O 없음 + buffered RX/TX pending
    -> usleep(WORKER_BUSY_WAIT_US)

activity/pending 모두 없음
    -> msleep(WORKER_IDLE_WAIT_MS)
```

WHY:

- sustained I/O path에서 Windows scheduler granularity에 의한 강제 sleep stall 제거
- 완전 busy-spin 대신 scheduler에 다른 ready thread 실행 기회 제공
- pending-only 상태는 기존 busy wait 유지
- idle 상태는 기존 1 ms wait 유지

변경하지 않은 항목:

- `BATCH_SIZE_THRESHOLD`
- `BATCH_TIMEOUT_MS`
- TX queue 전량 drain
- read chunk size
- queue-before-open
- final RX flush
- stop 시 TX drain
- write error propagation

## 3.3 Synthetic 결과

GitHub Actions Windows / Python 3.11.9 / repeat=3:

```text
pytest       652 passed
warnings     2 external lark warnings
Ruff         Green
lang-keys    Green
task-boards  Green

worker_loop
  rx_mb_s       226.700 MB/s
  tx_mb_s        56.675 MB/s
  elapsed_ms     70.578 ms
  rx_batches   2048
  stop_ms         0.913 ms
```

상세 결과:

- [`../benchmarks/worker_loop_optimization_20260830.md`](../benchmarks/worker_loop_optimization_20260830.md)

이 수치는 in-memory synthetic transport의 software-loop ceiling이며 실제 UART 성능 보장이 아니다.

## 3.4 추가 후보 판단

현재 evidence로 다음 변경은 **도입하지 않는다**.

- TX drain quota
- adaptive read chunk
- `QWaitCondition`

WHY:

- 관찰된 sustained RX bottleneck은 active sleep 제거만으로 해소
- 추가 scheduling/queue policy는 regression surface를 넓힘
- TX fairness/CPU 문제가 실제 장비나 별도 workload에서 확인될 때 독립 후보로 검증하는 편이 원인 분리에 유리

## 3.5 실제 Serial acceptance — 미완료

Serial I/O 최적화는 Mock/LOOPBACK/synthetic benchmark Green만으로 완료 처리하지 않는다.

최소 확인:

```text
실제 USB Serial 장치 1종
  + open / close
  + sustained RX/TX smoke
  + simultaneous RX/TX
  + disconnect / reconnect
  + application shutdown
  + byte loss/error surface 확인
```

WHY:

- pyserial/OS driver의 `in_waiting`, timeout, disconnect behavior는 synthetic transport와 다를 수 있음
- 이 검증은 P4 종합 실기기 검증을 대체하지 않고, 이번 scheduling 변경 직후의 최소 regression gate 역할만 수행

따라서 **software candidate 선정/구현은 완료**, Task #5의 최종 `[x]` 처리는 hardware acceptance 후 수행한다.

---

# 4. 테스트 계획

기능 회귀:

- `tests/test_runtime_benchmark_smoke.py`
- `tests/test_rx_view_benchmark_smoke.py`
- `tests/test_connection_worker_wait_policy.py`
- `tests/test_tx_flush.py`
- connection lifecycle tests
- file transfer tests
- high-speed parser/RX tests

추가 검증은 실제 evidence가 생길 때 수행:

- simultaneous RX/TX fairness
- 4-port sustained physical load
- heavy TX 중 worker stop
- heavy RX 중 worker stop
- idle CPU / sustained RX CPU

---

# 5. 산출물

```text
benchmark environment
baseline commit
candidate commit
scenario matrix
raw result summary
candidate comparison
actual USB Serial smoke result (Serial I/O 변경 시)
결론: 적용 / 보류 / 폐기
```

- benchmark 정의/비교 규칙: `doc/runtime_benchmark_baseline_spec_20260830.md`
- Rx View 판정 결과: `doc/benchmarks/rx_view_baseline_20260830.md`
- Worker loop 판정 결과: `doc/benchmarks/worker_loop_optimization_20260830.md`
- 과거 Core micro 결과: `doc/benchmark_20260822.md`
- 이후 실제 측정 결과: `doc/benchmarks/` 아래 날짜별 보존
