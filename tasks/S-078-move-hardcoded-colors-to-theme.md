# S-078 — 코드의 하드코딩 색을 테마 리소스로 이동

- Status: DONE (2026-08-23 — 상위 직접 수행. `resources/themes/palette.json` 신설,
  `LOG_COLOR_*` 상수 12개 제거, 테마별 대비 4.5:1 확보. pytest 497 passed, ruff 0건)
- Recommended model: **상위 전용** (사용자 지시 대응 — 이미 완료, 기록용 문서)
- 선행: S-077 (테마 파일 통일)
- Skills to load: task-done
- 근거: 사용자 지시 "코드 내에 하드 코딩되어 있는 색상은 테마로 모두 이동해야 함" (2026-08-23)

## 목적 (Why) — 옮기려다 결함이 나왔다

`common/constants.py`에 `LOG_COLOR_DARK_*` / `LOG_COLOR_LIGHT_*` 12개가 박혀 있었고,
`color_manager.py`와 `color_rule_repository.py`가 이를 소비했다.

**두 벌뿐인데 테마는 4개다.** `ColorManager`가 `theme_name == 'light'`로 밝기를
판정해, 밝은 테마인 **classic이 다크용 색을 받고 있었다.** 흰 배경 위에 어두운
배경용 색을 얹은 셈이다.

| 테마 | 배경 | 기준(4.5:1) 미달 |
|---|---|---|
| classic | `#ffffff` | **11개 중 10개** (기본 텍스트 1.61) |
| light | `#ffffff` | 5개 |
| dracula | `#21222c` | 1개 |
| dark | `#1e1e1e` | 1개 |

또 같은 값이 `color_rules.json`에도 있어 "동일 값 유지"를 **주석으로만 약속**한
상태였다(S-022 주석). 정본이 둘이면 언젠가 갈라진다.

## 수행 결과

### 정본을 테마 리소스로

`resources/themes/palette.json` 신설 — 4테마 × {`is_light`, `background`, `log`{11색}}.
`background`를 함께 적어 **대비를 같은 파일 안에서 검사**할 수 있게 했다.

`ThemeResourceLoader.get_log_colors()` / `.is_light_theme()`를 추가하고,
`ColorManager`와 `ColorRuleRepository`가 이를 쓰도록 바꿨다. `LOG_COLOR_*` 상수 12개는
제거했고, 그 자리에 "색은 테마 리소스가 갖는다"는 주석을 남겼다.

**밝기 분류도 테마가 답한다.** 코드의 `theme_name == 'light'` 판정을 없애고
팔레트의 `is_light`를 읽는다 — 밝기는 테마의 성질이지 코드가 알 일이 아니다.

### 대비 보정은 최소로

기존 값을 유지하고 **미달인 것만** 고쳤다. 색조(H)·채도(S)는 그대로 두고 명도(L)만
옮겨 의미색의 인지를 지켰다. 총 12건 — dark 1, light 5, classic 5(light와 동일 팔레트),
dracula 1. 나머지는 원래 값 그대로다.

처음엔 모든 색을 새로 계산했다가 light의 `rx`가 `#0000FF`(이미 8.59로 통과)에서
`#0B79D0`으로 바뀌어 특성화 테스트가 깨졌다. 통과하는 값을 건드릴 이유가 없어
"기존 값 유지 + 미달만 보정"으로 다시 짰다.

### 부수로 잡은 것

`ColorManager._get_qcolor`의 폴백이 `QColor("#000000")`였다. 잘못된 색이 들어오면
**어두운 테마에서 검은 글씨가 배경에 묻혀 보이지 않는다.** 현재 테마의 기본 텍스트
색(`COLOR_DEFAULT`)을 쓰도록 바꿨다.

## 남겨 둔 하드코딩 (의도적)

- `ThemeResourceLoader.THEME_DARK/THEME_LIGHT` — **QSS 파일을 읽지 못할 때**의 폴백
  팔레트. 파일로 옮기면 "파일이 없을 때"를 대비하는 의미가 사라진다.
- `_LOG_PALETTE_FALLBACK` / `_PALETTE_FALLBACK` — 같은 이유로 `palette.json`을 읽지
  못할 때만 쓰는 최소 폴백. 주석에 "정본은 palette.json"을 명시했다.

이 둘은 **정본이 아니라 최후 방어선**이라 코드에 두는 것이 맞다고 판단했다.
그 외 색 리터럴은 전부 docstring 예시(`'#FF0000'` 등)로, 실제 렌더에 쓰이지 않는다.

## 테스트

`tests/test_log_palette.py` — 4테마 항목 존재, 필수 색 키 존재, **각 색이 그 테마의
배경 위에서 4.5:1 이상**, `is_light`가 배경 밝기와 모순 없음, 코드에 색 리터럴 재발 방지.

classic 팔레트를 다크 색으로 되돌려 11개 미달이 그대로 보고되는 것을 확인했다.
