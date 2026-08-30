"""Packet Inspector의 annotation/export용 immutable packet snapshot."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class PacketRecord:
    """Parser Packet에서 분리한 Inspector용 immutable snapshot."""

    packet_id: str
    port: str
    time_str: str
    packet_type: str
    raw_data: bytes
    data_hex: str
    data_ascii: str
    checksum_ok: Optional[bool] = None
    annotation: str = ""

    def with_annotation(self, note: str) -> "PacketRecord":
        return replace(self, annotation=note.strip())
