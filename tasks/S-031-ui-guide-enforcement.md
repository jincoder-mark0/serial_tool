# S-031 — UI 가이드 기계적 강제 테스트 + 잔여 위반 정리

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 정적 스캔 테스트 4종 신설,
  스캔 위반 4그룹 전부 실수정(허용 목록 0건): about_dialog 인라인 font-size→QSS 클래스,
  theme_manager 폴백 QSS 한글 주석 11건 영문화, 폰트 미리보기 팬그램→언어 키,
  system_log 죽은 statement 삭제. 색 리터럴 위반 0건 확인(S-022 완전성 검증).
  테스트 +4 → 기준선 122. 캡처 4조합 회귀 없음)
- Recommended model: **하위(Sonnet) 가능**
- 선행: `.agent/rules/ui_guide.md` (2026-08-22 제정 — 이 태스크의 근거 문서)
- Skills to load: task-done

## 목적 (Why)

UI 가이드(`.agent/rules/ui_guide.md`)가 문서로만 있으면 어긴 코드가 조용히 늘어난다.
원자료(`doc/ui-guidelines.md`)의 핵심 설계가 "테스트가 기계적으로 강제한다"였다 —
SerialTool 판 강제 테스트를 만들고, 그 테스트가 잡아내는 현행 잔여 위반을 정리한다.

## Steps

1. **신규 `tests/test_ui_guidelines.py`** — 소스 정적 스캔 테스트 4종
   (Qt 실행 불필요 — 파일 텍스트/토큰 검사. `pathlib`로 `view/`·`presenter/` `.py` 순회):
   a. `test_no_color_literals_in_widget_code`: `setStyleSheet(` 호출 안에 색 리터럴
      (`#[0-9a-fA-F]{3,8}`, `rgb(`, `color: <이름>`)이 없는지. 위반 발견 시 파일:라인 목록을
      assert 메시지로 출력. **허용 목록**(파일 경로+사유 dict)을 테스트 상단에 두되,
      시작 시점 허용 목록은 비어 있는 것이 목표 — 스캔에서 나오는 위반은 아래 3단계에서
      실제로 고친 뒤 목록을 비운다 (도저히 못 고치는 것만 사유와 함께 등재).
   b. `test_no_inline_font_size`: `setStyleSheet` 안 `font-size` 금지 (동일 허용 목록 구조).
   c. `test_no_hardcoded_korean_in_code`: `view/`·`presenter/`의 **문자열 리터럴**에 한글 금지 —
      `tokenize` 모듈로 STRING 토큰만 검사해 주석·docstring은 제외한다.
      (허용: 언어 JSON 경로가 아닌 로그 메시지? — 아니다, logger 메시지는 영어가 관례.
      위반이 나오면 언어 키로 전환하거나 사유 등재.)
   d. `test_layout_constants_exist`: `common.constants`에 LAYOUT_* 6종 + ICON_BUTTON_SIZE가
      존재하고 값이 가이드 표와 일치하는지 (상수 무단 삭제·변경 감지).
2. 테스트를 먼저 실행해 **현행 위반 전수 목록**을 얻는다 (이 목록이 3단계의 작업 목록).
3. 위반 정리 (알려진 것 + 스캔 결과):
   - `view/dialogs/about_dialog.py` — S-022가 남긴 인라인 `font-size` → 3테마 QSS 클래스로 이전.
   - 스캔이 찾은 나머지 색/폰트/한글 리터럴 — 가이드 방식(QSS 동적 속성·언어 키)으로 전환.
     **수정이 큰 판단을 요구하면(구조 변경 등) 고치지 말고 허용 목록에 사유와 함께 등재 후 보고.**
4. 검증: 전체 pytest(offscreen, 기준선 118+신규 4) + `tools/check_language_keys.py`
   (언어 키를 추가했다면) + 캡처 4조합(dark/light × ko/en) 회귀 확인 —
   `.venv\Scripts\python tools\ux_capture.py ...` 후
   `git checkout -- resources/configs/settings.json`.

## Acceptance criteria (DoD)

- [ ] 강제 테스트 4종이 존재하고 통과한다 (허용 목록 항목은 각각 사유 명기).
- [ ] about_dialog 인라인 font-size 제거, 스캔 발견 위반은 수정 또는 사유 등재.
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
