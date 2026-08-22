# S-019 — DataLogWidget init_ui 중복 생성 블록 제거

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 중복 블록 26줄 삭제 —
  첫 블록이 connect 포함 완전 초기화임을 확인. pytest 85 passed, 캡처 검증 완료.
  후속 발견: 검색창이 툴바 공간 부족으로 35px까지 축소되는 별개 이슈 → S-026에 등재)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (UX 점검 최우선 결함 — 2026-08-22, doc/ux_audit_20260822.md #L1)
- Skills to load: task-done

## 목적 (Why)

수신 로그(DataLog) 툴바의 위젯 생성 코드가 `init_ui()` 안에 **통째로 두 번** 있어,
두 번째 블록이 첫 블록의 설정을 조용히 덮어쓴다. 실행 화면 실측으로 확인된 증상:
툴바 전체 툴팁 소실, 검색창 placeholder 소실·폭 무제한, 이전/다음 버튼 objectName·고정폭
소실. 스크린샷 판정에서도 같은 영역의 "비정상적으로 좁은/빈 컨트롤"이 관측됐다.

## 배경 (자족적 설명)

- 파일: `view/widgets/data_log.py` — `init_ui()` 내부.
  - 첫 블록 `:134-212`: `data_log_search_edit`(setPlaceholderText·setMaximumWidth(200)),
    `data_log_search_prev/next_btn`(setFixedWidth(30)·setObjectName), 각종 체크박스·버튼의
    `setToolTip` 등 **완전한 초기화**.
  - 중복 블록 `:213-238`: 주석 `# Components Init (Reuse existing initialization code)`로
    시작하며 **같은 속성명들을 재생성**해 위 설정을 전부 무효화.
- 이 위젯의 언어 재번역은 `retranslate_ui()`가 담당한다 — 삭제 후 retranslate가 참조하는
  위젯이 전부 살아 있는지 확인 필요.

## Steps

1. `view/widgets/data_log.py`의 `init_ui()`에서 213~238행 부근 중복 생성 블록을 찾아
   **첫 블록과 겹치는 재생성 줄만** 삭제한다. 삭제 전 반드시 확인:
   중복 블록에만 있고 첫 블록에 없는 신규 위젯·설정이 있으면 그 줄은 남긴다(또는 첫 블록으로 이동).
2. 삭제 후 파일 내 모든 `self.<위젯명>` 참조(레이아웃 add, 시그널 connect, `retranslate_ui`)가
   생성된 위젯을 가리키는지 Grep으로 대조한다 — 미정의 참조가 남으면 안 된다.
3. 실행 확인: 아래 검증 방법의 스크린샷 캡처로 (a) 검색창에 placeholder가 보이고
   폭이 제한되며 (b) 이전/다음 버튼이 고정폭인지 육안 확인.

## Acceptance criteria (DoD)

- [ ] `init_ui()`에 동일 위젯 재생성이 없다.
- [ ] 툴바 위젯들의 툴팁·placeholder·폭 설정이 실행 화면에서 살아 있다 (캡처 첨부).
- [ ] 전체 pytest 통과 (기준선 85).

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
# 실행 화면 캡처 (네이티브 렌더 — RULES.md §7):
.venv\Scripts\python tools\ux_capture.py --theme dark --lang ko --out <스크래치패드>\after_s019
# 캡처 PNG를 Read로 열어 검색창·버튼 상태 육안 확인 후 보고에 명기
```
