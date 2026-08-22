# S-057 — ruff 잔여 위반 정리 + CI lint 차단 전환

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-055, S-056 커밋 후 (여러 파일을 건드리므로 마지막에)
- Skills to load: task-done
- 근거: S-047 도입 시 스코프 밖으로 남긴 잔여 + S-056 에스컬레이션

## 목적 (Why)

S-047이 ruff를 도입하면서 자기 스코프(85건)만 고치고 **45건을 남겼다**. CI의 lint job은
그래서 `continue-on-error: true`로 두었고, 주석에 "정리되면 플래그를 뗀다"고 적혀 있다.
잔여가 남아 있는 한 lint는 **새 위반을 막지 못한다** — 누가 F401을 하나 더 넣어도 CI가
초록이다. 검사가 강제력을 가지려면 0건이어야 한다.

## Steps

1. `.venv\Scripts\python -m ruff check .` 실행 → **유형별로 집계**해 보고한다
   (F401 미사용 import, E501 줄 길이, E402 import 위치 등).
2. 유형별로 처리한다. **`--fix` 자동 수정을 일괄로 돌리지 말 것** — 유형별로 판단이 다르다:
   - **F401(미사용 import)**: 대부분 안전하게 제거. 단 `__init__.py`의 재수출이나
     side-effect import(예: 등록용)는 제거하면 안 된다 — 해당하면 `# noqa: F401`에
     사유를 적어 남긴다.
   - **E501(줄 길이 120 초과)**: 의미 있게 줄바꿈한다. 억지로 쪼개면 가독성이 나빠지는
     줄(긴 문자열·URL 등)은 `# noqa: E501` + 사유.
   - **E402(모듈 레벨 import가 위가 아님)**: `tools/benchmark.py`처럼 `sys.path` 조작 후
     import하는 패턴은 정당하므로 `# noqa: E402` + 사유. 억지로 옮기면 깨진다.
   - 그 외 유형은 케이스별 판단 후 근거 보고.
3. **0건 달성 후** `.github/workflows/ci.yml`의 lint job에서 `continue-on-error: true`를
   제거해 **실제 게이트로 만든다**(주석의 약속 이행).
4. `pyproject.toml`에 필요하면 per-file-ignores를 정리한다(테스트 파일 등).
   단 규칙을 통째로 끄는 방식(`select`에서 제거)은 쓰지 말 것 — 그러면 검사가 무의미해진다.

## 검증 방법

- `ruff check .` → **0 errors**.
- 전체 pytest(offscreen, 기준선은 S-055/S-056 커밋 후 값) 2회 연속 — import 제거가
  side-effect를 깨뜨리지 않았는지 확인하는 것이 핵심이다.
- `.venv\Scripts\python -c "import main"` 스모크 + 캡처 1회(dark/ko).
- CI yml 변경 후 로컬에서 동일 명령이 통과하는지 확인(러너 실검증은 push 후).

## Acceptance criteria (DoD)

- [ ] `ruff check .` 0건.
- [ ] `# noqa`로 남긴 항목마다 **사유 주석**이 있다(무근거 억제 금지).
- [ ] CI lint job이 실제 차단 게이트다.
- [ ] 전체 pytest 통과, import 스모크·캡처 회귀 없음.
