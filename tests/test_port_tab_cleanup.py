"""포트 탭 닫기 연결 정리와 open 실패 registry cleanup 회귀 테스트."""
from unittest.mock import patch

import pytest
import serial

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import SerialFlowControl, SerialParity, SerialStopBits
from model.connection_controller import ConnectionController
from model.port_scan_manager import PortScanManager
from presenter.port_presenter import PortPresenter
from view.sections.main_left_section import MainLeftSection


@pytest.fixture
def loopback_config() -> PortConfig:
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


@pytest.fixture
def wired_presenter(qapp, mock_settings_manager):
    """실제 View + Presenter + Controller를 명시적 dependency graph로 조립합니다."""
    left_section = MainLeftSection()
    controller = ConnectionController()
    port_scan_manager = PortScanManager()
    presenter = PortPresenter(
        left_section,
        controller,
        mock_settings_manager,
        port_scan_manager,
    )
    try:
        yield left_section, presenter, controller
    finally:
        port_scan_manager.stop()
        controller.close_all_and_wait()


class TestTabCloseReleasesConnection:
    def test_closing_tab_closes_loopback_connection_and_allows_reopen(
        self,
        wired_presenter,
        loopback_config,
    ):
        left_section, _presenter, controller = wired_presenter
        left_section.add_new_port_tab()

        panel0 = left_section.get_port_panel_at(0)
        panel0.apply_state({"port_settings_widget": {"port": LOOPBACK_PORT_NAME}})
        assert panel0.get_port_name() == LOOPBACK_PORT_NAME

        assert controller.open_connection(loopback_config) is True
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is True

        left_section.port_tab_panel.close_port_tab(0)

        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        assert controller.open_connection(loopback_config) is True
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is True


class TestFailedOpenDoesNotLeaveZombieWorker:
    def test_open_failure_cleans_up_worker_registry(
        self,
        qapp,
        qtbot,
        sample_port_config,
    ):
        controller = ConnectionController()

        with patch(
            "core.transport.serial_transport.serial.Serial",
            side_effect=serial.SerialException(
                "could not open port: no such device"
            ),
        ):
            assert controller.open_connection(sample_port_config) is True
            qtbot.waitUntil(
                lambda: sample_port_config.port not in controller.workers,
                timeout=2000,
            )

        assert controller.has_active_connection is False
        assert controller.is_connection_open(sample_port_config.port) is False


class TestClosingUnconnectedTabIsHarmless:
    def test_closing_tab_without_connection_does_not_raise(self, wired_presenter):
        left_section, _presenter, controller = wired_presenter
        left_section.add_new_port_tab()
        assert controller.has_active_connection is False

        left_section.port_tab_panel.close_port_tab(0)

        assert controller.has_active_connection is False

    def test_closing_tab_with_selected_but_unconnected_port_does_not_raise(
        self,
        wired_presenter,
    ):
        left_section, _presenter, controller = wired_presenter
        left_section.add_new_port_tab()

        panel0 = left_section.get_port_panel_at(0)
        panel0.apply_state(
            {"port_settings_widget": {"port": "COM_NEVER_OPENED"}}
        )
        assert panel0.get_port_name() == "COM_NEVER_OPENED"

        left_section.port_tab_panel.close_port_tab(0)

        assert "COM_NEVER_OPENED" not in controller.workers
        assert controller.has_active_connection is False
