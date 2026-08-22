# UI 규칙 (가독성·일관성)

2026-08-20 전 페이지 감사(`tools/ui_audit.py`, 다크/라이트 × 한글/영문 ×
기본/최소 창 = 8조합 × 12페이지) 결과로 정한 규칙이다. **`tests/unit/
test_ui_guidelines.py`가 이 규칙을 기계적으로 강제**한다 — 규칙을 어기면 테스트가
실패한다. 새 화면을 만들 때 이 문서를 먼저 읽는다.

## 1. 색과 대비

| 대상 | 최소 대비비 | 근거 |
|---|---|---|
| 본문 텍스트 (라벨·버튼·체크박스) | **4.5:1** | WCAG AA |
| 큰 글씨(24px+ 또는 굵은 18.7px+) | **3.0:1** | WCAG AA Large |
| 비활성(disabled) 텍스트 | **3.0:1** | "흐리게"는 읽히는 범위에서 |

- 색상값을 페이지에 직접 쓰지 않는다. `ui/theme.py`가 색의 집이다 —
  objectName 규약(`pageTitle`/`pageBody`/`badgeOk`/`badgeWarn`/`errorLine`/
  `bigValue`), 직접 칠해야 할 때는 `palette(theme)`, 자체 그리기 위젯은
  `STEP_PALETTES`/`CHART_PALETTES`, 판정 색은 `RESULT_COLORS`를 쓴다.
  `test_colors_live_in_the_theme_module`이 화면/위젯의 색 리터럴을 막는다
  (예외: `ui/menu_style.py` — 값이 PyDracula 템플릿의 색·치수에서 온다).
- **상태색·계열색은 테마별로 값이 다르다.** 다크에서 잘 보이는 형광 계열
  (`#6fe08c` 등)은 밝은 배경에서 대비 1.5까지 떨어진다. 새 색이 필요하면
  팔레트에 다크/라이트 쌍으로 추가한다 (`SERIES_*_COLOR`도 테마별 함수 경유).
- 정보를 색으로만 전달하지 않는다 (PASS/FAIL은 문구도 함께).

## 2. 여백과 간격

- 페이지 최상위 레이아웃 여백: **`UI_PAGE_MARGIN`(24px)**. Qt 기본값(9px)을
  그대로 두지 않는다. **페이지마다 다른 값을 쓰지 않는다** - 여백이 다르면
  화면을 옮길 때마다 제목이 그만큼 튄다 (사용자 지적 2026-08-21, 24/40 혼용).
- 제목(`objectName="pageTitle"`)의 줄 높이는 theme.py가 `min-height`
  (`UI_TITLE_ROW_H`)로 고정한다. 제목 옆에 버튼이 있는 페이지만 줄이 높아져
  제목 글자가 내려앉는 것을 막는다. 페이지에서 제목 높이를 따로 정하지 않는다.
  `tests/unit/test_ui_guidelines.py::test_page_titles_sit_at_the_same_place`가
  전 페이지의 제목 위치·높이를 고정한다.
- 위젯 간 간격: **`UI_GAP`(12px)** 기준, 논리 그룹 사이는 `UI_GAP_LARGE`(20px).
- 값은 `constants.py`에서 가져온다 (매직 넘버 금지 - CLAUDE.md). 간격은
  사다리에서 고른다: `UI_GAP_TIGHT`(6) / `UI_GAP_SMALL`(8) / `UI_GAP`(12) /
  `UI_GAP_INLINE`(16) / `UI_GAP_LARGE`(20) / `UI_GAP_SECTION`(28).
  `test_pages_do_not_hardcode_layout_numbers`가 위젯 API에 직접 쓴 숫자를 막는다.
- 페이지 골격은 `scrollable_page(self)` 하나로 만든다 - 여백·간격이 같아지고
  좁은 창에서 눌리는 대신 스크롤한다.
- 래퍼 페이지(자식 하나에 위임)는 안쪽 위젯이 여백을 가지면 된다.

## 3. 텍스트 잘림 금지

- 라벨·버튼은 **표시 문구가 잘리지 않아야 한다** (`sizeHint > 실제 크기` 금지).
  한글 → 영문 전환에서 문구가 길어지는 것을 항상 가정한다.
- 긴 문구(경로·설명·통계·제목)는 다음 중 하나를 쓴다 (공용 구현이 있다):
  1. `widgets.labels.enable_wrap(label)` — 설명문. `setWordWrap(True)`만 하면
     minimumSizeHint가 **한 줄 기준**이라 두 줄로 늘어난 만큼 아래 위젯을
     침범한다(실측). 이 헬퍼는 heightForWidth를 켜 실제 높이를 예약한다.
  2. `widgets.labels.ElidedLabel` — 경로·통계·제목. 폭에 맞춰 말줄임하고
     **원문은 툴팁**으로 남는다. 값 비교/테스트는 `full_text()`로 한다
     (`text()`는 말줄임된 표시 문구다).
  3. `widgets.layout.scrollable_page(page)` — 내용이 많은 페이지. 세로는
     스크롤, 가로는 넘칠 때만 스크롤(잘라내지 않는다).
- 확장(Expanding) 라벨과 같은 줄의 버튼은 `labels.lock_text_width(button)`으로
  글자 폭을 최소 폭으로 고정한다 (레이아웃이 버튼까지 줄여 글자가 잘렸다).
- 고정 폭 슬롯(예: 시리얼 미리보기)은 상한을 두고 그 아래로는 말줄임한다 —
  고정 폭이 옆 위젯을 밀어 겹치게 만들면 안 된다.
- 버튼 높이는 `UI_BUTTON_MIN_H`(32px) 이상을 보장한다 (좁은 창에서 세로 압축
  금지 - 실측 27px로 눌려 글자가 잘렸다).
- 숫자 강조(`bigValue`)는 폰트 크기에 맞는 최소 높이를 확보한다.

### 글자 크기는 한 곳에서만 (인라인 `font-size` 금지)

- 페이지/위젯에서 `setStyleSheet("font-size: ...")`를 쓰지 않는다. 크기는
  `theme.control_style()`의 objectName 규칙으로만 정한다:
  `pageTitle`(제목, `UI_TITLE_PX`) / `pageAccent`(제목 색·본문 크기 강조 슬롯) /
  `pageBody`(본문, `UI_BODY_PX`) / `pageNote`(주석, `UI_NOTE_PX`) /
  `counterValue`·`bigValue`(숫자 강조).
- 이유(실측 2026-08-20, 사용자 지적): 페이지마다 인라인으로 지정하다 보니
  같은 제목이 프로비저닝/설정은 24px, 모니터/기록/파워는 18px로 갈렸다.
  `tests/unit/test_ui_guidelines.py::test_pages_do_not_set_font_size_inline`이
  재발을 막는다.
- **글꼴 선택은 레이아웃을 바꾼다.** 설정에서 고른 글꼴의 줄 높이가 크면 모든
  컴포넌트가 커진다 (실측: `Sans Serif Collection` 13pt는 줄 높이 46px로
  `Segoe UI` 12pt(21px)의 2배 이상 - 같은 화면에서 감사 위반 0건이 90건이
  되었다). 감사·스크린샷 비교는 **같은 글꼴 설정**에서 해야 한다.

## 4. 반응형 (최소 창 크기)

- 기준 창 크기는 **실제 값**을 쓴다: 시작 `UI_DEFAULT_WINDOW`(1280×720),
  최소 `UI_MIN_WINDOW`(940×560) — PyDracula 템플릿의 `resize`/`setMinimumSize`와
  일치하며 테스트가 이를 고정한다. 두 크기 모두에서 잘림·겹침이 없어야 한다.
  (임의 크기로 확인하면 세로 압축을 과소평가한다 — 실측 사고 2026-08-20)
- 절대 좌표 배치(`move()`)는 차트 위 배지 같은 **의도적 오버레이**에만
  허용하고, objectName을 `recBadge`/`chartOverlay` 규약으로 둔다
  (감사 예외 목록과 일치).
- 그림(구성도 등)은 `Qt.KeepAspectRatio`로 컨테이너에 맞춰 축소한다.
  고정 픽셀 그림을 그대로 넣지 않는다.

## 5. 다국어 (한글/영문)

- **사용자에게 보이는 모든 문구는 `i18n.tr(key)` 경유**. 페이지에 한글
  리터럴을 두지 않는다 (그림 속 글자 포함 - 그림은 언어별 파일 또는 라벨로).
- 페이지는 `retranslate()`를 구현하고, 셸의 `retranslate()` 목록에 등록한다.
- 키 규약: `page.<페이지>.<요소>`, `widget.<위젯>.<요소>`, `common.<공통어>`.
- ko/en 사전(`resources/lang/*.json`)에 **양쪽 모두** 값을 넣는다.

## 6. 테마 전환

- 테마 변경은 **셸 QSS(`ThemeManager.apply`) + 페이지 팔레트
  (`_apply_page_themes`)를 함께** 적용해야 한다. 한쪽만 바꾸면 어두운 배경에
  어두운 글자가 남는다.
- 커스텀 페인팅 위젯(`TrendChart`, `StepIndicator` 등)은 `set_theme(theme)`를
  구현하고 셸의 `_themed_pages` 경로에서 호출되게 한다.
- 애니메이션(좌측 패널 여닫기) 중에는 위젯 좌표와 그려진 픽셀이 어긋난다.
  캡처·검증은 애니메이션이 끝난 뒤에 한다.

## 7. 커스텀 페인팅 위젯

감사 도구가 픽셀로 검사하지 못하므로 직접 지킨다:

- 축·범례·스텝 라벨도 §1 대비 기준을 따르고 **언어도 따른다**
  (`TrendChart.retranslate_series(labels, x_title=, y_title=)`).
  계열색은 라이트 테마에서 `LIGHT_DARKEN` 비율로 어둡게 해 대비를 만족시킨다.
- 라벨이 위젯 경계를 넘지 않게 그린다 (첫/마지막 스텝 라벨은 안쪽 정렬).
- 회전 텍스트(세로 축 제목)는 폭을 확보해 글자가 겹치지 않게 한다.

## 8. 상태 기억 (무엇을 기억하고 무엇을 기억하지 않는가)

위젯 상태를 재시작 후에도 유지할지는 취향이 아니라 **안전·정합성 판단**이다.
새 상태를 추가할 때 아래 셋 중 어디인지 먼저 정한다 (사용자 지시 2026-08-21).

| 분류 | 예 | 처리 |
|---|---|---|
| **기억한다** | 언어·테마·글꼴, 장비 드라이버, 포트 선택, CLI 경로, 메뉴별 마지막 서브 메뉴 | `ui_settings.json` (SettingsStore) |
| **기억할 필요 없다** | 표 선택 행, 차트 확대/스크롤, 통신 기록 | 저장하지 않음 (세션 내 상태) |
| **기억해서는 안 된다** | 프로비저닝 진행(시리얼 확정·준비 체크·점검 결과), 로깅 진행·경과, 보드 모니터 자동 갱신, 장비 연결 상태 | 저장 금지 - 항상 초기값으로 시작 |

- 포트는 **"무엇을 쓸지"만** 기억하고 **"연결됨"은** 기억하지 않는다.
- **작업자 이름은 저장하지 않는다** (T-018). 저장하면 "마지막 사람"이
  기본값이 되어, 다른 사람이 작업해도 앞사람 이름이 기록에 남는다.
  대신 PC 로그인 계정을 **흐리게 제시**하고 비워 두면 그 값이 쓰인다 -
  별도 기입을 요구하지 않으면서 기록의 '누가'도 비지 않는다.
- 프로비저닝은 서브 메뉴 위치도 기억하지 않는다 - 재시작하면 보드도 장비
  상태도 알 수 없으므로 시리얼부터 다시 시작해야 한다.
- 저장 대상 목록은 `test_persisted_fields_are_the_agreed_list`가 고정한다.
  새 필드를 넣으면 그 테스트가 실패하며 위 분류를 다시 보게 한다.

## 9. 검증 절차 (변경 전후 필수)

```
$env:PYTHONPATH="src"; .venv\Scripts\python tools/ui_audit.py --json out.json --shots shots
.venv\Scripts\python -m pytest tests/unit/test_ui_guidelines.py
```

- 감사 도구는 **실행 진입점과 같은 환경**(`QT_FONT_DPI=96`)에서 실사용 크기로
  돌린다. 캡처 픽셀은 화면 배율(DPR)만큼 커지므로 좌표를 보정해 샘플링한다.
- 대비는 화면 픽셀에서 **명도 차이가 가장 큰 색**을 글자색으로 본다
  (색상 거리로 고르면 서브픽셀 안티에일리어싱의 색 프린지를 글자로 오인한다).

- 감사는 위반을 종류별(`contrast`/`clipped`/`hclip`/`overlap`/`outside`/
  `margin`/`untranslated`)로 보고한다. **신규 위반 0**이 통과 조건이다.
- 언어 선택 콤보(`objectName="languageCombo"`)는 각 언어 이름을 그대로 쓰는
  것이 관례라 번역 검사에서 제외한다.
- 픽셀 좌표를 다루는 변경은 실제 배율(125% 등) 화면 캡처로도 확인한다
  (`docs/mistakes.md` DPR 사고 참조).
