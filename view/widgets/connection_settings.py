"""Unified Serial/SPI/I2C connection settings for one Port tab.

The UI stays unified while runtime ownership stays separated: Serial produces
``PortConfig`` and SPI/I2C produce ``TransactionConnectionConfig``. Adapter
identity is stored as backend/stable-id/channel and restored after asynchronous
discovery without relying on Qt QVariant equality for Python dataclasses.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from common.constants import (
    CONTROL_WIDTH_PORT_DATA_COMBO,
    CONTROL_WIDTH_PORT_PARITY_COMBO,
    CONTROL_WIDTH_PORT_STOP_COMBO,
    DEFAULT_BAUDRATE,
    LAYOUT_MARGIN_DEFAULT,
    LAYOUT_MARGIN_NONE,
    LAYOUT_SPACING_DEFAULT,
    VALID_BAUDRATES,
)
from common.defaults import (
    DEFAULT_PORT_BYTESIZE,
    DEFAULT_PORT_PROTOCOL,
    DEFAULT_SPI_MODE,
    DEFAULT_SPI_SPEED,
)
from common.dtos import PortConfig, PortInfo
from common.enums import (
    ConnectionProtocol,
    PortState,
    SerialFlowControl,
    SerialParity,
    SerialStopBits,
)
from core.logger import logger
from core.transport.transaction.config import TransactionConnectionConfig
from core.transport.transaction.dto import (
    AdapterDescriptor,
    AdapterIdentity,
    I2cConfig,
    SpiConfig,
    TransactionProtocol,
)
from view.managers.language_manager import language_manager
from view.widgets.port_settings import ClickableComboBox

_SERIAL_BYTESIZES = (5, 6, 7, 8)
_SPI_SPEED_OPTIONS = (
    30_000_000,
    12_000_000,
    4_000_000,
    1_000_000,
    500_000,
    100_000,
)
_I2C_SPEED_OPTIONS = (1_000_000, 400_000, 100_000, 50_000, 10_000)


class ConnectionSettingsWidget(QGroupBox):
    """Protocol-aware endpoint/config editor used by every PortPanel."""

    connect_requested = pyqtSignal(object)
    disconnect_requested = pyqtSignal()
    endpoint_refresh_requested = pyqtSignal(str)
    port_connection_changed = pyqtSignal(bool)
    endpoint_changed = pyqtSignal()
    port_scan_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(language_manager.get_text("port_grp_settings"), parent)

        self.protocol_combo = QComboBox()
        self.endpoint_stack = QStackedWidget()
        self.port_combo = ClickableComboBox()
        self.adapter_combo = ClickableComboBox()
        self.channel_combo = QComboBox()
        self.connect_btn = QPushButton(language_manager.get_text("port_btn_connect"))
        self.settings_stack = QStackedWidget()

        self.serial_controls_ui: Dict[str, QWidget] = {}
        self.spi_controls_ui: Dict[str, QWidget] = {}
        self.i2c_controls_ui: Dict[str, QWidget] = {}

        self._adapter_descriptors: list[AdapterDescriptor] = []
        self._descriptor_by_identity: dict[AdapterIdentity, AdapterDescriptor] = {}
        self._pending_identity: AdapterIdentity | None = None

        self._init_ui()
        self.set_connection_state(PortState.DISCONNECTED)
        language_manager.language_changed.connect(self.retranslate_ui)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
        )
        layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.protocol_combo.addItems(
            [
                ConnectionProtocol.SERIAL,
                TransactionProtocol.SPI.value,
                TransactionProtocol.I2C.value,
            ]
        )
        self.protocol_combo.setCurrentText(DEFAULT_PORT_PROTOCOL)
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)

        self.port_combo.setMinimumWidth(180)
        self.port_combo.popup_show_requested.connect(self._request_endpoint_refresh)
        self.port_combo.currentTextChanged.connect(self.endpoint_changed.emit)

        self.adapter_combo.setMinimumWidth(220)
        self.adapter_combo.popup_show_requested.connect(self._request_endpoint_refresh)
        self.adapter_combo.currentIndexChanged.connect(self._on_adapter_changed)
        self.channel_combo.currentIndexChanged.connect(self.endpoint_changed.emit)

        self.endpoint_stack.addWidget(self._create_serial_endpoint())
        self.endpoint_stack.addWidget(self._create_transaction_endpoint())

        self.connect_btn.setCheckable(True)
        self.connect_btn.setMinimumWidth(70)
        self.connect_btn.clicked.connect(self._on_connect_clicked)

        top = QHBoxLayout()
        top.addWidget(QLabel(language_manager.get_text("port_lbl_protocol")))
        top.addWidget(self.protocol_combo)
        top.addWidget(self.endpoint_stack, 1)
        top.addWidget(self.connect_btn)
        layout.addLayout(top)

        self.settings_stack.addWidget(self._create_serial_settings())
        self.settings_stack.addWidget(self._create_spi_settings())
        self.settings_stack.addWidget(self._create_i2c_settings())
        layout.addWidget(self.settings_stack)
        self._apply_protocol_view()

    def _create_serial_endpoint(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(language_manager.get_text("port_lbl_port")))
        row.addWidget(self.port_combo, 1)
        return widget

    def _create_transaction_endpoint(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Adapter"))
        row.addWidget(self.adapter_combo, 1)
        row.addWidget(QLabel("Channel"))
        row.addWidget(self.channel_combo)
        return widget

    @staticmethod
    def _add_labeled(row: QHBoxLayout, label: str, control: QWidget) -> None:
        row.addWidget(QLabel(label))
        row.addWidget(control)

    def _create_serial_settings(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(LAYOUT_SPACING_DEFAULT)

        baud = QComboBox()
        baud.setEditable(True)
        baud.addItems([str(value) for value in VALID_BAUDRATES])
        baud.setCurrentText(str(DEFAULT_BAUDRATE))
        baud.setValidator(QIntValidator(min(VALID_BAUDRATES), max(VALID_BAUDRATES)))
        self.serial_controls_ui["baud_combo"] = baud

        data = QComboBox()
        data.addItems([str(value) for value in _SERIAL_BYTESIZES])
        data.setCurrentText(str(DEFAULT_PORT_BYTESIZE))
        data.setFixedWidth(CONTROL_WIDTH_PORT_DATA_COMBO)
        self.serial_controls_ui["data_combo"] = data

        parity = QComboBox()
        parity.addItems([item.value for item in SerialParity])
        parity.setFixedWidth(CONTROL_WIDTH_PORT_PARITY_COMBO)
        self.serial_controls_ui["parity_combo"] = parity

        stop = QComboBox()
        stop.addItems([str(item.value) for item in SerialStopBits])
        stop.setFixedWidth(CONTROL_WIDTH_PORT_STOP_COMBO)
        self.serial_controls_ui["stop_combo"] = stop

        flow = QComboBox()
        flow.addItems([item.value for item in SerialFlowControl])
        self.serial_controls_ui["flow_combo"] = flow

        controls = (
            (language_manager.get_text("port_lbl_baudrate"), baud),
            (language_manager.get_text("port_lbl_bytesize"), data),
            (language_manager.get_text("port_lbl_parity"), parity),
            (language_manager.get_text("port_lbl_stop"), stop),
            (language_manager.get_text("port_lbl_flow"), flow),
        )
        for label, control in controls:
            self._add_labeled(row, label, control)
        row.addStretch()
        return widget

    def _create_spi_settings(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
        )

        speed = QComboBox()
        speed.setEditable(True)
        speed.addItems([str(value) for value in _SPI_SPEED_OPTIONS])
        speed.setCurrentText(str(DEFAULT_SPI_SPEED))
        speed.setValidator(QIntValidator(1_000, 60_000_000))
        self.spi_controls_ui["speed_combo"] = speed

        mode = QComboBox()
        mode.addItems(["0", "1", "2", "3"])
        mode.setCurrentText(str(DEFAULT_SPI_MODE))
        self.spi_controls_ui["mode_combo"] = mode

        cs = QComboBox()
        cs.addItem("0")
        self.spi_controls_ui["cs_combo"] = cs

        bit_order = QComboBox()
        bit_order.addItems(["MSB", "LSB"])
        self.spi_controls_ui["bit_order_combo"] = bit_order

        duplex = QComboBox()
        duplex.addItems(["Full", "Half"])
        self.spi_controls_ui["duplex_combo"] = duplex

        controls = (
            (language_manager.get_text("port_lbl_speed"), speed),
            (language_manager.get_text("port_lbl_mode"), mode),
            ("CS", cs),
            ("Bit Order", bit_order),
            ("Duplex", duplex),
        )
        for label, control in controls:
            self._add_labeled(row, label, control)
        row.addStretch()
        return widget

    def _create_i2c_settings(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)

        speed = QComboBox()
        speed.setEditable(True)
        speed.addItems([str(value) for value in _I2C_SPEED_OPTIONS])
        speed.setCurrentText("100000")
        speed.setValidator(QIntValidator(1_000, 5_000_000))
        self.i2c_controls_ui["speed_combo"] = speed

        address = QLineEdit("0x50")
        address.setMaximumWidth(80)
        self.i2c_controls_ui["address_edit"] = address

        address_bits = QComboBox()
        address_bits.addItems(["7", "10"])
        self.i2c_controls_ui["address_bits_combo"] = address_bits

        stretch = QCheckBox("Clock Stretch")
        self.i2c_controls_ui["stretch_chk"] = stretch

        self._add_labeled(row, "Speed (Hz)", speed)
        self._add_labeled(row, "Address", address)
        self._add_labeled(row, "Address Bits", address_bits)
        row.addWidget(stretch)
        row.addStretch()
        return widget

    def current_protocol(self) -> str:
        return self.protocol_combo.currentText()

    def _on_protocol_changed(self, _protocol: str) -> None:
        self._apply_protocol_view()
        self.endpoint_changed.emit()
        self._request_endpoint_refresh()

    def _apply_protocol_view(self) -> None:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            self.endpoint_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)
            return

        self.endpoint_stack.setCurrentIndex(1)
        if protocol == TransactionProtocol.SPI.value:
            self.settings_stack.setCurrentIndex(1)
        else:
            self.settings_stack.setCurrentIndex(2)
        self._refresh_transaction_choices()

    def _request_endpoint_refresh(self) -> None:
        if not self.is_connected():
            self.endpoint_refresh_requested.emit(self.current_protocol())

    def set_port_list(self, ports: List[PortInfo]) -> None:
        current = self.get_port_name()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for info in ports:
            text = (
                f"{info.device} ({info.description})"
                if info.description
                else info.device
            )
            self.port_combo.addItem(text, info.device)
        index = self.port_combo.findData(current)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
        self.port_combo.blockSignals(False)
        self.endpoint_changed.emit()

    def set_adapter_descriptors(self, descriptors: List[AdapterDescriptor]) -> None:
        self._adapter_descriptors = list(descriptors)
        self._descriptor_by_identity = {
            descriptor.identity: descriptor for descriptor in descriptors
        }
        self._refresh_transaction_choices()

    def _refresh_transaction_choices(self) -> None:
        if self.current_protocol() == ConnectionProtocol.SERIAL:
            return

        protocol = TransactionProtocol(self.current_protocol())
        grouped: dict[tuple[str, str], list[AdapterDescriptor]] = defaultdict(list)
        for descriptor in self._adapter_descriptors:
            if descriptor.capabilities.supports(protocol):
                identity = descriptor.identity
                grouped[(identity.backend_id, identity.stable_id)].append(descriptor)

        selected_key = self.adapter_combo.currentData()
        if self._pending_identity is not None:
            selected_key = (
                self._pending_identity.backend_id,
                self._pending_identity.stable_id,
            )

        self.adapter_combo.blockSignals(True)
        self.adapter_combo.clear()
        for key, descriptors in grouped.items():
            sample = descriptors[0]
            label = f"{sample.device_family} {sample.identity.stable_id}"
            if not sample.identity_persistent:
                label += " [temporary]"
            self.adapter_combo.addItem(label, key)

        adapter_index = self._combo_index_for_data(
            self.adapter_combo,
            selected_key,
        )
        if adapter_index >= 0:
            self.adapter_combo.setCurrentIndex(adapter_index)
        self.adapter_combo.blockSignals(False)
        self._on_adapter_changed()

    def _on_adapter_changed(self) -> None:
        key = self.adapter_combo.currentData()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()

        if key is not None:
            protocol = TransactionProtocol(self.current_protocol())
            for descriptor in self._adapter_descriptors:
                identity = descriptor.identity
                if (identity.backend_id, identity.stable_id) != key:
                    continue
                if not descriptor.capabilities.supports(protocol):
                    continue
                self.channel_combo.addItem(
                    identity.channel_id or "Default",
                    identity,
                )

        self.channel_combo.blockSignals(False)
        self._restore_pending_channel()
        self._apply_selected_capabilities()
        self.endpoint_changed.emit()

    @staticmethod
    def _combo_index_for_data(combo: QComboBox, expected) -> int:
        if expected is None:
            return -1
        for index in range(combo.count()):
            if combo.itemData(index) == expected:
                return index
        return -1

    def _restore_pending_channel(self) -> None:
        identity = self._pending_identity
        if identity is None:
            return
        index = self._combo_index_for_data(self.channel_combo, identity)
        if index < 0:
            return
        self.channel_combo.setCurrentIndex(index)
        self._pending_identity = None

    def _selected_descriptor(self) -> Optional[AdapterDescriptor]:
        identity = self.channel_combo.currentData()
        return self._descriptor_by_identity.get(identity)

    def _apply_selected_capabilities(self) -> None:
        descriptor = self._selected_descriptor()
        if descriptor is None:
            return

        protocol = TransactionProtocol(self.current_protocol())
        if protocol is TransactionProtocol.SPI and descriptor.capabilities.spi:
            caps = descriptor.capabilities.spi
            self._replace_combo_values(
                self.spi_controls_ui["mode_combo"],
                sorted(caps.modes),
            )
            self._replace_combo_values(
                self.spi_controls_ui["cs_combo"],
                range(caps.chip_select_count),
            )
            self._replace_combo_values(
                self.spi_controls_ui["bit_order_combo"],
                [value.upper() for value in sorted(caps.bit_orders)],
            )
            self.spi_controls_ui["duplex_combo"].setEnabled(caps.full_duplex)
            return

        if protocol is TransactionProtocol.I2C and descriptor.capabilities.i2c:
            caps = descriptor.capabilities.i2c
            widths = []
            if caps.seven_bit_address:
                widths.append(7)
            if caps.ten_bit_address:
                widths.append(10)
            self._replace_combo_values(
                self.i2c_controls_ui["address_bits_combo"],
                widths,
            )
            self.i2c_controls_ui["stretch_chk"].setEnabled(caps.clock_stretching)
            if not caps.clock_stretching:
                self.i2c_controls_ui["stretch_chk"].setChecked(False)

    @staticmethod
    def _replace_combo_values(combo: QComboBox, values: Iterable) -> None:
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems([str(value) for value in values])
        index = combo.findText(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def get_port_name(self) -> str:
        if self.current_protocol() == ConnectionProtocol.SERIAL:
            data = self.port_combo.currentData()
            return str(data) if data else self.port_combo.currentText()

        identity = self.channel_combo.currentData()
        if not isinstance(identity, AdapterIdentity):
            identity = self._pending_identity
        if not isinstance(identity, AdapterIdentity):
            return ""

        suffix = f"[{identity.channel_id}]" if identity.channel_id else ""
        return f"{identity.stable_id}{suffix}"

    def get_connection_display_name(self) -> str:
        return self.get_port_name()

    def get_current_config(self) -> PortConfig | TransactionConnectionConfig:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            return self._serial_config()

        identity = self.channel_combo.currentData()
        if not isinstance(identity, AdapterIdentity):
            raise ValueError("No available transaction adapter/channel selected")

        if protocol == TransactionProtocol.SPI.value:
            return self._spi_config(identity)
        return self._i2c_config(identity)

    def _serial_config(self) -> PortConfig:
        config = PortConfig(
            port=self.get_port_name(),
            protocol=ConnectionProtocol.SERIAL,
        )
        config.baudrate = int(self.serial_controls_ui["baud_combo"].currentText())
        config.bytesize = int(self.serial_controls_ui["data_combo"].currentText())
        config.parity = self.serial_controls_ui["parity_combo"].currentText()
        config.stopbits = float(self.serial_controls_ui["stop_combo"].currentText())
        config.flowctrl = self.serial_controls_ui["flow_combo"].currentText()
        return config

    def _spi_config(self, identity: AdapterIdentity) -> TransactionConnectionConfig:
        return TransactionConnectionConfig(
            name=self.get_connection_display_name(),
            protocol=TransactionProtocol.SPI,
            adapter=identity,
            spi=SpiConfig(
                frequency_hz=int(self.spi_controls_ui["speed_combo"].currentText()),
                mode=int(self.spi_controls_ui["mode_combo"].currentText()),
                chip_select=int(self.spi_controls_ui["cs_combo"].currentText()),
                bit_order=self.spi_controls_ui["bit_order_combo"].currentText().lower(),
                full_duplex=self.spi_controls_ui["duplex_combo"].currentText() == "Full",
            ),
        )

    def _i2c_config(self, identity: AdapterIdentity) -> TransactionConnectionConfig:
        address = int(self.i2c_controls_ui["address_edit"].text().strip(), 0)
        return TransactionConnectionConfig(
            name=self.get_connection_display_name(),
            protocol=TransactionProtocol.I2C,
            adapter=identity,
            i2c=I2cConfig(
                frequency_hz=int(self.i2c_controls_ui["speed_combo"].currentText()),
                address=address,
                address_bits=int(self.i2c_controls_ui["address_bits_combo"].currentText()),
                clock_stretching=self.i2c_controls_ui["stretch_chk"].isChecked(),
            ),
        )

    def _on_connect_clicked(self) -> None:
        if not self.connect_btn.isChecked():
            self.disconnect_requested.emit()
            return
        try:
            config = self.get_current_config()
        except Exception as exc:
            logger.warning(f"Invalid connection configuration: {exc}")
            self.connect_btn.setChecked(False)
            self.set_connection_state(PortState.ERROR)
            return
        self.connect_requested.emit(config)
        self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))

    def set_connection_state(self, state: PortState) -> None:
        self.connect_btn.setProperty("state", state.value)
        is_connected = state is PortState.CONNECTED
        is_disconnected = state is PortState.DISCONNECTED
        self.connect_btn.setChecked(is_connected)

        if is_connected:
            text_key = "port_btn_disconnect"
        elif state is PortState.ERROR:
            text_key = "port_btn_reconnect"
        else:
            text_key = "port_btn_connect"
        self.connect_btn.setText(language_manager.get_text(text_key))

        self.protocol_combo.setEnabled(is_disconnected)
        self.endpoint_stack.setEnabled(is_disconnected)
        self.settings_stack.setEnabled(is_disconnected)
        self.port_connection_changed.emit(is_connected)

    def set_connected(self, connected: bool) -> None:
        state = PortState.CONNECTED if connected else PortState.DISCONNECTED
        self.set_connection_state(state)

    def is_connected(self) -> bool:
        return self.connect_btn.property("state") == PortState.CONNECTED.value

    def toggle_connection(self) -> None:
        self.connect_btn.click()

    def get_state(self) -> dict:
        identity = self.channel_combo.currentData()
        if not isinstance(identity, AdapterIdentity):
            identity = self._pending_identity

        identity_state = None
        if isinstance(identity, AdapterIdentity):
            identity_state = {
                "backend_id": identity.backend_id,
                "stable_id": identity.stable_id,
                "channel_id": identity.channel_id,
            }

        return {
            "protocol": self.current_protocol(),
            "port": self.get_port_name() if self.current_protocol() == ConnectionProtocol.SERIAL else "",
            "serial": self._serial_state(),
            "spi": self._spi_state(),
            "i2c": self._i2c_state(),
            "transaction_identity": identity_state,
        }

    def _serial_state(self) -> dict:
        return {
            "baudrate": self.serial_controls_ui["baud_combo"].currentText(),
            "bytesize": self.serial_controls_ui["data_combo"].currentText(),
            "parity": self.serial_controls_ui["parity_combo"].currentText(),
            "stopbits": self.serial_controls_ui["stop_combo"].currentText(),
            "flowctrl": self.serial_controls_ui["flow_combo"].currentText(),
        }

    def _spi_state(self) -> dict:
        return {
            "speed": self.spi_controls_ui["speed_combo"].currentText(),
            "mode": self.spi_controls_ui["mode_combo"].currentText(),
            "chip_select": self.spi_controls_ui["cs_combo"].currentText(),
            "bit_order": self.spi_controls_ui["bit_order_combo"].currentText().lower(),
            "full_duplex": self.spi_controls_ui["duplex_combo"].currentText() == "Full",
        }

    def _i2c_state(self) -> dict:
        return {
            "speed": self.i2c_controls_ui["speed_combo"].currentText(),
            "address": self.i2c_controls_ui["address_edit"].text(),
            "address_bits": self.i2c_controls_ui["address_bits_combo"].currentText(),
            "clock_stretching": self.i2c_controls_ui["stretch_chk"].isChecked(),
        }

    def apply_state(self, state: dict) -> None:
        if not state:
            return

        protocol = state.get("protocol", DEFAULT_PORT_PROTOCOL)
        valid_protocols = {
            ConnectionProtocol.SERIAL,
            TransactionProtocol.SPI.value,
            TransactionProtocol.I2C.value,
        }
        self.protocol_combo.setCurrentText(
            protocol if protocol in valid_protocols else DEFAULT_PORT_PROTOCOL
        )

        self._restore_serial_state(state)
        self._restore_spi_state(state)
        self._restore_i2c_state(state)
        self._restore_identity_state(state)

    def _restore_serial_state(self, state: dict) -> None:
        port = state.get("port", "")
        if port:
            index = self.port_combo.findData(port)
            if index < 0:
                self.port_combo.addItem(port, port)
                index = self.port_combo.count() - 1
            self.port_combo.setCurrentIndex(index)

        serial = state.get("serial", {})
        self.serial_controls_ui["baud_combo"].setCurrentText(
            str(serial.get("baudrate", DEFAULT_BAUDRATE))
        )
        self.serial_controls_ui["data_combo"].setCurrentText(
            str(serial.get("bytesize", DEFAULT_PORT_BYTESIZE))
        )
        self.serial_controls_ui["parity_combo"].setCurrentText(
            serial.get("parity", SerialParity.NONE.value)
        )
        self.serial_controls_ui["stop_combo"].setCurrentText(
            str(serial.get("stopbits", SerialStopBits.ONE.value))
        )
        self.serial_controls_ui["flow_combo"].setCurrentText(
            serial.get("flowctrl", SerialFlowControl.NONE.value)
        )

    def _restore_spi_state(self, state: dict) -> None:
        spi = state.get("spi", {})
        self.spi_controls_ui["speed_combo"].setCurrentText(
            str(spi.get("speed", DEFAULT_SPI_SPEED))
        )
        self.spi_controls_ui["mode_combo"].setCurrentText(
            str(spi.get("mode", DEFAULT_SPI_MODE))
        )

        # Discovery 전에 CS capability가 아직 없더라도 persisted selection을 잃지 않는다.
        # 이후 _apply_selected_capabilities()가 실제 지원 CS 목록으로 교체할 때 현재 text가
        # 유효하면 그대로 재선택되고, 지원하지 않는 값이면 capability 기본값으로 정규화된다.
        saved_cs = str(spi.get("chip_select", 0))
        cs_combo = self.spi_controls_ui["cs_combo"]
        if cs_combo.findText(saved_cs) < 0:
            cs_combo.addItem(saved_cs)
        cs_combo.setCurrentText(saved_cs)

        self.spi_controls_ui["bit_order_combo"].setCurrentText(
            str(spi.get("bit_order", "msb")).upper()
        )
        self.spi_controls_ui["duplex_combo"].setCurrentText(
            "Full" if spi.get("full_duplex", True) else "Half"
        )

    def _restore_i2c_state(self, state: dict) -> None:
        i2c = state.get("i2c", {})
        self.i2c_controls_ui["speed_combo"].setCurrentText(
            str(i2c.get("speed", 100_000))
        )
        self.i2c_controls_ui["address_edit"].setText(
            str(i2c.get("address", "0x50"))
        )
        self.i2c_controls_ui["address_bits_combo"].setCurrentText(
            str(i2c.get("address_bits", 7))
        )
        self.i2c_controls_ui["stretch_chk"].setChecked(
            bool(i2c.get("clock_stretching", False))
        )

    def _restore_identity_state(self, state: dict) -> None:
        identity_state = state.get("transaction_identity") or {}
        backend_id = str(identity_state.get("backend_id", "")).strip()
        stable_id = str(identity_state.get("stable_id", "")).strip()
        if not backend_id or not stable_id:
            return

        channel_id = identity_state.get("channel_id")
        self._pending_identity = AdapterIdentity(
            backend_id=backend_id,
            stable_id=stable_id,
            channel_id=(str(channel_id) if channel_id is not None else None),
        )
        self._refresh_transaction_choices()

    def retranslate_ui(self) -> None:
        self.setTitle(language_manager.get_text("port_grp_settings"))
        self.connect_btn.setToolTip(
            language_manager.get_text("port_btn_connect_tooltip")
        )
