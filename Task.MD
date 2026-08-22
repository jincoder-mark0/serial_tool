# Task.MD — SerialTool 작업 보드

최상위 작업 현황판. Phase별 상세 완료 체크리스트(이력)는 `doc/task.md`,
구현 계획은 `doc/implementation_plan.md` 참조.
태스크 시작·완료 시 이 표의 상태를 갱신한다 (CLAUDE.md 지시).

## 현재 상태 (2026-08-22)

- **Phase 1~5.5 완료**: MVP 구조·멀티포트 시리얼·매크로/파일 전송/로깅·테마/다국어·
  Presenter 세분화·안정화. 테스트 기준선 **85개 통과** (offscreen, Mock Transport).
- 실제 통신 Transport는 `SerialTransport`뿐 — SPI/I2C·플러그인·패키징 미착수 (README §1.4).
- 처리량 수치는 자동 벤치마크 도입 전까지 비보장.
- 문서·에이전트 설정 정비 (2026-08-22): 타 프로젝트에서 복사돼 있던 CLAUDE.md/RULES.md/
  Task.MD/`.claude/`/`tools/analysis` 등을 SerialTool 기준으로 재작성. chatlog 훅·스킬
  (task-done, lang-keys) 도입.

## 작업 보드

상태 값: `⏸ 대기` / `▶ 진행` / `✅ 완료` / `⛔ 보류(사유 기재)`

| ID | 제목 | Phase | 상태 | 비고 |
|---|---|---|---|---|
| S-001 | MVP 골격·UI·테마·다국어 | 1~2.5 | ✅ 완료 | doc/task.md Phase 1~2.5 |
| S-002 | Core 유틸리티 (EventBus/Settings/구조체) | 3 | ✅ 완료 | 설정 스키마 검증·마이그레이션 포함 |
| S-003 | Model 계층 (Connection/Macro/FileTransfer/Parser) | 4 | ✅ 완료 | Fast Path·Backpressure 포함 |
| S-004 | Presenter 세분화·EventRouter | 5 | ✅ 완료 | |
| S-005 | 안정화·테스트 기준선 85개 | 5.5 | ✅ 완료 | 경합·교착 수정, conftest 복구 |
| S-006 | `AutoTxScheduler` (주기적 자동 전송) | 6 | ⏸ 대기 | |
| S-007 | 성능 최적화 (BatchRenderer·RingBuffer bytearray·I/O 루프) | 6 | ⏸ 대기 | 벤치마크(S-011) 선행 권장 — 측정 없는 최적화 금지 |
| S-008 | Rx 파일 캡처 (`RxCaptureWriter`) | 6 | ⏸ 대기 | data_logger와 역할 경계 정의 필요 |
| S-009 | 플러그인 인프라 (base/loader/Example) | 7 | ⏸ 대기 | 인터페이스 설계 리뷰 선행 |
| S-010 | 가상 시리얼 포트 테스트 환경 (com0com/socat) | 8 | ⏸ 대기 | 실기기 미검증 항목 해소용 |
| S-011 | 성능 벤치마크 (Rx 처리량·UI 렌더링) | 8 | ⏸ 대기 | 통과 후 README 수치 보장 전환 |
| S-012 | 패키징 (pyinstaller spec, 독립 실행 파일) | 8 | ⏸ 대기 | 설정 파일 사용자 디렉터리 분리(S-013) 선행 |
| S-013 | 설정 파일 사용자 디렉터리 분리 | 8 | ⏸ 대기 | 현재 `resources/configs/settings.json`에 직접 저장 — 배포 시 필수 |
| S-014 | GitHub Actions CI (pytest + 언어 키 검사) | 8 | ⏸ 대기 | `check_language_keys.py`는 CI 용도로 이미 작성됨 |
| S-015 | SPI/I2C Transport 확장 | 후속 | ⏸ 대기 | `BaseTransport` 뒤에서만 구현 |

## 우선순위 메모

1. **S-010 가상 포트 환경** — "실기기 미검증" 딱지를 떼는 기반. 다른 항목의 검증 품질이 여기에 걸린다.
2. **S-013 → S-012 → S-014** — 배포 트랙. 설정 경로 분리가 패키징의 선행 조건.
3. **S-011 → S-007** — 측정 먼저, 최적화는 그다음.
4. S-006/S-008은 독립적이라 언제든 착수 가능. S-009/S-015는 요구 구체화 후.

## 운영 규칙

- 새 태스크는 `S-0xx` 번호로 이 표에 추가한다 (번호는 증가만, 재사용 금지).
  규모가 큰 태스크는 목적/선행 조건/작업 항목/완료 조건(DoD)/검증 방법을 비고 또는 별도 문서에 적는다.
- 완료 선언은 RULES.md §2 검증 규율을 따른다 (실행한 명령·결과·Mock/실기기 여부 명시).
- 완료 시: 이 표 갱신 → `doc/task.md` 체크리스트 반영 → `doc/CHANGELOG.md` 기록 → 커밋
  (`.claude/skills/task-done` 절차).
