# S-027 — 설정 네임스페이스 마이그레이션 구현 (`settings.*` 정본화)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (결정은 S-016에 확정됨 — 벗어나면 중단·보고)
- 선행: **S-013 (설정 사용자 디렉터리 분리) 커밋 완료 후** — 같은 파일(settings_manager) 수정
- Skills to load: task-done

## 목적 (Why)

S-016 조사 결과: 스키마·기본값은 `global.theme/language`를 정의하는데 코드 전체는
`settings.*`(ConfigKeys)를 사용해, 실제 파일에 `global.theme="dark"`와
`settings.theme="dracula"`가 **동시에 존재하며 값도 다르다**. 스키마 검증이 실사용 키를
전혀 보호하지 못하고 `global`은 죽은 데이터다. `ui.proportional_font_size` 등 ui 블록의
폰트 키 4종도 읽히지 않는 죽은 키다 (S-024 수행 중 실측).

## 확정 결정 (S-016, 2026-08-22) — 이대로 구현

정본 = **`settings.*`** (코드 실태 기준, 변경 범위 최소).

## Steps

1. `core/settings_manager.py`:
   - `CURRENT_VERSION` `"1.0"` → `"1.1"`.
   - `_migrate_settings()`에 1.0→1.1 이관 추가:
     a. `global` 블록이 있으면 `global.theme`/`global.language`를 `settings.*`로 이관하되
        **`settings.*`에 이미 값이 있으면 그 값을 유지**(실사용 값 우선), 이관 후 `global` 블록 삭제.
     b. `ui` 블록에서 죽은 폰트 키 제거: `proportional_font_family`, `proportional_font_size`,
        `fixed_font_family`, `fixed_font_size` (실사용은 `settings.*` 쪽 —
        `common/constants.py` ConfigKeys.PROP_FONT_* 참조).
     c. 기존 1.0 리네임 매핑(`:216-250` 부근)은 그대로 두고 버전 체인으로 연결.
2. `core/settings_schema.py` `CORE_SETTINGS_SCHEMA` 재작성:
   - `required: ["version", "settings"]`, `settings`는 `theme`/`language` required.
   - `theme`: `enum: ["dark", "light", "dracula"]` (S-023에서 dracula 정식 등록됨),
     `language`: `enum: ["en", "ko"]`.
   - 나머지 블록(ui/ports/packet 등)은 type만 느슨하게(object) 유지 — 과잉 고정 금지.
   - `global` 정의는 스키마에서 제거.
3. `common/defaults.py` `create_fallback_settings()`: `global` 블록 → `settings` 블록
   (theme "dark", language "en" — 기존 global 기본값 유지).
4. 테스트 추가 (`tests/` — 기존 `mock_settings_manager` fixture 패턴):
   - 1.0 파일(global+settings 공존, 값 상이)을 로드하면 1.1로 이관되고 settings 값이
     살아남으며 global이 사라지는지.
   - global만 있고 settings가 없는 1.0 파일 → settings로 이관되는지.
   - 죽은 ui 폰트 키가 제거되는지.
   - 1.1 파일은 무변경 통과하는지.
5. 실행 스모크: 캡처 1회(dark/ko) 후 `resources/configs/settings.json`이 1.1로 이관되어
   `global` 블록이 사라졌는지 확인 — **이 파일의 이관 결과는 커밋 대상이다**
   (배포 기본값 정리). 단 캡처가 함께 저장한 창 지오메트리 변화는 그대로 커밋해도 무방.

## Acceptance criteria (DoD)

- [ ] 마이그레이션 테스트 4종 통과, 전체 pytest 통과.
- [ ] `settings.json`에 `global` 블록·죽은 ui 폰트 키가 없다 (버전 1.1).
- [ ] 스키마가 실사용 키(`settings.theme/language`)를 실제로 검증한다
      (잘못된 theme 값으로 검증 실패하는 테스트 1건).
- [ ] 앱 실행(캡처)이 정상 — 테마·언어가 기존 사용자 값으로 유지.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\ux_capture.py --theme dark --lang ko --out <스크래치패드>\after_s027
# settings.json에서 global 부재·version 1.1 확인. 이 파일 변경은 원복하지 말고 커밋 대상.
```
