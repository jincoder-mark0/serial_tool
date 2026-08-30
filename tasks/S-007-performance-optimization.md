# S-007 — 성능 최적화 (Rx 경로·렌더링)

- Status: ⛔ 보류 — **측정 결과 병목 없음** (2026-08-22, 상위 판정)
- 판정 근거 (doc/benchmark_20260822.md 실측): RingBuffer 10,005 MB/s ·
  ThreadSafeQueue 8.27M ops/s · DelimiterParser 32.98M lines/s · DataLogger 1,105 MB/s.
  시리얼 최고 속도(4Mbps ≈ 0.5MB/s) 대비 3~4자릿수 여유 — model/core 경로 최적화는
  측정상 근거가 없다. 계획의 "RingBuffer bytearray화"는 이미 구현돼 있었다
  (`core/structures.py:110` — 계획 문서가 코드보다 낡음).
- 재개 조건: ① 사용자가 실사용에서 UI 지연·CPU 점유 체감을 보고하거나
  ② UI 렌더 구간(QSmartListView append·30ms flush)의 별도 측정에서 병목이 확인될 때.
  재개 시 첫 스텝은 UI 구간 벤치마크 추가다 (S-011 도구 확장).
- Recommended model: **상위 권장** (병목 판단·트레이드오프 결정) — 측정 해석이 본체
- 선행: **S-011 (벤치마크)** — 측정 없이 시작 금지 (완료됨)
- Skills to load: task-done

## 목적 (Why)

루트 `Task.MD` Post-merge backlog: BatchRenderer(RxLog)와 논블로킹 I/O 루프
최적화. 단, **어느 것이 실제 병목인지 측정된 바 없다.**

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
