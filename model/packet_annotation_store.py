"""Packet annotation의 독립 저장소.

Parser Packet/PacketViewData를 직접 mutation하지 않고 stable packet_id를 key로 note를
관리합니다. 현재 annotation은 runtime session state이며 설정 파일에는 저장하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PacketAnnotation:
    packet_id: str
    note: str


class PacketAnnotationStore:
    """Runtime packet annotation owner."""

    def __init__(self) -> None:
        self._notes: dict[str, str] = {}

    def set_note(self, packet_id: str, note: str) -> PacketAnnotation:
        packet_id = packet_id.strip()
        if not packet_id:
            raise ValueError("packet_id must not be empty")

        normalized = note.strip()
        if normalized:
            self._notes[packet_id] = normalized
        else:
            self._notes.pop(packet_id, None)
        return PacketAnnotation(packet_id=packet_id, note=normalized)

    def get_note(self, packet_id: str) -> str:
        return self._notes.get(packet_id, "")

    def remove(self, packet_id: str) -> None:
        self._notes.pop(packet_id, None)

    def clear(self) -> None:
        self._notes.clear()

    def snapshot(self) -> tuple[PacketAnnotation, ...]:
        return tuple(
            PacketAnnotation(packet_id=packet_id, note=note)
            for packet_id, note in self._notes.items()
        )
