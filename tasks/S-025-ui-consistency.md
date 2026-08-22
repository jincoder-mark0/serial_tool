# S-025 — UI 일관성 정비 (툴팁·크기/여백 상수·다이얼로그·니모닉)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-019 (DataLog 중복 제거 — 툴팁 상태가 바뀌므로 먼저)
- Skills to load: task-done, lang-keys

## 목적 (Why)

같은 성격의 컨트롤이 파일마다 다른 크기·여백·툴팁 정책을 갖는다
(근거: doc/ux_audit_20260822.md 중간·낮음 — 상수 부재, 툴팁 불균등, 다이얼로그 혼재).

## 수정 목록

1. **레이아웃 상수 신설** — `common/constants.py`에 추가 (각각 주석 한 줄):
   `LAYOUT_MARGIN_NONE=0`, `LAYOUT_MARGIN_DEFAULT=5`, `LAYOUT_MARGIN_DIALOG=15`,
   `LAYOUT_SPACING_TIGHT=2`, `LAYOUT_SPACING_DEFAULT=5`, `ICON_BUTTON_SIZE=30`.
   기존 사용처를 상수로 교체하되 **현재 값 그대로 매핑** (시각 변화 최소화가 원칙 —
   값 통일 여부는 파일별 현행 값을 표로 보고하고, 명백히 동일 계열인 곳만 통일).
2. **아이콘형 소형 버튼 크기 통일** — macro_list(30×30)/manual_control(40×20, 40×30)/
   data_log·system_log(폭30) → `ICON_BUTTON_SIZE` 기준으로 정리. 시각 확인 필수(캡처).
3. **툴팁 보강 (lang-keys 절차)** — `view/panels/packet_panel.py:194-213` 툴바 4개,
   `view/widgets/manual_control.py` prefix_chk(:135)/suffix_chk(:136)/local_echo_chk(:146),
   `view/widgets/file_progress.py:67-70` cancel_btn,
   `view/sections/main_menu_bar.py` 툴팁 없는 액션들(open_port/close_tab/save_data_log/
   preferences/file_transfer/about).
4. **메뉴 니모닉** — 최상위 메뉴(File/View/Tools/Help) 언어 값에 `&` 니모닉 추가
   (en "&File" 등; ko는 "파일(&F)" 관례). Alt+F 동작 확인.
5. **DataLog↔SystemLog 툴바 stretch 정책 통일** — `system_log.py:161-168`에 data_log와
   같은 `addStretch()` 규칙 적용.
6. **PreferencesDialog 버튼바** — 수동 QPushButton 3개(`preferences_dialog.py:80-91`) →
   `QDialogButtonBox(Ok|Cancel|Apply)`로 교체 (`font_settings_dialog.py:138-142` 패턴 참고,
   기존 시그널 연결 유지).
7. **PortStatsWidget** — `view/widgets/port_stats.py:39-40` 그리드에 spacing 명시(형제와 동일 값).

## Acceptance criteria (DoD)

- [ ] constants.py 신설 상수가 사용처를 대체 (grep으로 잔여 리터럴 보고).
- [ ] 추가된 툴팁 전부 en/ko 키 경유, check_language_keys 통과.
- [ ] Alt+F/V/T/H 메뉴 열림 (수동 확인 또는 캡처 보고).
- [ ] 8조합 캡처 회귀 없음, 전체 pytest 통과.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\check_language_keys.py
foreach ($t in 'dark','light') { foreach ($l in 'ko','en') { .venv\Scripts\python tools\ux_capture.py --theme $t --lang $l --out <스크래치패드>\after_s025 } }
```
