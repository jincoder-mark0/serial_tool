# tasks/ — 세부 태스크 문서

완료·보류된 S-xxx 작업과 후속 기능 후보의 상세 기록입니다. 루트
[`Task.MD`](../Task.MD)는 현재 검증 작업만 관리하며, 이 문서는 과거 태스크 파일의
상태 인덱스를 유지합니다.

## 사용 방법 (모든 세션)

1. `AGENTS.md`와 루트 `Task.MD`를 먼저 읽는다.
2. 루트 `Task.MD`에서 현재 작업과 우선순위를 확인한다. 신규 기능 착수 승인이 있을 때만
   아래 표의 TODO/보류 항목과 의존 관계를 참고한다.
3. 태스크 파일의 과거 "Skills to load" 항목은 현재 환경에 같은 skill이 있을 때만 참고한다.
4. Steps를 그대로 따르고 Acceptance criteria를 충족한 뒤 태스크 파일 Status,
   이 인덱스와 `doc/CHANGELOG.md`를 함께 갱신한다.
5. **Task 파일 밖의 재량 판단이 필요해지면 진행을 멈추고** 현재 상태를 보고한 뒤 상위 모델 검토를 요청한다.

## 공통 환경 (모든 태스크)

```powershell
Set-Location e:\Python\serial_tool
$env:QT_QPA_PLATFORM="offscreen"          # GUI 없는 환경 필수
.venv\Scripts\python -m pytest -q          # 2026-08-30 로컬 기준선 622개
```

## 태스크 목록 (의존 순서)

| ID | 제목 | Recommended model | 선행 | 상태 |
|---|---|---|---|---|
| [S-019](S-019-datalog-duplicate-init.md) | DataLogWidget init_ui 중복 블록 제거 | **하위 가능** | — | DONE |
| [S-020](S-020-langpack-broken-keys.md) | 언어팩 결함 수정 (깨진 키·오타·용어) | **하위 가능** | — | DONE |
| [S-022](S-022-theme-contrast-hardcoded-colors.md) | 테마 대비·하드코딩 색 수정 | **하위 가능** | — | DONE |
| [S-024](S-024-text-clipping-fixed-sizes.md) | 텍스트 잘림·고정 크기 수정 | **하위 가능** | — | DONE |
| [S-023](S-023-theme-system-structural.md) | 테마 시스템 구조 결함 수정 | **하위 가능** | — | DONE |
| [S-021](S-021-hardcoded-messages-i18n.md) | 하드코딩 메시지 언어팩 전환 | **하위 가능** | S-020 권장 | DONE |
| [S-025](S-025-ui-consistency.md) | UI 일관성 정비 (툴팁·상수·니모닉) | **하위 가능** | S-019 | DONE |
| [S-017](S-017-ui-refresh-constant.md) | UI 갱신 주기 리터럴 30 상수화 | **하위 가능** | — | DONE |
| [S-018](S-018-meipass-detection-fix.md) | PyInstaller 감지 버그 수정 (`os._MEIPASS`→`sys`) | **하위 가능** | — | DONE |
| [S-006](S-006-auto-tx-scheduler.md) | AutoTxScheduler (주기적 자동 전송) | **하위 가능** | — | DONE |
| [S-011](S-011-benchmark.md) | 성능 벤치마크 도구 | **하위 가능** | — | DONE |
| [S-013](S-013-user-config-dir.md) | 설정 파일 사용자 디렉터리 분리 | **하위 가능** | S-018 | DONE |
| [S-014](S-014-github-actions-ci.md) | GitHub Actions CI | **하위 가능** | — | DONE (러너 확인 대기) |
| [S-027](S-027-settings-namespace-migration.md) | 설정 네임스페이스 마이그레이션 (settings.* 정본화) | **하위 가능** | S-013 | DONE |
| [S-028](S-028-right-width-key-conflict.md) | 우측 폭 저장 키 이중화 해소 | 상위 결정 후 하위 | S-027 | DONE |
| [S-030](S-030-flowctrl-key-resurrection.md) | 루트 serial 고아 블록 정리 (flowctrl 부활 근본 원인) | **하위 가능** | S-028 | DONE |
| [S-031](S-031-ui-guide-enforcement.md) | UI 가이드 기계적 강제 테스트 + 잔여 위반 정리 | **하위 가능** | ui_guide 제정 | DONE |
| [S-012](S-012-packaging.md) | PyInstaller 패키징 | 하위 가능 (수동 확인 항목 있음) | S-013, S-018 | DONE |
| [S-029](S-029-bundle-log-path.md) | 번들 로그 경로 사용자 디렉터리화 | **하위 가능** | S-012 | DONE |
| [S-016](S-016-settings-namespace.md) | 설정 키 네임스페이스 이중화 해소 | **상위 전용** (결정 필요) | — | DONE (결정 — 구현은 S-027) |
| [S-008](S-008-rx-capture-writer.md) | RxCaptureWriter 필요성 판정 | **상위 전용** (결정 필요) | — | DONE (폐기 결정) |
| [S-007](S-007-performance-optimization.md) | 성능 최적화 | **상위 권장** | S-011 | ⛔ 보류 (실측상 병목 없음) |
| [S-009](S-009-plugin-system.md) | 플러그인 인프라 | **상위 전용** (설계 선행) | — | TODO |
| [S-026](S-026-minimum-window-width.md) | 최소 창 크기 완화 (1471→1093px) | 상위 설계 + 하위 수행 | S-019, S-024 | DONE |
| [S-032](S-032-min-height-and-macro-header.md) | 최소 높이 마무리 + 매크로 헤더 잘림 | **하위 가능** | S-026 | DONE (높이 잔여는 보류 판정) |
| [S-033](S-033-loopback-dummy-port.md) | 루프백 더미 포트 (디버깅용) | **하위 가능** | — | DONE |
| [S-037](S-037-send-before-open-race.md) | 연결 직후 send 침묵 실패 레이스 | **하위 가능** | S-033 | DONE |
| [S-034](S-034-remove-scan-button.md) | 중복 검색 버튼 제거 (팝업 자동 스캔 존재) | **하위 가능** | — | DONE |
| [S-035](S-035-spacing-grouping-polish.md) | 마진·구획 정비 (테두리 대비·제목 간격·그루핑) | **하위 가능** | S-033, S-034 | DONE |
| [S-036](S-036-fixed-font-routing-and-i18n.md) | 고정폭 폰트 설정 미반영 수정 + 언어팩 잔여 | **하위 가능** | S-035 | DONE |
| [S-010](S-010-virtual-serial-env.md) | 가상 시리얼 포트 실환경 검증 | 사용자 개입 필요 (com0com 설치) | — | TODO |
| [S-015](S-015-spi-i2c-transport.md) | SPI/I2C Transport 확장 | **상위 전용** (요구 미확정) | — | ⛔ 보류 |

### 리팩토링 감사 산출 (2026-08-22, `doc/refactor_audit_20260822.md`)

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-038](S-038-log-view-duplicate-methods.md) | 로그 뷰 표시 파손 (중복 메서드 정의) | P0 | DONE |
| [S-039](S-039-tx-data-loss.md) | TX 데이터 유실 (close flush + write_timeout) | P0 | DONE |
| [S-040](S-040-port-tab-close-cleanup.md) | 포트 탭 좀비 연결 + 워커 잔존 | P0 | DONE |
| [S-041](S-041-parser-and-protocol-wiring.md) | 파서 설정 무효 + SPI 선택 기만 | P1 | DONE |
| [S-042](S-042-silent-failures.md) | 전송 실패 무통보 + 매크로 종료 알림 | P1 | DONE |
| [S-043](S-043-settings-pollution.md) | 설정 기본값 개인정보 오염 차단 | P1 | DONE |
| [S-044](S-044-dead-code-and-dto.md) | dead code 3건 + DTO/enum 우회 | P2 | DONE |
| [S-045](S-045-test-coverage-gaps.md) | 커버리지 공백 5모듈 + DataLogger 종료 | P2 | DONE |
| [S-046](S-046-docs-and-rules-sync.md) | 문서·규칙 정합 (EventBus 규칙 정밀화 포함) | P2 | DONE |
| [S-047](S-047-magic-numbers-naming-lint.md) | 매직 넘버·명명 + ruff 도입 | P3 | DONE |
| [S-048](S-048-singleton-isolation-and-key-check.md) | 싱글톤 격리 + 언어 키 사용처 검증 | P3 | DONE |
| [S-049](S-049-log-widget-commonization.md) | 로그 위젯 중복 공통화 | P3 | DONE |
| [S-050](S-050-theme-manager-safety-net.md) | 테마/색 매니저 안전망 + 순환 참조 해소 | P3 | DONE |
| [S-051](S-051-datalog-broadcast-init-mismatch.md) | DataLog 브로드캐스트 초기값 불일치 | — | DONE |
| [S-052](S-052-log-control-flow-unify.md) | 로그 위젯 제어 흐름 통일 (Presenter 권위) | 후속 | DONE |
| [S-053](S-053-theme-manager-decompose.md) | ThemeManager 분해 (FontManager + ResourceLoader) | 후속 | DONE |
| [S-054](S-054-color-manager-decompose.md) | ColorManager 분해 (Qt 비의존 Repository) | 후속 | DONE |
| [S-055](S-055-system-log-persistence-missing.md) | 시스템 로그 저장이 동작하지 않음 | 후속 | DONE |
| [S-056](S-056-error-handler-layer-violation.md) | 크래시 다이얼로그 계층 역전 + 계층 의존 자동 검사 | 후속 | DONE |
| [S-057](S-057-ruff-cleanup-and-ci-gate.md) | ruff 잔여 정리 → 0건·CI 게이트 전환 | 후속 | DONE |
| [S-058](S-058-main-presenter-decompose.md) | MainPresenter 분해 (설정·종료·포맷 결정) | 후속 | DONE |
| [S-059](S-059-datalogger-not-stopped-on-exit.md) | 종료 시 RX 로거 미정리 유실 (stop_all 미호출) | 후속 | DONE |

### 결함 해결·테마 확장 (2026-08-22, 사용자 지시 "결함을 해결합시다. 클래식 테마도")

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-060](S-060-classic-theme.md) | 클래식 테마 추가 (4번째 테마) | 기능 | DONE |
| [S-061](S-061-packet-view-throttle.md) | 패킷 뷰 스로틀 (측정 선행 후 판단) | 성능 | DONE |
| [S-062](S-062-scanner-cleanup-and-filter-dedup.md) | PortScanWorker 종료 정리 + 필터 판정 중복 해소 | 안정성 | DONE |
| [S-063](S-063-semantic-button-contrast.md) | 의미색 버튼 텍스트 대비 미달 (전송·반복 버튼) | UX | DONE |
| [S-064](S-064-parser-buffer-truncation-loss.md) | 파서 버퍼 잘라내기로 완결 패킷 유실 | P1 | DONE |
| [S-065](S-065-qss-contrast-regression-test.md) | QSS 대비 회귀 테스트 + 포트 상태 색 점검 | UX | DONE |
| [S-066](S-066-flaky-shutdown-datalogger-test.md) | 종료 시 DataLogger 테스트 간헐 실패 조사 | 안정성 | DONE |

### 사용자 보고 대응 (2026-08-22)

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-067](S-067-port-tab-change-crash-and-theme-schema.md) | 포트 탭 전환 AttributeError + 클래식 테마 저장 불가 | P0 | DONE |
| [S-068](S-068-right-section-min-width.md) | 우측 패널 최소 폭 지정 (매크로 가로 스크롤 방지) | UX | DONE |
| [S-069](S-069-port-tab-close-hard-crash.md) | 테스트 하네스 하드 크래시 | 안정성 | DONE |
| [S-070](S-070-mock-spec-interface-drift.md) | Presenter→View 인터페이스 드리프트를 Mock이 삼킴 | P1 | DONE |

### 프로토콜 분석 확장 (2026-08-23, WireScope 참고 — 개념만, AGPL 코드 복사 금지)

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-071](S-071-checksum-validation.md) | 패킷 체크섬 검증 (XOR/SUM/CRC 7종) | 기능 | DONE |
| [S-072](S-072-framing-length-field-and-gap.md) | 프레이밍 확장 — 길이 필드 파서 + 갭 기반 파서 | 기능 | DONE |

### 사용자 보고 후속 (2026-08-23)

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-073](S-073-classic-square-corners.md) | 클래식 테마 사각 모서리 | UX | DONE |
| [S-074](S-074-right-panel-toggle-roundtrip.md) | 우측 패널 토글 왕복이 항등이 아님 | UX | DONE |
| [S-075](S-075-port-settings-column-alignment.md) | 포트 설정 첫 열 정렬 + 언어 전환 시 이동 | UX | DONE |
| [S-076](S-076-dialog-layout-and-i18n.md) | 서브 윈도우 레이아웃·다국어 점검 | UX | DONE |
| [S-077](S-077-theme-uniformity-and-component-distinction.md) | 테마 파일 구조 통일 + 컴포넌트 구분 | UX | DONE |
| [S-078](S-078-move-hardcoded-colors-to-theme.md) | 코드의 하드코딩 색을 테마 리소스로 이동 | UX | DONE |
| [S-079](S-079-remaining-screens-sweep.md) | 남은 화면 훑기 (매크로 패널 상세 / 포트 탭 다중 상태) | UX | DONE |
| [S-080](S-080-macro-send-result.md) | 매크로 스텝 판정을 실제 전송 결과에 연결 | 설계 | DONE |
| [S-081](S-081-settings-durability.md) | 설정 저장 원자화 + 손상 파일 백업 | 설계 | DONE |
| [S-082](S-082-modal-not-reentrant.md) | 모달 알림 재진입 제거 | 설계 | DONE |
| [S-083](S-083-remove-dead-event-legs.md) | 소비자 없는 EventBus 갈래 제거 | 설계 | DONE |

- **하위 가능**: Steps가 자족적으로 작성됨. Steps 밖 판단이 필요해지면 즉시 중단·보고.
- **상위 전용/권장**: 설계·판단이 본체인 태스크. 하위 모델은 시작하지 않는다.
- 상태 값: `TODO` / `DOING` / `DONE` / `⛔ 보류(사유)` — 태스크 파일 상단 Status와 이 표를 함께 갱신.

## 태스크 파일 형식 (새 태스크 작성 시 — 상위 모델만)

`S-0xx-<slug>.md` — Status / Recommended model / 선행 / Skills to load 헤더 +
목적(Why) / 배경(자족적 설명) / 참조 파일(경로:라인) / Steps / Acceptance criteria / 검증 방법.
번호는 Task.MD 보드와 공유하며 증가만 한다 (재사용 금지).
