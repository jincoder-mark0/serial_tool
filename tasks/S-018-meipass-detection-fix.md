# S-018 — PyInstaller 감지 버그 수정 (`os._MEIPASS` → `sys._MEIPASS`)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. pytest 85 passed,
  개발 모드 경로 불변 확인. 코드상 os._MEIPASS 잔존 0건)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

`ResourcePath`가 PyInstaller 번들 환경을 감지하려고 `_MEIPASS` 속성을 확인하는데,
PyInstaller는 이 속성을 **`sys` 모듈**에 심는다. 현재 코드는 `os`에서 찾고 있어
감지가 항상 실패한다 — 지금(개발 모드)은 증상이 없지만, 패키징(S-012) 시
리소스 경로가 전부 깨지는 잠복 버그다.

## 배경 (자족적 설명)

- `core/resource_path.py:31` `class ResourcePath` — 모든 리소스(설정/언어/테마/아이콘) 경로의 단일 원천.
- `:47-55` base_dir 결정 로직: 인자 없으면 `hasattr(os, '_MEIPASS')` 확인(`:48`) →
  참이면 `Path(os._MEIPASS)`(`:50`), 아니면 `Path(__file__).parent.parent`(프로젝트 루트, `:53`).
- PyInstaller 공식 동작: 번들 실행 시 `sys._MEIPASS`에 임시 추출 경로를 넣는다. `os._MEIPASS`는 존재한 적 없음.

## Steps

1. `core/resource_path.py`의 base_dir 결정 부분(47~55행 부근)에서
   `hasattr(os, '_MEIPASS')` → `hasattr(sys, '_MEIPASS')`,
   `Path(os._MEIPASS)` → `Path(sys._MEIPASS)`로 수정한다.
2. 파일 상단에 `import sys`가 없으면 추가한다 (`import os` 옆, 표준 라이브러리 정렬 유지).
3. 프로젝트 전체에서 `os._MEIPASS`가 더 없는지 Grep으로 확인한다 (다른 파일에 있으면 동일 수정).

## Acceptance criteria (DoD)

- [ ] `_MEIPASS` 참조가 전부 `sys` 기준이다.
- [ ] 개발 모드 동작 불변: 아래 검증 스크립트가 프로젝트 루트를 출력한다.
- [ ] 전체 pytest 85개 통과.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python -c "from core.resource_path import ResourcePath; p=ResourcePath(); print(p.base_dir); assert p.settings_file.exists()"
# 기대: E:\Python\serial_tool 출력, assert 통과 (개발 모드 경로 불변 확인)
```

번들 환경 실검증은 S-012(패키징)에서 수행한다 — 이 태스크에서는 개발 모드 무변경만 보장.
