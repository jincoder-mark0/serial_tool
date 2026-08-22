# S-008 — RxCaptureWriter 필요성 판정

- Status: DONE — **폐기 결정** (2026-08-22, 상위 판정)
- 판정: RxCaptureWriter는 만들지 않는다. DataLogger(+DataLoggerManager)가 이미 포트별
  BIN/HEX/PCAP 기록·논블로킹 큐·전이중(RX+TX) 기록을 제공해 차별 기능이 없다.
  계획(doc/implementation_plan.md)은 DataLogger가 지금 형태로 자라기 전에 세운 항목이다.
  잠재 차별점 검토 결과: ① RX만 분리 기록 — 필요해지면 DataLogger에 방향 필터 옵션 추가로
  흡수(새 클래스 불요), ② 자동 파일명/세션 자동 시작 — 로깅 UX 개선이지 별도 Writer의
  근거가 아님(요구가 생기면 별도 태스크로). doc/task.md Phase 6 항목에는 폐기 주석을 남긴다.
- Recommended model: **상위 전용** (중복 여부 판정) — 하위 모델 시작 금지
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

`doc/task.md` Phase 6에 "Rx 파일 캡처(RxCaptureWriter)"가 계획으로 남아 있는데,
**기존 DataLogger가 이미 그 기능을 상당 부분 수행한다** — 중복 구현 위험.

## 판정 재료 (2026-08-22 코드 조사)

- `core/data_logger.py:31 DataLogger` — Queue+Thread 논블로킹, BIN/HEX/PCAP 3포맷,
  `:203 DataLoggerManager`가 포트별 인스턴스 관리. Presenter가 RX(`presenter/data_handler.py:80-81`)와
  TX(`:104-105`, 전이중)를 직접 write.
- 파일명 자동 생성은 없음 — 사용자가 다이얼로그로 경로 지정
  (`presenter/main_presenter.py:704-737`, 확장자로 포맷 결정: .pcap/.txt/기타=bin).

## 결정할 것 (상위 모델)

1. RxCaptureWriter가 DataLogger 대비 제공해야 할 차별 기능이 실재하는가
   (예: RX만 분리 캡처, 자동 파일명/롤링, 세션 자동 시작). 없다면 **계획 항목 폐기**하고
   doc/task.md·Task.MD에 폐기 사유 기록.
2. 차별 기능이 있다면 DataLogger 확장으로 흡수할지 별도 클래스로 둘지.

## Acceptance criteria

- [ ] 폐기 또는 구현 방향 결정이 근거와 함께 이 파일과 Task.MD에 기록됨.
- [ ] 구현으로 결정 시 하위 모델용 상세 태스크 신설.
