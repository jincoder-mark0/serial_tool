# chat log -- SerialTool -- 2026-08-22

형식: `## (턴번호) USER|AGENT -- 시각` + 내용. 읽을 때는 `python tools\chatlog.py tail` (전체 읽기 금지).

## (1) AGENT -- 2026-08-22 13:01:18

완료했습니다. 요약합니다.

## 결과

기존 `.claude/`, `tools/`, `CLAUDE.md`, `RULES.md`, `Task.MD`는 **모두 다른 프로젝트(Board Provisioner·STOM 복원·Persephone FPGA)에서 복사된 내용**이었고, 이를 SerialTool(PyQt5 Strict MVP 시리얼 통신 도구) 기준으로 전면 재작성했습니다.

**재작성한 파일**

- [CLAUDE.md](CLAUDE.md) — 실행·검증 명령(`main.py`, offscreen pytest, 언어 키 검사), MVP 아키텍처 불변식(의존 방향, DTO, EventBus/Fast Path 예외, 30ms Throttling, 스레드/설정/다국어/테마 규칙), 작업 방식, 자가 진화, 커밋 규약, 문서·구조 안내.
- [RULES.md](RULES.md) — 자가 진화 프로토콜, 검증 규율(완료 선언 3단계 + Mock/실기기 구분), MVP·다국어·커밋·chatlog 규율. 실재하는 도구·테스트만 참조합니다.
- [Task.MD](Task.MD) — `doc/task.md`(Phase 이력)와 README §1.4를 근거로 작업 보드를 신설: 완료된 Phase 1~5.5(S-001~005)와 잔여 작업 S-006~S-015(AutoTx, 성능, 플러그인, 가상 포트 테스트 환경, 패키징, CI, SPI/I2C), 우선순위 메모 포함.
- [.claude/settings.json](.claude/settings.json) — `e:/FPGA/Persephone_v200`을 가리키던 chatlog 훅을 이 프로젝트의 [tools/chatlog.py](tools/chatlog.py)로 교체. `settings.local.json`의 타 프로젝트 권한도 초기화.
- [.claude/skills/task-done/SKILL.md](.claude/skills/task-done/SKILL.md), [.claude/skills/lang-keys/SKILL.md](.claude/skills/lang-keys/SKILL.md) — 이 프로젝트용 스킬 2종 신설(태스크 마감 절차, 언어 키 절차).
- [tools/chatlog.py](tools/chatlog.py) — `PROJECT = "STOM"` → `"SerialTool"`. 초기화 실행 확인, 로그가 `chatlog/chat_SerialTool_26-08-22.md`에 생성됩니다.
- [doc/mistakes.md](doc/mistakes.md) — 실수 대장 신설(1번 항목: 타 프로젝트 설정 복사 건 기록).

**덤으로 고친 실제 버그**: [tools/check_language_keys.py:34](tools/check_language_keys.py#L34)와 [tools/manage_language_keys.py:33](tools/manage_language_keys.py#L33)가 존재하지 않는 `resources/lang`을 가리켜 항상 실패했습니다 → `resources/languages`로 수정 (manage 쪽은 `..` 누락도 함께). `.agent/rules/`와 언어 키 도구 2종은 이 프로젝트 고유 자산이라 유지했습니다.

**검증**: 전체 pytest **85 passed** (offscreen), `check_language_keys.py` **SUCCESS(exit 0)**, chatlog init/tail 정상 동작. 모두 Mock/로컬 기준이며 실기기 검증 대상 아님.

**사용자 조치 필요 — 삭제 1건**: 타 프로젝트 잔재 파일 삭제는 권한 분류기가 차단해 제가 실행하지 못했습니다. 아래는 이 프로젝트에서 동작하지 않는 복사본들입니다 (`ui_audit.py`는 `board_provisioner`를 import, `tools/analysis/`는 STOM pyd 분석 도구, 스킬 7종은 RTL 디컴파일용). 전체를 스크래치패드 `foreign_backup`(29개 파일)에 백업해 두었고, 원본은 각자의 소스 프로젝트에 존재함을 확인했습니다. 확인 후 다음을 실행해 주세요:

```powershell
Remove-Item e:\Python\serial_tool\tools\analysis, e:\Python\serial_tool\tools\ui_audit.py, e:\Python\serial_tool\tools\__pycache__ -Recurse -Force
Remove-Item e:\Python\serial_tool\.claude\skills\cosim-check, e:\Python\serial_tool\.claude\skills\lec-check, e:\Python\serial_tool\.claude\skills\mechanical-decompile, e:\Python\serial_tool\.claude\skills\memory-models, e:\Python\serial_tool\.claude\skills\module-done, e:\Python\serial_tool\.claude\skills\netlist-extract, e:\Python\serial_tool\.claude\skills\refactor-rules, e:\Python\serial_tool\.claude\skills\frontend-design -Recurse -Force
```

새 훅은 다음 세션 시작부터 적용됩니다. 커밋을 원하시면 말씀해 주세요 (전부 미추적 신규 파일이라 `git add` 범위만 정하면 됩니다).

## (2) USER -- 2026-08-22 13:07:17

<ide_opened_file>The user opened the file e:\Python\serial_tool\CLAUDE.md in the IDE. This may or may not be related to the current task.</ide_opened_file>
모든 파일 add 커밋 하위 모델이 파악 없이 업무 진행하도록 세부 task를 /tasks 폴더를 만들어서 작성
