# PyInstaller Artifact Smoke — 2026-09-02

> 대상: P4 #18 (최신 `main` artifact build + smoke)
> 계획 정본: [`doc/plans/environment_validation_plan.md`](plans/environment_validation_plan.md) §2.1
> 판정: **부분 통과** — 자동 검증 통과, 대화형 기능 항목은 미검증

---

## 1. 실행 환경

```text
OS                  Windows 11 Enterprise 10.0.26200
빌드 기준 커밋      main 9220bd2 (+ 이 브랜치의 spec 수정)
빌드 도구           PyInstaller 6.22.2 (.venv)
Python              3.13.15
Qt 바인딩           PyQt5 5.15.11
Serial backend      pyserial 3.5 (물리 장치 없음 — LOOPBACK만)
빌드 명령           .venv\Scripts\python.exe -m PyInstaller serial_tool.spec --noconfirm
빌드 소요           약 45초 (초회)
artifact            dist/SerialTool (onedir), SerialTool.exe 5,643,690 bytes,
                    _internal 214개 파일, 총 98 MB
```

---

## 2. 검증한 것과 결과

| 항목 | 방법 | 결과 |
|---|---|---|
| 빌드 성공 | spec 빌드 | 통과 (exit 0) |
| 리소스 번들 완전성 | `resources/` 소스와 번들 파일 목록 diff | 통과 (제외 대상 1개 외 36/36 동일) |
| 기동 | exe 실행 후 8초 뒤 프로세스/창 확인 | 통과 (`MainWindowTitle = "Serial Tool v1.0"`) |
| 번들 경로 resource 로드 | 로그의 실제 로드 경로 확인 | 통과 (`_internal\resources\{languages,themes}`) |
| 언어 로드 | en/ko | 통과 (각 302 keys) |
| 테마 로드 | dracula qss | 통과 |
| 설정 읽기/쓰기 | APPDATA 경로 | 통과 (`%APPDATA%\SerialTool\settings.json`) |
| **설정 마이그레이션** | 기존 v1.2 설정 → v1.3 | 통과 (orphan `serial` 블록 제거 포함) |
| 로깅 경로 | frozen 시 APPDATA 하위 | 통과 (`logs\serial_tool_20260902.log`) |
| 포트 스캔 | 기동 후 비동기 스캔 | 통과 (`Found ports: ['LOOPBACK']`) |
| 정상 종료 | `CloseMainWindow()` → ShutdownCoordinator | 통과 (약 3~5 ms, 잔존 프로세스 없음) |
| 로그 내 오류 | WARNING/ERROR/CRITICAL 계수 | **0건** (2회 실행 모두) |
| optional backend 격리 | PyFtdi 미설치 상태 | 통과 (`missing module named pyftdi (delayed, optional)` 경고만, 기동 정상) |

PyFtdi 격리는 Task.MD 12번의 architecture requirement("PyFtdi 미설치여도 startup 유지")가
**패키징된 artifact에서도** 성립함을 확인한 것이다.

---

## 3. 발견하고 고친 결함

**개발자 로컬 설정이 배포본에 실렸다.**

`serial_tool.spec`의 `datas=[('resources', 'resources')]`가 디렉터리를 통째로 담아,
git이 추적하지 않는 `resources/configs/settings.local.json`이 artifact에 포함됐다.
빌드한 개발자의 창 위치·포트 탭 상태·수동 입력값이 배포본에 들어간다.

이 파일은 S-043이 "개발자 로컬 세션이 커밋에 섞이는 오염"을 막으려고 분리하고
`.gitignore`에 넣은 것이다. **그 보호가 git 단계에서만 작동해 빌드로는 그대로 샜다.**

번들 실행 시 사용자 설정은 APPDATA를 쓰므로(`ResourcePath.user_settings_file`)
이 파일은 읽히지도 않는다 — 기능 결함은 아니고 순수 유출이며, 빌드하는 사람마다
artifact가 달라져 재현성도 깨진다.

조치: spec에 `EXCLUDED_DATA_BASENAMES`를 두어 번들에서 제외하고,
회귀 방지 계약을 `tests/test_packaging_spec_contract.py`에 추가했다.

부수 발견: PyInstaller가 `requirements.txt`에도 `requirements-backends/`에도 없어
깨끗한 체크아웃에서는 빌드가 불가능했다. `requirements-build.txt`로 선언했다.

---

## 4. 미검증 — 사람이 GUI에서 확인해야 하는 항목

계획 §2.1 체크리스트 중 아래는 **대화형 조작이 필요해 이번 자동 smoke에서 제외**했다.
통과했다고 기록하지 않는다.

- LOOPBACK 연결 후 Manual TX/RX
- Macro 기본 실행
- Packet Inspector 동작
- File Transfer 기본 경로
- 로그 저장 file dialog 경로
- 아이콘 로드 (spec에 .ico 미지정 — S-012 당시부터 후속 대상)

이 항목들은 packaging 문제가 아니라 기능 동작이므로, 개발 모드에서는 자동 테스트가
덮고 있다. artifact에서의 확인만 남았다.

---

## 5. 남은 P4 게이트

- #19 Windows com0com Serial E2E
- #20 실제 USB Serial 종합 검증
- #21 Linux socat (Linux가 지원 대상일 때)
