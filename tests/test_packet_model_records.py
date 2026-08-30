"""PacketModel의 display DTO / immutable record 정합성 테스트."""
from common.dtos import PacketViewData
from common.packet_records import PacketRecord
from view.panels.packet_panel import PacketModel


def _view(value: str) -> PacketViewData:
    return PacketViewData(
        time_str="00:00:00.000",
        packet_type="Raw",
        data_hex=value,
        data_ascii=value,
    )


def _record(packet_id: str, value: bytes = b"x") -> PacketRecord:
    return PacketRecord(
        packet_id=packet_id,
        port="COM3",
        time_str="00:00:00.000",
        packet_type="Raw",
        raw_data=value,
        data_hex=value.hex(" ").upper(),
        data_ascii="x",
    )


def test_buffer_eviction_keeps_display_and_record_deques_aligned(qapp):
    model = PacketModel(buffer_size=2)
    model.append_packet(_view("A"), _record("p1", b"A"))
    model.append_packet(_view("B"), _record("p2", b"B"))
    model.append_packet(_view("C"), _record("p3", b"C"))

    assert model.rowCount() == 2
    assert [record.packet_id for record in model.records_for_rows([0, 1])] == ["p2", "p3"]


def test_buffer_resize_keeps_record_alignment(qapp):
    model = PacketModel(buffer_size=3)
    for packet_id in ("p1", "p2", "p3"):
        model.append_packet(_view(packet_id), _record(packet_id))

    model.set_buffer_size(2)

    assert model.rowCount() == 2
    assert [record.packet_id for record in model.records_for_rows([0, 1])] == ["p2", "p3"]


def test_records_for_rows_deduplicates_and_sorts_selection(qapp):
    model = PacketModel(buffer_size=4)
    for packet_id in ("p1", "p2", "p3"):
        model.append_packet(_view(packet_id), _record(packet_id))

    records = model.records_for_rows([2, 0, 2, 99, -1])
    assert [record.packet_id for record in records] == ["p1", "p3"]


def test_set_annotation_updates_only_matching_record(qapp):
    model = PacketModel(buffer_size=3)
    model.append_packet(_view("A"), _record("p1"))
    model.append_packet(_view("B"), _record("p2"))

    model.set_annotation(("p2",), "memo")

    records = model.records_for_rows([0, 1])
    assert records[0].annotation == ""
    assert records[1].annotation == "memo"
    assert model.data(model.index(1, 5)) == "memo"
