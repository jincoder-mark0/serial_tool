# S-079 — 남은 화면 훑기 (매크로 패널 상세 / 포트 탭 다중 상태)

- Status: DONE (2026-08-23 — 상위 직접 수행. 결함 4건 수정, 테스트 12개 추가.
  pytest 509 passed, ruff 0건, 언어 키 OK, 보드 73건 일치)
- Recommended model: **상위 전용** (실행 화면 판단이 필요 — RULES §7)
- 선행: S-077 (테마 통일), S-078 (색 팔레트 이동)
- Skills to load: task-done
- 근거: 사용자 지시 "남은 화면(매크로 패널 상세, 포트 탭 다중 상태 등)도 한 번 훑으세요" (2026-08-23)

## 방법 (How) — 코드가 아니라 실행 화면을 봤다

`scratchpad/sweep_screens.py`로 실제 `MainWindow` + `MainPresenter`를 띄워
네이티브(offscreen 아님) 캡처를 찍었다. 만든 상태:

- 매크로 5행 — 긴 명령(`AT+VERY+LONG+COMMAND+THAT+OVERFLOWS=1234567890`),
  HEX 행(`68 01 00 16 AA 55 FF EE DD CC BB`), 짧은 행 혼재
- 실행 중 상태 (`set_running_state(True, is_repeat=True)`, `3 / 10`)
- 포트 탭 4개 + LOOPBACK 연결
- 시스템 로그를 WARN/ERROR/SUCCESS/INFO로 채움
- dark·light x ko·en

## 찾은 것과 고친 것

### 1. 포트 탭 4개가 모두 같은 이름이었다

탭 제목은 `"{custom_name}:{포트명}"` 인데, 모든 탭이 기본 이름 "포트"로 시작하고
포트 콤보가 목록의 첫 항목을 자동 선택한다. 결과는 넷 다 **"포트:LOOPBACK"** —
멀티포트 도구인데 정작 탭으로 포트를 구분할 수 없었다.

번호는 형제 탭을 볼 수 있는 `PortTabPanel`이 붙인다. 전역 카운터로 매기는 안을
먼저 넣었다가 실행 화면에서 **"포트, 포트 3, 포트 4, 포트 5"** 로 튀는 것을 보고
되물렸다 — 버려진 인스턴스가 번호를 먹었다. 지금은 **쓰이지 않는 가장 작은 번호**를
고르므로 닫고 다시 열어도 번호가 커지지 않는다.

- `view/panels/port_tab_panel.py` — `_next_default_tab_name()`
- `view/panels/port_panel.py` — 기본 이름은 그대로, 번호는 컨테이너가 부여
- `tests/test_port_tab_naming.py` (4개)

### 2. 매크로 표에서 가장 중요한 "명령" 열이 가장 좁았다

우측 패널 최소 폭에서 실측:

| | 명령 열 | 필요 폭 | 나머지 열 합 |
|---|---|---|---|
| 수정 전 | **114px** | 375px | 472px |
| 수정 후 | 232px (ko) · 227px (en) | 375px | 332px |

원인은 헤더 잘림을 막으려던 S-032의 수정이었다. `setMinimumSectionSize()`는
**전 열에 공통으로** 걸리는 값이라, "가장 넓은 헤더"(지연(ms), 78px)를 최소로 잡자
헤더 글자가 하나도 없는 체크박스 열까지 78px가 됐다.

측정해 보면 ResizeToContents가 이미 열마다 헤더 텍스트 폭 + QSS 패딩을 반영한다
(접두사 64 / 지연(ms) 82 — 라벨 실측 폭과 일치). **전역 최소값은 좁은 열만 부풀리고
넓은 열에는 아무것도 더해 주지 않았다** — 잃기만 한 장치였다.

최소 섹션 폭을 체크박스 규모(23px)로 낮췄다. 최소 폭에서 헤더 잘림 0건, 가로 스크롤
없음(S-068 조건 유지)을 네이티브로 재확인했다.

- `view/widgets/macro_list.py` — `_compute_checkbox_min_section_size()`
- `tests/test_macro_column_widths.py` (5개)

### 3. 잘린 명령을 읽을 방법이 없었다

표 전체에 걸린 툴팁은 고정 안내 문구라 무엇이 잘렸는지 알려 주지 않는다. 전문을
보려면 셀을 편집 상태로 만들어야 했다. 명령 셀에 내용 툴팁을 붙였다 — 행 생성 시
한 번, 이후 편집마다 갱신한다(생성 시에만 붙이면 편집 후 옛 문자열이 남아 없는 것보다
나쁘다).

- `view/widgets/macro_list.py` — `_insert_row()` / `on_item_changed()`
- `tests/test_macro_column_widths.py` (2개)

### 4. 비활성 위젯 글자가 기준 미달이었다

매크로 실행 중 "전송" 버튼이 거의 안 보여 실측했다:

| 테마 | 수정 전 | 수정 후 | 기준 |
|---|---|---|---|
| dark | 2.44 | **3.19** | 3.0 |
| light | 2.29 | **3.19** | 3.0 |
| dracula | 3.36 | (유지) | 3.0 |
| classic | 3.04 | (유지) | 3.0 |

S-063은 accent/danger/warning **의미색 버튼만** 훑었다. 정작 화면에 가장 많은
민짜 버튼·입력창·콤보·탭은 검사 밖이었고, 넷 다 같은 실패 조합을 쓰고 있었다
(테마당 4곳 x 2테마 = 8칸).

- `resources/themes/dark_theme.qss` `#606060` → `#727272`
- `resources/themes/light_theme.qss` `#a0a0a0` → `#868686`
- `tests/test_qss_contrast.py` — `PLAIN_DISABLED_FAMILIES` 추가

## 남긴 것 (사용자 판단 필요)

**연결된 탭에 시각적 표시가 없다.** 지금은 *선택된* 탭만 강조되고, 어느 탭이
실제로 열려 있는지는 그 탭을 눌러 봐야 안다. 상태바에는 점(●/○)이 있으나 탭에는
없다. 탭 텍스트에 표식을 넣을지, 탭 배경에 상태색을 줄지는 보기의 문제라
사용자에게 물어야 한다 — 결함이 아니라 기능 추가다.

## 검증 방법 — 픽셀이 아니라 기전을 쟀다

`tests/test_macro_column_widths.py`는 열의 실제 픽셀 폭을 재지 않는다. pytest
하네스(offscreen, 테마 QSS 미적용)에서는 델리게이트 크기 힌트가 실행 화면과 크게
달라(접두사 열이 361px로 나온다) 픽셀 비교가 거짓 통과·거짓 실패를 모두 낸다.
대신 **폭을 정하는 기전**(최소 섹션 폭의 규모, Stretch 열의 개수, 헤더 반영 여부)을
본다. 실제 폭은 네이티브 실측으로 확인하고 그 수치를 문서에 남겼다.

파괴 시험 결과 (결함을 되살렸을 때 실제로 실패하는가):

| 되살린 결함 | 실패한 테스트 |
|---|---|
| 탭 번호 부여 제거 | 4개 중 3개 |
| 전역 헤더 기준 최소값 복원 | `test_minimum_section_size_is_checkbox_scale_not_header_scale` |
| DELAY 열도 Stretch로 | `test_command_is_the_only_stretching_column` |
| 편집 시 툴팁 갱신 제거 | `test_command_cell_tooltip_follows_edits` |
| 비활성 색 원복 | `test_plain_widget_disabled_contrast` (8칸 전부) |

## 실기기 미검증

없음 — 전부 UI 레이아웃·색 문제로, 시리얼 장비와 무관하다.
