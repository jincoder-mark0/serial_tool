# 성능 벤치마크 결과 (2026-08-22)

S-011 — `tools/benchmark.py`로 수신 데이터 경로의 모델/코어 구간(RingBuffer,
ThreadSafeQueue, DelimiterParser, DataLogger)을 실측한 결과. README §1.4의
"처리량 수치는 자동 벤치마크가 도입되기 전까지 보장하지 않습니다" 선언에 대한
최초 실측 기준선이며, **이 문서 자체는 수치 보장을 선언하지 않는다** — CI에서의
반복 측정 이후 상위 모델이 판단할 사항이다. UI 렌더링 경로는 환경(디스플레이/
드라이버) 의존이 커서 측정 범위에서 제외했다(모델/코어 구간만 대상).

## 실행 환경

| 항목 | 값 |
|---|---|
| OS | Windows-11-10.0.26200-SP0 |
| CPU | Intel64 Family 6 Model 197 Stepping 2, GenuineIntel (AMD64) |
| Python | 3.13.15 |
| 실행 위치 | `e:\Python\serial_tool` (venv: `.venv`) |

## 실행 명령

```powershell
.venv\Scripts\python tools\benchmark.py
```

## 결과 (3회 반복 중앙값)

| 항목 | 값 | 단위 | 측정 대상 |
|---|---:|---|---|
| ringbuffer | 10,005.37 | MB/s | `core/structures.py` `RingBuffer` — 4KB 청크 write+read, 총 256MB, 512KB 버퍼(`RING_BUFFER_SIZE`) |
| queue | 8,266,273.19 | ops/s | `core/structures.py` `ThreadSafeQueue` — 10만 항목 enqueue+dequeue |
| parser | 32,981,530.50 | lines/s | `model/packet_parser.py` `DelimiterParser` — AT 응답 혼합 샘플(OK/+CSQ/ERROR/+CREG 순환) 1만 라인 |
| logger | 1,105.11 | MB/s | `core/data_logger.py` `DataLogger`(BIN 포맷) — 임시 파일에 256MB write 후 큐 드레인 완료까지 |

원문 출력(실제 실행 결과, 가공 없음):

```
Python 3.13.15 / Intel64 Family 6 Model 197 Stepping 2, GenuineIntel
repeat=3

항목                         값  단위
----------------------------------------
ringbuffer         10,005.37  MB/s
queue           8,266,273.19  ops/s
parser         32,981,530.50  lines/s
logger              1,105.11  MB/s
```

## 측정 방법 메모

- 각 항목은 독립적으로 3회 반복 실행 후 중앙값을 채택했다(1회성 잡음 완화).
- `ringbuffer`는 4KB write 직후 동일 크기 read를 반복하는 방식으로 512KB
  버퍼에 256MB 상당의 write+read 트래픽(합산 512MB)을 흘려보냈다(수신→즉시
  소비 패턴 모사). 처리량은 write+read 합산 바이트 기준.
- `queue`는 10만 회 enqueue 전량 수행 후 10만 회 dequeue 전량 수행, ops/s는
  20만 연산 기준.
- `parser`는 `ParserFactory.create_parser(ParserType.DELIMITER, delimiter=b"\n")`로
  생성한 파서에 1만 라인을 한 번에 `parse()` 호출.
- `logger`는 `DataLogger.stop_logging()`의 `join(timeout=1.0)`이 대용량 드레인
  완료를 보장하지 않으므로(코어 코드 미수정), 벤치마크 측에서 내부 큐
  (`queue.Queue`, 공개 API `qsize()`)가 완전히 빌 때까지 직접 폴링해 실제
  디스크 기록 완료 시점을 측정했다.

## 참고

- 도구: `tools/benchmark.py` (`--json <path>`로 기계 판독용 결과 저장 가능,
  `--repeat N`으로 반복 횟수 조정 가능).
- 스모크 테스트: `tests/test_benchmark_smoke.py` — 위 4개 함수를 각각
  1MB/1천 항목·라인 규모로 1회 호출해 예외 없이 양수를 반환하는지만 확인
  (전체 pytest에 편입, 1초 미만 유지).
- 본 실측은 이 PC/이 시점 1회 기준선이며, 하드웨어·부하 상황에 따라 달라질 수
  있다. 회귀 감시(CI 반복 측정, 임계값 설정 등)는 별도 태스크 범위.
