# S-028 — 우측 폭 저장 키 이중화 해소 (`saved_right_section_width` vs `right_section_width`)

- Status: DONE (2026-08-22 — 상위 결정 + 하위 모델 수행, 상위 리뷰 승인. reader 전수 확인
  (right_section_width 독자 0건 — DTO 필드명은 별개), 1.0 개명 매핑 제거, 1.1→1.2
  마이그레이션(값 보전 후 잔존 키 삭제), defaults 버전 동기화. 테스트 +3(순증) →
  기준선 112. settings.json 1.2 이관 커밋.
  부수 발견: serial.flowctrl 부활(defaults 옛 키) → S-030 등재)
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

## 확정 결정 (2026-08-22, 상위) — 이대로 구현

정본 = **`ui.saved_right_section_width`** (코드 실태 우선·변경 범위 최소 — S-016과 동일 원칙).
ConfigKeys·defaults는 이미 이 키를 쓰므로 변경 없음. 마이그레이션만 고친다.

## Steps

1. **사전 확인**: `right_section_width`를 읽는 코드가 정말 없는지 Grep으로 전수 확인
   (`common/ core/ model/ presenter/ view/ tests/` — 마이그레이션 매핑 자체 제외).
   **독자(reader)가 하나라도 있으면 중단·보고** (결정 전제가 깨짐).
2. `core/settings_manager.py`:
   - 1.0 리네임 매핑에서 `saved_right_section_width` → `right_section_width` 항목 제거
     (실사용 키를 없애던 원흉).
   - `CURRENT_VERSION` `"1.1"` → `"1.2"` + 1.1→1.2 마이그레이션: `ui.right_section_width`
     잔존 키가 있으면 삭제하되, **`ui.saved_right_section_width`가 없거나 None이면 그 값을
     이어받은 뒤** 삭제 (과거 1.0→1.1 이관으로 값이 옮겨가 버린 사용자의 폭 복원 보전).
3. 테스트 추가: ① 1.0 파일의 `saved_right_section_width`가 개명되지 않고 살아남는다,
   ② 1.1 파일의 잔존 `right_section_width`가 값 보전 후 삭제된다, ③ 1.2 무변경 통과.
4. 캡처 1회(dark/ko) 후 `resources/configs/settings.json`이 1.2로 이관되어 `right_section_width`가
   사라졌는지 확인 — settings.json 이관 결과는 커밋 대상 (checkout 금지).

## Acceptance criteria

- [ ] 마이그레이션 후 `saved_right_section_width`만 남고 값이 보전된다 (테스트 3종).
- [ ] defaults·ConfigKeys·마이그레이션이 같은 키를 가리킨다 (개명 매핑 부재).
- [ ] 전체 pytest 통과 (기준선 109+신규), settings.json version 1.2.
