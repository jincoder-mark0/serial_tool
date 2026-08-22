# S-006 — AutoTxScheduler (주기적 자동 전송)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. model/auto_tx.py(QTimer,
  View 무의존), 수동 전송 가공 로직을 _process_and_send로 추출해 공유(중복 0), Auto UI+
  언어 키 3종, 상태 저장/복원 배선. 테스트 9건 → 기준선 109. 에스컬레이션 2건 승인:
  패널 facade 릴레이(형제 기능과 동일 LoD 패턴), main_presenter/lifecycle의 상태 직렬화
  필드 추가(재시작 복원 DoD에 필수). 실기기 전송은 미검증)
- Recommended model: **하위(Sonnet) 가능** (Steps에 설계가 확정되어 있음 — 벗어나면 중단·보고)
- 선행: 없음
- Skills to load: task-done, lang-keys

## 목적 (Why)

수동 Command를 일정 주기로 반복 전송하는 기능(폴링 명령 자동화)이 계획에만 있고
구현이 없다 (`doc/implementation_plan.md:311`, `doc/task.md:210`). 매크로(MacroRunner)는
리스트 순차 실행용이라, "한 명령을 N ms마다" 용도로는 무겁다.

## 배경 (자족적 설명)

- 수동 전송 흐름: View(ManualCtrlWidget) → `ManualCommand` DTO(`common/dtos.py:213` —
  command/hex_mode/prefix_enabled/suffix_enabled/local_echo_enabled/broadcast_enabled) →
  `presenter/manual_control_presenter.py:169-183`이 prefix/suffix·hex 가공
  (`:152` `CommandProcessor.process_command`) 후 broadcast면 `send_broadcast_data`, 아니면 `send_data` 호출.
- 유사 선례 (반드시 이 패턴을 따를 것):
  - `model/macro_runner.py:114` `start(loop_count=1, interval_ms=0, ...)` — **loop_count=0 = 무한**(`:278`),
    `loop_progress(int, int)` 시그널(`:283`), `_interruptible_sleep`(`:397`, QWaitCondition).
  - `common/dtos.py:330` `MacroRepeatOption(max_runs=0, interval_ms=0, ...)` — 옵션 DTO 형식.
  - 상수: `common/constants.py:162` `DEFAULT_MACRO_INTERVAL_MS = 1000`.
- 아키텍처 제약(CLAUDE.md): Model은 View를 모른다. 계층 간 DTO만. 새 상수는 `common/constants.py`.
  새 EventBus 토픽은 `EventTopics`에 등록.

## 확정 설계 (이대로 구현 — 변경 필요 시 중단·보고)

- **새 파일 `model/auto_tx.py`** — `class AutoTxScheduler(QObject)`:
  - UI 스레드 상주 `QTimer` 기반 (별도 스레드 불필요 — 실제 I/O는 ConnectionWorker가 처리).
    정밀 타이밍이 목적이 아니므로 QThread를 만들지 않는다.
  - 공개 API: `start(self, command: ManualCommand, interval_ms: int, max_runs: int = 0) -> None`
    (max_runs=0 무한), `stop() -> None`, `is_running() -> bool` (property).
  - 시그널: `send_requested = pyqtSignal(object)` (ManualCommand — MacroRunner `:63`과 동일 패턴),
    `progress = pyqtSignal(int, int)` (current, total), `finished = pyqtSignal()`.
  - 동작: start 시 즉시 1회 emit 후 타이머 시작. max_runs 도달 시 자동 stop + finished.
    start 중복 호출은 기존 타이머 stop 후 재시작. interval 하한은
    `common/constants.py`에 `MIN_AUTO_TX_INTERVAL_MS: int = 50` 신설(문서화: 과도한 폴링으로
    TX 큐 포화 방지)해 clamp.
- **Presenter 배선** — `presenter/manual_control_presenter.py`:
  - AutoTxScheduler 인스턴스 생성, `send_requested`를 기존 수동 전송 처리 메서드
    (prefix/suffix 가공 → send 분기, `:147-183` 경로)에 연결해 **가공 로직을 재사용**한다.
    가공 코드를 복사하지 말 것 — 필요하면 기존 메서드를 private 헬퍼로 추출해 공용화.
  - 포트가 모두 닫히면(연결 종료 이벤트 수신 시) 자동 stop.
- **View** — ManualControl 위젯(`view/widgets/` 안 manual control 관련 파일)에 최소 UI:
  Auto 체크박스(또는 토글 버튼) + interval 입력(SmartNumberEdit 계열 기존 커스텀 위젯 재사용) +
  시그널 `auto_tx_toggled(bool)` emit만. **View에 스케줄 로직 금지** (Passive View).
  라벨·툴팁 문자열은 언어 키로 (lang-keys 스킬 절차, 키 예: `manual_chk_auto_tx`,
  `manual_input_auto_interval`).
- **설정 유지**: interval 값은 `ConfigKeys.MANUAL_CONTROL_STATE`(`"manual_control"`) 저장 구조에
  편승 — 기존 manual_control 상태 저장/복원 코드가 있는 곳에 필드 추가.

## Steps

1. `common/constants.py`에 `MIN_AUTO_TX_INTERVAL_MS = 50` 추가 (주석으로 근거 한 줄).
2. `model/auto_tx.py` 작성 (위 설계 그대로, 모듈 헤더는 WHY/WHAT/HOW 관례 —
   기존 `model/macro_runner.py` 헤더 형식 참고, 한국어 주석·타입 힌트 필수).
3. `tests/test_model.py` 또는 신규 `tests/test_auto_tx.py`에 단위 테스트 4건 이상:
   시작 즉시 1회 발신 / max_runs 도달 시 finished / stop 후 미발신 / interval clamp.
   (QTimer 테스트는 `qapp` fixture(`tests/conftest.py:49`) + `QTest.qWait` 또는
   `pytest-qt`의 `qtbot.waitSignal` 사용 — pytest-qt는 requirements.txt에 이미 있음.)
4. Presenter 배선 + 포트 전체 종료 시 자동 stop.
5. View 최소 UI + 언어 키 (lang-keys 스킬 절차 완주: en → manage → ko 번역 → check).
6. 상태 저장/복원 필드 추가.
7. 전체 검증 후 task-done 절차.

## Acceptance criteria (DoD)

- [ ] `model/auto_tx.py` 신설, View import 없음 (MVP 준수).
- [ ] 수동 전송 가공 로직(prefix/suffix/hex) 재사용 — 중복 구현 없음.
- [ ] 단위 테스트 4건 이상 추가, 전체 pytest 통과 (기준선 85 + 신규).
- [ ] 언어 키 en/ko 완비, `tools/check_language_keys.py` 통과.
- [ ] interval 설정이 재시작 후 복원된다 (상태 저장 테스트 또는 수동 확인 보고).
- [ ] 실기기 전송 확인은 불가 항목 — "실기기 미검증"으로 보고.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest tests/test_auto_tx.py -q
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\check_language_keys.py
```
