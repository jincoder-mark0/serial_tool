---
name: module-done
description: 모듈 Task 완료 판정 체크리스트 — LEC/init감사/cosim 3중 게이트, 로그 보존, 문서화, git 커밋 규약.
---

# 모듈 Task 완료 체크리스트

Task는 아래 **전부** 충족해야 DONE이다. 하나라도 빠지면 IN-PROGRESS.

```
[ ] LEC:        python verify\lec\run_lec.py --module <MOD> [--gate rtl\<MOD>.v] [--elab-dsp]  → exit 0
[ ] Init 감사:  python tools\check_inits.py --module <MOD> [--rtl rtl\<MOD>.v]                 → exit 0
[ ] Cosim:      python verify\cosim\run_cosim.py --module <MOD> [--stage rtl]
                --seeds 1 2 3 --cycles <티어 기준: cosim-check 스킬 표 참조>                    → exit 0
[ ] 로그가 verify\logs\ 에 저장돼 있고 파일명을 Task 파일에 기록했다
[ ] (Stage 2) docs\module_notes\<MOD>.md 작성/갱신 (개명표, 복원 이디엄, 발견 사항)
[ ] tasks\TASK-xxx-<name>.md 의 Status를 DONE으로 갱신하고 결과 요약을 적었다
[ ] 루트 TASK.md 마스터 체크리스트의 해당 체크박스를 체크했다
[ ] git 커밋 1개: "TASK-xxx: <한 줄 결과>" (예: "TASK-021: Cursor refactor, LEC+init+cosim 3x200k pass")
```

## 특례
- **Mem_\***: LEC/init감사 대신 `python tools\mem_extract.py --check` exit 0 + cosim 3×500k.
- **mul_add쌍**: LEC에 `--elab-dsp` 필수. cosim에 2^20 전수 directed(`verify\cosim\directed\mul_add_operation.vh`)가 있으면 함께.
- **톱(Persephone_v200)**: 서브트리 전체가 gate에 포함되므로 모든 자식이 먼저 DONE이어야 의미 있음.

## 절대 하지 말 것
- 게이트를 통과시키기 위한 스텀리스 약화/사이클 축소.
- 실패 로그 삭제. 실패는 Task 파일 Notes에 기록하고 원인 분석 후 재실행.
- rtl_gen\ 또는 넷리스트 원본 수정.
