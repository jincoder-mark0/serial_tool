# S-042 — [P1] 조용한 실패 2건 (수동 전송 실패 무통보 + 매크로 종료 알림 뒤바뀜)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: S-039, S-040 커밋 후
- Skills to load: task-done, lang-keys
- 근거: `doc/refactor_audit_20260822.md` B-4, C-1

## 목적 (Why)

**(1) 수동 전송 실패가 사용자에게 전혀 안 알려진다**:
`presenter/manual_control_presenter.py`의 `_process_and_send()`는 세 실패 경로
— HEX 파싱 오류(`CommandProcessor`의 `ValueError`), 브로드캐스트 대상 없음, 포트 미연결 —
에서 전부 로그만 남기고 `False`를 반환하는데, 호출부는 **반환값을 쓰지 않는다**
("View에 에러 알림 필요 시 추가 구현" 주석이 미구현 상태). 매크로 경로는 QMessageBox로
알리므로 **비대칭**이다. Auto Tx(S-006) 경로도 같은 함수를 타므로 함께 조용히 실패한다.

재현: HEX 모드에서 `"ZZ"`(잘못된 문자) 또는 홀수 자리 HEX 입력 후 Send → 화면 무반응,
사용자는 전송된 줄 안다.

**(2) 매크로 종료 알림이 뒤바뀜**: `model/macro_runner.py`의 `stop()`과 `run()`이 각각
`macro_finished`를 emit해 **수동 정지 시 2회 발생**(UI 이중 리셋). 반대로 **정상 종료
(루프 소진)에서는 `EventTopics.MACRO_FINISHED` 이벤트가 한 번도 발행되지 않아** 상태바에
"매크로 종료"가 뜨지 않는다 — 끝까지 실행하면 알림이 없고, 중간에 멈추면 알림이 있다.

## 확정 설계

1. **전송 실패 표면화** — `presenter/manual_control_presenter.py`:
   - `_process_and_send()`의 실패를 호출부가 사용자에게 알리도록 연결한다.
     표면화 수단은 **기존 관례를 따른다** — 매크로 경로(`presenter/main_presenter.py`의
     `_notify_macro_error` 등)가 쓰는 방식(상태바/다이얼로그)을 먼저 읽고 동일 관례를 재사용.
   - 실패 사유별로 사용자가 무엇을 고쳐야 하는지 알 수 있게 메시지를 구분한다
     (HEX 형식 오류 / 대상 포트 없음 / 미연결). **언어 키 경유**(lang-keys 절차).
   - Auto Tx 반복 중 실패가 매초 다이얼로그를 띄우지 않도록 주의 — 반복 경로에서는
     상태바·로그 수준으로 낮추거나 1회만 알리는 방식을 택하고 근거를 보고하라.
2. **매크로 종료 알림 정합** — `model/macro_runner.py`:
   - `macro_finished` Qt 시그널이 **한 번만** 발행되도록 정리(정지/정상 종료 모두 1회).
   - `EventTopics.MACRO_FINISHED` 이벤트가 **정상 종료에서도 발행**되도록 한다.
   - 두 채널의 역할은 감사 판정(C-6)대로 유지: Qt 시그널 = 소유 Presenter 직결,
     EventBus = 계층 건너뛰는 팬아웃. 어느 한쪽을 없애지 말 것.
   - `stop()`이 `wait()` 후 emit하는 현재 구조를 바꿀 때 **교착이 생기지 않는지** 확인
     (RULES §2 스레드 규율: 시작·정상 종료·강제 종료 3경로 테스트).

## 검증 방법

- 테스트 신설/보강 `tests/test_silent_failures.py`:
  ① 잘못된 HEX로 전송 시도 → 사용자 알림 경로가 호출되는지(mock 검증).
  ② 미연결 상태 전송 → 알림 경로 호출.
  ③ 매크로 정상 종료 시 `MACRO_FINISHED` 이벤트가 정확히 1회 발행되는지.
  ④ 매크로 수동 정지 시 `macro_finished` 시그널이 정확히 1회인지(중복 아님).
- 전체 pytest(offscreen) + `check_language_keys` + 캡처 1회(dark/ko) 후
  **`git checkout -- resources/configs/settings.json`**.

## Acceptance criteria (DoD)

- [ ] 세 실패 경로 모두 사용자에게 사유가 보인다 (테스트로 고정, 언어 키 경유).
- [ ] Auto Tx 반복 실패가 알림 폭주를 만들지 않는다 (채택 방식 보고).
- [ ] 매크로 종료 알림이 정상/수동 종료 모두 정확히 1회.
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
