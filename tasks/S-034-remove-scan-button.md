# S-034 — 중복 검색 버튼 제거 (팝업 자동 스캔이 이미 존재)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 순수 삭제 20줄 + 언어 키 2종
  제거, 잔존 참조 0건. 팝업 자동 스캔 시그널 경로 검증(미연결 시 스캔·연결 중 억제).
  최소 폭 변화 없음 — 병목은 시리얼 설정 행(콤보 10개)이라는 위젯 단위 실측 근거 첨부)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (사용자 제안 2026-08-22 — "버튼보다 리스트 펼칠 때 검색")
- Skills to load: task-done, lang-keys

## 코드 전제 (2026-08-22 작성 시점 확인 — RULES §8)

**팝업 자동 스캔은 이미 구현되어 있다**: `view/widgets/port_settings.py:48`
`ClickableComboBox.showPopup()` 오버라이드 → `popup_show_requested` →
`:295 on_port_combo_clicked()`가 미연결 시 `port_scan_requested` emit → 스캔 후 목록 갱신
(`:391-421`, 현재 선택 보존). 따라서 검색 버튼(`:139-143 scan_btn`)은 **완전한 중복**이다.

## 확정 설계

1. `view/widgets/port_settings.py`: `scan_btn` 생성·레이아웃 추가(`:171`)·상태 갱신(`:455`)·
   시그널 연결(`on_port_scan_clicked` — 콤보 경로가 같은 시그널을 쓰면 핸들러 유지 여부 판단:
   콤보 경로만 남기고 버튼 전용 코드는 제거)·retranslate 항목을 제거한다.
2. 언어 키 정리: `port_btn_scan`, `port_btn_scan_tooltip`이 다른 곳에서 안 쓰이면 en/ko에서
   제거 (Grep 확인 후 — lang-keys 절차, check_language_keys 통과).
3. 잔존 참조 0건 확인 (`scan_btn` Grep — 테스트 포함. 테스트가 참조하면 테스트도 갱신).
4. 실행 확인: 캡처 1회(dark/ko) — 버튼이 사라지고 포트 콤보~열기 버튼 정렬이 자연스러운지,
   콤보를 열면 스캔 로그가 찍히는지(`Port combo clicked, requesting scan...`) 확인.
   minimumSizeHint가 줄었으면 수치 보고. **캡처 후 settings.json checkout**.

## Acceptance criteria (DoD)

- [ ] scan_btn 관련 코드·언어 키·참조 0건, 팝업 자동 스캔 동작 유지 (로그 확인).
- [ ] 전체 pytest 통과 (기준선 122+α), 캡처 회귀 없음.
