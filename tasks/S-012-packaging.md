# S-012 — PyInstaller 패키징

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. onedir spec + resources 번들,
  PyInstaller 6.22.2, hiddenimports 불요 확인. exe 스모크: 5초 생존 + 번들 로그로 전체 초기화
  시퀀스 확인 + 실행 창 스크린샷(다크 테마·패널 렌더 확인). pytest 회귀 없음.
  잔여 수동 항목: 언어 전환 클릭 확인. 후속 등재: .ico 아이콘 자산 없음(기본 아이콘),
  번들 로그가 _internal\logs\에 쓰임 → S-029(사용자 디렉터리화))
- Recommended model: 하위(Sonnet) 가능 — 단, 최종 실행 확인은 수동(GUI) 항목
- 선행: **S-013(사용자 설정 분리), S-018(PyInstaller 감지 수정)** — 미완이면 시작 금지
- Skills to load: task-done

## 목적 (Why)

독립 실행 파일이 없어 배포·현장 사용이 불가하다 (`doc/task.md` Phase 8 미완 항목).

## 배경 (자족적 설명)

- 진입점: `main.py`. 리소스는 전부 `resources/` 하위 (언어 JSON/테마 QSS/SVG 아이콘/기본 설정).
- 경로 해석: `core/resource_path.py` — S-018 완료 후 `sys._MEIPASS`로 번들 리소스를,
  S-013 완료 후 사용자 설정은 APPDATA를 향한다. **이 두 태스크가 끝나야 번들이 동작한다.**
- 의존성: PyQt5, pyserial, commentjson, requests, qdarkstyle, jsonschema (`requirements.txt`).
- 버전: `common/app_info.py:20` `__version__ = "1.0.0"`.

## Steps

1. `.venv`에 pyinstaller 설치 (`pip install pyinstaller`) — `requirements.txt`에는 추가하지 않고
   `requirements-dev.txt`를 신설해 pyinstaller와 pytest 계열을 옮기는 것은 **하지 말 것**
   (기존 파일 구조 유지) — pyinstaller만 별도 명시: README 빌드 절에 설치 명령 기록.
2. `serial_tool.spec` 신설 (onedir 모드 — onefile은 시작 느림·백신 오탐 잦음):
   - `datas=[('resources', 'resources')]` 전체 포함.
   - `name='SerialTool'`, 콘솔 숨김(`console=False`), 아이콘은 `resources/icons/`에
     .ico가 있으면 지정, 없으면 생략(변환 작업 금지 — 후속 보고).
   - hiddenimports는 빌드 에러가 실제로 나는 것만 추가 (선제 추측 금지).
3. 빌드: `.venv\Scripts\pyinstaller serial_tool.spec --noconfirm` → `dist/SerialTool/`.
4. 스모크(자동 가능한 부분): `dist\SerialTool\SerialTool.exe`를 실행해 5초 내 프로세스가
   살아 있고 `logs/` 대신 번들 로그 경로에 로그가 생기는지, 비정상 종료 코드가 없는지 확인
   (PowerShell `Start-Process` + `Sleep 5` + `HasExited` 확인 후 `Stop-Process`).
5. `.gitignore`에 `build/`, `dist/` 추가 (이미 있으면 생략). spec 파일은 커밋.
6. README §2에 빌드 절차 추가.

## Acceptance criteria (DoD)

- [ ] `serial_tool.spec` 커밋, `dist/SerialTool/SerialTool.exe` 빌드 성공.
- [ ] exe 스모크: 5초 생존 + 로그 생성 확인 (결과 원문 보고).
- [ ] **수동 확인 항목으로 명시 보고**: 창 표시·테마·언어 전환·포트 스캔 (GUI 육안 —
      에이전트가 스크린샷 캡처로 대체 가능하면 캡처 첨부).
- [ ] 전체 pytest 통과 (소스 무변경이어야 정상).

## 검증 방법

빌드·스모크 명령과 출력 원문, 수동/미검증 항목 구분을 보고에 포함한다.
