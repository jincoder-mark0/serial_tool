# Performance Optimization Plan

> 우선순위: P2
> 대상: RxLogView rendering, Serial non-blocking I/O
> 원칙: **측정 전 최적화 금지**

---

## 1. 목표

성능 개선의 목표는 단순 throughput 최대화가 아니라 다음 균형이다.

- RX byte loss 0
- UI freeze 최소화
- command/interaction latency 유지
- CPU 사용량 안정화
- memory growth bounded
- shutdown/data-preservation invariant 유지

---

# 2. RxLogView `BatchRenderer` 재평가

## 2.1 문제 정의

현재 RX path는 `DataTrafficHandler`가 UI 업데이트를 batching한다. `BatchRenderer` 도입은 추가 abstraction이므로 실제 병목이 View rendering인지 먼저 증명해야 한다.

검증할 질문:

1. 병목이 signal delivery인가?
2. string formatting인가?
3. model append인가?
4. viewport repaint인가?
5. max-line trimming인가?
6. search/highlight bookkeeping인가?

---

## 2.2 Benchmark Matrix

데이터 패턴:

- small burst: 32~128 B
- medium stream: 1~4 KB chunk
- high-rate stream: 8~64 KB chunk
- burst + idle 반복
- multi-port simultaneous RX: 2 / 4 ports

표시 모드:

- ASCII
- HEX
- mixed/highlight rules

측정 항목:

- input bytes/s
- rendered lines/s
- p50/p95 UI update latency
- main-thread CPU
- process CPU
- peak RSS
- queue/backlog high-water mark
- dropped/coalesced update count

---

## 2.3 비교 후보

### A. Current baseline

현재 `DataTrafficHandler -> View` batching 유지.

### B. BatchRenderer

역할:

```text
RX DTO
  -> format batch
  -> append batch
  -> bounded repaint cadence
```

BatchRenderer가 도입된다면 View-specific rendering adapter여야 하며 Model/Connection 계층에 들어가지 않는다.

### C. Model-side append optimization

QAbstractItemModel append range / beginInsertRows 호출 횟수 최적화.

### D. Rendering degradation policy

고속 RX에서 optional하게:

- autoscroll cadence 제한
- highlight 재계산 cadence 제한
- viewport repaint coalescing

데이터 자체를 버리는 정책은 기본값으로 허용하지 않는다.

---

## 2.4 도입 판단 기준

BatchRenderer 도입 조건:

- baseline 대비 p95 UI latency 유의미한 개선
- CPU 감소 또는 처리량 증가
- memory/backlog 악화 없음
- 코드 복잡도 증가 대비 효과 명확

도입하지 않는 조건:

- 차이가 5~10% 이내의 측정 노이즈 수준
- bottleneck이 formatting/model 쪽으로 확인
- shutdown/state ownership 복잡도만 증가

---

# 3. Serial Non-Blocking I/O Loop 최적화

## 3.1 현재 경로

```text
SerialTransport
  -> ConnectionWorker QThread
     -> in_waiting
     -> read
     -> RX batch
     -> TX queue drain
     -> adaptive sleep
```

현재 구조의 안정성 특성은 유지한다.

- queue-before-open 허용
- stop 시 TX drain
- read/write error propagation
- stale worker identity guard
- final RX batch preservation

---

## 3.2 측정 포인트

- loop iterations/s
- idle CPU
- sustained RX CPU
- RX latency p50/p95
- TX queue drain latency
- simultaneous RX/TX fairness
- 1/2/4 port scaling
- stop latency

---

## 3.3 후보안

### A. Sleep tuning

`WORKER_IDLE_WAIT_MS`, `WORKER_BUSY_WAIT_US`를 benchmark 기반으로 조정.

가장 낮은 위험도의 첫 후보.

### B. Read chunk adaptation

`in_waiting` 및 backlog에 따라 read size를 adaptive하게 선택.

주의:

- 지나친 chunk 증가 시 UI burst latency 증가
- 작은 chunk는 signal/loop overhead 증가

### C. TX drain quota

현재 한 loop에서 queue를 전부 drain하는 정책이 RX fairness에 미치는 영향 측정.

필요 시:

```text
max TX chunks per iteration
```

정책을 도입할 수 있으나 file transfer throughput과 함께 검증해야 한다.

### D. Wait primitive / event-driven wakeup

QWaitCondition 또는 다른 wakeup primitive 검토.

단, pyserial의 blocking/read timeout semantics와 복잡도가 크게 증가하므로 A~C로 충분하지 않을 때만 진행.

---

## 3.4 금지 사항

- `QThread.terminate()` 사용
- error를 빈 bytes/0으로 숨기기
- shutdown drain 제거
- TX latency 개선을 위해 RX starvation 유발
- benchmark 없이 constant 임의 조정

---

# 4. 테스트 계획

기능 회귀:

- `tests/test_tx_flush.py`
- connection lifecycle tests
- file transfer tests
- high-speed parser/RX tests

추가 권장 테스트:

- simultaneous RX/TX fairness
- 4-port sustained synthetic load
- worker stop during heavy TX
- worker stop during heavy RX

---

# 5. 산출물

성능 작업마다 다음을 남긴다.

```text
benchmark environment
baseline commit
candidate commit
scenario matrix
raw result summary
median/p95 comparison
CPU/memory comparison
결론: 적용 / 보류 / 폐기
```

결과 문서는 `doc/benchmarks/` 아래에 날짜별로 보존하는 것을 권장한다.
