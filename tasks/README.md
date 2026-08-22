# tasks/ — 세부 태스크 문서

루트 [Task.MD](../Task.MD)(작업 보드)의 각 항목을 **하위 모델이 프로젝트 전체 파악 없이
Steps 그대로 수행할 수 있는 수준**으로 상세화한 문서 모음.

## 사용 방법 (모든 세션)

1. CLAUDE.md·RULES.md를 먼저 읽는다.
2. 루트 `Task.MD`에서 현재 위치를 파악하고, 아래 표에서 다음 TODO를 고른다
   (의존 순서 준수, **Recommended model 확인 — 상위 모델 권장 태스크를 하위 모델이 시작하지 않는다**).
3. 태스크 파일의 "Skills to load"에 적힌 스킬을 로드한다 (`.claude/skills/`: task-done, lang-keys).
4. Steps를 그대로 따르고, Acceptance criteria 전부 충족 후 **task-done 스킬 절차**로 마감한다
   (검증 3단계 → Task.MD·태스크 파일 Status 갱신 → doc/CHANGELOG.md → 커밋).
5. **Task 파일 밖의 재량 판단이 필요해지면 진행을 멈추고** 현재 상태를 보고한 뒤 상위 모델 검토를 요청한다.

## 공통 환경 (모든 태스크)

```powershell
Set-Location e:\Python\serial_tool
$env:QT_QPA_PLATFORM="offscreen"          # GUI 없는 환경 필수
.venv\Scripts\python -m pytest -q          # 전체 테스트 (기준선 85개)
```

## 태스크 목록 (의존 순서)

| ID | 제목 | Recommended model | 선행 | 상태 |
|---|---|---|---|---|
| [S-019](S-019-datalog-duplicate-init.md) | DataLogWidget init_ui 중복 블록 제거 | **하위 가능** | — | TODO |
| [S-020](S-020-langpack-broken-keys.md) | 언어팩 결함 수정 (깨진 키·오타·용어) | **하위 가능** | — | TODO |
| [S-022](S-022-theme-contrast-hardcoded-colors.md) | 테마 대비·하드코딩 색 수정 | **하위 가능** | — | TODO |
| [S-024](S-024-text-clipping-fixed-sizes.md) | 텍스트 잘림·고정 크기 수정 | **하위 가능** | — | TODO |
| [S-023](S-023-theme-system-structural.md) | 테마 시스템 구조 결함 수정 | **하위 가능** | — | TODO |
| [S-021](S-021-hardcoded-messages-i18n.md) | 하드코딩 메시지 언어팩 전환 | **하위 가능** | S-020 권장 | TODO |
| [S-025](S-025-ui-consistency.md) | UI 일관성 정비 (툴팁·상수·니모닉) | **하위 가능** | S-019 | TODO |
| [S-017](S-017-ui-refresh-constant.md) | UI 갱신 주기 리터럴 30 상수화 | **하위 가능** | — | TODO |
| [S-018](S-018-meipass-detection-fix.md) | PyInstaller 감지 버그 수정 (`os._MEIPASS`→`sys`) | **하위 가능** | — | TODO |
| [S-006](S-006-auto-tx-scheduler.md) | AutoTxScheduler (주기적 자동 전송) | **하위 가능** | — | TODO |
| [S-011](S-011-benchmark.md) | 성능 벤치마크 도구 | **하위 가능** | — | TODO |
| [S-013](S-013-user-config-dir.md) | 설정 파일 사용자 디렉터리 분리 | **하위 가능** | S-018 | TODO |
| [S-014](S-014-github-actions-ci.md) | GitHub Actions CI | **하위 가능** | — | TODO |
| [S-012](S-012-packaging.md) | PyInstaller 패키징 | 하위 가능 (수동 확인 항목 있음) | S-013, S-018 | TODO |
| [S-016](S-016-settings-namespace.md) | 설정 키 네임스페이스 이중화 해소 | **상위 전용** (결정 필요) | — | TODO |
| [S-008](S-008-rx-capture-writer.md) | RxCaptureWriter 필요성 판정 | **상위 전용** (결정 필요) | — | TODO |
| [S-007](S-007-performance-optimization.md) | 성능 최적화 | **상위 권장** | S-011 | TODO |
| [S-009](S-009-plugin-system.md) | 플러그인 인프라 | **상위 전용** (설계 선행) | — | TODO |
| [S-026](S-026-minimum-window-width.md) | 최소 창 크기 과대 완화 (1435px) | **상위 권장** (설계) | S-019, S-024 | TODO |
| [S-010](S-010-virtual-serial-env.md) | 가상 시리얼 포트 실환경 검증 | 사용자 개입 필요 (com0com 설치) | — | TODO |
| [S-015](S-015-spi-i2c-transport.md) | SPI/I2C Transport 확장 | **상위 전용** (요구 미확정) | — | ⛔ 보류 |

- **하위 가능**: Steps가 자족적으로 작성됨. Steps 밖 판단이 필요해지면 즉시 중단·보고.
- **상위 전용/권장**: 설계·판단이 본체인 태스크. 하위 모델은 시작하지 않는다.
- 상태 값: `TODO` / `DOING` / `DONE` / `⛔ 보류(사유)` — 태스크 파일 상단 Status와 이 표, Task.MD를 함께 갱신.

## 태스크 파일 형식 (새 태스크 작성 시 — 상위 모델만)

`S-0xx-<slug>.md` — Status / Recommended model / 선행 / Skills to load 헤더 +
목적(Why) / 배경(자족적 설명) / 참조 파일(경로:라인) / Steps / Acceptance criteria / 검증 방법.
번호는 Task.MD 보드와 공유하며 증가만 한다 (재사용 금지).
