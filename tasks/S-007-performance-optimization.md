# S-007 — 성능 최적화 (Rx 경로·렌더링)

- Status: TODO
- Recommended model: **상위 권장** (병목 판단·트레이드오프 결정) — 측정 해석이 본체
- 선행: **S-011 (벤치마크)** — 측정 없이 시작 금지
- Skills to load: task-done

## 목적 (Why)

`doc/task.md` Phase 6 계획 항목: BatchRenderer(RxLog), RingBuffer 최적화, 논블로킹
I/O 루프 최적화. 단, **어느 것이 실제 병목인지 측정된 바 없다.**

## 원칙

- S-011의 벤치마크 실측값으로 병목을 특정한 뒤, 병목인 것만 손댄다.
- RingBuffer는 이미 bytearray+memoryview 기반(`core/structures.py:110-112`)이다 —
  doc의 "bytearray 최적화" 항목은 이미 반영된 상태일 수 있으니 계획을 맹신하지 말 것.
- 수신 배치는 `model/connection_worker.py:106` BATCH_SIZE_THRESHOLD/BATCH_TIMEOUT_MS(50ms),
  UI 스로틀은 30ms(`presenter/data_handler.py`) — 두 타이밍의 상호작용 분석 포함.
- 최적화 전후 벤치 수치를 같은 조건에서 비교해 개선 폭을 보고한다. 수치 없는 "빨라졌다" 금지.

## Acceptance criteria (착수 시 상세화)

- [ ] 병목 판정 근거(S-011 수치) 기록.
- [ ] 개선 전/후 수치 비교, 전체 pytest 통과.
