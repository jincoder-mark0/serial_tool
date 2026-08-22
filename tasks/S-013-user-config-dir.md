# S-013 — 설정 파일 사용자 디렉터리 분리

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 번들 모드 APPDATA\SerialTool
  (+홈 폴백)·첫 실행 자연 이관·저장은 항상 사용자 경로. 개발 모드 두 경로 동일(완전 불변,
  기존 테스트 전부 통과). 신규 테스트 5건 → 기준선 95. README §6.5 현행화.
  설계 판단 승인: dev 모드 user_settings_file은 기존 settings_file 속성 재사용
  (테스트의 override 패턴과 호환 — 근거 명시됨). main.py GUI 실행은 수동 미확인)
- Recommended model: **하위(Sonnet) 가능** (설계 확정됨 — 벗어나면 중단·보고)
- 선행: S-018 (PyInstaller 감지 수정)
- Skills to load: task-done

## 목적 (Why)

설정이 `resources/configs/settings.json`(프로그램 설치 위치)에 직접 저장된다.
패키징(S-012) 후에는 설치 폴더가 읽기 전용일 수 있고, 업데이트 시 사용자 설정이
덮어써진다. 배포 전 반드시 사용자 디렉터리로 분리해야 한다 (README §6.5도 명시).

## 배경 (자족적 설명)

- `core/resource_path.py:62` — `settings_file` = `resources/configs/settings.json`.
- `core/settings_manager.py:103` `_get_config_path()` → `resource_path.settings_file`;
  `:112 _get_user_settings_path()` → **현재 config_path와 동일** (분리 없음, 주석뿐).
- 로드: `:122 load_settings()` — 마이그레이션(`:139`) → jsonschema 검증(`:146`) → fallback merge.
  저장: `:298 save_settings()` → `:287 _save_to_file`.
- 손상 백업: `:275 _backup_corrupted_settings()` → `.json.bak`.
- 번들 감지: S-018 완료 후 `hasattr(sys, '_MEIPASS')` 또는 `getattr(sys, 'frozen', False)`.

## 확정 설계 (이대로 구현)

- `ResourcePath`에 `user_config_dir` 프로퍼티 신설:
  - **번들 실행**(`getattr(sys, 'frozen', False)`): `Path(os.environ['APPDATA']) / 'SerialTool'`
    (Windows 전용 앱이므로 APPDATA 고정; APPDATA 부재 시 `Path.home() / '.serial_tool'` 폴백).
  - **개발 모드**: 기존 `resources/configs`를 그대로 반환 — **현행 동작·테스트 완전 불변**.
- `user_settings_file` 프로퍼티 = `user_config_dir / 'settings.json'`.
- `SettingsManager._get_user_settings_path()`가 `user_settings_file`을 반환하도록 수정.
  로드 순서: 사용자 파일이 있으면 그것을 로드, 없으면 `resources/configs/settings.json`
  (기본 배포본)을 로드한 뒤 **저장은 항상 사용자 경로에** → 첫 실행 시 자연 이관.
- `resources/configs/settings.json`은 "기본값 배포본"으로 강등 — 번들 모드에서 쓰기 금지.

## Steps

1. S-018이 완료되었는지 확인 (`core/resource_path.py`가 `sys._MEIPASS` 사용). 아니면 중단·보고.
2. `ResourcePath`에 `user_config_dir`/`user_settings_file` 추가 (위 설계, 디렉터리는
   `mkdir(parents=True, exist_ok=True)`로 보장, 한국어 docstring).
3. `SettingsManager` 수정: `_get_user_settings_path()` 교체 + `load_settings()`가
   "사용자 파일 우선, 없으면 기본 배포본" 순서로 읽고, `_save_to_file`은 항상 사용자 경로에 쓰도록.
4. 테스트 추가 (`tests/test_core_refinement.py` 또는 신규 파일, 기존
   `mock_settings_manager` fixture(`tests/conftest.py:105`) 패턴 참고):
   - 개발 모드에서 경로가 기존과 동일한지 (회귀 방지).
   - `sys.frozen`을 monkeypatch로 흉내 낸 상태에서 사용자 경로가 APPDATA를 향하는지,
     사용자 파일 부재 시 기본 배포본에서 로드 후 사용자 경로에 저장되는지 (`tmp_path`로
     APPDATA를 patch.dict).
5. `README.md` §6.5의 "배포 시 사용자별 설정 디렉터리로 분리하는 작업은 아직 필요합니다"
   문장을 현행화.

## Acceptance criteria (DoD)

- [ ] 개발 모드 동작·기존 테스트 결과 완전 불변.
- [ ] 번들 모드(모의)에서 사용자 경로 저장·첫 실행 이관이 테스트로 증명됨.
- [ ] 전체 pytest 통과 (기준선 + 신규).
- [ ] README §6.5 현행화.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python main.py 를 잠깐 띄워 설정 저장 경로가 개발 모드 그대로인지 확인(수동, 보고에 명기)
```
