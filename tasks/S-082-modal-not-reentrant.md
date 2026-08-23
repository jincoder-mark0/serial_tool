# S-082 — 모달 알림 재진입 제거

- Status: DONE (2026-08-23 — 상위 직접 수행. pytest 519 passed, ruff 0건)
- Recommended model: **상위 전용**
- 선행: 없음
- Skills to load: task-done
- 근거: 사용자 지시 "전체 기능 설계에 결함은 없는지 다시 살펴보세요" (2026-08-23)

## 목적 (Why)

포트를 닫으면 이런 사슬이 돌았다:

```
close_connection()          ← self.workers를 아직 정리하는 중
 → on_worker_closed() → EventBus.publish()
 → [메인 스레드 발행은 동기 재진입이다 — 실측 확인]
 → EventRouter._on_port_closed → MainPresenter.on_port_closed
 → _notify_macro_error → QMessageBox.warning()
```

워커를 정리하는 함수의 스택 위에서 모달이 열린다. 모달은 중첩 이벤트 루프를
돌리므로, 그동안 밀려 있던 이벤트가 끼어들어 정리 중이던 객체가 발밑에서 파괴될 수
있다.

근본 원인은 **EventBus의 의미가 발행 스레드에 따라 갈린다**는 점이다. 실측:

| 발행 위치 | 동작 |
|---|---|
| 메인 스레드 | **동기 재진입 호출** |
| 워커 스레드 | 비동기(큐) |

같은 `publish()` 한 줄인데 의미가 다르다.

## 수행 결과

`MainWindow.show_alert_message`와 `PortPresenter`의 에러 모달을 `QTimer.singleShot(0, …)`으로
미뤄, 현재 호출 스택이 풀린 뒤에 열리게 했다. 알림은 반환값을 쓰는 호출자가 없는
순수 통지이므로 의미가 바뀌지 않는다.

## 정정 — 크래시 원인 귀속이 틀렸다

이 경로가 offscreen에서 **8/8 access violation**으로 죽는 것을 관찰하고 처음엔
재진입 탓으로 봤다. **틀렸다.**

`QApplication` + `QWidget` + `QMessageBox.warning()`만으로도 offscreen에서는 똑같이
죽는다 — SerialTool 코드가 하나도 없는 상태에서 확인했다. Qt offscreen 플랫폼의
한계이지 이 앱의 결함이 아니다. 네이티브는 0/5로 죽지 않았고, 이 수정 후에도
offscreen은 7/8로 여전히 죽는다.

그래서 이 태스크는 **크래시를 고쳤다고 주장하지 않는다.** 없앤 것은 재진입뿐이다.

실무적 함의 하나: **헤드리스/CI에서 모달에 도달하는 테스트는 프로세스를 죽인다.**
현재 519개 테스트 중 실제 모달을 여는 것은 없다.

## 검증

| 되살린 결함 | 실패한 테스트 |
|---|---|
| 즉시 표시로 원복 | `test_alert_is_not_opened_inside_the_caller_stack` |
| 아예 띄우지 않음 | `test_alert_is_still_shown_after_the_event_loop_turns` |

진짜 모달은 띄우지 않는다(offscreen에서 죽으므로). `QMessageBox` 호출을 스파이로
갈아 끼워 **언제 불리는지**만 본다.

## 남은 사항 (보고)

`presenter/port_presenter.py`가 `QMessageBox`를 직접 import해 View 위젯을 부모로
넘긴다 — 프레젠터가 위젯 종류를 아는 계층 냄새다. 이번 결함과 별개이고 View 파사드
경유로 바꾸려면 배선 변경이 필요해 손대지 않았다.
