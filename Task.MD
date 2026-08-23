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

### 리팩토링 감사 산출 (2026-08-22) — 전량 완료

읽기 전용 4축 감사(아키텍처 규칙 / 구조·설계 / 오동작 예상 / 테스트·문서) 결과를
우선순위대로 처리했다. 진단 근거와 남은 항목은 **[doc/refactor_audit_20260822.md](doc/refactor_audit_20260822.md)**,
세부 절차는 `tasks/S-038~S-051`. 테스트 **134 → 284**.

| ID | 제목 | 우선 | 상태 |
|---|---|---|---|
| [S-038](tasks/S-038-log-view-duplicate-methods.md) | 로그 뷰 표시 파손 (중복 메서드 정의) | P0 | ✅ 완료 |
| [S-039](tasks/S-039-tx-data-loss.md) | TX 데이터 유실 (close flush + write_timeout) | P0 | ✅ 완료 |
| [S-040](tasks/S-040-port-tab-close-cleanup.md) | 포트 탭 좀비 연결 + 워커 잔존 | P0 | ✅ 완료 |
| [S-041](tasks/S-041-parser-and-protocol-wiring.md) | 파서 설정 무효 + SPI 선택 기만 | P1 | ✅ 완료 |
| [S-042](tasks/S-042-silent-failures.md) | 전송 실패 무통보 + 매크로 종료 알림 | P1 | ✅ 완료 |
| [S-043](tasks/S-043-settings-pollution.md) | 설정 기본값 개인정보 오염 차단 | P1 | ✅ 완료 |
| [S-044](tasks/S-044-dead-code-and-dto.md) | dead code 3건 + DTO/enum 우회 | P2 | ✅ 완료 |
| [S-045](tasks/S-045-test-coverage-gaps.md) | 커버리지 공백 5모듈 + DataLogger 종료 | P2 | ✅ 완료 |
| [S-046](tasks/S-046-docs-and-rules-sync.md) | 문서·규칙 정합 (EventBus 규칙 정밀화) | P2 | ✅ 완료 |
| [S-047](tasks/S-047-magic-numbers-naming-lint.md) | 매직 넘버·명명 + ruff 도입 | P3 | ✅ 완료 |
| [S-048](tasks/S-048-singleton-isolation-and-key-check.md) | 싱글톤 격리 + 언어 키 사용처 검증 | P3 | ✅ 완료 |
| [S-049](tasks/S-049-log-widget-commonization.md) | 로그 위젯 중복 공통화 | P3 | ✅ 완료 |
| [S-050](tasks/S-050-theme-manager-safety-net.md) | 테마/색 매니저 안전망 + 순환 참조 해소 | P3 | ✅ 완료 |
| [S-051](tasks/S-051-datalog-broadcast-init-mismatch.md) | DataLog 브로드캐스트 초기값 불일치 | — | ✅ 완료 |

### 후속 처리 (2026-08-22, 사용자 지시 "후속후보 진행, 불일치는 통일")

| ID | 제목 | 상태 |
|---|---|---|
| [S-052](tasks/S-052-log-control-flow-unify.md) | 로그 위젯 제어 흐름 **Presenter 권위로 통일** | ✅ 완료 |
| [S-053](tasks/S-053-theme-manager-decompose.md) | ThemeManager(833줄) → FontManager + ThemeResourceLoader + 오케스트레이터 | ✅ 완료 |
| [S-054](tasks/S-054-color-manager-decompose.md) | ColorManager(511줄) → Qt 비의존 ColorRuleRepository + 어댑터 | ✅ 완료 |
| [S-036](tasks/S-036-fixed-font-routing-and-i18n.md) | **고정폭 폰트 설정 미반영** + 언어팩 잔여 4건 | ✅ 완료 (실측 전후 증명) |
| [S-055](tasks/S-055-system-log-persistence-missing.md) | 시스템 로그 저장이 동작하지 않음(구독자 0건) | ✅ 완료 (구현 판정) |
| [S-056](tasks/S-056-error-handler-layer-violation.md) | 크래시 다이얼로그 계층 역전 + **계층 의존 자동 검사** | ✅ 완료 |
| [S-057](tasks/S-057-ruff-cleanup-and-ci-gate.md) | ruff 잔여 정리 → **0건·CI 게이트 전환** | ✅ 완료 |
| [S-058](tasks/S-058-main-presenter-decompose.md) | MainPresenter 분해(설정·종료·포맷 결정) | ✅ 완료 |
| [S-059](tasks/S-059-datalogger-not-stopped-on-exit.md) | **종료 시 RX 로거 미정리 유실**(stop_all 호출처 0건) | ✅ 완료 |

- S-052~S-054는 **S-050 특성화 테스트 무수정 통과**를 안전 판정 기준으로 삼아 검증됐다.
- **S-036은 2026-08-22 실측으로 미해결이 확정됐다**: `class="fixed-font"` 위젯에
  D2Coding 16pt를 설정해도 실제 렌더는 Consolas 9pt다. common.qss의 폰트 하드코딩이
  QSS 특이도로 동적 규칙을 이기며, **동적 규칙이 문자열상 뒤에 있어도 마찬가지**다.

**후속 처리 중 새로 드러난 결함 3건**(모두 수정 완료): 시스템 로그 저장 미배선(S-055),
`stop_all()` 미호출로 종료 시 데이터 유실(S-059 — S-045에서 고친 안전장치가 정작 호출되지
않고 있었다), DataLog 브로드캐스트 초기값 불일치(S-051).

감사가 남겼던 3건(패킷 뷰 스로틀·PortScanWorker 종료 미정리·로그 필터 판정 중복)은
아래 S-061/S-062로 착수했다. 상세는 `doc/refactor_audit_20260822.md`.

### 결함 해결·테마 확장 (2026-08-22, 사용자 지시 "결함을 해결합시다. 클래식 테마도")

| ID | 제목 | 상태 |
|---|---|---|
| [S-060](tasks/S-060-classic-theme.md) | 클래식 테마 추가 — 4번째 테마 | ✅ 완료 |
| [S-061](tasks/S-061-packet-view-throttle.md) | 패킷 뷰 스로틀 — **측정 선행 후 판단**(S-007 원칙) | ✅ 완료 |
| [S-062](tasks/S-062-scanner-cleanup-and-filter-dedup.md) | PortScanWorker 종료 정리 + 필터 판정 중복 해소 | ✅ 완료 |
| [S-063](tasks/S-063-semantic-button-contrast.md) | **의미색 버튼 텍스트 대비 미달** — 전송·반복 버튼이 안 읽힘 | ✅ 완료 |

- S-063은 S-060이 클래식 테마를 만들며 발견해 에스컬레이션한 결함이다. 대칭성을 위해
  기존 3테마의 규칙을 그대로 복사하다 **원본에 있던 문제**를 드러냈다. 48칸 중 18칸이
  기준 미달이었고, 최악은 `warning:disabled`의 **1.22:1**(글씨가 배경과 거의 같은 색).
  `warning:pressed` 배경이 danger 빨강이던 별도 버그도 함께 교정됐다.

### 위 작업에서 파생된 후속 (2026-08-22)

| ID | 제목 | 상태 |
|---|---|---|
| [S-064](tasks/S-064-parser-buffer-truncation-loss.md) | **파서 버퍼 잘라내기로 완결 패킷 유실** (P1) | ✅ 완료 |
| [S-065](tasks/S-065-qss-contrast-regression-test.md) | QSS 대비 회귀 테스트 + 포트 상태 색 점검 | ✅ 완료 |
| [S-066](tasks/S-066-flaky-shutdown-datalogger-test.md) | 종료 시 DataLogger 테스트 간헐 실패 조사 | ✅ 완료 |

- S-064는 S-061이 고속 측정 중 발견했다. `DelimiterParser.parse()`가 구분자로 나누기
  **전에** 버퍼를 자르는데, 파서 상한(4096B)이 워커 배치 임계값(8192B)보다 작아
  **완결된 패킷까지 조용히 버려진다.** 전제는 상위가 코드로 확인했다.
  **완료(2026-08-22)**: 수정 전 회귀 테스트로 3파서 모두 유실을 실측 확인
  (Delimiter 1992개·AT 1494개·FixedLength 1192개 유실) 후 "완결 패킷 먼저 분리 → 남은
  조각에만 상한 적용" 순서로 교정. FixedLengthParser도 동일 순서 버그가 있어 함께
  고쳤다. 미완결 조각 폐기 시 경고 로그 추가, `max_buffer_size` 기본값을
  `common/constants.py`의 `PARSER_MAX_BUFFER_SIZE`(=BATCH_SIZE_THRESHOLD*2=16384)로
  단일 관리. pytest 393 passed(+8), ruff 0건. 상세는 태스크 파일 Status 참조.
- **S-065 완료(2026-08-22)**: `tests/test_qss_contrast.py` 신설 — 4테마 QSS를 파싱해
  의미색 버튼(accent/danger/warning)·포트 상태 버튼/라벨(state=connected/disconnected/
  error/recording)의 대비를 계산하고 활성 ≥4.5:1·disabled ≥3.0:1을 강제한다.
  `:hover`/`:pressed`가 `color`를 재선언하지 않으면 기본 규칙 글자색을 상속하도록 구현.
  이 테스트가 **실제 미달 5건**을 새로 찾아냈다: light/classic
  `state="connected"`(#ffffff on #4CAF50=2.78·hover 2.36 FAIL), light/classic
  `state="error"`(#ffffff on #F44336=3.68·hover 3.49 FAIL), dark
  `state="connected"`:hover(#ffffff on #388E3C=4.12 FAIL), dracula
  `state="disconnected"`:hover(4.41 FAIL), classic `QLabel[state="disconnected"]`
  (#616161 on #d4d0c8=4.03 FAIL — 이 파일 자체 주석 표에 값이 적혀 있었는데도 기준
  미달인 채 방치돼 있었음). S-063이 검증한 accent/danger 값을 그대로 재사용해 수정
  (connected→어두운 글씨 #1b1b1b, error→danger와 동일 배경 톤). 일부러 색을 되돌려
  테스트가 실패하는 것을 확인 후 복구. pytest 393 passed(+3), ruff 0건.
- **S-066 완료(2026-08-22)**: `doc/mistakes.md` #7이 남겨둔 간헐 실패의 정체를
  특정했다. **판정: 테스트 문제** (프로덕션 유실 아님). 원인:
  `test_shutdown_stops_data_logger_and_preserves_written_bytes`/
  `test_shutdown_closes_pcap...`가 `connection_controller.send_data()`로 payload를
  보냈는데, 이 API는 발신(TX) 즉시 EventBus 경유로 `DataTrafficHandler.on_data_sent()`
  에도 라우팅되어(전이중 로깅, 기존 설계) 로거에 곧바로 1회 기록된다. LOOPBACK은
  보낸 바이트가 그대로 에코되어 RX Fast Path로도 다시 들어오므로, 종료 전에 그 RX
  배치까지 추가로 flush되는지 여부(스레드 스케줄링 경합)에 따라 파일에 payload가
  1회(TX만, 우연히 테스트 의도와 일치) 또는 2회(TX+RX, 테스트 실패) 기록됐다 —
  실제 종료 시퀀스(S-059/S-061/S-062)는 매 회 데이터를 온전히 보존했고 유실은 한
  번도 재현되지 않았다(재현: 단독 파일 반복 실행만으로 200/250회 중 5회 실패,
  전이중 우회 후 450회 전부 통과 — in-process 300회 별도 재현에서도 0/300).
  형제 테스트(`test_shutdown_flushes_pending_leftover_batch...`)가 이미 문서화한
  "TX 경로 우회(transport에 직접 write)" 패턴을 두 테스트에도 동일 적용해 순수 RX
  Fast Path만 재현하도록 수정. 조기 종료 판정 오탐(큐가 "아직 비어 있음"과 "다
  써서 비어 있음"을 구분 못 함)도 `_file.tell()` 확인을 추가해 함께 보강.
  이 태스크는 테스트 개수를 늘리지 않았다(기존 2개 테스트 본문만 수정). 검증 시점
  전체 스위트 397 passed(병행 작업 중인 다른 태스크의 변경 포함, 10회 반복 전부
  통과), ruff 0건. 상세는 태스크 파일 Status 및 `doc/mistakes.md` #7 참조.

### 사용자 보고 대응 (2026-08-22)

사용자가 실행 중 관찰한 4건("클래식인데 둥근 모서리", "패널 토글 시 컴포넌트 크기가
미묘하게 변함", "포트 탭 추가할 때마다 오류", "우측 패널 최소폭을 매크로 가로 스크롤이
없는 범위로")을 조사했다. 원인은 모두 실행·측정으로 확정했다.

| ID | 제목 | 상태 |
|---|---|---|
| [S-067](tasks/S-067-port-tab-change-crash-and-theme-schema.md) | 포트 탭 전환 AttributeError + 클래식 테마 저장 불가 | ✅ 완료 |
| [S-068](tasks/S-068-right-section-min-width.md) | 우측 패널 최소 폭 지정 (매크로 가로 스크롤 방지) | ✅ 완료 |
| [S-069](tasks/S-069-port-tab-close-hard-crash.md) | **포트 탭 닫기·재연결 시 프로세스 하드 크래시** | ⏸ 대기 |
| [S-070](tasks/S-070-mock-spec-interface-drift.md) | Presenter→View 인터페이스 드리프트를 Mock이 삼킴 | ⏸ 대기 |

- **S-069(2026-08-23 갱신)**: 원인은 `serial.tools.list_ports.comports()`를 **워커
  스레드에서 호출**하는 것이었다(스텁 시 60회 중 0회, 스레드 수명 개입은 전부 무효).
  `tests/conftest.py`에서 열거를 스텁해 주원인을 제거했다 — 20% → 5%.
  **실제 앱 종료 경로는 40회 전부 정상이라 사용자 영향은 없다**(등재 당시 P0 서술 철회).
  잔여 5%는 LOOPBACK 연결 개폐 경로로 좁혀졌다.
- S-070은 S-067이 드러낸 구멍이다. Presenter 테스트가 View를 `spec` 없는 `MagicMock`으로
  만들어 **존재하지 않는 메서드 호출도 통과**시킨다(프로젝트 전체 `spec=` 사용 0건).
  그래서 393개가 초록인 동안 앱은 탭을 바꿀 때마다 죽고 있었다.

**아직 안 고친 사용자 보고 2건** (원인만 확정):
- 클래식 테마의 둥근 모서리 — `border-radius`가 테마 파일엔 0곳, **`common.qss`에 13곳**.
  4테마가 공유하는 파일이라 클래식만 빠져나갈 수 없다(S-036과 같은 구조 문제).
  테마 QSS가 common 뒤에 붙으므로 클래식에서 덮어쓰면 이긴다.
- 패널 토글 시 크기 변화 — 실측: 숨길 때 `left + margins`(999px)로 줄이려 하나 창 최소
  폭에 막혀 1055로 클램프되고 **차액 56px를 좌측 패널이 흡수**한다. 다시 켜면 창이
  원래보다 56px 커진다(왕복이 항등이 아님).

### 프로토콜 분석 확장 (2026-08-23, 사용자 요청 — WireScope 참고)

사용자가 `reference/wirescope`(Tauri+React 시리얼/TCP 모니터)를 클론해 두고 "프로토콜
분석 기능이 마음에 든다, 다른 좋은 기능은 없는지" 요청했다. 기능을 조사해 SerialTool에
없는 것 중 값어치가 큰 순으로 정리했고, 상위 2건을 태스크로 등재한다.

**⚠️ WireScope는 AGPL-3.0이다.** 기능 개념 참고는 자유지만 **코드를 가져오면 SerialTool
전체가 AGPL 전염 대상**이 된다. 두 태스크 모두 "개념만 참고, 독자 구현"을 명시했다.

| ID | 제목 | 상태 |
|---|---|---|
| [S-071](tasks/S-071-checksum-validation.md) | 패킷 체크섬 검증 (XOR/SUM/CRC 7종) | ✅ 완료 |
| [S-072](tasks/S-072-framing-length-field-and-gap.md) | 프레이밍 확장 — 길이 필드 + 갭 기반 파서 | ✅ 완료 |

- **체크섬을 1순위로 둔 이유**: SerialTool엔 체크섬 개념이 아예 없다(코드 0건). 패킷
  경계는 나눌 수 있는데 "이 패킷이 유효한가"를 답할 수단이 없어, 프로토콜 디버깅의
  가장 잦은 질문에 사람이 HEX를 눈으로 더해야 한다.
- **프레이밍을 2순위로 둔 이유**: 현재 `FixedLengthParser`는 *상수 길이*라 "헤더에
  길이가 들어있는" 프로토콜을 못 다루고, Modbus RTU식 **유휴 시간 프레이밍**도 없다.
  둘은 서로 맞물린다 — 체크섬 오프셋은 프레이밍이 정해져야 의미가 있다.

**후순위로 남긴 것**(구현하지 않음, 판단 대기): 갭 통계·TX→RX 사이클 응답시간 등
**분석기**, `starts:`/`len>8`/`checksum:fail` 같은 **구조화된 패킷 필터**, 수신 패턴에
반응하는 **트리거 전송**(현재 AutoTx는 주기 전송만), 패킷별 메모, 바이트 표시 형식
전환(hex/ascii/dec/bin), 연결 프리셋, 선택 구간 export, TCP/UDP 세션.

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
| [S-033](tasks/S-033-loopback-dummy-port.md) | 루프백 더미 포트 (디버깅용) | 기능 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 테스트 +8, 기준선 130. 레이스 발견 → S-037 |
| [S-037](tasks/S-037-send-before-open-race.md) | 연결 직후 send 침묵 실패 레이스 | 안정성 | ✅ 완료 | 하위 모델 수행 (2026-08-22). 옵션 A(큐잉 허용), 회귀 4건. 기준선 134 |
| [S-034](tasks/S-034-remove-scan-button.md) | 중복 검색 버튼 제거 | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 삭제 20줄·키 2종 제거, 자동 스캔 경로 검증 |
| [S-035](tasks/S-035-spacing-grouping-polish.md) | 마진·구획 정비 (테두리 대비·제목 간격·그루핑) | UX | ✅ 완료 | 하위 모델 수행 (2026-08-22). 대비 3:1↑·간격 상수 2종·ms 라벨. 최소 높이 +11 |
| [S-036](tasks/S-036-fixed-font-routing-and-i18n.md) | 고정폭 폰트 설정 미반영 + 언어팩 잔여 4건 | UX | ✅ 완료 | 근본 원인은 common.qss 하드코딩이 QSS 특이도로 동적 폰트 규칙을 이긴 것 — 그 블록 삭제로 해소, 실측 전후 증명 |

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
