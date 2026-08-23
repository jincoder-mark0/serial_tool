---
trigger: always_on
---

# SerialTool UI 가이드 (가독성·일관성·다국어·테마)

UI를 새로 만들거나 고칠 때 지키는 규칙이다. 원자료는 타 프로젝트에서 실측으로 얻은
규칙집(`doc/ui-guidelines.md` — 참조 전용, 그쪽 코드 구조 기준이라 그대로 쓰지 않는다)이며,
이 문서가 **SerialTool의 구조에 맞춘 정본**이다. 2026-08-22 UX 전면 점검
(`doc/ux_audit_20260822.md`, 결함 35건)에서 실제로 깨졌던 항목이 근거다.
기계적 강제는 `tests/test_ui_guidelines.py`가 담당한다 — 어기면 테스트가 실패한다.

## 1. 색과 대비

| 대상 | 최소 대비비 | 근거 |
|---|---|---|
| 본문 텍스트 (라벨·버튼·체크박스) | **4.5:1** | WCAG AA |
| 큰 글씨 (24px+ 또는 굵은 18.7px+) | **3.0:1** | WCAG AA Large |
| 비활성(disabled) 텍스트 | **3.0:1** | "흐리게"는 읽히는 범위에서 |

- **위젯 코드에 색 리터럴(`#...`, `rgb(`, `color: red` 등)을 쓰지 않는다.**
  색은 3테마 QSS(`resources/themes/{dark,light,dracula}_theme.qss`)가 정한다.
  상태에 따라 색이 바뀌는 위젯은 **동적 속성 방식**을 쓴다:
  `setProperty("state", "...")` + `style().unpolish/polish()` → QSS `[state="..."]` 규칙
  (실례: REC 표시, 포트 연결 ●/○, danger 프로그레스바 — S-022).
- 로그 강조색은 `resources/configs/color_rules.json` + `ColorManager` 경유
  (다크/라이트 쌍으로 정의 — 다크에서 좋은 색이 라이트에서 대비 1점대로 떨어진다).
- 새 색을 넣을 때는 대비를 **계산으로 확인**한다 (검증 스크립트:
  `tasks/S-022-theme-contrast-hardcoded-colors.md`의 relative luminance 계산식).
- 정보를 색으로만 전달하지 않는다 (연결 상태는 ●/○ 기호+색, PASS/FAIL은 문구도 함께).
- 상태 셀렉터 커버리지: 상호작용 위젯의 QSS에 `:disabled`·`:hover`를 3테마 동일 패턴으로 갖춘다.

## 2. 여백·간격·크기

- 수치는 `common/constants.py`의 상수에서 고른다 — 매직 넘버 금지:
  `LAYOUT_MARGIN_NONE`(0) / `LAYOUT_MARGIN_DEFAULT`(5) / `LAYOUT_MARGIN_DIALOG`(15),
  `LAYOUT_SPACING_TIGHT`(2) / `LAYOUT_SPACING_DEFAULT`(5), `ICON_BUTTON_SIZE`(30).
  사다리에 없는 값이 정말 필요하면 상수를 추가하거나, 리터럴에 **사유 주석**을 남긴다.
- 아이콘형 소형 버튼은 `ICON_BUTTON_SIZE` 정사각형으로 통일한다.
- 같은 성격의 형제 위젯(예: 두 로그 뷰의 툴바)은 같은 stretch/spacing 규칙을 쓴다.

## 3. 텍스트 잘림 금지

- **`setFixedWidth/Height/Size`를 텍스트가 있는 컨트롤에 쓰지 않는다** —
  `setMinimum*`으로 하한만 주고 폭·높이는 Qt sizeHint에 맡긴다.
  이유(실측 S-024): 고정 크기는 ko 폰트 메트릭 기준이 되기 쉬워
  ① 영문 전환("검색"→"Scan", "반복 시작"→"Start Repeat")에서 잘리고
  ② 런타임 텍스트 변경(Connect→Reconnect)과 ③ 폰트 확대 설정(6~24pt)에 못 따라간다.
- 한글 → 영문 전환에서 문구가 길어지는 것을 항상 가정한다.
- 숫자 입력란 폭은 폰트 메트릭 기반으로 계산한다
  (`fontMetrics().horizontalAdvance("00000") + 여백` — 실측: 16pt에서 "1000"이 ")00"으로 잘림).
- 긴 문구(경로·설명)는 말줄임(elide)+툴팁 또는 word wrap으로 처리하고,
  고정 폭이 옆 위젯을 밀어 겹치게 하지 않는다.
- **인라인 `font-size` 금지**: 위젯 코드의 `setStyleSheet("font-size: ...")`를 쓰지 않는다.
  글자 크기 위계는 QSS 클래스(`section-title` 등)로만 정한다 — 페이지마다 크기가 갈린다.
- 폰트 설정이 레이아웃을 바꾼다: 크기 관련 변경은 기본 폰트와 확대 폰트(16pt) 양쪽에서 확인한다.

## 4. 반응형 (최소 창 크기)

- 창 최소 크기는 **실측으로 감시**한다: `tools/ux_capture.py`가 출력하는
  `minimumSizeHint`를 변경 전후로 비교하고, 키우는 변경은 사유를 보고한다.
  (확정 실측 2026-08-23, S-068 후 최신: **ko 1274×791 / en 1213×791** — 이 값이 회귀 기준선.
  이력: S-026/S-032 직후 780 → S-035의 간격 확보로 +11(높이) →
  **S-068에서 우측 패널 최소 폭 580px을 지정하며 폭이 크게 늘었다**(ko 1093→1274,
  en 1097→1213). 매크로 표의 6개 ResizeToContents 컬럼이 요구하는 폭이라 임의로
  줄일 수 없다 — 줄이려면 컬럼 리사이즈 정책을 손대야 한다(사용자 판단 대기).
  **최소 크기를 바꾸는 변경은 이 줄을 함께 갱신한다** — 갱신을 빠뜨리면 다음 작업자가
  실측치를 회귀로 오인한다(2026-08-22 실제 발생, doc/mistakes.md #5).
  높이 730 목표는 구조 재설계 없이는 불가로 보류 판정 — 실사용 문제 보고 시 재개.)
- 툴바·행 레이아웃에는 줄어들 수 있는 위젯(stretch 또는 elide 가능 요소)을 둔다 —
  전 컨트롤이 고정/최소 폭이면 stretch가 0으로 수렴해 하한 없는 위젯이 짓눌린다
  (실측: RX 로그 검색창 35px).

## 5. 다국어 (한글/영문)

- **사용자에게 보이는 모든 문구는 언어 키 경유** (`language_manager.get_text(key)`).
  위젯 코드에 한글·영문 리터럴 금지 — Presenter의 상태 메시지·다이얼로그 문구도 포함.
- 키 규칙: `[context]_[type]_[name]` (예: `port_btn_connect`, `manual_control_chk_auto_tx`).
- 절차는 `.claude/skills/lang-keys` 스킬: en.json 먼저 → `tools/manage_language_keys.py`
  동기화 → ko 번역([TODO] 제거) → `tools/check_language_keys.py` 통과.
- 위젯은 `retranslate_ui()`를 구현하고 `language_changed` 경로에 연결한다 —
  생성자에서만 텍스트를 설정하면 언어 전환 시 이전 문구가 남는다.
  **f-string으로 매번 조립하는 라벨(상태바 등)은 값을 캐시**해 retranslate에서 재렌더한다 (S-021 패턴).
- 용어는 화면 간 통일한다 (예: "명령"(Command), "패킷 분석기", "브로드캐스트" —
  같은 개념에 새 번역을 만들기 전에 기존 키를 검색).

## 6. 테마 전환

- 테마 전환의 완전한 경로는 `main_window.switch_theme()`다 — QSS 적용 + ColorManager +
  메뉴 동기화 + 테마 의존 아이콘 재생성(`update_plus_tab_icon` 등)을 함께 수행한다.
  테마에 따라 다시 그려야 하는 요소를 새로 만들면 이 경로에 등록한다.
- 아이콘은 `ThemeManager.get_icon()` 경유 (테마별 디렉터리 라우팅 — dark/light/dracula).
- 다크/라이트 양쪽에서 확인하지 않은 색 변경은 완료가 아니다 (dracula는 dark 계열로 함께 확인).

## 7. 상태 기억 (무엇을 저장하는가)

새 위젯 상태를 저장할지는 취향이 아니라 정합성 판단이다. 셋 중 어디인지 먼저 정한다:

| 분류 | 예 (SerialTool 현행) | 처리 |
|---|---|---|
| **기억한다** | 테마·언어·폰트, 창 지오메트리·스플리터, 포트 설정 탭, 매크로 목록·반복 옵션, 수동 제어 옵션(prefix/suffix/auto_tx interval), 명령 히스토리 | `SettingsManager` (ConfigKeys 등록 필수) |
| **기억할 필요 없다** | 로그 스크롤 위치, 검색어, 표 선택 행 | 저장하지 않음 (세션 내) |
| **기억해서는 안 된다** | 포트 "연결됨" 상태, 로깅 진행 중, 파일 전송 진행, 매크로 실행 중 | 저장 금지 — 항상 초기값으로 시작 |

- 포트는 **"무엇을 쓸지"만** 기억하고 **"연결됨"은** 기억하지 않는다.
- 새 저장 필드는 DTO(`common/dtos.py`) + `get_state()/apply_state()` +
  presenter 직렬화 배선까지 한 세트다 (S-006 auto_tx 패턴 참고).

## 8. 검증 절차 (UI 변경 전후 필수 — RULES.md §7)

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\check_language_keys.py
# 실행 화면 실측 (offscreen은 폰트 미렌더 — 판정 불가):
foreach ($t in 'dark','light') { foreach ($l in 'ko','en') {
  .venv\Scripts\python tools\ux_capture.py --theme $t --lang $l --out <스크래치패드>\shots } }
git checkout -- resources/configs/settings.json   # 캡처의 지오메트리 저장 부작용 원복
```

- 캡처 PNG를 눈으로 판정한다: 잘림·겹침·키 원문 노출·테마 잔존 조각·minimumSizeHint 변화.
- 코드 정독은 원인을, 스크린샷은 증상을 준다 — UI 결함 보고는 둘을 짝지어 기록한다.
