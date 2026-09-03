# tools/ — 도구 목록과 판정 기준

`tools/`의 스크립트가 무엇을 검사하고 **exit 0이 무엇이 참임을 뜻하는지** 적는다.
게이트로 쓰는 도구는 그 의미를 모른 채 "통과했다"고 인용하면 안 된다.

관련 규율은 `RULES.md` §11.

---

## 게이트 도구 (CI가 돌린다)

### `check_language_keys.py`

```powershell
python tools/check_language_keys.py
```

- **검사**: `resources/languages/en.json`과 `ko.json`의 키 집합이 같은지, `[TODO]`가 남아
  있는지, 코드에서 쓰는 `get_text("...")` 리터럴 키가 en.json에 있는지.
- **exit 0 = ** 두 언어 파일의 키가 일치하고 `[TODO]`가 없으며, 정적으로 확인 가능한
  키가 모두 존재함.
- **덮지 못하는 것**: 동적 키(`get_text(variable)`)는 판정할 수 없어 WARN으로만 나온다.
  현재 8곳이 이에 해당하며, 이 경고가 있다고 실패가 아니다. **번역 품질도 보지 않는다.**

### `check_task_boards.py`

```powershell
python tools/check_task_boards.py
```

- **검사**: `tasks/S-0xx-*.md`의 `- Status:`와 `tasks/README.md` 표의 상태가 일치하는지,
  한 보드 안에 같은 ID가 다른 상태로 두 번 나오는지, 미등재·유령 행이 있는지.
- **exit 0 = ** 과거 S-xxx 태스크의 상태 기록이 두 소스에서 일치함.
- **덮지 못하는 것**: **루트 `Task.MD`의 내용 정합은 보지 않는다.** 인덱스 정합성만 본다.
  실제로 2026-09-01에 `Task.MD` 12번 하위 14건이 전부 `[ ]`였으나 13건이 이미 병합된
  상태였고, 이 검사는 그것을 잡지 못했다.

### `manage_language_keys.py`

```powershell
python tools/manage_language_keys.py
```

- **동작**: en.json 기준으로 ko.json의 누락 키에 `[TODO]` 템플릿을 만들고 양쪽을 정렬·저장.
- **쓰기 도구다.** 실행하면 두 파일을 덮어쓴다.
- **형식은 저장된 파일이 정본**이다(2칸 들여쓰기 + 끝 개행). 도구가 다른 형식으로
  저장하면 키 하나를 추가할 때마다 파일 전체가 재포맷되어 diff가 노이즈로 덮인다.
  이 일치는 `tests/test_language_tool_format.py`가 고정한다 (PR #26).

---

## 벤치마크 / 측정 도구

수치를 문서에 인용하려면 **어떤 명령으로 얻었는지** 함께 적는다 (`RULES.md` §11).

| 도구 | 무엇을 재는가 |
|---|---|
| `benchmark.py` | `RingBuffer`/`ThreadSafeQueue` 등 core 자료구조 처리량 (ops/s) |
| `runtime_benchmark.py` | RX pipeline + `ConnectionWorker` mixed RX/TX 런타임 |
| `serial_loop_benchmark.py` | Serial worker I/O 루프 대기 전략 비교 |
| `rx_view_benchmark.py`, `rx_view_batch_matrix.py` | RX 로그 뷰 렌더/배치 조합 측정 |
| `ux_capture.py` | 테마 × 언어 × 창 크기 조합 캡처. **offscreen은 폰트를 렌더하지 않아 텍스트가 공백으로 나온다 — 네이티브에서 실행한다** |

기준선 문서는 `doc/benchmarks/`에 있다.

---

## 보조 도구

| 도구 | 용도 |
|---|---|
| `chatlog.py` | 세션 대화 로그 append/tail. 읽기는 반드시 `tail` |
| `analysis/` | 일회성 분석 스크립트 모음 |

---

## `tools/oneoff/`

커밋·PR·문서에 **인용된 수치를 만든** 1회성 스크립트를 보존한다. 게이트가 아니며 CI가
돌리지 않는다. 규약과 목록은 `tools/oneoff/README.md`.
