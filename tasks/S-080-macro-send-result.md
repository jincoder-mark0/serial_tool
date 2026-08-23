# S-080 — 매크로 스텝 판정을 실제 전송 결과에 연결

- Status: DONE (2026-08-23 — 상위 직접 수행. pytest 514 passed, ruff 0건)
- Recommended model: **상위 전용** (계층 간 계약 변경 판단 필요)
- 선행: 없음
- Skills to load: task-done
- 근거: 사용자 지시 "전체 기능 설계에 결함은 없는지 다시 살펴보세요" (2026-08-23)

## 목적 (Why) — 도구의 핵심 기능이 거짓을 보고했다

포트를 **하나도 열지 않고** 매크로를 돌린 실측 결과:

```
연결된 포트 수: 0
스텝 시작 1 / 성공보고 1 / 실패보고 0
매크로 에러 이벤트 0건
실제 전송 0건
```

실행 루프가 `send_requested.emit()` — 반환값 없는 fire-and-forget 시그널 — 로
전송을 요청하고 결과를 기다리지 않은 채 스텝을 성공으로 넘겼다.
`ConnectionController.send_data()`도 `None`을 반환해 실패를 에러 이벤트로만 알렸다.

파장이 컸다:

- **`stop_on_error`가 전송 실패에 무력**했다. `expect` 패턴이 걸린 행에서만 실패할 수
  있으니, expect 없는 매크로는 원리적으로 실패할 수 없었다.
- 브로드캐스트에서 일부 포트만 조용히 실패해도 알 수 없었다. `send_broadcast_data`는
  워커가 실행 중이기만 하면 `sent_any = True`로 두고 수락 여부를 보지 않았다.
- 케이블이 빠져도 UI는 초록 성공 표시를 계속 냈다.

## 수행 결과

| 파일 | 변경 |
|---|---|
| `model/connection_controller.py` | `send_data`/`send_broadcast_data`/`send_data_to_all`이 bool 반환. 브로드캐스트는 **대상 전부 수락**을 성공으로 본다 |
| `common/dtos.py` | `MacroSendResult` DTO 신설 (성공 여부·사유·전송 바이트) |
| `presenter/main_presenter.py` | `deliver_macro_command()` — 결과를 돌려주는 전송, 위젯 미접근. `show_local_echo()` 분리 |
| `model/macro_runner.py` | `set_send_handler()` 주입, `_send()` 헬퍼, 스텝 판정을 결과에 연결 |

수정 후 같은 조건: **성공보고 0 / 실패보고 1 / 에러 이벤트 1건**.

## 설계 판단 — 왜 시그널로 결과를 되받지 않았나

`Qt.BlockingQueuedConnection`으로 결과를 받는 안을 먼저 검토했으나 **확실한 교착**이다:

- `MacroRunner.stop()`은 메인 스레드에서 `self.wait()`로 매크로 스레드를 기다린다.
- 매크로 스레드가 메인 스레드를 기다리면 서로를 기다린다.

그래서 핸들러를 **매크로 스레드에서 동기 호출**한다. 안전한 이유:

- `ConnectionWorker.send_data()`는 뮤텍스+큐로 스레드 안전하고 이미 bool을 반환한다.
- 핸들러는 위젯을 만지지 않는다 — Local Echo는 메인 스레드 슬롯에 남겼다.

## 검증

파괴 시험 (전송 결과를 무시하도록 되돌렸을 때): `tests/test_macro_send_result.py` 5개 전부 실패.

기존 테스트 2건도 옛 계약을 관찰하고 있어 함께 고쳤다:
`test_macro_start_and_signal`(시그널 → 핸들러 관찰), `test_macro_pause_resume`(핸들러
미등록 시 첫 스텝에서 멈추므로 핸들러 등록 추가).

## 실기기 미검증

전송 실패 판정 자체는 Mock/LOOPBACK으로 검증했다. **실제 시리얼 포트에서 케이블을
뽑았을 때** `send_data`가 False를 반환하는지는 미검증 — pyserial의 write 실패가
워커 큐 수락 단계까지 전파되는지는 실기기 확인이 필요하다.
