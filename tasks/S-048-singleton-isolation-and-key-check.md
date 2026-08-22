# S-048 — [P3] 싱글톤 테스트 격리 + 언어 키 사용처 검증 도구

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (tests/·tools/ 중심 — 다른 P3와 병렬 안전)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-7, D

## 목적 (Why)

**(1) 싱글톤 오염 잠재**: `SettingsManager`/`EventBus`는 `tests/conftest.py`에 리셋 장치가
있지만(이미 문제가 실물로 드러나 만들어진 것), `ThemeManager`/`ColorManager`/
`LanguageManager`에는 **없다**. 이 셋 중 하나라도 상태를 바꾸는 테스트가 생기면 같은 세션의
이후 테스트로 상태가 새는 순서 의존 오염이 발생한다. 현재 227개 그린은 "아직 안 걸렸다"는
뜻이지 안전하다는 뜻이 아니다 — S-049(God object 분해)에서 이 매니저들을 건드릴 예정이라
**그 전에 안전망을 깔아야 한다**.

**(2) 언어 키 검증 사각지대**: `tools/check_language_keys.py`는 en/ko 키 집합 대칭과
`[TODO]` 마커만 본다. **코드가 참조하는 키가 JSON에 실재하는지 검증하지 않아**
오타 키가 런타임에 조용히 폴백된다(S-020에서 실제로 `manual_panel_title`이 전 화면에 원문
노출된 사고가 이 유형이다). 플레이스홀더(`{0}`) 개수 불일치도 미검출 —
`.format()` 시 `IndexError`가 난다.

## Steps

1. **싱글톤 리셋 픽스처** — `tests/conftest.py`:
   - `ThemeManager`/`ColorManager`/`LanguageManager`의 `_instance`(및 초기화 플래그)를
     테스트 전후로 복원하는 픽스처를 추가한다. 기존 `SettingsManager` 리셋 패턴을 그대로 따를 것.
   - autouse로 할지 opt-in으로 할지는 **비용을 재보고 판단**하라(매 테스트 재생성이 느리면
     opt-in + 상태를 바꾸는 테스트에만 적용). 근거를 보고에 적어라.
   - 픽스처가 실제로 오염을 막는지 증명하는 테스트 1건 추가(예: 테마를 바꾸는 더미 테스트
     2개를 만들어 서로 영향이 없음을 확인).
2. **언어 키 사용처 검증** — `tools/check_language_keys.py` 확장:
   - `view/`·`presenter/` 소스를 AST로 훑어 `get_text("...")` 형태의 **리터럴 키를 수집**하고,
     JSON에 없는 키가 있으면 실패시킨다. 동적 키(f-string, 변수)는 검출 불가하므로
     **경고로 분리 보고**(예: `main_menu_theme_{name}` 패턴 — 실제 사용 중이라 실패시키면 안 됨).
   - en/ko 값의 **플레이스홀더 개수 불일치** 검사 추가(`{0}`, `{1}`... 카운트 비교).
   - 기존 검사(대칭·`[TODO]`)는 그대로 유지. 종료 코드 규약도 유지(CI가 이미 사용 중).
3. 확장한 검사를 실행해 **현재 위반이 있으면 목록을 보고**하라. 고칠 수 있는 것(오타 키,
   플레이스홀더 불일치)은 고치고, 판단이 필요한 것은 보고만.
4. `tests/`에 이 도구의 회귀 테스트 1건(가짜 JSON·가짜 소스로 검출되는지) 추가 권장.

## 검증 방법

- 전체 pytest(offscreen, **기준선 227**+신규) 2회 연속 — 픽스처 추가로 기존 테스트가
  느려지거나 깨지지 않는지 확인(실행 시간 전후 비교 보고).
- `.venv\Scripts\python tools\check_language_keys.py` → 확장 후에도 SUCCESS(또는 발견된
  위반 보고).

## Acceptance criteria (DoD)

- [ ] 세 매니저 싱글톤 리셋 장치 존재, 오염 방지 증명 테스트 통과.
- [ ] 언어 키 도구가 코드 참조 키 실재 여부와 플레이스홀더 개수를 검사한다.
- [ ] 동적 키를 오탐으로 실패시키지 않는다(경고 분리).
- [ ] 전체 pytest 통과, 실행 시간 회귀 보고.
