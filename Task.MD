# Task.MD — SerialTool 작업 보드

최상위 작업 현황판. **세부 실행 절차는 `tasks/S-0xx-*.md`** (하위 모델용 자족적 문서 —
시작 방법은 [tasks/README.md](tasks/README.md)). Phase별 완료 체크리스트(이력)는 `doc/task.md`,
구현 계획은 `doc/implementation_plan.md` 참조.
태스크 시작·완료 시 이 표와 태스크 파일의 Status를 갱신한다 (CLAUDE.md 지시).

## 현재 상태 (2026-08-22)

- **Phase 1~5.5 완료**: MVP 구조·멀티포트 시리얼·매크로/파일 전송/로깅·테마/다국어·
  Presenter 세분화·안정화. 테스트 기준선 **85개 통과** (offscreen, Mock Transport).
- 실제 통신 Transport는 `SerialTransport`뿐 — SPI/I2C·플러그인·패키징 미착수 (README §1.4).
- 처리량 수치는 자동 벤치마크 도입 전까지 비보장.
- 문서·에이전트 설정 정비 (2026-08-22): 타 프로젝트에서 복사돼 있던 CLAUDE.md/RULES.md/
  Task.MD/`.claude/`/`tools/analysis` 등을 SerialTool 기준으로 재작성. chatlog 훅·스킬
  (task-done, lang-keys) 도입. 세부 태스크 체계 `tasks/` 신설 (하위 모델용 자족 문서).
- **UX 전면 점검 (2026-08-22, 사용자 지시)**: 실행 스크린샷 8조합(`tools/ux_capture.py` 신설,
  네이티브 렌더 — offscreen은 폰트 미렌더로 판정 불가) + 정적 점검 3종(테마/언어팩/레이아웃)을
  하위 모델로 수행. 결함 35건(높음 10·중간 15·낮음 10) — 보고서 `doc/ux_audit_20260822.md`,
  수정 태스크 S-019~S-026 등재. 코드 조사 중 별도 결함 3건(S-016~S-018)도 발견.

## 작업 보드

상태 값: `⏸ 대기` / `▶ 진행` / `✅ 완료` / `⛔ 보류(사유 기재)`

| ID | 제목 | Phase | 상태 | 비고 |
|---|---|---|---|---|
| S-001 | MVP 골격·UI·테마·다국어 | 1~2.5 | ✅ 완료 | doc/task.md Phase 1~2.5 |
| S-002 | Core 유틸리티 (EventBus/Settings/구조체) | 3 | ✅ 완료 | 설정 스키마 검증·마이그레이션 포함 |
| S-003 | Model 계층 (Connection/Macro/FileTransfer/Parser) | 4 | ✅ 완료 | Fast Path·Backpressure 포함 |
| S-004 | Presenter 세분화·EventRouter | 5 | ✅ 완료 | |
| S-005 | 안정화·테스트 기준선 85개 | 5.5 | ✅ 완료 | 경합·교착 수정, conftest 복구 |
| [S-006](tasks/S-006-auto-tx-scheduler.md) | `AutoTxScheduler` (주기적 자동 전송) | 6 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 테스트 9건, 실기기 미검증. 기준선 109 |
| [S-007](tasks/S-007-performance-optimization.md) | 성능 최적화 (Rx 경로·렌더링) | 6 | ⛔ 보류 | **실측상 병목 없음** (2026-08-22 판정, benchmark_20260822.md). 체감 보고 시 재개 |
| [S-008](tasks/S-008-rx-capture-writer.md) | Rx 파일 캡처 (`RxCaptureWriter`) 필요성 판정 | 6 | ✅ 완료 | **폐기 결정** (2026-08-22) — DataLogger가 전이중·3포맷 기록 이미 제공 |
| [S-009](tasks/S-009-plugin-system.md) | 플러그인 인프라 (base/loader/Example) | 7 | ⏸ 대기 | 인터페이스 설계 선행 (상위 전용) |
| [S-010](tasks/S-010-virtual-serial-env.md) | 가상 시리얼 포트 실환경 검증 (com0com) | 8 | ⏸ 대기 | 사용자 설치 개입 필요. 실기기 미검증 해소 기반 |
| [S-011](tasks/S-011-benchmark.md) | 성능 벤치마크 도구 | 8 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 실측: doc/benchmark_20260822.md. S-007 선행 해소 |
| [S-012](tasks/S-012-packaging.md) | 패키징 (pyinstaller spec, 독립 실행 파일) | 8 | ✅ 완료 | 하위 모델 수행 (2026-08-22). exe 빌드·스모크·스크린샷 확인. 아이콘·언어 전환 수동 잔여 |
| [S-029](tasks/S-029-bundle-log-path.md) | 번들 로그 경로 사용자 디렉터리화 | 8 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 번들=APPDATA\logs, 개발 모드 불변. 기준선 115 |
| [S-013](tasks/S-013-user-config-dir.md) | 설정 파일 사용자 디렉터리 분리 | 8 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 번들=APPDATA, 개발 모드 불변. S-012 선행 해소 |
| [S-014](tasks/S-014-github-actions-ci.md) | GitHub Actions CI (pytest + 언어 키 검사) | 8 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 러너 실검증은 push 후 확인 필요 |
| [S-015](tasks/S-015-spi-i2c-transport.md) | SPI/I2C Transport 확장 | 후속 | ⛔ 보류 | 요구 미확정 (대상 하드웨어·유스케이스) |
| [S-016](tasks/S-016-settings-namespace.md) | 설정 키 네임스페이스 이중화 해소 (`settings.*` vs `global.*`) | 유지보수 | ✅ 완료 | **결정**: `settings.*` 정본 (2026-08-22). 구현은 S-027 |
| [S-027](tasks/S-027-settings-namespace-migration.md) | 설정 네임스페이스 마이그레이션 구현 (1.0→1.1) | 유지보수 | ✅ 완료 | 하위 모델 수행 (2026-08-22). global 소멸·스키마 실검증. 기준선 100 |
| [S-028](tasks/S-028-right-width-key-conflict.md) | 우측 폭 저장 키 이중화 해소 | 유지보수 | ✅ 완료 | 하위 모델 수행 (2026-08-22). saved_* 정본, 1.2 마이그레이션. 기준선 112 |
| [S-030](tasks/S-030-flowctrl-key-resurrection.md) | 루트 serial 고아 블록 정리 + defaults no-op 가드 | 유지보수 | ✅ 완료 | 하위 조사로 전제 오류 정정 후 완결 (2026-08-22). 1.3 승격, 재발 차단 테스트. 기준선 118 |
| [S-031](tasks/S-031-ui-guide-enforcement.md) | UI 가이드 강제 테스트 + 잔여 위반 정리 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 정적 스캔 4종·위반 4그룹 실수정·허용 목록 0건. 기준선 122 |
| [S-017](tasks/S-017-ui-refresh-constant.md) | UI 갱신 주기 리터럴 30 상수화 | 유지보수 | ✅ 완료 | 하위 모델 수행 (2026-08-22). pytest 85 passed |
| [S-018](tasks/S-018-meipass-detection-fix.md) | PyInstaller 감지 버그 수정 (`os._MEIPASS`→`sys`) | 유지보수 | ✅ 완료 | 하위 모델 수행 (2026-08-22). S-012/013 선행 해소 |
| [S-019](tasks/S-019-datalog-duplicate-init.md) | DataLogWidget init_ui 중복 생성 블록 제거 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 26줄 삭제, pytest 85+캡처 검증. 검색창 축소 별건은 S-026로 |
| [S-020](tasks/S-020-langpack-broken-keys.md) | 언어팩 결함 수정 (깨진 키·오타·용어 통일) | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 캡처 8조합 키 노출 0건. packet.py dead code 발견(보고만) |
| [S-021](tasks/S-021-hardcoded-messages-i18n.md) | 하드코딩 사용자 메시지 언어팩 전환 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 키 32개 신설, 상태바·통계 retranslate 연동 |
| [S-022](tasks/S-022-theme-contrast-hardcoded-colors.md) | 테마 대비 미달·하드코딩 색 수정 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 색 리터럴 제거·대비 전 조합 ≥4.5 |
| [S-023](tasks/S-023-theme-system-structural.md) | 테마 시스템 구조 결함 (죽은 경로·dracula 라우팅) | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 3테마 정상 경로 로드, 동기화·번역 정합 |
| [S-024](tasks/S-024-text-clipping-fixed-sizes.md) | 텍스트 잘림·고정 크기 수정 (영문 버튼 등) | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 고정→최소 크기 5곳, 캡처 8조합+16pt 검증 |
| [S-025](tasks/S-025-ui-consistency.md) | UI 일관성 정비 (툴팁·상수·다이얼로그·니모닉) | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 상수 6종·툴팁 14키·니모닉·버튼바 통일 |
| [S-026](tasks/S-026-minimum-window-width.md) | 최소 창 크기 완화 | UX | ✅ 완료 | **1471×786 → 1093×780** (2026-08-22). 폭 목표 초과 달성. 높이 잔여는 S-032 |
| [S-032](tasks/S-032-min-height-and-macro-header.md) | 최소 높이 마무리 + 매크로 헤더 잘림 | UX | ✅ 완료 | 헤더 잘림 해소(스크롤 허용 판정). 높이 780 잔여는 ⛔ 보류(재개 조건부). 전제 오류 → RULES §8 규칙화 |
| [S-033](tasks/S-033-loopback-dummy-port.md) | 루프백 더미 포트 (디버깅용) | 기능 | ⏸ 대기 | 사용자 제안 (2026-08-22). 실기기 없는 전 경로 디버깅 |
| [S-034](tasks/S-034-remove-scan-button.md) | 중복 검색 버튼 제거 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 삭제 20줄·키 2종 제거, 자동 스캔 경로 검증 |
| [S-035](tasks/S-035-spacing-grouping-polish.md) | 마진·구획 정비 (테두리 대비·제목 간격·그루핑) | UX | ⏸ 대기 | 2026-08-22 마진·배치 점검 처방 — 테두리 1.1:1, 제목 간격 10배 차 등 |
| [S-036](tasks/S-036-fixed-font-routing-and-i18n.md) | 고정폭 폰트 설정 미반영 + 언어팩 잔여 4건 | UX | ⏸ 대기 | 근본 원인: common.qss 하드코딩이 QSS 특이도로 동적 폰트 규칙을 이김 |

## 우선순위 메모

1. **S-010 가상 포트 환경** — "실기기 미검증" 딱지를 떼는 기반. 다른 항목의 검증 품질이 여기에 걸린다.
2. **S-013 → S-012 → S-014** — 배포 트랙. 설정 경로 분리가 패키징의 선행 조건.
3. **S-011 → S-007** — 측정 먼저, 최적화는 그다음.
4. S-006/S-008은 독립적이라 언제든 착수 가능. S-009/S-015는 요구 구체화 후.

## 운영 규칙

- 새 태스크는 `S-0xx` 번호로 이 표에 추가하고 `tasks/S-0xx-<slug>.md`를 작성한다
  (번호는 증가만, 재사용 금지). 태스크 파일 작성은 상위 모델 담당 — RULES.md §8.
  형식: 목적 / 배경(자족적) / 참조 파일 / Steps / Acceptance criteria / 검증 방법.
- 완료 선언은 RULES.md §2 검증 규율을 따른다 (실행한 명령·결과·Mock/실기기 여부 명시).
- 완료 시: 이 표 갱신 → `doc/task.md` 체크리스트 반영 → `doc/CHANGELOG.md` 기록 → 커밋
  (`.claude/skills/task-done` 절차).
