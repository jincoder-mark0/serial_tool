# S-028 — 우측 폭 저장 키 이중화 해소 (`saved_right_section_width` vs `right_section_width`)

- Status: TODO
- Recommended model: **상위 판단 후 하위 가능** (정본 키 결정 1건 필요)
- 선행: S-027 (같은 마이그레이션 체인에 이어 붙임)
- Skills to load: task-done

## 목적 (Why) — S-027 수행 중 발견 (2026-08-22)

`ui` 블록에 `saved_right_section_width`와 `right_section_width`가 **동시에** 남는다:

- 기존 1.0 마이그레이션(`core/settings_manager.py`의 리네임 매핑)은
  `saved_right_section_width` → `right_section_width`로 **개명**한다.
- 그런데 `common/constants.py:91` `ConfigKeys.SAVED_RIGHT_WIDTH = "ui.saved_right_section_width"` —
  **코드는 여전히 옛 키를 읽고 쓴다**. 즉 마이그레이션이 실사용 키를 없애고,
  런타임이 그 키를 다시 만들어 두 키가 공존한다.
- `common/defaults.py`의 fallback에도 `saved_right_section_width: None`이 남아 merge 시 되살아난다.

## 결정할 것 (상위)

정본 키: 코드 실태(`saved_right_section_width`, ConfigKeys)를 정본으로 하고 1.0 리네임 매핑에서
이 항목을 제거 + `right_section_width` 잔존 키를 마이그레이션으로 삭제할지 — 또는 반대로
`right_section_width`로 통일하고 ConfigKeys·사용처를 바꿀지. (S-016 결정 원칙 "코드 실태 우선,
변경 범위 최소"를 따르면 전자가 자연스럽다.)

## Acceptance criteria (결정 후)

- [ ] 마이그레이션 후 두 키 중 하나만 남고, 창 우측 폭 복원이 동작한다 (테스트).
- [ ] defaults·ConfigKeys·마이그레이션이 같은 키를 가리킨다.
