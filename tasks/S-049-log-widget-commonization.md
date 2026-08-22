# S-049 — [P3] 로그 위젯 중복 공통화 (DataLog ↔ SystemLog)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (단, 시그널·제어 흐름 보존이 까다로움 — 벗어나면 중단·보고)
- 선행: S-047 (명명 개명 완료 후 — 겹치는 파일)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-7

## 목적 (Why)

`view/widgets/data_log.py`와 `view/widgets/system_log.py`가 150~200줄을 중복한다:
검색창+이전/다음 버튼, 필터 체크박스, "● REC" 로깅 토글 스타일 전환
(`setProperty("state","recording")` + unpolish/polish 시퀀스), `get_state`/`apply_state`의
공통 키(`filter_enabled`/`search_text`). 한쪽을 고치면 다른 쪽을 빠뜨리기 쉽다.

**게다가 제어 흐름이 서로 반대다**: DataLog는 Presenter가 `set_logging_active()`를 호출해야
REC 스타일이 바뀌는 "Presenter 권위" 방식이고, SystemLog는 위젯이 스스로 바꾸는
"자기 권위" 방식이다. 거의 같아 보이는 두 위젯이 같은 개념을 반대 방향으로 구현했다.

## 확정 설계

1. **공통 요소 추출** — 신규 `view/widgets/log_toolbar.py`(또는 믹스인/베이스 위젯):
   - 검색바(입력 + 이전/다음 버튼), 필터 체크박스, REC 토글 버튼의 **생성과 스타일 전환**을
     공통화한다. 각 위젯이 자신의 언어 키·objectName을 주입할 수 있어야 한다
     (키가 서로 다르다: `data_log_*` vs `sys_log_*`).
   - **상속 vs 컴포지션**: 현재 두 위젯의 구조를 읽고 판단해 근거를 보고하라.
     Qt 위젯 상속은 편하지만 결합이 세다 — 컴포지션(툴바 컴포넌트를 소유)이 더 안전할 수 있다.
2. **시그널 계약은 절대 보존**:
   - DataLog: `logging_start_requested`(인자 없음) 등
   - SystemLog: `sys_logging_started(str)`(파일명 포함) 등
   - **이름·시그니처가 서로 다르므로 통합하지 말 것.** Presenter(`main_presenter.py`)가
     각각을 구독 중이라 바꾸면 배선이 깨진다. 공통화는 **내부 구현**에만 적용한다.
3. **제어 흐름 불일치는 이번에 통일하지 않는다** — 어느 쪽이 옳은지는 별도 판단이 필요하고
   (Presenter 권위가 MVP상 더 맞지만 SystemLog는 파일명을 스스로 정한다), 이번 태스크는
   **중복 제거가 목적**이다. 불일치는 그대로 두고 **주석으로 사실을 남긴 뒤 보고**하라.
4. `get_state`/`apply_state`의 **저장 키 문자열은 바꾸지 말 것**(사용자 설정 호환).

## 검증 방법

- 전체 pytest(offscreen, **기준선 243**). 기존 테스트가 두 위젯의 동작을 얼마나 덮는지
  먼저 확인하고, **부족하면 공통화 전에 특성화 테스트(characterization test)를 먼저 추가**하라
  — 리팩토링 전후 동작이 같음을 보장하는 것이 이 태스크의 핵심 위험 관리다.
  (검색 다음/이전 이동, 필터 토글, REC 스타일 전환, 상태 저장/복원 왕복)
- 캡처 4조합(dark/light × ko/en) 육안 — 두 로그 위젯의 툴바가 이전과 같아야 한다.
  캡처 후 `git status`에서 `settings.json` 무변경 확인.
- `ruff check` 신규/수정 파일 클린.

## Acceptance criteria (DoD)

- [ ] 중복 로직이 한 곳으로 모이고 두 위젯이 그것을 사용한다.
- [ ] 시그널 이름·시그니처, 저장 키가 **모두 그대로**다(테스트로 고정).
- [ ] 특성화 테스트로 리팩토링 전후 동작 동일성이 보장된다.
- [ ] 전체 pytest 통과, 캡처 회귀 없음, 제어 흐름 불일치는 주석+보고로 남김.
