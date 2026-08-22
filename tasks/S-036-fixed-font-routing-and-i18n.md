# S-036 — 고정폭 폰트 설정 미반영 수정 + 언어팩 잔여 4건

- Status: TODO — **미해결 확정 (2026-08-22 실측)**
- Recommended model: **하위(Sonnet) 가능** (확정 설계 기준)
- 선행: S-035·S-053 커밋 완료 (충돌 없음)

## ⚠ 실측 증거 (2026-08-22, 상위 모델 직접 측정)

`QSmartListView`에 `class="fixed-font"`를 주고 `ThemeManager.set_fixed_font()`로 폰트를
바꾼 뒤 `QFontInfo(widget.font())`로 실제 적용 폰트를 확인:

```
설정: Consolas 9pt      →  실제: Consolas 9pt
설정: D2Coding 16pt     →  실제: Consolas 9pt   ← 반영 안 됨
설정: Courier New 20pt  →  실제: Consolas 9pt   ← 반영 안 됨

common.qss 정적 규칙 위치: 5246, 동적 규칙 위치: 15632 (동적이 뒤에 있음)
```

**동적 규칙이 스타일시트 뒤에 붙어 있는데도 정적 규칙이 이긴다** — Qt QSS는 특이도를
먼저 보고 순서는 특이도가 같을 때만 따지기 때문이다(`QSmartListView.fixed-font` = type+class
vs `.fixed-font` = class 단독).

### 함께 고칠 것: S-050의 폰트 계약 테스트가 잘못된 것을 고정하고 있다

`tests/test_theme_color_managers.py`의 폰트 관련 테스트는 "동적 폰트 블록이 문자열상
**뒤에 위치**한다"를 검증한다. 위 실측대로 **순서는 무의미**하므로, 이 테스트는 통과하면서도
실제 반영 실패를 잡지 못한다. **실제 위젯의 `QFontInfo`로 검증하도록 고쳐야 한다.**
- Skills to load: task-done, lang-keys

## 목적 (Why) — 사용자 보고 "폰트 구분 부정확" + "언어팩 누락" (2026-08-22 점검 판정)

**폰트**: `resources/themes/common.qss:280-287`이 `QSmartListView.fixed-font` 등
element+class 결합 선택자로 "Consolas 9pt"를 하드코딩 → Qt QSS 특이도(type+class=2)가
`view/managers/theme_manager.py:438` 동적 규칙(class 또는 type 단독=1)을 **항상 이김**.
결과: RX 로그·시스템 로그·명령 입력·Auto 간격 입력은 설정의 fixed_font(D2Coding 등)를
바꿔도 9pt Consolas 고정, 매크로·패킷 테이블만 설정 반영 — 위젯군마다 결과가 갈림.

## 확정 설계

**A. 폰트 라우팅 (단일 원천화)**
1. `common.qss:280-287`의 fixed-font 폰트 하드코딩 규칙 **삭제** — 폰트 패밀리/크기의
   유일 원천은 ThemeManager의 동적 스타일시트다. (common.qss에 폰트 외 속성이 같은 규칙에
   섞여 있으면 폰트 선언만 제거.)
2. 삭제 후 동적 규칙이 같은 위젯 집합(QSmartListView/QSmartTextEdit/QPlainTextEdit/
   QTextEdit/QLineEdit.fixed-font/QTableView)을 빠짐없이 커버하는지
   `theme_manager.py:438 _generate_font_stylesheet()`에서 확인 — 부족하면 동적 규칙에 보강.
3. 일관성: `view/widgets/macro_control.py:100` `repeat_interval_ms_edit`(QLineEdit)에
   `setProperty("class", "fixed-font")` 부여 — Auto 간격 입력(fixed)과 같은 성격(ms 숫자).
4. 검증: 설정 fixed_font_size를 임시로 14로 바꾼 캡처에서 RX 로그 placeholder·시스템 로그·
   명령 입력의 글자가 실제로 커지는지 전/후 비교 (settings.json은 검증 후 checkout).

**B. 언어팩 잔여**
5. `resources/languages/ko.json` `manual_control_chk_auto_tx`: "Auto" → "자동"
   (기존 "자동 스크롤"/"자동 감지" 관례 준수).
6. `view/dialogs/preferences_dialog.py:129-130` 언어 콤보: "Korean" → "한국어"
   (endonym 관례 — "English"는 유지).
7. `core/error_handler.py:157-158` 크래시 다이얼로그: 언어 키 경유로 전환하되
   **try/except로 감싸 실패 시 기존 영어 폴백** (손상된 상태에서도 다이얼로그가 떠야 함 —
   방어적 설계 유지). 신설 키 예: `error_title_critical`, `error_msg_unexpected`.
8. `view/panels/port_panel.py:78,318` 탭 기본 이름 "Port": 언어 키 신설(`port_tab_default_name`,
   en "Port"/ko "포트") — **사용자 커스텀 이름 저장 로직과의 상호작용 확인**: 저장된 커스텀
   이름은 그대로 두고 기본값 경로만 번역. 저장 형식이 기본값 문자열을 비교에 쓰면 중단·보고.
9. 의도적 유지 (수정 금지 — 판정 근거는 점검 보고): Serial/SPI, 흐름 "None"(enum 값 겸용 —
   표시 분리는 별도 과제), Raw/CR/CRLF/LF, "0 / ∞", 폰트 미리보기 샘플, about 저작권 문구,
   RX/TX 등 통신 약어.

## 검증 방법

전체 pytest(offscreen) + check_language_keys + A-4의 폰트 크기 전/후 캡처 비교 +
ko 캡처에서 "자동" 표시 확인 + **캡처·실험 후 `git checkout -- resources/configs/settings.json`**.

## Acceptance criteria (DoD)

- [ ] fixed_font 설정 변경이 로그 뷰·입력창에 실제 반영 (캡처 전/후 첨부).
- [ ] 폰트 패밀리/크기 선언의 원천이 ThemeManager 한 곳 (common.qss에 폰트 하드코딩 0).
- [ ] 언어팩 4건 반영(ko "자동"·"한국어"·크래시 다이얼로그 키+폴백·Port 탭 기본명),
      check_language_keys 통과.
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
