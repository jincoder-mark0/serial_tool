# S-011 — 성능 벤치마크 도구

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 4종 측정 구현·실측 기록
  (ringbuffer 10,005 MB/s·queue 8.27M ops/s·parser 32.98M lines/s·logger 1,105 MB/s —
  doc/benchmark_20260822.md). 스모크 5건 추가 → pytest 기준선 90. 코어 무수정.
  측정 설계 메모: ringbuffer는 인터리브 write+read(512KB 링에 순차 256MB는 무의미),
  logger는 join(1s) 한계를 피해 큐 드레인 폴링 후 stop — 실 디스크 처리량 측정)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

README §1.4가 "처리량 수치는 자동 벤치마크가 도입되기 전까지 보장하지 않습니다"라고
선언한 상태다. 성능 최적화(S-007)를 하려면 **먼저 측정**이 있어야 한다 — 측정 없는
최적화는 금지(Task.MD 우선순위 메모).

## 배경 (자족적 설명)

측정 대상은 수신 데이터 경로의 모델/코어 구간이다 (UI 렌더링은 환경 의존이 커서 제외):

- `core/structures.py:95` `RingBuffer` — bytearray+memoryview 기반, `:119 write(data)->int`,
  `:170 read(count)->bytes`, 기본 크기 512KB(`common/constants.py:138 RING_BUFFER_SIZE`).
- `core/structures.py:25` `ThreadSafeQueue` — deque+Lock, `enqueue/dequeue`.
- `model/packet_parser.py` — `ParserFactory`로 AT/Delimiter/FixedLength 파서 생성.
- `core/data_logger.py:31` `DataLogger` — Queue+Thread 논블로킹 쓰기, `:113 write(data)`.

## Steps

1. `tools/benchmark.py` 신설 (CLI, argparse). 측정 4종 — 각각 3회 반복 후 중앙값 출력:
   - `ringbuffer`: 4KB 청크(`DEFAULT_READ_CHUNK_SIZE=4096`, `constants.py:131`)를 총 256MB
     write+read → MB/s.
   - `queue`: 10만 항목 enqueue+dequeue → ops/s.
   - `parser`: AT 응답 샘플(`b"OK\r\n"`, `b"+CSQ: 18,99\r\n"` 등 혼합 1만 라인)을
     Delimiter 파서로 파싱 → lines/s. (파서 생성 API는 `model/packet_parser.py`에서 확인해 사용.)
   - `logger`: DataLogger BIN 포맷으로 임시 파일에 256MB write 후 stop → MB/s
     (임시 파일은 `tempfile.mkdtemp()` 사용, 종료 시 삭제).
2. 출력 형식: `항목  값  단위` 표 + `--json <path>` 옵션(기계 판독용).
3. 결과를 `doc/benchmark_YYYYMMDD.md`에 기록: 실행 환경(CPU 모델은 `platform` 모듈로,
   Python 버전), 명령, 결과 표. **README 수치 보장 선언은 하지 않는다** (그건 CI 반복 측정
   이후 상위 모델 판단).
4. `tests/`에 스모크 테스트 1건: 각 벤치를 아주 작은 크기(1MB/1천 항목)로 호출해
   예외 없이 숫자를 반환하는지만 확인 (실행 시간 1초 미만 유지).

## Acceptance criteria (DoD)

- [ ] `tools/benchmark.py`가 4종 측정을 수행하고 표+JSON을 출력한다.
- [ ] `doc/benchmark_YYYYMMDD.md`에 이 PC 실측값 기록.
- [ ] 스모크 테스트 추가, 전체 pytest 통과.
- [ ] 프로젝트 코드(core/model)는 **수정하지 않았다** — 측정만.

## 검증 방법

```powershell
.venv\Scripts\python tools\benchmark.py                # 실측 실행
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
```
