# S-016 — 설정 키 네임스페이스 이중화 해소

- Status: TODO
- Recommended model: **상위 전용** (정본 결정 + 마이그레이션 설계) — 하위 모델 시작 금지
- 선행: 없음 (S-013보다 먼저 결정하는 것이 이상적)
- Skills to load: task-done

## 목적 (Why) — 발견된 실결함 (2026-08-22 코드 조사)

설정 파일에 같은 개념이 **두 네임스페이스로 이중 저장**되고 있다:

- 스키마·기본값의 정의: `core/settings_schema.py:29` — `global.theme`/`global.language`가
  required. `common/defaults.py:104-115 create_fallback_settings()`도 `global` 블록 생성.
- 코드가 실제 쓰는 키: `common/constants.py:62-63` — `ConfigKeys.THEME="settings.theme"`,
  `LANGUAGE="settings.language"` (전 코드가 ConfigKeys 경유).
- 실제 `resources/configs/settings.json`: `global.theme="dark"`와 `settings.theme="dracula"`가
  **동시에 존재하며 값도 다르다**. `SettingsManager.set()`(`core/settings_manager.py:341-346`)이
  중간 경로를 자동 생성해 `settings` 블록이 스키마 밖에서 자라난 결과다
  (스키마 `additionalProperties` 미지정 = 통과).

결과: 스키마 검증이 실사용 키를 전혀 보호하지 못하고, `global` 블록은 죽은 데이터다.

## 결정할 것 (상위 모델)

1. 정본 네임스페이스: 실사용 중인 `settings.*`(ConfigKeys — 코드 전체가 사용)로 통일할지,
   스키마의 `global.*`로 이관할지. (권장 방향: 코드 실태인 `settings.*`를 정본으로 하고
   스키마·defaults를 실태에 맞춰 재작성 — 코드 변경 범위 최소.)
2. `CURRENT_VERSION`(`settings_manager.py:50`, 현재 "1.0") 증가 + `_migrate_settings`
   (`:198`)에 `global.*` → 정본 이관 규칙 추가 여부.
3. 스키마를 실사용 키 전체(ConfigKeys 30개)로 확장할지, 최소 골격만 유지할지.
4. `resources/configs/settings.json`의 `settings.theme="dracula"` — dracula 테마 QSS는
   존재하지 않는다(`resource_path.py:74`는 common/dark/light만). 값 정리 필요.
5. (S-024 수행 중 추가 확인, 2026-08-22) 폰트 키도 같은 이중화: 실소비 키는
   `settings.proportional_font_size`(ConfigKeys.PROP_FONT_SIZE)이고 `ui.proportional_font_size`는
   파일에 존재하지만 읽히지 않는 죽은 키다 — theme/language만의 문제가 아니라 ui 블록 전반 점검 필요.

## Acceptance criteria (결정 후 구현 태스크로 분할)

- [ ] 정본 네임스페이스 결정과 근거가 이 파일에 기록됨.
- [ ] 마이그레이션 포함 구현 태스크(S-0xx)가 하위 모델용으로 작성됨.
