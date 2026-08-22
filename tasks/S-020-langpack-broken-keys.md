# S-020 — 언어팩 결함 수정 (깨진 키·오타·용어 통일·사체 정리)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 키 신설 3·개명 1·오타 1·
  용어 통일 7·고아 키 2 삭제·template_en.json 삭제. check_language_keys SUCCESS,
  pytest 85 passed, 8조합 캡처에서 키 원문 노출 0건 확인.
  부수 발견: `view/widgets/packet.py`는 어디서도 import되지 않는 dead code — 삭제하지 않고 보고만.
  명명 규칙 위반 잔여 목록은 아래 Step 7 및 doc/ux_audit_20260822.md 참조)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (근거: doc/ux_audit_20260822.md 높음 #2·#3, 중간 용어/명명, 낮음 template)
- Skills to load: task-done, lang-keys

## 목적 (Why)

실행 화면에서 언어 키 원문이 그대로 노출되고(`manual_panel_title` — 8조합 전부),
Packet Inspector는 생성자와 retranslate가 서로 다른 미등록 키를 써서 한국어 모드에서도
영어가 나오며 전환 시 키 문자열로 바뀐다. 번역 용어도 화면마다 다르다.

## Steps

lang-keys 스킬 절차(en 먼저 → manage → ko 번역 → check)를 각 항목에 적용한다.

1. **깨진 키 A**: `view/panels/manual_control_panel.py:76,100`이 조회하는 `manual_panel_title` —
   en/ko에 키 신설(en "Manual Control" / ko "수동 제어" — 기존 `manual_control_*` 키들의
   용어와 일치시킬 것: 먼저 en.json에서 manual_control 계열 표기를 확인).
2. **깨진 키 B**: `view/panels/packet_panel.py` 생성자(`:194-202`)와 `retranslate_ui()`(`:238-241`)의
   키 이름을 **하나로 통일**(명명 규칙 `[context]_[type]_[name]`에 맞는 쪽 — `packet_grp_title`,
   `packet_chk_capture`, `packet_chk_autoscroll` 형태 권장)하고 en/ko에 등록.
   기존 `packet_panel_btn_clear` 키도 context를 `packet_`으로 정렬(코드 참조 동시 수정).
3. **오타**: en.json `right_tooltip_packet` = "Packet packet panel" → "Packet Inspector panel".
4. **용어 통일 (ko.json)**: ① "Command" 영문 혼용 4곳(라인 46,89,90,100 부근 — "다음 Command" 등)
   → "명령". ② "Packet Inspector" 번역을 "패킷 분석기"로 통일(`right_tab_packet`="분석기" 포함 —
   탭 폭이 좁으면 "패킷 분석기" 적용 후 S-024 검증 캡처에서 잘림 확인). ③
   `data_log_chk_tx_broadcast_allowed`(+`_tooltip`) ko 값을 "TX 브로드캐스트"로.
5. **고아 키 삭제**: `main_menu_language_en`, `main_menu_language_ko` — 코드 참조가 없는지
   Grep으로 재확인 후 en/ko 양쪽에서 제거.
6. **사체 정리**: `resources/languages/template_en.json`은 로더가 제외하는 죽은 파일
   (`view/managers/language_manager.py:131`) — 삭제하고, 참조가 없는지 Grep 확인.
7. 명명 규칙 위반 잔여(`*_tooltip_*` 어순, `_title` 세그먼트 혼재 등)는 **이번에 고치지 않는다**
   (키 개명은 코드 전 참조 수정을 동반하는 별도 작업) — 발견 목록만 보고에 재기재.

## Acceptance criteria (DoD)

- [ ] 8조합 캡처에서 키 원문 노출 0건, Packet 탭이 ko에서 한국어로 표시.
- [ ] `tools/check_language_keys.py` 통과, `tests/test_view_translations.py` 통과.
- [ ] 전체 pytest 통과. template_en.json 부재.

## 검증 방법

```powershell
.venv\Scripts\python tools\check_language_keys.py
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
foreach ($t in 'dark','light') { foreach ($l in 'ko','en') { .venv\Scripts\python tools\ux_capture.py --theme $t --lang $l --out <스크래치패드>\after_s020 } }
# 캡처를 Read로 열어 manual/packet 영역 육안 확인, 보고에 명기
```
