# tools/oneoff — 결론의 근거가 된 1회성 스크립트

여기 있는 스크립트는 **커밋 메시지·PR·`doc/CHANGELOG.md`·`Task.MD`에 인용된 수치를 만든 것**이다.
수치만 문서에 남기고 스크립트를 세션 스크래치에 두면, 그 수치는 **재현할 수 없는 주장**이 된다
(RULES.md §11).

## 규약

- **그때 돌린 그대로 둔다.** 리팩토링·일반화하지 않는다. 값은 재현 가능성이지 코드 품질이 아니다.
- 상단 주석 4줄이 필수다: 무엇을 / 언제 / 무엇을 증명했는지 / 실행법.
- 승격하면서 바꾸는 것은 **`sys.path` 한 줄뿐**이다(하드코딩 절대경로 → 저장소 상대경로).
  그 외 본문을 손대면 "그때 그 결과"가 아니게 된다.
- 여기 스크립트는 게이트가 아니다. CI가 돌리지 않고, 회귀 방지는 `tests/`가 맡는다.

## 목록

| 스크립트 | 증명한 것 | 인용된 곳 |
|---|---|---|
| `probe_right_panel_geometry.py` | 우측 패널을 숨겨도 창 폭이 3838로 유지되고 좌측이 3244→3828로 늘어남 | PR #19, `doc/CHANGELOG.md`, `tests/test_right_panel_toggle_roundtrip.py` |
| `probe_layout_invalidation_strategies.py` | 레이아웃 제약 재계산 전략 A/B/C 비교 — 전체 사슬만 동작 | PR #19 |
| `repro_dequeued_transaction_loss.py` | 큐에서 꺼낸 직후 stop()이 오면 request 1건이 통지 없이 사라짐 | PR #19, S-085 |
| `repro_defaults_contamination.py` | 사용자 설정 로드가 모듈 전역 기본값을 덮어씀 / 손상 복구가 직전 사용자 값을 되살림 | PR #19, `doc/CHANGELOG.md` |
| `check_defaults_leak_after_suite.py` | 전체 스위트 1회 실행만으로 `DEFAULT_MANUAL_CONTROL_STATE`가 변조됨 | PR #19, `doc/CHANGELOG.md` |

모두 2026-09-01~02 세션의 코드 점검에서 나왔다. 지금은 각각에 대응하는 회귀 테스트가
`tests/`에 있으므로, 이 스크립트들은 **당시 판정의 근거**로만 보존한다.

## 지금 돌리면 결함이 재현되지 않는다 — 정상이다

결함은 모두 수정됐으므로 현재 `main`에서 실행하면 **고쳐진 동작**이 나온다.

```text
repro_dequeued_transaction_loss    LOST request ids: []          (당시: [1])
repro_defaults_contamination       공유 여부: False               (당시: True)
probe_right_panel_geometry         숨김: 창 3838 -> 3254          (당시: 3838 유지)
```

이 스크립트의 값은 "지금 재현된다"가 아니라 **"그때 이 명령으로 이 수치를 얻었다"**를
남기는 데 있다. 당시 동작을 보려면 해당 수정 커밋 이전으로 checkout해서 돌린다.
