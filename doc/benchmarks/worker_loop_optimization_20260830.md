# Serial Worker Loop Optimization Benchmark — 2026-08-30

> 대상: P2-B #5 Serial non-blocking I/O loop
> 환경: GitHub-hosted Windows runner / Python 3.11.9 / synthetic in-memory transport
> 목적: `ConnectionWorker` scheduling policy의 **상대 비교**
> 주의: 아래 처리량은 실제 USB Serial/UART 성능 보장이 아님

---

## 1. 문제 정의

기존 Worker loop는 loop 마지막에 내부 상태만 보고 wait를 선택했다.

```text
batch_buffer empty + TX queue empty
    -> msleep(1 ms)
else
    -> usleep(100 us)
```

그러나 RX batch를 emit하면 `batch_buffer.clear()`가 즉시 수행된다.

```text
Transport에는 다음 RX가 계속 대기
    ↓
현재 batch threshold 도달
    ↓
data_received emit
    ↓
batch_buffer.clear()
    ↓
"buffer empty"를 idle로 오판
    ↓
1 ms sleep
```

또한 Windows에서는 `QThread.usleep(100)` 같은 sub-millisecond sleep도 scheduler granularity 영향으로 실제로는 약 1 ms급 stall처럼 동작할 수 있다.

따라서 이번 작업은 wait constant 자체를 임의 tuning하지 않고 **실제 I/O activity와 scheduling primitive를 분리**해 비교했다.

---

## 2. Benchmark workload

`tools/runtime_benchmark.py`의 기존 `worker_loop` scenario 사용.

```text
RX             16 MiB
TX              4 MiB
Read chunk      4 KiB
RX batch        8 KiB threshold
Transport       immutable bytes + offset synthetic transport
Repeat          3, median
Timeout         10 s / run
```

고정 검증:

- RX byte preservation
- TX byte preservation
- 실제 `ConnectionWorker(QThread)` 사용
- TX queue / batch signal 경로 사용
- stop latency 측정

---

## 3. Baseline — 기존 main

정책:

```text
buffer empty && TX queue empty
    -> msleep(1 ms)
else
    -> usleep(100 us)
```

GitHub Actions run `33316518788` 결과:

```text
Timeout after 10 s
RX = 3,301,376 / 16,777,216 bytes
TX = 4,194,304 / 4,194,304 bytes
```

즉 TX는 완료했지만 RX는 10초 동안 약 3.15 MiB만 처리했다.

이 결과에서 중요한 것은 절대 MB/s가 아니라 **메모리 transport임에도 worker loop가 16 MiB를 10초 안에 처리하지 못했다는 점**이다.

---

## 4. Candidate A — activity-aware busy/idle 선택

변경:

```text
이번 iteration에 실제 RX/TX activity 있음
    -> usleep(WORKER_BUSY_WAIT_US)

activity 없음 + pending 없음
    -> msleep(WORKER_IDLE_WAIT_MS)
```

목적:

- batch emit 직후 내부 buffer가 비었다는 이유만으로 idle wait를 선택하지 않음

결과:

GitHub Actions run `33316706549`:

```text
Full pytest = 652 passed, 2 external warnings

Benchmark timeout after 10 s
RX = 3,252,224 / 16,777,216 bytes
TX = 4,194,304 / 4,194,304 bytes
```

### 판정

**효과 없음.**

activity 판정 자체는 올바르지만 Windows에서 `QThread.usleep(100)`이 충분히 짧은 wait로 동작하지 않았다.

따라서 단순히 `1 ms -> 100 us`로 분기를 바꾸는 것은 해결책이 아니었다.

---

## 5. Candidate B — active I/O에서 thread yield

최종 후보:

```text
실제 RX/TX activity 있음
    -> QThread.yieldCurrentThread()

새 I/O 없음 + buffered RX/TX pending
    -> usleep(WORKER_BUSY_WAIT_US)

activity/pending 모두 없음
    -> msleep(WORKER_IDLE_WAIT_MS)
```

### WHY

- sustained I/O path에서 Windows sleep granularity에 의한 강제 stall 제거
- 완전 busy-spin 대신 OS scheduler에 다른 ready thread 실행 기회 제공
- 새 I/O가 없는 pending-batch 상태에서는 기존 busy wait 유지
- 완전 idle 상태에서는 기존 1 ms wait 유지

변경하지 않은 정책:

- `BATCH_SIZE_THRESHOLD`
- `BATCH_TIMEOUT_MS`
- TX queue 전량 drain
- queue-before-open
- final RX flush
- stop 시 TX drain
- write error propagation
- shutdown/data-preservation ordering

---

## 6. Candidate B 결과

GitHub Actions run `33316851480`, Windows job `99271765801`.

기능 검증:

```text
pytest:      652 passed
warnings:    2 external lark warnings
Ruff:        Green
lang-keys:   Green
task-boards: Green
```

Runtime benchmark / repeat=3 median:

```text
[rx_pipeline]
ingest_mb_s   517.678 MB/s
flush_ms        6.667 ms
view_batches    1

[worker_loop]
rx_mb_s       226.700 MB/s
tx_mb_s        56.675 MB/s
elapsed_ms     70.578 ms
rx_batches   2048
stop_ms         0.913 ms
```

16 MiB RX + 4 MiB TX workload를 timeout 없이 완료했다.

---

## 7. 비교 판정

```text
Baseline
  16 MiB RX workload -> 10 s 내 완료 실패
  observed RX        -> 약 3.15 MiB

Candidate A
  16 MiB RX workload -> 10 s 내 완료 실패
  observed RX        -> 약 3.10 MiB

Candidate B
  16 MiB RX workload -> 70.578 ms에 완료
  synthetic RX       -> 226.700 MB/s
  synthetic TX       ->  56.675 MB/s
  stop               ->   0.913 ms
```

### 결론

**Candidate B 채택.**

관찰된 병목은 read/batch algorithm보다 active loop에 강제된 sleep/scheduler granularity였다.

추가 `TX drain quota`, adaptive read chunk, `QWaitCondition` 도입은 이번 evidence로는 필요하지 않다. 독립적인 fairness/CPU 문제가 실제로 확인될 때 별도 후보로 검토한다.

---

## 8. 해석 제한

이 benchmark는 실제 Serial device가 아니다.

검증한 것:

- Python/PyQt Worker loop scheduling overhead
- RX/TX queue/batch software path
- byte preservation
- synthetic sustained load
- stop responsiveness

검증하지 않은 것:

- USB-UART driver latency
- 실제 baudrate throughput
- OS Serial buffer behavior
- cable/device disconnect behavior
- pyserial `in_waiting` device-specific 특성
- 2/4 physical-port CPU scaling

따라서 P2-B #5의 **software optimization은 완료**했지만 전체 task 완료 조건은 아직 아니다.

---

## 9. 남은 Hardware Acceptance

최소 실제 USB Serial 검증:

```text
1. open / close
2. sustained RX
3. sustained TX
4. simultaneous RX/TX smoke
5. disconnect
6. reconnect
7. application shutdown
8. byte loss / error surface 확인
```

이 검증이 완료되기 전까지 `Task.MD`의 P2-B #5는 `[x]`로 닫지 않는다.

P4의 종합 실기기 검증과 역할 차이:

```text
P2-B #5 hardware gate
  -> 이번 worker scheduling 변경 직후 최소 regression acceptance

P4 final validation
  -> 전체 기능이 합쳐진 최신 main 제품 관점 종합 검증
```
