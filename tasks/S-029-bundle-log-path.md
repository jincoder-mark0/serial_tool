# S-029 — 번들 모드 로그 경로 사용자 디렉터리화

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-012 (패키징 — 증상 확인 경로)
- Skills to load: task-done

## 목적 (Why) — S-012 수행 중 확인 (2026-08-22)

번들 실행 시 로그가 `dist\SerialTool\_internal\logs\`에 생성된다
(`core/resource_path.py`의 `logs_dir = base_dir/'logs'`가 `sys._MEIPASS` 기준이라).
Program Files 등 읽기 전용 위치에 설치되면 **로그 기록이 실패**하고, 업데이트 시 로그가
유실된다. 설정(S-013)과 같은 문제의 로그 판이다.

## 확정 설계 (S-013과 동일 패턴)

- `ResourcePath.logs_dir`: 번들(`getattr(sys,'frozen',False)`)이면
  `user_config_dir / 'logs'`(= `%APPDATA%\SerialTool\logs`), 개발 모드는 기존
  `base_dir/'logs'` 그대로 — **개발 모드 동작 불변**.
- `user_config_dir`는 S-013에서 이미 구현됨 — 재사용.

## Steps

1. `core/resource_path.py`의 `logs_dir` 프로퍼티를 위 설계로 수정 (한국어 docstring).
2. 테스트: 개발 모드 경로 불변 + `sys.frozen` monkeypatch 시 APPDATA 하위를 가리키는지
   (S-013 테스트의 monkeypatch 패턴 재사용).
3. README §2.4의 `_internal\logs\` 서술을 현행화.
4. (가능하면) 재빌드 후 exe 스모크로 로그가 `%APPDATA%\SerialTool\logs\`에 생기는지 확인 —
   재빌드가 부담이면 "번들 실검증 미실시"로 보고.

## Acceptance criteria (DoD)

- [ ] 개발 모드 로그 경로 불변 (기존 테스트 통과).
- [ ] 번들 모드(모의)에서 APPDATA 하위 경로 반환 테스트 통과.
- [ ] README §2.4 현행화. 전체 pytest 통과.
