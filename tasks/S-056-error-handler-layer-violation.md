# S-056 — 크래시 다이얼로그 번역이 만든 계층 역전 정리

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능** (설계 확정)
- 선행: S-036 (도입 경위)
- Skills to load: task-done

## 목적 (Why) — S-036이 스스로 보고한 긴장

S-036에서 크래시 다이얼로그를 언어 키 경유로 바꾸면서 `core/error_handler.py`가
`view.managers.language_manager`를 **지연 import + try/except**로 참조하게 됐다.

이는 CLAUDE.md 절대 규칙 **의존 방향 `View → Presenter → Model → Core ← Common`**과
어긋난다(Core가 View를 안다). 감사①에서 "core/가 상위 계층을 import: 위반 0건"이었던
것이 이 변경으로 1건이 됐다. 수행자가 지시받은 위치대로 구현하면서 이 사실을 정확히
보고했으므로, 상위가 구조로 정리한다.

## 확정 설계 — 메시지 주입 방식

Core가 번역을 **모르게** 하되 번역된 문구는 그대로 쓴다:

1. `core/error_handler.py`의 전역 핸들러가 표시할 문구를 **외부에서 주입**받는다.
   - 예: `install_global_error_handler(title: str = ..., message_template: str = ...)`
     또는 문구를 돌려주는 콜백(`Callable[[], tuple[str, str]]`)을 받는다.
     **콜백 방식이 낫다** — 앱 실행 중 언어를 바꾸면 다음 크래시부터 새 언어가 반영된다.
     둘 중 택해 근거를 보고하라.
   - 인자를 주지 않으면 **현재의 영어 하드코딩이 기본값**으로 남아야 한다(손상된 상태·
     테스트·라이브러리 사용 시 안전).
2. `main.py`가 조립 지점이므로 **거기서 주입**한다. `main.py`는 이미 LanguageManager를
   초기화하므로(`설정 → Language/Theme/Color → MainWindow → MainPresenter` 순서),
   그 뒤에 핸들러를 재설치하거나 주입하면 된다. **현재 `install_global_error_handler()`가
   LanguageManager 초기화보다 먼저 호출되는지 확인**하고, 순서 문제가 있으면 주입 시점을
   조정하라(핸들러 설치 자체는 가능한 이르게 두는 것이 좋다 — 초기화 중 크래시도 잡아야 한다).
3. `core/error_handler.py`에서 `view.*` import를 **완전히 제거**한다.
4. S-036이 넣은 언어 키(`error_title_critical`, `error_msg_unexpected`)는 그대로 쓰되,
   키를 읽는 주체가 View/조립 계층이 되도록 옮긴다.

## 검증 방법

- **계층 검사**: `core/`에 `view`/`presenter`/`model` import가 0건임을 확인하는 테스트를
  `tests/test_ui_guidelines.py`(또는 신규)에 추가한다 — 감사①이 수동으로 확인했던 것을
  **기계적으로 고정**한다. 4방향(View→Model 금지 등) 전부를 검사하면 더 좋다.
- 크래시 다이얼로그가 여전히 번역되는지 실측(언어 ko/en 각각), 주입 없이 호출했을 때
  영어 폴백이 나오는지 실측.
- 전체 pytest(offscreen, 기준선 317) + ruff 클린.

## Acceptance criteria (DoD)

- [ ] `core/`에서 상위 계층 import 0건, 이를 고정하는 테스트 존재.
- [ ] 크래시 다이얼로그가 ko/en 모두 번역되고, 주입 없으면 영어 폴백.
- [ ] 초기화 중 크래시도 여전히 잡힌다(설치 시점 확인 보고).
- [ ] 전체 pytest 통과.
