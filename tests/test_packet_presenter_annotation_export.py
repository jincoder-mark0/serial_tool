"""PacketPresenter annotation/export orchestration regression tests."""
from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import PacketEvent
from model.packet_annotation_store import PacketAnnotationStore
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
        self.records = []
        self.annotations: list[tuple[tuple[str, ...], str]] = []

    def set_buffer_size(self, _size: int) -> None:
        pass

    def set_autoscroll(self, _enabled: bool) -> None:
        pass

    def set_capture_state(self, _enabled: bool) -> None:
        pass

    def set_filter_state(self, _enabled: bool) -> None:
        pass

    def set_filter_error(self, _message: str) -> None:
        pass

    def clear_filter_error(self) -> None:
        pass

    def append_packet(self, _data, record=None) -> None:
        self.records.append(record)

    def set_packet_annotation(self, packet_ids, note: str) -> None:
        self.annotations.append((tuple(packet_ids), note))
        ids = set(packet_ids)
        self.records = [
            record.with_annotation(note)
            if record is not None and record.packet_id in ids
            else record
            for record in self.records
        ]

    def clear_view(self) -> None:
        self.records.clear()


class _FakeController(QObject):
    packet_received = pyqtSignal(object)
    connection_closed = pyqtSignal(object)


class _FakeSettings:
    def get(self, _key, default=None):
        return default


class _FakeExportManager(QObject):
    export_completed = pyqtSignal(str, int)
    export_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.requests = []
        self.stop_called = False

    def export_async(self, records, path: str, export_format: str) -> bool:
        self.requests.append((tuple(records), path, export_format))
        return True

    def stop(self) -> None:
        self.stop_called = True


def _event(data: bytes, port: str = "COM3") -> PacketEvent:
    return PacketEvent(
        port=port,
        packet=Packet(data=data, timestamp=0.0, metadata={"type": "AT"}),
    )


def _presenter(qapp):
    panel = _FakePanel()
    store = PacketAnnotationStore()
    export_manager = _FakeExportManager()
    presenter = PacketPresenter(
        panel,
        _FakeController(),
        _FakeSettings(),
        store,
        export_manager,
    )
    return presenter, panel, store, export_manager


def test_presenter_creates_unique_record_identity_and_raw_snapshot(qapp):
    presenter, panel, _store, _export = _presenter(qapp)
    try:
        presenter.on_packet_received(_event(b"A"))
        presenter.on_packet_received(_event(b"B"))
        presenter._flush_pending_packets()

        assert [record.packet_id for record in panel.records] == ["COM3:1", "COM3:2"]
        assert [record.raw_data for record in panel.records] == [b"A", b"B"]
        assert all(record.port == "COM3" for record in panel.records)
    finally:
        presenter.stop()


def test_annotation_request_updates_store_and_visible_snapshot(qapp):
    presenter, panel, store, _export = _presenter(qapp)
    try:
        presenter.on_packet_received(_event(b"A"))
        presenter._flush_pending_packets()
        packet_id = panel.records[0].packet_id

        presenter.on_annotation_requested((packet_id,), "  important  ")

        assert store.get_note(packet_id) == "important"
        assert panel.annotations[-1] == ((packet_id,), "important")
        assert panel.records[0].annotation == "important"
    finally:
        presenter.stop()


def test_clear_removes_runtime_annotations(qapp):
    presenter, panel, store, _export = _presenter(qapp)
    try:
        presenter.on_packet_received(_event(b"A"))
        presenter._flush_pending_packets()
        packet_id = panel.records[0].packet_id
        presenter.on_annotation_requested((packet_id,), "memo")

        presenter.on_clear_requested()

        assert store.get_note(packet_id) == ""
        assert panel.records == []
    finally:
        presenter.stop()


def test_export_request_passes_immutable_record_snapshot_to_manager(qapp):
    presenter, panel, _store, export_manager = _presenter(qapp)
    try:
        presenter.on_packet_received(_event(b"A"))
        presenter._flush_pending_packets()
        record = panel.records[0]

        presenter.on_export_requested((record,), "result.json", "json")

        records, path, export_format = export_manager.requests[-1]
        assert records == (record,)
        assert path == "result.json"
        assert export_format == "json"
    finally:
        presenter.stop()


def test_presenter_stop_stops_export_owner(qapp):
    presenter, _panel, _store, export_manager = _presenter(qapp)
    presenter.stop()
    assert export_manager.stop_called is True
