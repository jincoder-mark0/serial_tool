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

현재 RX path는 `DataTrafficHandler`가 UI 업데이트를 batching한다. `BatchRenderer` 도입은 추가 abstraction이므로 실제 병목이 View rendering인지 먼저 증명해야 한다.

검증 질문:

1. signal delivery
2. string formatting
3. model append
4. viewport repaint
5. max-line trimming
6. search/highlight bookkeeping

Benchmark matrix:

- 32~128 B burst
- 1~4 KB stream
- 8~64 KB high-rate stream
- burst + idle
- 2 / 4 port simultaneous RX
- ASCII / HEX / highlight mode

측정:

- input bytes/s
- rendered lines/s
- p50/p95 UI latency
- main/process CPU
- peak RSS
- backlog high-water mark
- dropped/coalesced update count

비교 후보:

- Current baseline
- BatchRenderer
- QAbstractItemModel range append 최적화
- autoscroll/highlight/repaint cadence 제한

데이터 자체를 버리는 정책은 기본값으로 허용하지 않는다.

도입 조건:

- p95 UI latency 유의미한 개선
- CPU 감소 또는 처리량 증가
- memory/backlog 악화 없음
- 복잡도 증가 대비 효과 명확

도입하지 않는 조건:

- 차이가 5~10% 이내의 측정 노이즈 수준
- bottleneck이 formatting/model 쪽으로 확인
- shutdown/state ownership 복잡도만 증가

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

측정 포인트:

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

- `tests/test_tx_flush.py`
- connection lifecycle tests
- file transfer tests
- high-speed parser/RX tests

추가 권장:

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

결과 문서는 `doc/benchmarks/` 아래에 날짜별로 보존한다.
