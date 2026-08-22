"""
AutoTxScheduler 및 배선(Presenter Wiring) 테스트 모듈

주기적 자동 전송(Auto Tx) 기능의 스케줄러 로직과, ManualControlPresenter로의
배선(토글 시작/정지, 포트 전체 종료 시 자동 정지)을 검증합니다.

## WHY
* QTimer 기반 반복 로직(즉시 1회 발신, max_runs 종료, clamp)의 정확성 보장
* Presenter 배선이 기존 수동 전송 가공 로직을 재사용하는지 회귀 방지

## WHAT
* AutoTxScheduler: 즉시 발신 / max_runs 종료 / stop 동작 / interval clamp / 재시작 테스트
* ManualControlPresenter: Auto Tx 토글 배선, 연결 종료 시 자동 정지 테스트

## HOW
* qapp 픽스처(session 범위 QApplication)로 QTimer 동작 환경 제공
* qtbot.waitSignal / qtbot.wait로 타이머 콜백 대기
* MagicMock으로 Panel/ConnectionController를 대체하여 Presenter 배선만 검증

pytest tests/test_auto_tx.py -v
"""
from unittest.mock import MagicMock

from model.auto_tx import AutoTxScheduler
from presenter.manual_control_presenter import ManualControlPresenter
from common.constants import MIN_AUTO_TX_INTERVAL_MS
from common.dtos import ManualCommand


# =============================================================================
# 1. AutoTxScheduler 단위 테스트
# =============================================================================

class TestAutoTxScheduler:
    """
    AutoTxScheduler의 시작/정지/반복/clamp 동작을 검증하는 테스트 클래스입니다.
    """

    def test_start_emits_immediately(self, qapp):
        """
        시작 즉시 1회 발신 테스트

        Logic:
            - Scheduler 생성 및 send_requested Spy 연결
            - start() 호출 (타이머 만료를 기다리지 않아도 즉시 발신되어야 함)
            - 전달된 DTO가 start()에 넘긴 command와 동일한지 확인
        """
        # GIVEN
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        # WHEN
        scheduler.start(command, interval_ms=5000, max_runs=0)

        # THEN: 타이머 만료 전에 이미 1회 발신되어야 함
        send_spy.assert_called_once_with(command)
        assert scheduler.is_running

        scheduler.stop()

    def test_max_runs_reached_stops_and_emits_finished(self, qapp, qtbot):
        """
        max_runs 도달 시 자동 정지 및 finished 시그널 발생 테스트

        Logic:
            - max_runs=2, interval_ms=MIN(50)으로 시작
            - finished 시그널을 최대 1초 대기
            - 발신 횟수가 정확히 2회이고 더 이상 실행 중이 아님을 확인
        """
        # GIVEN
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        # WHEN
        with qtbot.waitSignal(scheduler.finished, timeout=2000):
            scheduler.start(command, interval_ms=MIN_AUTO_TX_INTERVAL_MS, max_runs=2)

        # THEN
        assert send_spy.call_count == 2
        assert not scheduler.is_running

    def test_stop_prevents_further_emission(self, qapp, qtbot):
        """
        stop() 호출 후 추가 발신이 없는지 테스트

        Logic:
            - 무한 반복(max_runs=0)으로 시작 후 즉시 stop() 호출
            - 짧게 대기하여도 첫 즉시 발신(1회) 외 추가 발신이 없어야 함
        """
        # GIVEN
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command = ManualCommand(command="AT")

        # WHEN
        scheduler.start(command, interval_ms=MIN_AUTO_TX_INTERVAL_MS, max_runs=0)
        scheduler.stop()
        qtbot.wait(200)

        # THEN: 시작 시 즉시 발신된 1회만 존재해야 함
        assert send_spy.call_count == 1
        assert not scheduler.is_running

    def test_interval_is_clamped_to_minimum(self, qapp):
        """
        interval_ms가 하한(MIN_AUTO_TX_INTERVAL_MS) 미만이면 clamp되는지 테스트

        Logic:
            - interval_ms=1(하한 미만)로 시작
            - 내부 QTimer의 실제 interval이 MIN_AUTO_TX_INTERVAL_MS로 clamp되었는지 확인
        """
        # GIVEN
        scheduler = AutoTxScheduler()
        command = ManualCommand(command="AT")

        # WHEN
        scheduler.start(command, interval_ms=1, max_runs=0)

        # THEN
        assert scheduler._timer.interval() == MIN_AUTO_TX_INTERVAL_MS

        scheduler.stop()

    def test_restart_replaces_previous_command(self, qapp):
        """
        실행 중 재시작(중복 start 호출) 시 기존 타이머를 정지하고 새로 시작하는지 테스트

        Logic:
            - command1로 시작 후, 정지 없이 command2로 다시 start() 호출
            - 두 번째 호출도 즉시 발신되며, 최신 명령(command2)으로 교체되었는지 확인
        """
        # GIVEN
        scheduler = AutoTxScheduler()
        send_spy = MagicMock()
        scheduler.send_requested.connect(send_spy)
        command1 = ManualCommand(command="AT1")
        command2 = ManualCommand(command="AT2")

        # WHEN
        scheduler.start(command1, interval_ms=5000, max_runs=0)
        scheduler.start(command2, interval_ms=5000, max_runs=0)

        # THEN: 각 start() 호출마다 즉시 발신 -> 총 2회, 마지막은 command2
        assert send_spy.call_count == 2
        assert send_spy.call_args[0][0] is command2
        assert scheduler.is_running

        scheduler.stop()


# =============================================================================
# 2. ManualControlPresenter 배선 테스트
# =============================================================================

def _make_mock_panel(text: str = "AT", interval_ms: int = 200) -> MagicMock:
    """
    Auto Tx 배선 테스트용 Mock Panel을 생성합니다.

    Args:
        text (str): get_input_text()가 반환할 명령 텍스트.
        interval_ms (int): get_auto_tx_interval_ms()가 반환할 간격(ms).

    Returns:
        MagicMock: Panel Facade를 흉내내는 Mock 객체.
    """
    panel = MagicMock()
    panel.get_input_text.return_value = text
    panel.is_hex_mode.return_value = False
    panel.is_prefix_enabled.return_value = False
    panel.is_suffix_enabled.return_value = False
    panel.is_local_echo_enabled.return_value = False
    panel.is_broadcast_enabled.return_value = False
    panel.get_auto_tx_interval_ms.return_value = interval_ms
    return panel


class TestManualControlPresenterAutoTxWiring:
    """
    ManualControlPresenter의 Auto Tx 배선을 검증하는 테스트 클래스입니다.
    """

    def test_toggle_on_starts_scheduler_and_sends_via_shared_helper(self, qapp):
        """
        토글 ON 시 스케줄러가 시작되고, 기존 수동 전송 경로(_process_and_send)를
        통해 실제 전송이 수행되는지 테스트 (가공 로직 재사용 확인).
        """
        # GIVEN
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.has_active_connection = True
        presenter = ManualControlPresenter(
            panel=panel,
            connection_controller=controller,
            local_echo_callback=MagicMock(),
            get_active_port_callback=lambda: "COM1",
        )

        # WHEN
        presenter.on_auto_tx_toggled(True)

        # THEN: 시작 즉시 1회 전송이 기존 send_data 경로로 수행되어야 함
        assert presenter.auto_tx_scheduler.is_running
        controller.send_data.assert_called_once_with("COM1", b"AT")

        # WHEN: 토글 OFF
        presenter.on_auto_tx_toggled(False)

        # THEN
        assert not presenter.auto_tx_scheduler.is_running

    def test_toggle_on_with_invalid_command_reverts_checkbox(self, qapp):
        """
        Panel Facade 조회 실패(AttributeError) 시 스케줄러를 시작하지 않고
        체크박스를 다시 해제(UI 동기화)하는지 테스트.
        """
        # GIVEN: get_input_text 호출 시 예외 발생하도록 설정
        panel = MagicMock()
        panel.get_input_text.side_effect = AttributeError("boom")
        controller = MagicMock()
        presenter = ManualControlPresenter(
            panel=panel,
            connection_controller=controller,
            local_echo_callback=MagicMock(),
            get_active_port_callback=lambda: "COM1",
        )

        # WHEN
        presenter.on_auto_tx_toggled(True)

        # THEN
        assert not presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_called_once_with(False)

    def test_connection_closed_stops_auto_tx_when_no_active_ports(self, qapp):
        """
        모든 포트가 닫히면(활성 연결 없음) Auto Tx가 자동으로 정지되고
        체크박스가 UI에서 해제되는지 테스트.
        """
        # GIVEN
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.has_active_connection = True
        presenter = ManualControlPresenter(
            panel=panel,
            connection_controller=controller,
            local_echo_callback=MagicMock(),
            get_active_port_callback=lambda: "COM1",
        )
        presenter.on_auto_tx_toggled(True)
        assert presenter.auto_tx_scheduler.is_running

        # WHEN: 마지막 포트까지 닫힘
        controller.has_active_connection = False
        presenter._on_connection_closed()

        # THEN
        assert not presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_called_once_with(False)

    def test_connection_closed_keeps_running_when_other_ports_active(self, qapp):
        """
        일부 포트만 닫히고 다른 활성 연결이 남아있으면 Auto Tx를 유지하는지 테스트.
        """
        # GIVEN
        panel = _make_mock_panel(text="AT", interval_ms=200)
        controller = MagicMock()
        controller.is_connection_open.return_value = True
        controller.has_active_connection = True
        presenter = ManualControlPresenter(
            panel=panel,
            connection_controller=controller,
            local_echo_callback=MagicMock(),
            get_active_port_callback=lambda: "COM1",
        )
        presenter.on_auto_tx_toggled(True)

        # WHEN: 여전히 활성 연결이 남아있는 상태에서 종료 이벤트 수신
        presenter._on_connection_closed()

        # THEN: 계속 실행 중이어야 함
        assert presenter.auto_tx_scheduler.is_running
        panel.set_auto_tx_checked.assert_not_called()
