"""
패킷 프레젠터 모듈

ConnectionController의 packet signal을 직접 받아 PacketPanel 표시 상태를 관리합니다.
고속 패킷 환경에서는 UI 반영을 타이머로 배치하여 GUI 블로킹을 줄입니다.
"""
from typing import List, Optional

from PyQt5.QtCore import QDateTime, QObject, QTimer

from common.constants import ConfigKeys, UI_REFRESH_INTERVAL_MS
from common.defaults import (
    DEFAULT_PACKET_AUTOSCROLL,
    DEFAULT_PACKET_BUFFER_SIZE,
    DEFAULT_PACKET_REALTIME,
)
from common.dtos import PacketEvent, PacketViewData, PreferencesState
from common.enums import ByteOrder
from core import checksum
from core.checksum import ChecksumAlgorithm
from core.logger import logger
from core.settings_manager import SettingsManager
from model.connection_controller import ConnectionController
from model.packet_filter import (
    CompiledPacketFilter,
    PacketFilterContext,
    PacketFilterEngine,
    PacketFilterSyntaxError,
)
from view.panels.packet_panel import PacketPanel


class PacketPresenter(QObject):
    """패킷 수신 데이터를 View용 DTO로 변환하고 표시 상태를 관리합니다."""

    def __init__(
        self,
        panel: PacketPanel,
        connection_controller: ConnectionController,
        settings_manager: SettingsManager,
    ) -> None:
        super().__init__()
        self.panel = panel
        self.connection_controller = connection_controller
        self.settings_manager = settings_manager
        self._is_capturing = True
        self._filter_enabled = False
        self._compiled_filter: CompiledPacketFilter = PacketFilterEngine.compile("")
        self._pending_packets: List[PacketViewData] = []
        self._buffer_size = DEFAULT_PACKET_BUFFER_SIZE

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._flush_pending_packets)
        self._flush_timer.start()

        self._apply_initial_settings()

        self.panel.clear_requested.connect(self.on_clear_requested)
        self.panel.capture_toggled.connect(self.on_capture_toggled)
        self.panel.filter_toggled.connect(self.on_filter_toggled)
        self.panel.filter_expression_changed.connect(self.on_filter_expression_changed)

        self.connection_controller.packet_received.connect(self.on_packet_received)
        self.connection_controller.connection_closed.connect(self._on_connection_closed)

    def _apply_initial_settings(self) -> None:
        buffer_size = self.settings_manager.get(
            ConfigKeys.PACKET_BUFFER_SIZE,
            DEFAULT_PACKET_BUFFER_SIZE,
        )
        autoscroll = self.settings_manager.get(
            ConfigKeys.PACKET_AUTOSCROLL,
            DEFAULT_PACKET_AUTOSCROLL,
        )
        realtime = self.settings_manager.get(
            ConfigKeys.PACKET_REALTIME,
            DEFAULT_PACKET_REALTIME,
        )

        self._buffer_size = buffer_size
        self.panel.set_buffer_size(buffer_size)
        self.panel.set_autoscroll(autoscroll)
        self._is_capturing = realtime
        self.panel.set_capture_state(realtime)
        self.panel.set_filter_state(False)

    def on_packet_received(self, event: PacketEvent) -> None:
        if not self._is_capturing or not event.packet:
            return

        packet = event.packet
        raw_data = getattr(packet, "data", b"")
        packet_type = "Raw"
        if packet.metadata and "type" in packet.metadata:
            packet_type = packet.metadata["type"]

        # Checksum은 Filter와 View가 같은 판정값을 공유합니다.
        checksum_ok = self._verify_checksum(raw_data)

        if self._filter_enabled:
            context = PacketFilterContext(
                port=event.port,
                packet_type=packet_type,
                data=raw_data,
                checksum_ok=checksum_ok,
            )
            if not self._compiled_filter.matches(context):
                return

        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        data_hex = " ".join(f"{byte:02X}" for byte in raw_data)
        data_ascii = "".join(
            chr(byte) if 32 <= byte < 127 else "." for byte in raw_data
        )

        self._pending_packets.append(
            PacketViewData(
                time_str=timestamp,
                packet_type=packet_type,
                data_hex=data_hex,
                data_ascii=data_ascii,
                checksum_ok=checksum_ok,
            )
        )

    def _verify_checksum(self, raw_data: bytes) -> Optional[bool]:
        algorithm = self.settings_manager.get(
            ConfigKeys.PACKET_CHECKSUM_ALGORITHM,
            ChecksumAlgorithm.NONE.value,
        )
        try:
            algo = ChecksumAlgorithm(algorithm)
        except ValueError:
            logger.warning(f"Unknown checksum algorithm in settings: {algorithm}")
            return None

        if algo is ChecksumAlgorithm.NONE:
            return None

        size = checksum.byte_length(algo)
        offset = int(self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_OFFSET, -1))
        lead = int(
            self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_EXCLUDE_LEADING, 0)
        )
        trail = int(
            self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_EXCLUDE_TRAILING, 0)
        )

        start = (len(raw_data) + offset + 1 - size) if offset < 0 else offset
        if start < 0 or start + size > len(raw_data):
            return None

        expected = int.from_bytes(
            raw_data[start:start + size],
            byteorder=ByteOrder.BIG.value,
        )
        target = raw_data[lead:len(raw_data) - trail] if trail else raw_data[lead:]
        if not target:
            return None

        return checksum.verify(algo, target, expected)

    def on_filter_expression_changed(self, expression: str) -> None:
        """새 expression이 유효할 때만 active compiled filter를 교체합니다.

        WHY:
        사용자가 rule을 편집하는 중 malformed 중간 상태가 생겨도 직전 valid filter를
        갑자기 해제하거나 RX path에 예외를 전달하면 안 됩니다.
        """
        try:
            compiled = PacketFilterEngine.compile(expression)
        except PacketFilterSyntaxError as exc:
            self.panel.set_filter_error(str(exc))
            logger.warning(f"Invalid packet filter: {exc}")
            return

        self._compiled_filter = compiled
        self.panel.clear_filter_error()
        logger.debug(f"Packet filter compiled: {compiled.source or '<pass-through>'}")

    def on_filter_toggled(self, enabled: bool) -> None:
        self._filter_enabled = enabled
        logger.debug(f"Packet filter state changed: {enabled}")

    def _on_connection_closed(self, _event) -> None:
        self._flush_pending_packets()

    def _flush_pending_packets(self) -> None:
        if not self._pending_packets:
            return

        pending = self._pending_packets
        self._pending_packets = []

        if self._buffer_size > 0 and len(pending) > self._buffer_size:
            pending = pending[-self._buffer_size:]

        for view_data in pending:
            self.panel.append_packet(view_data)

    def stop(self) -> None:
        self._flush_timer.stop()
        self._flush_pending_packets()

    def on_settings_changed(self, state: PreferencesState) -> None:
        self._buffer_size = state.packet_buffer_size
        self.panel.set_buffer_size(state.packet_buffer_size)
        self.panel.set_autoscroll(state.packet_autoscroll)

        if self._is_capturing != state.packet_realtime:
            self._is_capturing = state.packet_realtime
            self.panel.set_capture_state(state.packet_realtime)

    def on_clear_requested(self) -> None:
        self._pending_packets.clear()
        self.panel.clear_view()
        logger.debug("Packet view cleared by user.")

    def on_capture_toggled(self, enabled: bool) -> None:
        self._is_capturing = enabled
        logger.debug(f"Packet capture state changed: {enabled}")
