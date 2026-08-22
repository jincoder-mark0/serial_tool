# S-023 — 테마 시스템 구조 결함 수정

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (수정 방향 확정됨)
- 선행: 없음 (근거: doc/ux_audit_20260822.md 중간 — 테마 구조 4건 + 번역 2건)
- Skills to load: task-done, lang-keys

## 목적 (Why)

테마 로딩이 죽은 경로+우연한 폴백으로만 동작하고, dracula 테마는 아이콘·번역·동기화가
반쯤 끊긴 상태다. 지금은 증상이 작지만 "고쳐도 반영 안 되는" 함정 구조라 손대는 즉시 깨진다.

## 수정 목록

1. **테마 파일 조회 정합** — `core/resource_path.py:74-78` `theme_files` 딕셔너리 키와
   `view/managers/theme_manager.py:270-283` `_get_theme_file_path()`의 조회 형식이 어긋나
   딕셔너리가 한 번도 적중한 적 없음(3테마 전부 직조합 폴백으로 로드). **조회를 테마 키
   기반으로 정정**하고(딕셔너리 적중이 정상 경로가 되도록), dracula도 딕셔너리에 등록
   (`resources/themes/dracula_theme.qss` 실존). 폴백은 "미등록 테마 파일" 경고 로그와 함께 유지.
2. **apply_theme ↔ ColorManager 동기화** — `theme_manager.py:513-553` `apply_theme()`가
   docstring("5. ColorManager 업데이트")과 달리 color_manager를 호출하지 않음(import만).
   본문에서 `color_manager.apply_theme(theme_name)` 호출 추가 —
   단, `view/main_window.py:483-484`의 `switch_theme()`가 이미 둘을 나란히 호출하므로
   **이중 호출이 부작용 없는지**(idempotent) color_manager.apply_theme 구현을 먼저 읽고 확인.
   부작용이 있으면 중단·보고.
3. **dracula 아이콘 라우팅** — `theme_manager.py:188-196` `get_icon()`의 suffix를 무조건
   "dark"로 매핑하는 부분을 실제 테마명 사용으로 수정 (`resources/icons/dracula/` 실존 —
   현재 dark와 동일 사본이라 시각 변화 없음이 정상).
4. **"+" 탭 아이콘 테마 전환 갱신** — `view/panels/port_tab_panel.py:160`
   `update_plus_tab_icon()`을 `main_window.switch_theme()` 경로에서 재호출.
5. **dracula 번역** — en/ko에 `main_menu_theme_dracula` 키 추가 (lang-keys 절차).
6. **Preferences 테마 콤보 번역** — `view/dialogs/preferences_dialog.py:106-110,400-405`가
   원문("Dark"/"Light"/"Dracula")을 그대로 표시 → 메뉴와 동일하게
   `main_menu_theme_{name}` 키로 표시(저장 값은 원문 유지 — 표시만 번역).

## Acceptance criteria (DoD)

- [ ] 3테마 모두 딕셔너리 정상 경로로 로드 (폴백 경고 0건 — 로그 확인).
- [ ] 테마 전환 시 "+" 탭 아이콘·로그 색 동기 갱신.
- [ ] ko 모드에서 테마 메뉴·Preferences 콤보 표기 일치.
- [ ] 전체 pytest + check_language_keys 통과, 8조합 캡처 회귀 없음.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\check_language_keys.py
foreach ($t in 'dark','light') { .venv\Scripts\python tools\ux_capture.py --theme $t --lang ko --out <스크래치패드>\after_s023 }
```
