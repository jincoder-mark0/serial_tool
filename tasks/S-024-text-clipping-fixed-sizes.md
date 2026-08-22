# S-024 — 텍스트 잘림·고정 크기 수정 (영문 버튼·고정 높이·스크롤바 겹침)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 고정 크기 4곳 최소 크기로 완화
  (+같은 결함류인 Send 버튼 40x30 짓눌림 1건 범위 내 추가 수정), 다중행 입력창 하단에
  스크롤바 두께 여백 예약(재현 미확인 방어 수정으로 명기). en 잘림 해소·ko 회귀 없음·16pt
  높이 잘림 없음을 8조합+16pt 캡처로 확인. minimumSizeHint 기여 0 (A/B 격리 측정 —
  기준선 대비 변동은 병렬 언어 JSON 변경분). pytest 85 passed.
  부수 발견: ui.proportional_font_size는 죽은 키(→S-016 등재), interval 입력란 16pt 잘림(→S-025 등재))
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (근거: doc/ux_audit_20260822.md 높음 #4·#5, 중간 고정높이·스크롤바)
- Skills to load: task-done

## 목적 (Why)

실행 스크린샷(en 4조합)에서 반복 제어 버튼이 "tart Repeat"처럼 상단이 잘리고,
Scan 버튼 글자가 깨져 보인다. 원인은 한글 폰트 메트릭 기준의 고정 크기 하드코딩 —
영문/폰트 확대 시 재계산이 없다.

## 수정 목록

1. **반복 제어 버튼 잘림 (en)** — `view/widgets/macro_control.py`:
   - `:171` `execution_settings_grp.setFixedHeight(100)` → `setMinimumHeight(100)`으로 완화
     (또는 제거 후 sizeHint에 맡김 — 캡처로 어느 쪽이 자연스러운지 확인해 선택).
   - 버튼 자체에 고정 높이가 있으면(파일 내 `setFixed*` 전수 확인) 최소 높이로 완화.
2. **Scan 버튼 (en)** — `view/widgets/port_settings.py`의 검색/열기 버튼 고정폭을
   확인해 `setFixedWidth` → `setMinimumWidth`로 완화하거나 폰트 메트릭 기반
   (`fontMetrics().horizontalAdvance(text) + 여백`)으로 계산. en "Scan"/"Open"과
   ko "검색"/"열기" 모두 잘리지 않아야 한다.
3. **SystemLog 고정 높이** — `view/widgets/system_log.py:105` `setFixedHeight(100)` →
   `setMinimumHeight` + 수직 사이즈 정책 조정 (폰트 확대 시 잘림 방지).
4. **다중행 입력창 스크롤바 겹침** — 수동 명령 다중행 편집기(manual_control 계열)의
   가로 스크롤바가 마지막 줄 텍스트를 가림 — 스크롤바 정책 확인 후
   `Qt.ScrollBarAsNeeded` + 하단 여백(viewport margin) 확보 또는 줄바꿈 정책 재검토.
   구현 위치는 `view/widgets/manual_control.py`와 `view/custom_qt/`의 해당 에디터에서 찾는다.
5. 수정 후 **폰트 확대 회귀 확인**: 설정에서 폰트를 16pt로 올린 상태(설정 파일
   `settings.proportional_font_size` 임시 변경 후 복원)로 캡처 1회 — 잘림 없어야 함.

## Acceptance criteria (DoD)

- [ ] en 4조합 캡처에서 반복 버튼·Scan 버튼 텍스트 완전 표시.
- [ ] ko 조합 회귀 없음. 16pt 확대 캡처에서 그룹/로그 높이 잘림 없음.
- [ ] 다중행 입력창 마지막 줄이 스크롤바에 가려지지 않음.
- [ ] 전체 pytest 통과. minimumSizeHint가 기존(ko 1458×735)보다 **커지지 않음**
      (ux_capture 출력으로 확인 — 커지면 원인 보고).

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
foreach ($t in 'dark','light') { foreach ($l in 'ko','en') { .venv\Scripts\python tools\ux_capture.py --theme $t --lang $l --out <스크래치패드>\after_s024 } }
# 캡처 8장을 Read로 열어 잘림 여부 육안 판정, minimumSizeHint 출력값 비교 보고
```
