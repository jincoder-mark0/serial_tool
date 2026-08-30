"""Packet annotation store / export manager pure behavior tests."""
import json
from pathlib import Path

import pytest

from common.packet_records import PacketRecord
from model.packet_annotation_store import PacketAnnotationStore
from model.packet_export_manager import PacketExportError, PacketExportManager


def _record(packet_id: str = "COM3:1", annotation: str = "") -> PacketRecord:
    return PacketRecord(
        packet_id=packet_id,
        port="COM3",
        time_str="12:34:56.789",
        packet_type="AT",
        raw_data=b"AT+OK\r\n",
        data_hex="41 54 2B 4F 4B 0D 0A",
        data_ascii="AT+OK..",
        checksum_ok=True,
        annotation=annotation,
    )


def test_annotation_store_is_independent_from_packet_snapshot():
    store = PacketAnnotationStore()
    record = _record()

    annotation = store.set_note(record.packet_id, "important")

    assert annotation.note == "important"
    assert store.get_note(record.packet_id) == "important"
    assert record.annotation == ""


def test_empty_annotation_removes_existing_note():
    store = PacketAnnotationStore()
    store.set_note("p1", "note")
    store.set_note("p1", "   ")
    assert store.get_note("p1") == ""


def test_csv_export_contains_annotation(tmp_path):
    path = tmp_path / "packets.csv"
    PacketExportManager.write_records((_record(annotation="memo"),), path, "csv")

    text = path.read_text(encoding="utf-8")
    assert "annotation" in text
    assert "memo" in text
    assert "41 54 2B 4F 4B 0D 0A" in text


def test_json_export_preserves_raw_hex_and_identity(tmp_path):
    path = tmp_path / "packets.json"
    PacketExportManager.write_records((_record(),), path, "json")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload[0]["packet_id"] == "COM3:1"
    assert payload[0]["raw_hex"] == "41542B4F4B0D0A"
    assert payload[0]["checksum"] == "OK"


def test_hex_export_is_one_packet_per_line(tmp_path):
    path = tmp_path / "packets.txt"
    records = (_record("p1"), _record("p2", annotation="second"))
    PacketExportManager.write_records(records, path, "hex")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "41 54 2B 4F 4B 0D 0A" in lines[0]
    assert lines[1].endswith("second")


def test_raw_export_concatenates_selected_packet_bytes(tmp_path):
    path = tmp_path / "packets.bin"
    a = _record("p1")
    b = PacketRecord(
        packet_id="p2",
        port="COM3",
        time_str="",
        packet_type="Raw",
        raw_data=b"\x01\x02",
        data_hex="01 02",
        data_ascii="..",
    )
    PacketExportManager.write_records((a, b), path, "raw")
    assert path.read_bytes() == a.raw_data + b.raw_data


def test_export_uses_atomic_replace_and_cleans_temp_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "packets.json"
    path.write_text("old", encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", _boom)
    with pytest.raises(OSError):
        PacketExportManager.write_records((_record(),), path, "json")

    assert path.read_text(encoding="utf-8") == "old"
    assert not Path(str(path) + ".tmp").exists()


def test_unsupported_export_format_is_rejected(tmp_path):
    with pytest.raises(PacketExportError):
        PacketExportManager.write_records((_record(),), tmp_path / "x", "xml")
