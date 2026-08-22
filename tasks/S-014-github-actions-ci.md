# S-014 — GitHub Actions CI (pytest + 언어 키 검사)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

테스트 85개와 언어 키 무결성 검사가 로컬 수동 실행에만 의존한다.
`tools/check_language_keys.py`는 애초에 CI 용도로 작성된 도구다 (파일 docstring 명시).

## 배경 (자족적 설명)

- 테스트: `python -m pytest -q`, GUI 없는 환경은 `QT_QPA_PLATFORM=offscreen` 필수.
- 의존성: `requirements.txt` (PyQt5, pyserial, commentjson, requests, qdarkstyle,
  jsonschema, pytest, pytest-qt). Python 3.10+.
- 언어 키 검사: `python tools/check_language_keys.py` — 실패 시 exit 1.
- 리눅스 러너에서 PyQt5 offscreen 실행에는 시스템 라이브러리가 필요하다
  (`libgl1`, `libegl1`, `libxkbcommon-x11-0` 등). Windows 러너는 추가 설치 불필요.

## Steps

1. `.github/workflows/ci.yml` 신설:
   - 트리거: `push`(main), `pull_request`.
   - Job 1 `test-windows` (`windows-latest`): checkout → setup-python 3.11 →
     `pip install -r requirements.txt` → `$env:QT_QPA_PLATFORM='offscreen'` 설정 후
     `python -m pytest -q`.
   - Job 2 `lang-keys` (`ubuntu-latest`, Python만 필요 — Qt 불필요): checkout →
     setup-python 3.11 → `python tools/check_language_keys.py` (pip 설치 불필요 —
     표준 라이브러리만 사용하는지 파일 import를 먼저 확인하고, 필요 시 해당 패키지만 설치).
   - pip 캐시: `actions/setup-python`의 `cache: pip` 사용.
2. YAML 문법 로컬 검증: `.venv\Scripts\python -c "import yaml, io; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"`
   — PyYAML이 없으면 `pip install pyyaml`을 .venv에 설치하지 말고
   `python -c` 대신 온라인 실행 전 검토로 대체하고 그 사실을 보고.
3. 커밋 후 **CI 실제 통과 확인은 사용자 push 이후에만 가능** — DoD에서 "로컬에서 동일
   명령 통과"까지가 이 태스크 범위이고, 러너 결과 확인은 후속 보고 항목으로 남긴다.

## Acceptance criteria (DoD)

- [ ] `.github/workflows/ci.yml` 존재, YAML 파싱 통과(또는 검토 근거 보고).
- [ ] 워크플로가 수행할 명령과 동일한 명령이 로컬에서 통과: pytest 85개 + check_language_keys.
- [ ] 러너 실검증은 "미검증 — push 후 확인 필요"로 명시 보고.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\check_language_keys.py
```
