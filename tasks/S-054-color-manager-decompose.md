# S-054 — ColorManager 분해 (ColorRuleRepository + Qt 어댑터)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (분해 후보 확정 — 벗어나면 중단·보고)
- 선행: **S-050**(특성화 테스트가 안전망 — 완료)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-7 / S-050 보고의 분해 후보

## 목적 (Why)

`view/managers/color_manager.py`(511줄)가 데이터 로직과 Qt 어댑터를 한 클래스에 섞고 있다
(S-050 조사): 싱글톤 수명, 기본 규칙 데이터 + JSON 영속화, 규칙 CRUD, 테마→팔레트 동기화,
Qt 포맷 생성(`_create_format`, `rules` 프로퍼티 — 유일한 `PyQt5.QtGui` 접촉면),
`apply_rules` 파사드.

규칙 CRUD·영속화는 **Qt 없이 단위 테스트할 수 있는 순수 로직**인데 현재는 Qt에 묶여 있다.

## 확정 설계 (S-050 보고의 후보 채택)

1. **`ColorRuleRepository`** — Qt 의존 0:
   - 기본 규칙 데이터, `load_rules`/`save_rules`(JSON 영속화), `_ensure_hex` 정규화,
     `add_custom_rule`/`remove_rule`/`toggle_rule`/`get_rule_color`.
   - 이 클래스만 따로 import해도 PyQt5가 필요 없어야 한다(가능하면 그렇게, 구조상
     불가하면 사유 보고).
2. **Qt 어댑터**(`ColorManager`에 남기거나 별도 클래스로 — 판단해 근거 보고):
   - 테마→`COLOR_*` 팔레트 동기화(`apply_theme`), `_create_format`, `rules` 프로퍼티,
     `apply_rules` 파사드(`ColorService` 호출).
3. **외부 계약 절대 보존**: `color_manager` 싱글톤의 공개 메서드를 View·Presenter가 직접
   호출한다. **이름·시그니처 불변**. 내부만 위임으로 바꾼다.
4. S-050이 만든 `theme_state` 의존(현재 테마가 다크인지)은 그대로 유지 —
   **`theme_manager`를 다시 import하지 말 것**(순환 재도입 금지).

## 검증 방법

- **S-050의 `tests/test_theme_color_managers.py`가 수정 없이 그대로 통과해야 한다**.
  고쳐야 통과한다면 계약이 깨진 것이므로 중단·보고.
- `ColorRuleRepository` 단위 테스트 신규(Qt 없이 실행되는지 확인 포함).
- 전체 pytest(offscreen, **기준선 284**) 2회 연속 + 캡처 4조합 육안(로그 색 강조가
  이전과 동일 — 특히 다크/라이트 전환 시) + `ruff check` 클린.
  캡처 후 `settings.json` 무변경 확인.

## Acceptance criteria (DoD)

- [ ] 규칙 데이터·영속화가 Qt 비의존 클래스로 분리됨.
- [ ] **S-050 특성화 테스트 무수정 통과**, 공개 API 불변.
- [ ] 순환 참조 재도입 없음, 전체 pytest 통과, 캡처 회귀 없음.
