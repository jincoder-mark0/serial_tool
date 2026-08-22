# S-060 — 클래식 테마 추가

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 4번째 테마로 classic 추가,
  셀렉터 집합은 기존 3테마와 동일함을 확인. 작업 중 의미색 버튼 대비 결함을 발견해
  에스컬레이션 → S-063)
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: S-053(ThemeResourceLoader 분리 완료)
- Skills to load: task-done, lang-keys
- 근거: 사용자 지시 2026-08-22("클래식 테마도 만들어봅시다")

## 목적 (Why)

현재 테마는 dark / light / dracula 3종이다. 전통적인 Windows 클래식 룩(회색 배경 + 검은
텍스트 + 네이비 강조 + 뚜렷한 3D 테두리)을 **4번째 테마로 추가**한다.

## 코드 전제 (2026-08-22 작성 시점 확인 — RULES §8)

- `common/enums.py` `ThemeType`: DARK/LIGHT/DRACULA. 값은 소문자 문자열.
- `core/resource_path.py` `theme_files` 딕셔너리: common/dark/light/dracula 4키
  (S-023에서 키 기반 조회로 정합화됨).
- `view/managers/theme_state.py` `is_dark_theme()`: `dark`/`dracula`만 True.
- `view/managers/theme_resource_loader.py`(S-053 신설): 아이콘·테마 파일·QSS·팔레트 담당.
  `get_icon()`은 **실제 테마명으로 아이콘 디렉터리를 라우팅**한다(S-023).
- `resources/icons/`에 dark/dracula/light 3개 디렉터리 존재.
- QSS 3종은 셀렉터 집합이 **완전 대칭**이다(S-022 확인). classic도 같은 집합을 갖춰야 한다.

## 확정 설계

1. **`ThemeType.CLASSIC = "classic"`** 추가. 하드코딩 문자열 대신 이 enum을 쓴다.
2. **`resources/themes/classic_theme.qss`** 신설 — **dark/light QSS의 셀렉터 집합을 그대로**
   따른다(누락 시 그 위젯만 스타일이 빠져 이질적으로 보인다). 팔레트 지침:
   - 창/패널 배경 `#d4d0c8`(전통 회색), 입력·리스트 배경 `#ffffff`, 본문 텍스트 `#000000`
   - 강조/선택 `#000080`(네이비) + 선택 텍스트 `#ffffff`
   - 테두리 `#808080`, 3D 느낌이 필요하면 밝은 면 `#ffffff`·어두운 면 `#404040`
   - 비활성 텍스트 `#6d6d6d`
   - **대비 검증 필수**(ui_guide §1): 본문 ≥4.5:1, GroupBox 테두리 ≥3:1, 비활성 ≥3:1.
     계산식은 `tasks/S-022-theme-contrast-hardcoded-colors.md` 참조. 미달이면 값을 조정하고
     **계산 출력을 보고에 첨부**하라.
   - S-022/S-035가 3테마에 넣은 규칙을 classic에도 반드시 포함:
     `QPushButton[state="recording"]:checked`, `QLabel[state="connected"/"disconnected"]`,
     `QLabel[class="file-path-box"/"hint-text"]`, `QProgressBar[state="danger"]::chunk`,
     `:disabled`(QComboBox/QCheckBox indicator/QTabBar tab), `disconnected:hover`,
     `about-title/about-version/about-copyright`, GroupBox 테두리 대비.
3. **등록**: `core/resource_path.py` `theme_files`에 `'classic'` 추가.
4. **아이콘**: classic은 밝은 계열이므로 **light 아이콘을 쓴다**. 두 가지 방법 중 택해 근거 보고:
   (a) `resources/icons/classic/`에 light 아이콘 복사, (b) `ThemeResourceLoader.get_icon()`이
   classic → light suffix로 매핑. **(b)가 중복 파일을 만들지 않아 낫다** — 단 S-023이
   "실제 테마명 사용"으로 고친 의도(향후 테마별 아이콘 제작 가능)를 깨지 않도록,
   classic 디렉터리가 있으면 그것을 쓰고 없으면 light로 폴백하는 형태가 이상적이다.
5. **`is_dark_theme()`**: classic은 **밝은 계열**이므로 False를 유지한다(로그 색 규칙이
   light_color를 쓰게 된다). `theme_state.py`는 현재 "dark/dracula만 True"라 수정 불필요 —
   **확인만 하고 보고**하라.
6. **언어 키** `main_menu_theme_classic` (en "Classic" / ko "클래식") — lang-keys 절차.
   테마 메뉴(`view/sections/main_menu_bar.py`)와 Preferences 콤보 양쪽에 노출되는지 확인
   (S-023이 둘 다 `main_menu_theme_{name}` 키를 쓰도록 정합화했다).
7. **테스트**: `tests/test_theme_color_managers.py`의 기존 3테마 검증 패턴에 classic을 추가
   (테마 파일 실제 로드·아이콘 라우팅·색 매핑). 기존 테스트는 무수정으로 통과해야 한다.

## 검증 방법

- 대비 계산 출력(본문·테두리·비활성) 첨부.
- 전체 pytest(offscreen, **기준선 367**) + `check_language_keys` + **ruff 0건**(CI 게이트).
- **캡처: classic × ko/en 2조합 추가**(`tools/ux_capture.py`는 dark/light만 받으므로,
  classic 캡처는 임시 스크립트로 하거나 도구에 classic 선택지를 추가하라 —
  **도구 확장을 택했다면 그 사실을 보고**). 육안으로 잘림·대비·이질감 확인.
- 캡처 후 `git status`에서 `resources/configs/settings.json` 무변경 확인.

## Acceptance criteria (DoD)

- [ ] classic 테마가 메뉴·Preferences에서 선택되고 실제로 적용된다.
- [ ] 셀렉터 집합이 기존 3테마와 대칭이고, 대비 기준을 만족한다(계산 첨부).
- [ ] 아이콘이 정상 표시된다(방식과 근거 보고).
- [ ] 전체 pytest·ruff·언어 키 통과, 캡처 육안 확인.
