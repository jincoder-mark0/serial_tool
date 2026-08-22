"""
S-042 조용한 실패 회귀 테스트 모듈

(1) 수동 전송(및 Auto Tx) 실패가 사용자에게 표면화되는지,
(2) 매크로 종료 알림(Qt 시그널/EventBus 이벤트)이 정상/수동 종료 모두 정확히
    1회만 발행되는지를 검증합니다.

## WHY
* `presenter/manual_control_presenter.py`의 `_process_and_send()` 세 실패 경로
  (HEX 파싱 오류/브로드캐스트 대상 없음/미연결)가 로그만 남기고 호출부에 알리지
  않던 회귀를 고정
* `model/macro_runner.py`의 `stop()`/`run()`이 각각 `macro_finished`를 발행해
  수동 정지 시 2회 중복되고, 정상 종료 시 `EventTopics.MACRO_FINISHED`가 전혀
  발행되지 않던 회귀를 고정

## WHAT
* ① 잘못된 HEX 전송 시도 → `send_error` 시그널(사용자 알림 경로) 발행 검증
* ② 미연결 상태 전송 → `send_error` 시그널 발행 검증
* ③ 매크로 정상 종료(루프 소진) 시 `EventTopics.MACRO_FINISHED`가 정확히 1회
* ④ 매크로 수동 정지(`stop()`) 시 `macro_finished` 시그널이 정확히 1회(중복 아님)
* (보강) Auto Tx 반복 실패가 연속 실패 스트릭당 1회만 알림을 발행하는지
  (알림 폭주 방지 방식 검증)

## HOW
* Mock Panel/ConnectionController로 ManualControlPresenter를 격리 테스트
* 실제 QThread(MacroRunner)를 짧은 지연으로 구동하고 `qtbot.waitSignal`로
  스레드 종료를 동기적으로 대기

pytest tests/test_silent_failures.py -v
"""
from unittest.mock import MagicMock

from common.constants import EventTopics
from common.dtos import MacroEntry, ManualCommand
from core.event_bus import event_bus
from model.macro_runner import MacroRunner
from presenter.manual_control_presenter import ManualControlPresenter


# =============================================================================
# 1. 수동 전송 실패 표면화 (Silent Failure #1)
# =============================================================================

def _make_presenter(controller: MagicMock, *, hex_mode=False, broadcast=False,
                     text="ZZ") -> tuple[ManualControlPresenter, MagicMock]:
    """
    수동 전송 실패 테스트용 Presenter/Panel Mock을 생성합니다.

    Args:
        controller (MagicMock): ConnectionController Mock.
        hex_mode (bool): HEX 모드 여부.
        broadcast (bool): 브로드캐스트 모드 여부.
        text (str): 입력 커맨드 텍스트.

    Returns:
        tuple[ManualControlPresenter, MagicMock]: (Presenter, Panel Mock)
    """
    panel = MagicMock()
    panel.get_input_text.return_value = text
    panel.is_hex_mode.return_value = hex_mode
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = broadcast

    presenter = ManualControlPresenter(
        panel=panel,
        connection_controller=controller,
        local_echo_callback=MagicMock(),
        get_active_port_callback=lambda: "COM1",
    )
    return presenter, panel


class TestManualSendFailureSurfacing:
    """수동 전송 실패가 `send_error` 시그널로 표면화되는지 검증하는 테스트 클래스."""

    def test_invalid_hex_input_emits_send_error(self, qapp):
        """
        ① 잘못된 HEX 입력으로 전송 시도 시 `send_error`(사용자 알림 경로)가
        호출되는지 검증합니다. (재현: HEX 모드에서 "ZZ" 입력 후 Send)
        """
        # GIVEN
        controller = MagicMock()
        presenter, _ = _make_presenter(controller, hex_mode=True, text="ZZ")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        # WHEN
        presenter.on_send_requested()

        # THEN: 전송은 이루어지지 않고, 알림 경로가 정확히 1회 호출되어야 함
        controller.send_data.assert_not_called()
        error_spy.assert_called_once()
        title, message, show_dialog = error_spy.call_args[0]
        assert title  # 언어 키를 통한 제목이 비어있지 않아야 함
        assert message  # 사유를 알 수 있는 메시지
        # 수동 단발 전송 실패는 다이얼로그까지 표면화 (매크로 구조적 에러와 동일 관례)
        assert show_dialog is True

    def test_disconnected_port_emits_send_error(self, qapp):
        """
        ② 미연결 상태에서 전송 시도 시 `send_error`가 호출되는지 검증합니다.
        """
        # GIVEN: 포트가 열려있지 않음
        controller = MagicMock()
        controller.is_connection_open.return_value = False
        presenter, _ = _make_presenter(controller, text="TEST")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        # WHEN
        presenter.on_send_requested()

        # THEN
        controller.send_data.assert_not_called()
        error_spy.assert_called_once()
        _title, message, show_dialog = error_spy.call_args[0]
        assert message
        assert show_dialog is True

    def test_broadcast_no_active_ports_emits_send_error(self, qapp):
        """
        (보강) 브로드캐스트 모드인데 활성 포트가 하나도 없는 경우에도
        동일하게 `send_error`가 호출되는지 검증합니다 (세 번째 실패 경로).
        """
        # GIVEN
        controller = MagicMock()
        controller.has_active_broadcast_ports.return_value = False
        presenter, _ = _make_presenter(controller, broadcast=True, text="TEST")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        # WHEN
        presenter.on_send_requested()

        # THEN
        controller.send_broadcast_data.assert_not_called()
        error_spy.assert_called_once()
        _title, message, show_dialog = error_spy.call_args[0]
        assert message
        assert show_dialog is True

    def test_valid_send_does_not_emit_send_error(self, qapp):
        """
        회귀 방지: 정상 전송 시에는 `send_error`가 호출되지 않아야 합니다.
        """
        # GIVEN
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        presenter, _ = _make_presenter(controller, text="OK")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        # WHEN
        presenter.on_send_requested()

        # THEN
        controller.send_data.assert_called_once()
        error_spy.assert_not_called()


class TestAutoTxFailureDoesNotFlood:
    """
    Auto Tx 반복 실패가 알림 폭주를 만들지 않는지 검증하는 테스트 클래스.

    채택 방식: 연속 실패 스트릭의 첫 실패에서만 `send_error(show_dialog=False)`를
    발행하고, 이후 연속 실패는 침묵한다. 성공이 한 번이라도 발생하면 스트릭이
    해제되어 다음 실패에서 다시 알린다.
    """

    def test_repeated_auto_tx_failure_notifies_once_without_dialog(self, qapp):
        """
        Auto Tx가 동일한 사유로 연속 3회 실패해도 `send_error`는 1회만 발행되고,
        그마저도 다이얼로그 없이(show_dialog=False) 상태바 수준으로만 알려야 합니다.
        """
        # GIVEN: 포트 미연결 상태 (매 tick마다 실패)
        controller = MagicMock()
        controller.is_connection_open.return_value = False
        presenter, _ = _make_presenter(controller, text="AT")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        # WHEN: Auto Tx 반복 경로를 3회 연속 호출 (스케줄러 tick 시뮬레이션)
        command = ManualCommand(command="AT")
        presenter._on_auto_tx_send_requested(command)
        presenter._on_auto_tx_send_requested(command)
        presenter._on_auto_tx_send_requested(command)

        # THEN: 알림 폭주 없이 정확히 1회만 발행, 다이얼로그는 뜨지 않음
        error_spy.assert_called_once()
        _title, _message, show_dialog = error_spy.call_args[0]
        assert show_dialog is False

    def test_auto_tx_failure_notifies_again_after_recovering(self, qapp):
        """
        실패 스트릭 중 성공이 발생하면 스트릭이 해제되어, 다음 실패에서
        다시(edge-trigger) 알림이 발행되는지 검증합니다.
        """
        # GIVEN
        controller = MagicMock()
        presenter, _ = _make_presenter(controller, text="AT")
        error_spy = MagicMock()
        presenter.send_error.connect(error_spy)

        command = ManualCommand(command="AT")

        # WHEN: 실패 -> 성공 -> 실패
        controller.is_connection_open.return_value = False
        presenter._on_auto_tx_send_requested(command)  # 실패 1 (알림)

        controller.is_connection_open.return_value = True
        presenter._on_auto_tx_send_requested(command)  # 성공 (스트릭 해제)

        controller.is_connection_open.return_value = False
        presenter._on_auto_tx_send_requested(command)  # 실패 2 (다시 알림)

        # THEN
        assert error_spy.call_count == 2


# =============================================================================
# 2. 매크로 종료 알림 정합 (Silent Failure #2)
# =============================================================================

class TestMacroFinishedNotificationConsistency:
    """
    매크로 종료 알림(Qt 시그널/EventBus 이벤트)이 정상/수동 종료 모두
    정확히 1회만 발행되는지 검증하는 테스트 클래스 (RULES §2: 시작/정상 종료/
    강제 종료 3경로 테스트 중 정상 종료·강제(수동) 종료 2경로를 다룬다).
    """

    def test_normal_completion_publishes_macro_finished_event_once(self, qapp, qtbot):
        """
        ③ 매크로가 정상적으로 루프를 소진하고 종료할 때 `EventTopics.MACRO_FINISHED`
        이벤트가 정확히 1회 발행되는지 검증합니다 (기존에는 전혀 발행되지 않던 회귀).
        """
        # GIVEN: 아주 짧은 단일 엔트리, 1회 루프
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=0)])
        runner.send_requested.connect(MagicMock())  # 실제 전송은 필요 없음 (Sink)

        event_spy = MagicMock()
        event_bus.subscribe(EventTopics.MACRO_FINISHED, event_spy)

        # WHEN: 시작 후 자연 종료(정상 루프 소진)까지 대기
        with qtbot.waitSignal(runner.macro_finished, timeout=3000):
            runner.start(loop_count=1, interval_ms=0)

        # EventBus 디스패치는 워커 스레드 -> 메인 스레드 큐잉 전달이므로
        # 이벤트 루프를 반복 펌핑하여 큐가 비워질 때까지 기다린다.
        qtbot.waitUntil(lambda: event_spy.call_count == 1, timeout=1000)

        # THEN: 정확히 1회 발행 (추가 대기 후에도 늘지 않아야 함)
        qapp.processEvents()
        assert event_spy.call_count == 1

        event_bus.unsubscribe(EventTopics.MACRO_FINISHED, event_spy)

    def test_manual_stop_emits_macro_finished_signal_exactly_once(self, qapp, qtbot):
        """
        ④ 매크로 실행 중 `stop()`으로 수동 정지했을 때 `macro_finished` Qt 시그널이
        정확히 1회만 발생하는지 검증합니다 (기존에는 `run()`과 `stop()`이 각각
        발행해 2회 중복되던 회귀). 교착 회귀 방지를 위해 `stop()` 호출 자체가
        타임아웃 없이 반환되는지도 함께 확인한다 (내부에서 `wait()` 블로킹).
        """
        # GIVEN: 충분히 긴 지연을 가진 엔트리로, stop() 호출 시점에 대기 중이도록 구성
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])
        runner.send_requested.connect(MagicMock())

        finished_spy = MagicMock()
        runner.macro_finished.connect(finished_spy)

        # WHEN: 시작 후 진입 대기, 곧바로 수동 정지
        runner.start(loop_count=0, interval_ms=0)
        qtbot.wait(100)  # 스레드가 sleep 구간에 진입할 시간 확보

        runner.stop()  # 내부적으로 wait()로 블로킹 — 교착 없이 반환되어야 함

        # macro_finished는 워커 스레드에서 emit되고 Runner(QObject)의 스레드
        # 소속은 메인 스레드이므로 Cross-thread Queued 전달이다.
        # wait()는 이벤트 루프를 펌핑하지 않으므로 큐 처리를 위해 대기가 필요하다.
        qtbot.waitUntil(lambda: finished_spy.call_count >= 1, timeout=1000)

        # THEN: 정확히 1회만 발생 (중복 아님) — 추가 펌핑 후에도 늘지 않아야 함
        qapp.processEvents()
        assert finished_spy.call_count == 1
        assert not runner.isRunning()

    def test_start_then_immediate_stop_does_not_deadlock(self, qapp, qtbot):
        """
        (경로 보강: 시작 직후 즉시 강제 종료) start() 직후 스레드가 본격적으로
        루프에 진입하기 전에 stop()을 호출해도 교착 없이 반환되고, 종료 시그널이
        정확히 1회만 발행되는지 검증합니다 (RULES §2 스레드 규율의 '시작' 경로).
        """
        # GIVEN
        runner = MacroRunner()
        runner.load_macro([MacroEntry(enabled=True, command="CMD", delay_ms=5000)])
        runner.send_requested.connect(MagicMock())

        finished_spy = MagicMock()
        runner.macro_finished.connect(finished_spy)

        # WHEN: 시작 직후(대기 없이) 바로 정지
        runner.start(loop_count=0, interval_ms=0)
        runner.stop()

        # THEN: 교착 없이 반환되었고, 정확히 1회만 발행 (Cross-thread Queued 전달 대기)
        qtbot.waitUntil(lambda: finished_spy.call_count >= 1, timeout=1000)
        qapp.processEvents()
        assert finished_spy.call_count == 1
        assert not runner.isRunning()
