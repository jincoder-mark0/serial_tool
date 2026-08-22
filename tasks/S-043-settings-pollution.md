# S-043 — [P1] 설정 기본값 파일이 개발자 세션으로 오염됨

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: 없음 (다른 P0/P1과 파일 겹침 없음 — 병렬 가능)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-5

## 목적 (Why)

`resources/configs/settings.json`은 **배포 기본값 원본**(README §6.5)인데, 커밋된 내용에
개발자 로컬 세션이 그대로 들어 있다:

- `logging.path`: `C:\Users\lkj01\Desktop\Serial_Tool` — **사용자명이 저장소에 노출**
- `ui.window_x/y`, `splitter_state`(base64 블롭) — 개발자 창 위치
- `manual_control.input_text`: `"zx\nzc\nz\nzc\n"` — 매크로 테스트 입력 잔재

근본 원인: **개발 모드에서 앱이 이 파일에 직접 쓴다**(S-013은 번들 모드만 APPDATA로 분리).
그래서 앱을 한 번 띄우거나 캡처를 뜰 때마다 이 파일이 더러워지고, 커밋에 섞여 들어간다
(실제로 S-006/S-028/S-030 커밋에서 반복 수정된 이력).

## 확정 설계

1. **개발 모드에서도 사용자 설정을 분리**한다 — `core/resource_path.py`:
   - `user_settings_file`이 개발 모드에서 `resources/configs/settings.local.json`(신규,
     **.gitignore 대상**)을 가리키도록 한다. 번들 모드는 S-013대로 APPDATA 유지.
   - `settings_file`(배포 기본값 원본)은 **읽기 전용 소스**로만 남는다.
   - ⚠ S-013이 "개발 모드는 두 경로가 동일"을 회귀 테스트로 고정해 두었다
     (`tests/test_core_refinement.py`의 `test_dev_mode_user_settings_path_matches_config_path`
     계열). **그 테스트의 의도가 이번 변경으로 바뀌므로**, 삭제하지 말고
     "개발 모드에서는 settings.local.json을 쓴다"는 새 계약으로 **갱신**하고 사유를 주석에.
   - 기존 로드 우선순위 로직(사용자 파일 있으면 그것, 없으면 기본 배포본 → 사용자 경로로
     저장)은 그대로 재사용된다 — 첫 실행 시 자연 이관.
2. **`.gitignore`**: `resources/configs/settings.local.json` 추가.
3. **기본값 원본 정화** — `resources/configs/settings.json`:
   - `logging.path`를 빈 문자열 또는 상대 기본값으로(코드가 빈 값을 어떻게 처리하는지
     `SettingsManager`/로깅 경로 사용처를 먼저 확인하고, 안전한 값을 택해 근거 보고).
   - `ui.window_x/y`, `splitter_state`를 기본값(없음/null)으로 되돌린다.
   - `manual_control.input_text`를 빈 문자열로.
   - `version`은 현재 스키마(1.3) 유지, 그 외 키는 건드리지 않는다.
4. **재오염 방지 확인**: 변경 후 앱을 한 번 띄우고(`tools/ux_capture.py`) `git status`로
   `settings.json`이 **수정되지 않았는지** 확인한다 — 이것이 이 태스크의 성공 판정이다.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\ux_capture.py --theme dark --lang ko --out <스크래치패드>\s043
git status --short   # settings.json이 M으로 나오면 실패 (settings.local.json은 무시돼야 함)
```

## Acceptance criteria (DoD)

- [ ] 앱 실행 후 `resources/configs/settings.json`이 변경되지 않는다 (재오염 차단 확인).
- [ ] 커밋된 기본값에 개인 경로·창 위치·입력 잔재가 없다.
- [ ] 개발 모드 설정 저장/복원이 정상 동작한다 (S-013 테스트 갱신 + 신규 검증).
- [ ] `.gitignore`에 local 설정 추가. 전체 pytest 통과.
