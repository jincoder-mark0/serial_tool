# S-040 — [P0] 포트 탭을 닫아도 연결이 끊기지 않음 (좀비 연결)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: 없음
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` A-4, B-3

## 목적 (Why)

**재현**: ①COM3 연결 → ②탭 하나 더 추가(최소 탭 수 조건 통과용) → ③COM3 탭을 X로 닫기 →
④워커 스레드는 계속 실행되고 위젯은 시그널 람다가 참조를 붙잡아 잔존 → ⑤새 탭에서 COM3을
다시 열면 `is_connection_open("COM3")`이 True라 **"Connection is already open."** 에러.
UI 어디에도 그 탭이 없으므로 사용자는 **앱을 재시작하기 전까지 포트를 되찾을 수 없다**.

원인: `view/panels/port_tab_panel.py`의 `close_port_tab()`이 `removeTab()`만 호출하고,
`PortPresenter`는 탭 제거를 구독하지 않는다(저장소 전체에 탭 닫기→`close_connection()` 경로 없음).

**함께 고칠 것 (B-3)**: `ConnectionWorker.close_connection()`은 `transport.is_open()`일 때만
`connection_closed`를 emit한다. 포트 열기 자체가 실패하면 아무 시그널도 안 나가
`controller.workers[name]`에 죽은 워커가 남고, `has_active_connection`이 거짓 True가 되며
종료 시 "[COMx] Port closed"라는 오도하는 로그가 찍힌다(한 번도 연결된 적 없음).

## 확정 설계

1. **탭 닫기 → 연결 정리** (MVP 유지):
   - `PortTabPanel`은 탭이 닫힐 때 **시그널만 emit**한다(예: `port_tab_closed(str)` — 닫히는
     탭의 포트 이름 또는 식별자). View는 컨트롤러를 모른다 — 절대 규칙.
   - `PortPresenter`가 이 시그널을 구독해 `connection_controller.close_connection(name)`을
     호출한다. 닫는 탭이 미연결이면 무해하게 통과해야 한다.
   - 포트 이름을 얻는 방법은 현재 코드에서 확인해 결정하라(탭 위젯의 공개 API 우선;
     내부 위젯을 파고들지 말 것 — LoD). 적절한 공개 API가 없으면 **최소한의 파사드 메서드를
     패널에 추가**하고 그 근거를 보고.
2. **워커 종료 신호 누락** — `model/connection_worker.py`:
   - `close_connection()`이 `is_open()` 여부와 무관하게 종료를 알리도록 한다.
     기존 `connection_closed`의 의미(정상 연결 종료)를 흐리지 않도록, **열기 실패 경로에서도
     컨트롤러가 레지스트리를 정리할 수 있는 경로**를 보장하는 것이 목적이다.
     구현 선택(항상 emit vs 별도 시그널)은 `ConnectionController.on_worker_closed`의 현재
     동작을 읽고 판단해 근거와 함께 보고하라.
   - 주의: 이미 `error_occurred`가 발행되는 경로이므로 **에러 메시지가 중복되지 않게** 할 것.

## 검증 방법

- 회귀 테스트 신설 `tests/test_port_tab_cleanup.py`:
  ① LOOPBACK 연결 → 탭 닫기 시그널 발생 → `controller.is_connection_open()`이 False가 되고
     워커가 레지스트리에서 제거되는지.
  ② 존재하지 않는 포트로 연결 실패 → `has_active_connection`이 False이고 `workers`에 잔존이
     없는지 (B-3 회귀).
  ③ 미연결 탭 닫기가 예외 없이 통과하는지.
- 전체 pytest(offscreen, 기준선 139+신규) + 캡처 1회(dark/ko)로 UI 회귀 없음 확인
  (**캡처 후 `git checkout -- resources/configs/settings.json`**).

## Acceptance criteria (DoD)

- [ ] 탭을 닫으면 해당 연결이 정리되고 같은 포트를 곧바로 다시 열 수 있다 (테스트로 고정).
- [ ] 연결 실패 워커가 레지스트리에 남지 않는다 (테스트로 고정).
- [ ] View→Model 직접 호출 없음 (시그널 → Presenter → Controller 경로 유지).
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
