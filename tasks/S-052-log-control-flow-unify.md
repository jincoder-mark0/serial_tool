# S-052 — 로그 위젯 제어 흐름 통일 (Presenter 권위로)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (방향 확정 — 벗어나면 중단·보고)
- 선행: S-049 (공통화 완료)
- Skills to load: task-done, lang-keys
- 근거: `doc/refactor_audit_20260822.md` C-7 / 사용자 지시 2026-08-22("불일치는 통일")

## 목적 (Why)

거의 같은 두 로그 위젯이 로깅 토글을 **반대 방향의 제어 흐름**으로 구현한다:

- `DataLogWidget` — **Presenter 권위**: 토글 시 시그널만 emit하고, Presenter가 파일 경로를
  받아 로깅을 시작한 뒤 `set_logging_active()`로 위젯 스타일을 바꿔 준다.
- `SystemLogWidget` — **자기 권위**: 위젯이 스스로 `QFileDialog`를 열어 파일명을 정하고,
  REC 스타일도 직접 바꾸며, 파일명을 담은 `sys_logging_started(str)`을 emit한다.

**상위 판정: Presenter 권위로 통일한다.** 근거는 CLAUDE.md 절대 규칙과 RULES §3이다 —
"View는 시그널 emit + 인터페이스 메서드만"이고, "View에 로직이 들어가는 신호: 조건 분기로
상태를 해석하거나 문자열을 조립·변환하는 코드. 발견하면 Presenter로 옮긴다".
SystemLog는 파일 경로 결정·상태 판단을 위젯이 하고 있어 이 규칙에 어긋난다.

## 확정 설계

1. **`SystemLogWidget`을 DataLog 패턴으로 맞춘다**:
   - 토글 시 **시그널만 emit**한다. 위젯이 `QFileDialog`를 직접 호출하지 않는다.
   - 파일 다이얼로그는 DataLog가 쓰는 방식(View facade의 `show_save_log_dialog()` 계열)을
     **그대로 재사용**한다 — 새 방식을 만들지 말고 기존 경로를 따를 것.
   - REC 스타일 전환은 Presenter가 호출하는 `set_logging_active()`(또는 SystemLog의 동등
     메서드)로만 일어나게 한다. S-049에서 만든 `log_toolbar.apply_recording_style()`을 재사용.
2. **시그널 계약 변경 허용** (S-049에서는 보존이 조건이었으나 이번엔 통일이 목적):
   - `sys_logging_started(str)` → 인자 없는 요청 시그널로 정리(예: `sys_logging_start_requested`).
     이름은 DataLog 쪽(`logging_start_requested`)과 대칭이 되게 정하고 근거를 보고하라.
   - **`presenter/main_presenter.py`의 구독부를 반드시 함께 수정**한다. 두 로그의 시작/중지
     처리 로직이 거의 같아지므로, 공통 헬퍼로 묶을 수 있으면 묶되 **로그 종류별 차이
     (파일 확장자 기본값, 대상 위젯)는 파라미터로** 넘긴다.
3. **저장 키(`get_state`/`apply_state`)는 절대 바꾸지 않는다** — 사용자 설정 호환.
4. 언어 키가 새로 필요하면 lang-keys 절차를 따른다(다이얼로그 제목 등이 DataLog와 공유
   가능하면 재사용 우선).
5. S-049가 양쪽 docstring에 남긴 "제어 흐름 불일치" 주석을 **통일 완료 사실로 갱신**한다.

## 검증 방법

- S-049가 만든 특성화 테스트(`tests/test_log_widgets.py`)가 **계약 변경에 맞게 갱신되고
  전부 통과**해야 한다. 특히 REC 스타일 전환·시그널 발생을 검증하는 테스트.
- 신규: SystemLog 토글 시 **위젯이 QFileDialog를 직접 호출하지 않음**을 확인하는 테스트
  (monkeypatch로 QFileDialog를 감시해 호출 0회).
- 전체 pytest(offscreen, **기준선 284**) + `check_language_keys` + 캡처 4조합 육안.
  캡처 후 `git status`에서 `settings.json` 무변경 확인. `ruff check` 클린.

## Acceptance criteria (DoD)

- [ ] 두 로그 위젯이 같은 제어 흐름(Presenter 권위)을 쓴다.
- [ ] SystemLog 위젯이 QFileDialog를 직접 호출하지 않는다(테스트로 고정).
- [ ] 저장 키 불변, Presenter 구독부가 새 계약에 맞게 갱신됨.
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
