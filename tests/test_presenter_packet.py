"""
PacketPresenter 회귀 테스트.

EventRouter 제거 후 ConnectionController direct signal 배선, 패킷 표시 변환,
throttling, 설정 반영, checksum 검증을 확인합니다.
"""
from unittest.mock import MagicMock

import pytest

from common.constants import ConfigKeys
from common.dtos import PacketEvent, PacketViewData, PreferencesState
from model.connection_controller import ConnectionController
from model.packet_parser import Packet
from presenter.packet_presenter import PacketPresenter
from view.panels.packet_panel import PacketPanel


@pytest.fixture
def mock_panel():
    return MagicMock(spec=PacketPanel)


@pytest.fixture
def mock_connection_controller():
    return MagicMock(spec=ConnectionController)


@pytest.fixture
def mock_settings_manager():
    manager = MagicMock()

    def get_side_effect(key, default=None):
        mapping = {
            ConfigKeys.PACKET_BUFFER_SIZE: 100,
            ConfigKeys.PACKET_AUTOSCROLL: True,
            ConfigKeys.PACKET_REALTIME: True,
        }
        return mapping.get(key, default)

    manager.get.side_effect = get_side_effect
    return manager


@pytest.fixture
def presenter(mock_panel, mock_connection_controller, mock_settings_manager, qapp):
    instance = PacketPresenter(
        mock_panel,
        mock_connection_controller,
        mock_settings_manager,
    )
    yield instance
    instance.stop()


class TestPacketPresenter:
    def test_initialization(
        self,
        presenter,
        mock_panel,
        mock_connection_controller,
    ):
        mock_panel.set_buffer_size.assert_called_with(100)
        mock_panel.set_autoscroll.assert_called_with(True)
        mock_panel.set_capture_state.assert_called_with(True)
        mock_panel.clear_requested.connect.assert_called()
        mock_panel.capture_toggled.connect.assert_called()
        mock_connection_controller.packet_received.connect.assert_called()
        mock_connection_controller.connection_closed.connect.assert_called()

    def test_packet_processing(self, presenter, mock_panel):
        event = PacketEvent(
            port="COM1",
            packet=Packet(
                data=b"\x41\x42\x00\xff",
                timestamp=0,
                metadata={"type": "TEST_TYPE"},
            ),
        )
        presenter.on_packet_received(event)
        mock_panel.append_packet.assert_not_called()
        presenter._flush_pending_packets()

        view_data: PacketViewData = mock_panel.append_packet.call_args[0][0]
        assert view_data.packet_type == "TEST_TYPE"
        assert view_data.data_hex == "41 42 00 FF"
        assert view_data.data_ascii == "AB.."
        assert view_data.time_str

    def test_packet_ignored_when_not_capturing(self, presenter, mock_panel):
        presenter.on_capture_toggled(False)
        presenter.on_packet_received(
            PacketEvent(port="COM1", packet=Packet(b"\x00", 0))
        )
        mock_panel.append_packet.assert_not_called()

    def test_settings_update(self, presenter, mock_panel):
        state = PreferencesState(
            packet_buffer_size=500,
            packet_autoscroll=False,
            packet_realtime=False,
        )
        presenter.on_settings_changed(state)
        mock_panel.set_buffer_size.assert_called_with(500)
        mock_panel.set_autoscroll.assert_called_with(False)
        mock_panel.set_capture_state.assert_called_with(False)

    def test_clear_view(self, presenter, mock_panel):
        presenter.on_clear_requested()
        mock_panel.clear_view.assert_called_once()

    def test_capture_toggle(self, presenter, mock_panel):
        presenter.on_capture_toggled(False)
        presenter.on_packet_received(
            PacketEvent(port="COM1", packet=Packet(b"\x00", 0))
        )
        mock_panel.append_packet.assert_not_called()

        presenter.on_capture_toggled(True)
        presenter.on_packet_received(
            PacketEvent(port="COM1", packet=Packet(b"\x01", 0))
        )
        presenter._flush_pending_packets()
        mock_panel.append_packet.assert_called_once()


class TestPacketPresenterThrottle:
    @staticmethod
    def _make_event(index: int) -> PacketEvent:
        return PacketEvent(
            port="COM1",
            packet=Packet(
                data=bytes([index % 256]),
                timestamp=0,
                metadata={"type": str(index)},
            ),
        )

    def test_packets_are_buffered_not_applied_immediately(self, presenter, mock_panel):
        for index in range(10):
            presenter.on_packet_received(self._make_event(index))
        mock_panel.append_packet.assert_not_called()
        assert len(presenter._pending_packets) == 10

    def test_flush_applies_all_without_loss_and_in_order(self, presenter, mock_panel):
        for index in range(80):
            presenter.on_packet_received(self._make_event(index))
        presenter._flush_pending_packets()
        assert mock_panel.append_packet.call_count == 80
        assert [
            call.args[0].packet_type
            for call in mock_panel.append_packet.call_args_list
        ] == [str(index) for index in range(80)]

    def test_flush_caps_backlog_to_buffer_size_keeping_newest(self, presenter, mock_panel):
        for index in range(500):
            presenter.on_packet_received(self._make_event(index))
        presenter._flush_pending_packets()
        assert mock_panel.append_packet.call_count == 100
        assert [
            call.args[0].packet_type
            for call in mock_panel.append_packet.call_args_list
        ] == [str(index) for index in range(400, 500)]

    def test_flush_with_empty_buffer_does_nothing(self, presenter, mock_panel):
        presenter._flush_pending_packets()
        mock_panel.append_packet.assert_not_called()

    def test_stop_flushes_remaining_buffer_and_stops_timer(self, presenter, mock_panel):
        for index in range(5):
            presenter.on_packet_received(self._make_event(index))
        presenter.stop()
        assert mock_panel.append_packet.call_count == 5
        assert presenter._flush_timer.isActive() is False

    def test_port_closed_flushes_pending_buffer_immediately(
        self,
        presenter,
        mock_panel,
        mock_connection_controller,
    ):
        for index in range(3):
            presenter.on_packet_received(self._make_event(index))
        connected_slot = mock_connection_controller.connection_closed.connect.call_args[0][0]
        connected_slot(MagicMock())
        assert mock_panel.append_packet.call_count == 3

    def test_clear_requested_drops_pending_buffer(self, presenter, mock_panel):
        for index in range(4):
            presenter.on_packet_received(self._make_event(index))
        presenter.on_clear_requested()
        presenter._flush_pending_packets()
        mock_panel.append_packet.assert_not_called()
        mock_panel.clear_view.assert_called_once()


class TestPacketChecksumVerification:
    @staticmethod
    def _settings(algorithm, offset=-1, lead=0, trail=0):
        manager = MagicMock()

        def get_side_effect(key, default=None):
            mapping = {
                ConfigKeys.PACKET_BUFFER_SIZE: 100,
                ConfigKeys.PACKET_AUTOSCROLL: True,
                ConfigKeys.PACKET_REALTIME: True,
                ConfigKeys.PACKET_CHECKSUM_ALGORITHM: algorithm,
                ConfigKeys.PACKET_CHECKSUM_OFFSET: offset,
                ConfigKeys.PACKET_CHECKSUM_EXCLUDE_LEADING: lead,
                ConfigKeys.PACKET_CHECKSUM_EXCLUDE_TRAILING: trail,
            }
            return mapping.get(key, default)

        manager.get.side_effect = get_side_effect
        return manager

    @staticmethod
    def _make(panel, controller, settings):
        return PacketPresenter(panel, controller, settings)

    def test_none_algorithm_reports_not_verified(self, mock_panel, mock_connection_controller):
        p = self._make(mock_panel, mock_connection_controller, self._settings("none"))
        try:
            assert p._verify_checksum(b"\x01\x02\x03") is None
        finally:
            p.stop()

    def test_xor_trailing_byte_pass_and_fail(self, mock_panel, mock_connection_controller):
        payload = b"\x01\x02\x03"
        good = payload + bytes([0x01 ^ 0x02 ^ 0x03])
        bad = payload + bytes([0x01 ^ 0x02 ^ 0x03 ^ 0x01])
        p = self._make(
            mock_panel,
            mock_connection_controller,
            self._settings("xor", offset=-1, trail=1),
        )
        try:
            assert p._verify_checksum(good) is True
            assert p._verify_checksum(bad) is False
        finally:
            p.stop()

    def test_leading_bytes_can_be_excluded(self, mock_panel, mock_connection_controller):
        body = b"\x10\x20\x30"
        packet = b"\xAA\x55" + body + bytes([0x10 ^ 0x20 ^ 0x30])
        p = self._make(
            mock_panel,
            mock_connection_controller,
            self._settings("xor", offset=-1, lead=2, trail=1),
        )
        try:
            assert p._verify_checksum(packet) is True
        finally:
            p.stop()

    def test_packet_too_short_is_not_verified_rather_than_failed(
        self,
        mock_panel,
        mock_connection_controller,
    ):
        p = self._make(
            mock_panel,
            mock_connection_controller,
            self._settings("crc32", offset=-1),
        )
        try:
            assert p._verify_checksum(b"\x01") is None
        finally:
            p.stop()

    def test_unknown_algorithm_is_not_verified(self, mock_panel, mock_connection_controller):
        p = self._make(
            mock_panel,
            mock_connection_controller,
            self._settings("not_a_real_algorithm"),
        )
        try:
            assert p._verify_checksum(b"\x01\x02\x03\x04") is None
        finally:
            p.stop()

    def test_result_reaches_view_dto(self, mock_panel, mock_connection_controller):
        payload = b"\x01\x02\x03"
        wrong = (0x01 ^ 0x02 ^ 0x03) ^ 0x01
        p = self._make(
            mock_panel,
            mock_connection_controller,
            self._settings("xor", offset=-1, trail=1),
        )
        try:
            p.on_packet_received(
                PacketEvent(
                    port="COM1",
                    packet=Packet(data=payload + bytes([wrong]), timestamp=0.0),
                )
            )
            p._flush_pending_packets()
            view_data = mock_panel.append_packet.call_args[0][0]
            assert view_data.checksum_ok is False
        finally:
            p.stop()
