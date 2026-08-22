# SerialTool — 프로젝트 규칙

PyQt5 기반 멀티포트 시리얼 통신 유틸리티. **Strict MVP** + **EventBus** + **Fast Path** 아키텍처.
현재 상태: 핵심 기능(멀티포트/매크로/파일 전송/로깅/테마/다국어) 구현 완료,
테스트 기준선 **130개 통과**. PyInstaller 패키징·CI·AutoTx·벤치마크 도입 완료,
SPI/I2C Transport·플러그인은 미착수 (Task.MD 참조).

## 실행·검증 명령

```
.venv\Scripts\python main.py                                  # GUI 실행
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q   # 전체 테스트 (GUI 불필요)
.venv\Scripts\python -m pytest tests/test_model.py            # 부분 테스트
.venv\Scripts\python tools\check_language_keys.py             # 언어 키 무결성 검사 (en↔ko, [TODO] 스캔)
```

- Python 3.10+, 의존성: PyQt5, pyserial, commentjson, jsonschema (`requirements.txt`).
- 테스트는 실제 시리얼 장비 없이 전부 실행 가능 (Mock Transport / offscreen).

작업 현황은 **[Task.MD](Task.MD)** (작업 보드) + **`tasks/S-0xx-*.md`** (세부 절차 —
하위 모델용 자족적 문서, 시작 방법은 `tasks/README.md`)로 관리한다.
태스크 시작·완료 시 반드시 갱신한다. 모델 분담(상위=Task 작성·판단 / 하위=Steps 수행)은 RULES.md §8.
과거 Phase별 완료 체크리스트는 `doc/task.md`(이력 문서 — 추가만, 재구성 금지).

## 절대 규칙 (아키텍처 불변식)

- 의존성 방향: `View → Presenter → Model → Core ← Common`. 역방향 import 금지.
  - **View는 Model을 import하지 않는다** (Passive View — 시그널 emit + 인터페이스 메서드만).
  - **Model은 View/위젯을 모른다**. UI 갱신은 Presenter가 중재한다.
- 계층 간 데이터 전달은 `dict` 금지, `common/dtos.py`의 DTO만 사용.
- 상태·이벤트는 **EventBus**(`core/event_bus.py`) 경유. 예외는 단 하나 — 대량 RX 데이터의
  **Fast Path**(ConnectionController → MainPresenter 직접 시그널). 새 Fast Path를 임의로 늘리지 않는다.
- 수신 데이터의 UI 반영은 MainPresenter의 **30ms Throttling** 버퍼를 거친다. 위젯 직접 갱신 금지.
- 워커 스레드(ConnectionWorker/MacroRunner/FileTransferService)에서 위젯 직접 접근 금지 —
  Qt 시그널로만 UI 스레드에 전달.
- 설정 접근은 `SettingsManager`만 (JSON Schema 검증·마이그레이션 내장). 임의 파일 I/O로 설정을 읽고 쓰지 않는다.
- UI 문자열 하드코딩 금지 — `resources/languages/*.json` 키 경유, 키 형식은 `[context]_[type]_[name]`.
  키 추가·변경 시 en/ko 동기화(`tools/manage_language_keys.py`) 후 `tools/check_language_keys.py` 통과 필수.
- 전역 상수·이벤트 토픽·설정 키는 `common/constants.py` 단일 관리. 사용처에 매직 넘버 직접 쓰지 않는다.
- 색·스타일은 QSS 테마(`resources/themes/`)와 View 매니저(`view/managers/`) 경유. 위젯 코드에 색 리터럴 금지.

## 작업 방식

- 구현 전 가정을 한 줄로 밝히고 즉시 진행. 질문은 결과가 근본적으로 달라지고 되돌리기 어려운 경우만.
- 요구사항을 충족하는 최소 구현. 요청하지 않은 기능·추상화 금지.
- 기존 코드 수정 시 요청과 직접 관련된 줄만. 관련 없는 dead code는 삭제하지 말고 보고.
- 변경 후 가장 작은 관련 검증부터 실행하고, 실행한 명령·결과·Mock/실장 여부를 정확히 보고.
  검증 없이 "완료/정상 동작" 표현 금지. 실제 시리얼 포트 검증이 필요한 항목은 "실기기 미검증"으로 구분.
- 코딩 표준은 `.agent/rules/` 5종을 따른다: 코드 스타일(code_style_guide), 주석(comment_guide —
  Google Style Docstring + 모듈 헤더 WHY/WHAT/HOW), 명명(naming_convention_guide), Git(git_guide),
  **UI(ui_guide — 색·대비·잘림·다국어·테마·상태 저장, `tests/test_ui_guidelines.py`가 강제)**.
- 주석·Docstring은 한국어, 타입 힌트 필수.

## 자가 진화

- 실수/빌드 오류/규약 위반은 `doc/mistakes.md`에 기록: `YYYY-MM-DD | 증상 | 원인 | 일회성: 예/아니오 | 조치`.
- 동일 원인 2회 반복 시: ① 기계적 차단(테스트/도구/훅) → ② `.claude/skills/` 절차 갱신 → ③ CLAUDE.md·RULES.md 규칙 추가.
  규칙화 커밋 메시지는 `Rule: <무엇을 왜>`, 해당 mistakes 항목에 `→ 규칙화됨` 표시.
- 존재하지 않는 hook/자동화를 있는 것처럼 쓰지 않는다.

## 대화 로그 / Git

- 일자별 로그: `chatlog/chat_SerialTool_YY-MM-DD.md` — `.claude/settings.json` 훅이 자동 기록
  (SessionStart/UserPromptSubmit/Stop). 읽기는 `python tools\chatlog.py tail --lines 200`만
  (전체 읽기는 사용자가 복기 요청 시). 훅 미동작 시 수동: `python tools\chatlog.py append --role AGENT --text "..."`.
- 커밋 메시지는 **한국어**, 형식은 `Feat:/Fix:/Docs:/Refactor:/Style:/Test:/Rule:` 접두어 +
  명령형 제목 1줄, 필요 시 빈 줄 후 본문(왜를 쓴다 — 무엇은 diff가 말한다). 상세: `.agent/rules/git_guide.md`.
- 테스트 통과 구현/규칙 변경/설계 결정 단위로 pathspec 커밋(`git commit <경로...>`). 비밀정보 커밋 금지.
- 브랜치: `main`(안정) / `feature/기능명`(개발).
- 세션 종료 시 주요 변경은 `doc/CHANGELOG.md`에, 세션 기록은 `doc/history/session_summary_YYYYMMDD.md`에 남긴다.

## 문서 구조

| 문서 | 목적 |
|---|---|
| `README.md` | 사용자용 개요·설치·아키텍처 (기능 변경 시 현행화) |
| `Task.MD` | **작업 보드** (현재 상태·우선순위·잔여 작업) |
| `tasks/` | 태스크별 세부 절차 (하위 모델용 자족 문서, `tasks/README.md`부터) |
| `doc/00_overview.md` | 아키텍처·모듈 요약 |
| `doc/implementation_plan.md` | 단계별 구현 계획 |
| `doc/task.md` | Phase별 완료 체크리스트 (이력) |
| `doc/CHANGELOG.md` | 변경 이력 |
| `doc/mistakes.md` | 실수 대장 (자가 진화 §) |
| `doc/history/` | 세션별 작업 기록 |
| `tests/README.md` | 테스트 실행·해석 가이드 |
| `.agent/rules/` | 코드 스타일·주석·명명·Git·UI 가이드 (표준) |

## 구조 안내

- `common/` — 의존성 최하위: `constants.py`(상수·EventTopics·ConfigKeys), `dtos.py`, `enums.py`, `app_info.py`
- `core/` — 인프라: `event_bus.py`, `settings_manager.py`(+`settings_schema.py`), `logger.py`,
  `error_handler.py`, `data_logger.py`(Raw/Hex/Pcap), `structures.py`(RingBuffer 등),
  `command_processor.py`, `resource_path.py`, `transport/`(base + serial_transport)
- `model/` — 비즈니스 로직: `connection_controller.py`(Fast Path 기점), `connection_worker.py`(I/O QThread),
  `macro_runner.py`, `file_transfer_service.py`(Backpressure), `packet_parser.py`, `port_scanner.py`
- `presenter/` — 중재자: `main_presenter.py`(Throttling·Fast Path 수신), `lifecycle_manager.py`,
  `event_router.py`(EventBus→Qt Signal), port/macro/file/packet/manual_control presenter
- `view/` — Passive View: `main_window.py`, `panels/`, `sections/`, `widgets/`, `dialogs/`,
  `custom_qt/`, `managers/`(Theme/Language/Color), `services/`
- `resources/` — `languages/`(en/ko JSON), `themes/`(QSS), `icons/`(SVG), `configs/`(settings.json 기본값)
- `tools/` — `chatlog.py`(대화 로그), `check_language_keys.py`(CI 검사), `manage_language_keys.py`(키 동기화)
- 진입점: `main.py` (Manager 초기화 순서가 곧 조립 순서 — Settings → Language/Theme/Color → MainWindow → MainPresenter)
