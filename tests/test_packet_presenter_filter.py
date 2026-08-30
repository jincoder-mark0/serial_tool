"""PacketPresenter structured filter integration regression tests."""
from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import PacketEvent
from model.packet_parser import Packet
from presenter.packet_presenter import PacketPresenter


class _FakePanel(QObject):
    clear_requested = pyqtSignal()
    capture_toggled = pyqtSignal(bool)
    filter_toggled = pyqtSignal(bool)
    filter_expression_changed = pyqtSignal(str)
    annotation_requested = pyqtSignal(object, str)
    export_requested = pyqtSignal(object, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.appended = []
        self.records = []
        self.filter_errors: list[str] = []
        self.filter_state = False

    def set_buffer_size(self, _size: int) -> None:
        pass

    def set_autoscroll(self, _enabled: bool) -> None:
        pass

    def set_capture_state(self, _enabled: bool) -> None:
        pass

    def set_filter_state(self, enabled: bool) -> None:
        self.filter_state = enabled

    def set_filter_error(self, message: str) -> None:
        self.filter_errors.append(message)

    def clear_filter_error(self) -> None:
        self.filter_errors.clear()

    def append_packet(self, data, record=None) -> None:
        self.appended.append(data)
        self.records.append(record)

    def set_packet_annotation(self, _packet_ids, _note: str) -> None:
        pass

    def clear_view(self) -> None:
        self.appended.clear()
        self.records.clear()


class _FakeController(QObject):
    packet_received = pyqtSignal(object)
    connection_closed = pyqtSignal(object)


class _FakeSettings:
    def get(self, _key, default=None):
        return default


def _event(data: bytes, packet_type: str = "AT", port: str = "COM3") -> PacketEvent:
    return PacketEvent(
        port=port,
        packet=Packet(data=data, timestamp=0.0, metadata={"type": packet_type}),
    )


def _presenter(qapp):
    panel = _FakePanel()
    presenter = PacketPresenter(panel, _FakeController(), _FakeSettings())
    return presenter, panel


def test_filter_off_preserves_existing_packet_path(qapp):
    presenter, panel = _presenter(qapp)
    try:
        presenter.on_packet_received(_event(b"AT+OK\r\n"))
        presenter._flush_pending_packets()

        assert len(panel.appended) == 1
        assert panel.appended[0].packet_type == "AT"
        assert panel.records[0].raw_data == b"AT+OK\r\n"
    finally:
        presenter.stop()


def test_enabled_filter_keeps_only_matching_packets(qapp):
    presenter, panel = _presenter(qapp)
    try:
        presenter.on_filter_expression_changed("type=AT; ascii*=OK")
        presenter.on_filter_toggled(True)

        presenter.on_packet_received(_event(b"AT+OK\r\n"))
        presenter.on_packet_received(_event(b"AT+ERROR\r\n"))
        presenter.on_packet_received(_event(b"OK", packet_type="Raw"))
        presenter._flush_pending_packets()

        assert len(panel.appended) == 1
        assert "OK" in panel.appended[0].data_ascii
    finally:
        presenter.stop()


def test_invalid_expression_keeps_last_valid_filter(qapp):
    presenter, panel = _presenter(qapp)
    try:
        presenter.on_filter_expression_changed("ascii*=OK")
        presenter.on_filter_toggled(True)
        presenter.on_filter_expression_changed("byte[0]&0xF0=0xAF")

        assert panel.filter_errors

        presenter.on_packet_received(_event(b"AT+ERROR\r\n"))
        presenter.on_packet_received(_event(b"AT+OK\r\n"))
        presenter._flush_pending_packets()

        assert len(panel.appended) == 1
        assert "OK" in panel.appended[0].data_ascii
    finally:
        presenter.stop()


def test_valid_expression_clears_previous_error(qapp):
    presenter, panel = _presenter(qapp)
    try:
        presenter.on_filter_expression_changed("unknown=x")
        assert panel.filter_errors

        presenter.on_filter_expression_changed("port=COM3")
        assert panel.filter_errors == []
    finally:
        presenter.stop()
