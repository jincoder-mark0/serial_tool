"""
포트 탭 닫기 연결 정리 회귀 테스트 모듈 (S-040)

## WHY
* A-4: 포트 탭을 X로 닫아도 워커 스레드가 계속 실행되어 연결이 남는
  "좀비 연결" 버그. 재현: ①COM3 연결 → ②탭 추가 → ③COM3 탭 닫기 →
  ④같은 포트로 재연결 시도 → "Connection is already open." 오류.
* B-3: 포트 열기 자체가 실패하면(존재하지 않는 포트 등) Worker가
  connection_closed를 발행하지 않아 ConnectionController.workers에 죽은
  Worker가 남고, has_active_connection이 거짓 True가 된다.

## WHAT
* PortTabPanel.close_port_tab()이 port_tab_closed(str) 시그널을 emit하고,
  PortPresenter가 이를 구독해 ConnectionController.close_connection()을
  호출하는 MVP 경로(View→Presenter→Model) 전체를 검증한다 (①, ③).
* ConnectionWorker.close_connection()이 open 실패 시에도 worker_terminated를
  발행해 ConnectionController가 레지스트리를 정리하는지 검증한다 (②, B-3).

## HOW
* 실제 MainLeftSection + PortPresenter + ConnectionController를 조립하여
  탭 닫기 → 연결 정리 전체 경로를 통합 테스트로 검증한다 (LOOPBACK Transport,
  실기기 불필요).
* 포트 열기 실패는 core.transport.serial_transport.serial.Serial 생성자를
  예외로 패치하여 결정론적으로 재현한다 (실기기 불필요).

pytest tests/test_port_tab_cleanup.py -v
"""
import pytest
import serial
from unittest.mock import patch

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from model.connection_controller import ConnectionController
from presenter.port_presenter import PortPresenter
from view.sections.main_left_section import MainLeftSection


@pytest.fixture
def loopback_config() -> PortConfig:
    """LOOPBACK 더미 포트용 PortConfig DTO."""
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


@pytest.fixture
def wired_presenter(qapp):
    """
    실제 MainLeftSection + PortPresenter + ConnectionController 조립체.

    View(PortTabPanel)의 port_tab_closed 시그널 → Presenter → Controller로
    이어지는 MVP 경로를 그대로 태우기 위해 Mock이 아닌 실제 컴포넌트를 사용한다.

    Yields:
        tuple: (MainLeftSection, PortPresenter, ConnectionController)
    """
    left_section = MainLeftSection()
    controller = ConnectionController()
    presenter = PortPresenter(left_section, controller)
    try:
        yield left_section, presenter, controller
    finally:
        # 잔여 연결 정리 (다음 테스트로 좀비 연결이 새지 않도록)
        controller.close_connection()


# =============================================================================
# ① 탭 닫기 → 연결 정리 (A-4 회귀)
# =============================================================================

class TestTabCloseReleasesConnection:
    """탭을 닫으면 해당 연결이 정리되어 즉시 재연결이 가능해야 한다."""

    def test_closing_tab_closes_loopback_connection_and_allows_reopen(
        self, wired_presenter, loopback_config
    ):
        left_section, _presenter, controller = wired_presenter

        # 최소 탭 수(count<=2면 삭제 불가) 조건을 통과시키기 위한 두 번째 탭
        left_section.add_new_port_tab()

        # 첫 번째 탭에 LOOPBACK 포트를 설정하고 실제로 연결한다
        panel0 = left_section.get_port_panel_at(0)
        panel0.apply_state({"port_settings_widget": {"port": LOOPBACK_PORT_NAME}})
        assert panel0.get_port_name() == LOOPBACK_PORT_NAME

        assert controller.open_connection(loopback_config) is True
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is True

        # WHEN: 탭 닫기 (View의 close_port_tab을 그대로 호출 — 실제 X 버튼과 동일 경로)
        left_section.port_tab_panel.close_port_tab(0)

        # THEN: 연결이 정리되어 워커가 레지스트리에서 제거됨
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is False
        assert LOOPBACK_PORT_NAME not in controller.workers

        # THEN: 같은 포트로 곧바로 재연결이 가능해야 함
        # ("Connection is already open." 좀비 연결 회귀 방지)
        assert controller.open_connection(loopback_config) is True
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is True


# =============================================================================
# ② 연결 실패 시 레지스트리 잔존 방지 (B-3 회귀)
# =============================================================================

class TestFailedOpenDoesNotLeaveZombieWorker:
    """포트 열기 자체가 실패하면 Worker가 레지스트리에 남지 않아야 한다."""

    def test_open_failure_cleans_up_worker_registry(self, qapp, qtbot, sample_port_config):
        controller = ConnectionController()

        with patch(
            "core.transport.serial_transport.serial.Serial",
            side_effect=serial.SerialException("could not open port: no such device"),
        ):
            # open_connection은 Worker 스레드 시작 자체는 성공 반환한다
            # (open 성공 여부는 스레드 내부에서 비동기로 판명됨)
            assert controller.open_connection(sample_port_config) is True

            # THEN: 비동기로 open이 실패한 뒤 Worker가 레지스트리에서 제거됨
            qtbot.waitUntil(
                lambda: sample_port_config.port not in controller.workers, timeout=2000
            )

        # THEN: 죽은 Worker가 남아 has_active_connection을 거짓 True로 만들지 않음
        assert controller.has_active_connection is False
        assert controller.is_connection_open(sample_port_config.port) is False


# =============================================================================
# ③ 미연결 탭 닫기가 예외 없이 통과
# =============================================================================

class TestClosingUnconnectedTabIsHarmless:
    """연결된 적 없는 탭을 닫아도 예외 없이 통과해야 한다."""

    def test_closing_tab_without_connection_does_not_raise(self, wired_presenter):
        left_section, _presenter, controller = wired_presenter

        left_section.add_new_port_tab()

        panel0 = left_section.get_port_panel_at(0)
        # 아무 포트도 선택/연결하지 않은 기본 상태
        assert panel0.get_port_name() == ""

        # WHEN/THEN: 예외 없이 탭이 닫혀야 함
        left_section.port_tab_panel.close_port_tab(0)

        assert controller.has_active_connection is False

    def test_closing_tab_with_selected_but_unconnected_port_does_not_raise(
        self, wired_presenter
    ):
        left_section, _presenter, controller = wired_presenter

        left_section.add_new_port_tab()

        panel0 = left_section.get_port_panel_at(0)
        # 포트를 선택했지만 연결(open_connection)은 하지 않은 상태
        panel0.apply_state({"port_settings_widget": {"port": "COM_NEVER_OPENED"}})
        assert panel0.get_port_name() == "COM_NEVER_OPENED"

        # WHEN/THEN: close_connection("COM_NEVER_OPENED")이 무해하게 통과해야 함
        left_section.port_tab_panel.close_port_tab(0)

        assert "COM_NEVER_OPENED" not in controller.workers
        assert controller.has_active_connection is False
