# RULES.md — SerialTool 운영 규칙 (자가 진화 문서)

이 문서는 살아있는 규칙집이다. 모든 세션은 작업 시작 전 이 파일을 읽는다 (CLAUDE.md가 지시).
아키텍처 불변식은 CLAUDE.md에, 코딩 표준은 `.agent/rules/`에 있다 — 여기는 **작업·검증·커밋의
운영 규율**과 반복 실수에서 규칙화된 항목을 담는다.

## 1. 자가 진화 프로토콜 (Rule Evolution)

1. 실수/실행 오류/규약 위반이 발생하면 `doc/mistakes.md`(실수 대장)에 1줄 기록:
   `YYYY-MM-DD | 증상 | 원인 | 일회성: 예/아니오 | 조치`.
2. **동일 원인이 2회 이상 반복되면** 방지 지침을 다음 중 가장 강제력 있는 위치에 반영한다:
   - 기계적으로 차단 가능 → **테스트/도구에 검사 추가** 또는 **훅**(`.claude/settings.json`) — 최우선
   - 작업 레시피 문제 → 해당 **스킬**(`.claude/skills/*`) 갱신
   - 판단 규칙 문제 → 이 **RULES.md**에 규칙 추가
3. 규칙 반영 커밋 메시지는 `Rule: <무엇을 왜>` 접두어. mistakes.md 해당 항목에 "→ 규칙화됨" 표시.

## 2. 검증 규율 (Verification)

- **완료 선언 조건**: ① 변경과 가장 가까운 테스트 통과 → ② 전체 pytest 통과(현재 기준선 459개)
  → ③ UI 문자열을 건드렸으면 `tools/check_language_keys.py` 통과. 셋 중 실행한 것과 결과를
  명시해야 "완료"라고 쓸 수 있다.
- 테스트는 `QT_QPA_PLATFORM=offscreen` 환경에서 실행한다 (GUI 없는 환경/CI 공통).
- 검증에 사용한 것이 **Mock인지 실기기인지** 항상 구분해 보고한다. 실제 시리얼 포트로만
  확인 가능한 동작(타이밍·flow control·장비 echo 등)은 "실기기 미검증"으로 남기고 추정으로 채우지 않는다.
- 테스트 기준선이 늘어나면 이 문서와 README의 숫자를 갱신한다. 기존 테스트를 깨뜨린 채
  기준선 숫자를 줄이는 변경은 사용자 승인 없이 금지.
- 스레드 관련 수정(Worker/Runner/Service)은 시작·종료·강제 종료 경로를 테스트로 확인한다 —
  경합·교착은 재현이 어려우므로 "실행해 보니 됐다"는 검증이 아니다.

## 3. MVP 규율 (Architecture Discipline)

- 새 기능은 **View(시그널·표시) / Presenter(로직·중재) / Model(상태·I/O)** 3분할로 설계한 뒤 구현한다.
  한 계층에 몰아넣은 "일단 동작" 구현을 만들지 않는다.
- View에 로직이 들어가는 신호: 조건 분기로 Model 상태를 해석하거나, 문자열을 조립·변환하거나,
  설정을 직접 읽는 코드. 발견하면 Presenter로 옮긴다.
- EventBus 토픽·설정 키를 새로 만들 때는 `common/constants.py`(EventTopics/ConfigKeys)에 등록하고
  문자열 리터럴을 직접 쓰지 않는다.
- 설정 스키마(`core/settings_schema.py`)를 바꾸면 마이그레이션 경로와 기본값 폴백을 함께 제공한다 —
  기존 사용자의 settings.json이 깨져서는 안 된다.

## 4. UI·다국어 규율

- UI 텍스트 추가·변경 절차는 `.claude/skills/lang-keys` 스킬을 따른다:
  en.json에 키 추가 → `manage_language_keys.py`로 동기화 → ko 번역 채움([TODO] 제거) →
  `check_language_keys.py` + `tests/test_view_translations.py` 통과.
- 언어 키 명명은 `[context]_[type]_[name]` (예: `port_btn_connect`). 임의 형식 금지.
- 테마 색·폰트는 QSS/매니저 경유 — 위젯 코드의 `setStyleSheet("color: #...")` 하드코딩 금지.
- 다크/라이트 양쪽 테마에서 확인하지 않은 색 변경은 완료가 아니다.

## 5. 커밋 규율

- **커밋은 자주**: 검증이 통과한 상태·규칙/문서 갱신은 그 즉시 커밋한다. 결정이 내려진 산출물을
  미커밋 상태로 워킹트리에 방치하지 않는다.
- 커밋은 pathspec으로 범위를 좁힌다(`git commit <경로...>`), 신규 파일만 좁은 `git add` 선행.
- 커밋 메시지는 한국어, `Feat:/Fix:/Docs:/Refactor:/Style:/Test:/Rule:` 접두어 + 명령형 제목 1줄.
  본문에는 **왜**를 쓴다 (무엇은 diff가 말한다). 상세: `.agent/rules/git_guide.md`.
- 비밀정보(포트 캡처에 섞인 계정·키 포함) 커밋 금지. `logs/`, `__pycache__/`, `.venv/`는 커밋하지 않는다.

## 6. 대화 로깅 규약 (Chat History)

- 일자별 로그: `chatlog/chat_SerialTool_YY-MM-DD.md` (`:`는 Windows 파일명 불가라 `-` 사용).
- 훅이 자동 처리(`.claude/settings.json`): SessionStart→파일 생성(+날짜 롤오버 시 전일 마지막
  USER 턴 복사), UserPromptSubmit→USER 턴 기록, Stop→AGENT 최종 응답 기록.
- **읽기는 반드시 tail**: `python tools\chatlog.py tail [--lines N]`. 전체 파일 읽기는 사용자가
  "복기"를 명시 요청할 때만.
- 수동 기록(훅 미동작/보충 시): `python tools\chatlog.py append --role AGENT --text "..."`.
- 훅 미설정/미동작 시 자동 기록된다고 가정하지 않는다.

## 7. UX 판정 규율 (2026-08-22, 사용자 지시)

- UI/UX 점검·완료 판정은 **코드 정독만으로 하지 않는다 — 실행해서 본다.**
  offscreen 플랫폼은 폰트를 렌더하지 않아 텍스트 잘림·번역 노출을 잡지 못하므로,
  네이티브 플랫폼에서 창을 띄워 `widget.grab()`으로 스크린샷을 캡처해 판정한다
  (도구: `python tools\ux_capture.py --theme dark --lang ko --out <dir>` —
  테마 2 × 언어 2 × 창 크기 2 = 8조합, minimumSizeHint 회귀 감시 포함).
- 스크린샷 판정과 정적 코드 검토는 상호 보완이다: 스크린샷이 증상을, 코드가 원인을 준다.
  UI 결함 보고는 가능하면 둘을 짝지어 기록한다.

## 8. 모델 선택 전략 (Model Selection)

| 작업 유형 | 모델 | 예 |
|---|---|---|
| 단순 수행 | **하위 모델 (Sonnet)** | `tasks/` Steps에 명시된 코드 작성, 문서 작성, 테스트 실행, 점검·산출물 기록 |
| 계획·판단·점검·보완 | **상위 모델** | 계획 수립/개정, **`tasks/` Task 작성·개정**, Task 결과 리뷰, 설계 결정, 점검 결과 트리아지 |

- **Task 작성은 반드시 상위 모델이 한다.** 하위 모델이 전체 프로젝트 파악 없이 Steps만 따라
  진행할 수 있는 수준(자족적 배경, 정확한 경로:라인, 검증 가능한 Acceptance criteria)으로 작성한다.
- **Task의 전제(현재 코드 구조·키 방향·배치)는 추정하지 않고 작성 시점에 코드로 확인한다**
  (2026-08-22 규칙화 — S-030 마이그레이션 방향·S-032 PortStats 배치 전제 오류 2회 반복,
  doc/mistakes.md #4). 하위 모델의 Step 1은 가능하면 "전제 재확인 + 불일치 시 중단"으로 시작한다.
- **부분 확인은 확인이 아니다.** Task에 수치·값을 N개 적으면 **N개 모두 코드에서 읽는다.**
  한 건에서 본 패턴을 나머지에 일반화해 채우지 않는다 (2026-08-22 추가 — S-063에서 accent만
  QSS로 확인하고 danger/warning을 추정해 실재하지 않는 색 조합을 근거로 제시, mistakes.md #9).
  전수 확인이 부담스러우면 **수치를 적지 말고** "해당 셀렉터 전부를 계산해 확인하라"고 지시한다 —
  틀린 수치는 없는 수치보다 나쁘다.
- 하위 모델은 태스크 파일의 `Recommended model`을 따르고, 상위 전용 태스크를 시작하지 않는다.
- 하위 모델이 같은 오류를 2회 반복하거나 **Task 파일 밖의 재량 판단이 필요해지면 에스컬레이션**:
  현재 상태를 보고하고 상위 모델 검토를 요청한다.

## 9. 기존 확립 규칙 (요약)

- 확인되지 않은 동작은 추정으로 채우지 않는다 — 명시적 실패/미완료로 보고.
- Task 완료 = 검증 규율(§2) 충족 + `Task.MD` 상태 갱신 + 커밋 (`.claude/skills/task-done` 절차).
- `doc/task.md`는 이력 문서다 — 체크 추가만 하고 과거 항목을 재구성하지 않는다.
- 처리량·성능 수치는 자동 벤치마크 도입 전까지 문서에 보장 수치로 적지 않는다 (README §1.4).
