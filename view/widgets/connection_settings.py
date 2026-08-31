"""Serial/SPI/I2C를 한 Port 탭에서 다루는 통합 연결 설정 위젯.

WHY:
- 사용자는 protocol이 달라도 동일한 Port 탭 workflow를 사용합니다.
- Serial의 COM port와 SPI/I2C의 Adapter/Channel은 UI 위치는 공유하되 identity 의미는 분리합니다.
- 기존 PortConfig에 transaction field를 계속 추가하지 않고, SPI/I2C는 이미 확정된
  TransactionConnectionConfig를 그대로 사용합니다.

HOW:
- Protocol에 따라 endpoint stack을 Serial Port 또는 Adapter/Channel로 전환합니다.
- Config stack은 Serial/SPI/I2C 페이지를 전환합니다.
- Adapter capability를 기준으로 mode/CS/bit-order/address-width/clock-stretching UI를 제한합니다.
- 기존 PortSettingsWidget state schema의 Serial/SPI key를 읽어 migration 호환을 유지합니다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

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
_SPI_SPEED_OPTIONS = (30_000_000, 12_000_000, 4_000_000, 1_000_000, 500_000, 100_000)
_I2C_SPEED_OPTIONS = (1_000_000, 400_000, 100_000, 50_000, 10_000)


class ConnectionSettingsWidget(QGroupBox):
    """하나의 탭에서 Serial/SPI/I2C endpoint와 config를 전환하는 View."""

    connect_requested = pyqtSignal(object)  # PortConfig | TransactionConnectionConfig
    disconnect_requested = pyqtSignal()
    endpoint_refresh_requested = pyqtSignal(str)
    port_connection_changed = pyqtSignal(bool)
    endpoint_changed = pyqtSignal()

    # Legacy relay name. PortPanel/Presenter migration 중 기존 contract를 깨지 않습니다.
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
        self._current_session_name: Optional[str] = None

        self._init_ui()
        self.set_connection_state(PortState.DISCONNECTED)
        language_manager.language_changed.connect(self.retranslate_ui)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
        )
        main_layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.protocol_combo.addItems(
            [ConnectionProtocol.SERIAL, TransactionProtocol.SPI.value, TransactionProtocol.I2C.value]
        )
        self.protocol_combo.setCurrentText(DEFAULT_PORT_PROTOCOL)
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)

        self.port_combo.setMinimumWidth(180)
        self.port_combo.popup_show_requested.connect(self._request_current_endpoint_refresh)
        self.port_combo.currentTextChanged.connect(self.endpoint_changed.emit)

        self.adapter_combo.setMinimumWidth(220)
        self.adapter_combo.popup_show_requested.connect(self._request_current_endpoint_refresh)
        self.adapter_combo.currentIndexChanged.connect(self._on_adapter_changed)
        self.channel_combo.currentIndexChanged.connect(self.endpoint_changed.emit)

        self.endpoint_stack.addWidget(self._create_serial_endpoint_widget())
        self.endpoint_stack.addWidget(self._create_transaction_endpoint_widget())

        self.connect_btn.setCheckable(True)
        self.connect_btn.setMinimumWidth(70)
        self.connect_btn.clicked.connect(self._on_connect_clicked)

        top = QHBoxLayout()
        top.addWidget(QLabel(language_manager.get_text("port_lbl_protocol")))
        top.addWidget(self.protocol_combo)
        top.addWidget(self.endpoint_stack, 1)
        top.addWidget(self.connect_btn)
        main_layout.addLayout(top)

        self.settings_stack.addWidget(self._create_serial_settings_widget())
        self.settings_stack.addWidget(self._create_spi_settings_widget())
        self.settings_stack.addWidget(self._create_i2c_settings_widget())
        main_layout.addWidget(self.settings_stack)

        self._apply_protocol_view()

    def _create_serial_endpoint_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(language_manager.get_text("port_lbl_port")))
        layout.addWidget(self.port_combo, 1)
        return widget

    def _create_transaction_endpoint_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Adapter"))
        layout.addWidget(self.adapter_combo, 1)
        layout.addWidget(QLabel("Channel"))
        layout.addWidget(self.channel_combo)
        return widget

    def _create_serial_settings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.serial_controls_ui["baud_combo"] = QComboBox()
        baud = self.serial_controls_ui["baud_combo"]
        baud.setEditable(True)
        baud.addItems([str(v) for v in VALID_BAUDRATES])
        baud.setCurrentText(str(DEFAULT_BAUDRATE))
        baud.setValidator(QIntValidator(min(VALID_BAUDRATES), max(VALID_BAUDRATES)))

        self.serial_controls_ui["data_combo"] = QComboBox()
        self.serial_controls_ui["data_combo"].addItems([str(v) for v in _SERIAL_BYTESIZES])
        self.serial_controls_ui["data_combo"].setCurrentText(str(DEFAULT_PORT_BYTESIZE))
        self.serial_controls_ui["data_combo"].setFixedWidth(CONTROL_WIDTH_PORT_DATA_COMBO)

        self.serial_controls_ui["parity_combo"] = QComboBox()
        self.serial_controls_ui["parity_combo"].addItems([item.value for item in SerialParity])
        self.serial_controls_ui["parity_combo"].setFixedWidth(CONTROL_WIDTH_PORT_PARITY_COMBO)

        self.serial_controls_ui["stop_combo"] = QComboBox()
        self.serial_controls_ui["stop_combo"].addItems([str(item.value) for item in SerialStopBits])
        self.serial_controls_ui["stop_combo"].setFixedWidth(CONTROL_WIDTH_PORT_STOP_COMBO)

        self.serial_controls_ui["flow_combo"] = QComboBox()
        self.serial_controls_ui["flow_combo"].addItems([item.value for item in SerialFlowControl])

        for label, key in (
            (language_manager.get_text("port_lbl_baudrate"), "baud_combo"),
            (language_manager.get_text("port_lbl_bytesize"), "data_combo"),
            (language_manager.get_text("port_lbl_parity"), "parity_combo"),
            (language_manager.get_text("port_lbl_stop"), "stop_combo"),
            (language_manager.get_text("port_lbl_flow"), "flow_combo"),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(self.serial_controls_ui[key])
        layout.addStretch()
        return widget

    def _create_spi_settings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)

        speed = QComboBox()
        speed.setEditable(True)
        speed.addItems([str(v) for v in _SPI_SPEED_OPTIONS])
        speed.setCurrentText(str(DEFAULT_SPI_SPEED))
        speed.setValidator(QIntValidator(1_000, 60_000_000))
        self.spi_controls_ui["speed_combo"] = speed

        mode = QComboBox()
        mode.addItems(["0", "1", "2", "3"])
        mode.setCurrentText(str(DEFAULT_SPI_MODE))
        self.spi_controls_ui["mode_combo"] = mode

        chip_select = QComboBox()
        chip_select.addItem("0")
        self.spi_controls_ui["cs_combo"] = chip_select

        bit_order = QComboBox()
        bit_order.addItems(["MSB", "LSB"])
        self.spi_controls_ui["bit_order_combo"] = bit_order

        duplex = QComboBox()
        duplex.addItems(["Full", "Half"])
        self.spi_controls_ui["duplex_combo"] = duplex

        for label, control in (
            (language_manager.get_text("port_lbl_speed"), speed),
            (language_manager.get_text("port_lbl_mode"), mode),
            ("CS", chip_select),
            ("Bit Order", bit_order),
            ("Duplex", duplex),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(control)
        layout.addStretch()
        return widget

    def _create_i2c_settings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        speed = QComboBox()
        speed.setEditable(True)
        speed.addItems([str(v) for v in _I2C_SPEED_OPTIONS])
        speed.setCurrentText("100000")
        speed.setValidator(QIntValidator(1_000, 5_000_000))
        self.i2c_controls_ui["speed_combo"] = speed

        address = QLineEdit("0x50")
        address.setMaximumWidth(80)
        self.i2c_controls_ui["address_edit"] = address

        width = QComboBox()
        width.addItems(["7", "10"])
        self.i2c_controls_ui["address_bits_combo"] = width

        stretching = QCheckBox("Clock Stretch")
        self.i2c_controls_ui["stretch_chk"] = stretching

        layout.addWidget(QLabel("Speed (Hz)"))
        layout.addWidget(speed)
        layout.addWidget(QLabel("Address"))
        layout.addWidget(address)
        layout.addWidget(QLabel("Address Bits"))
        layout.addWidget(width)
        layout.addWidget(stretching)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------
    # Endpoint / capability
    # ------------------------------------------------------------------
    def current_protocol(self) -> str:
        return self.protocol_combo.currentText()

    def _on_protocol_changed(self, _protocol: str) -> None:
        self._apply_protocol_view()
        self.endpoint_changed.emit()
        self._request_current_endpoint_refresh()

    def _apply_protocol_view(self) -> None:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            self.endpoint_stack.setCurrentIndex(0)
            self.settings_stack.setCurrentIndex(0)
        elif protocol == TransactionProtocol.SPI.value:
            self.endpoint_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(1)
            self._refresh_transaction_choices()
        else:
            self.endpoint_stack.setCurrentIndex(1)
            self.settings_stack.setCurrentIndex(2)
            self._refresh_transaction_choices()

    def _request_current_endpoint_refresh(self) -> None:
        if self.is_connected():
            return
        protocol = self.current_protocol()
        self.endpoint_refresh_requested.emit(protocol)
        self.port_scan_requested.emit()

    def set_port_list(self, ports: List[PortInfo]) -> None:
        current = self.get_port_name()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for info in ports:
            text = f"{info.device} ({info.description})" if info.description else info.device
            self.port_combo.addItem(text, info.device)
        index = self.port_combo.findData(current)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
        self.port_combo.blockSignals(False)
        self.endpoint_changed.emit()

    def set_adapter_descriptors(self, descriptors: List[AdapterDescriptor]) -> None:
        """Discovery 결과 중 현재 protocol을 지원하는 adapter/channel만 표시합니다."""
        self._adapter_descriptors = list(descriptors)
        self._descriptor_by_identity = {d.identity: d for d in descriptors}
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

        previous = self.adapter_combo.currentData()
        self.adapter_combo.blockSignals(True)
        self.adapter_combo.clear()
        for key, items in grouped.items():
            sample = items[0]
            label = f"{sample.device_family} {sample.identity.stable_id}"
            if not sample.identity_persistent:
                label += " [temporary]"
            self.adapter_combo.addItem(label, key)
        if previous is not None:
            index = self.adapter_combo.findData(previous)
            if index >= 0:
                self.adapter_combo.setCurrentIndex(index)
        self.adapter_combo.blockSignals(False)
        self._on_adapter_changed()

    def _on_adapter_changed(self) -> None:
        key = self.adapter_combo.currentData()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        if key is not None:
            for descriptor in self._adapter_descriptors:
                identity = descriptor.identity
                if (identity.backend_id, identity.stable_id) != key:
                    continue
                protocol = TransactionProtocol(self.current_protocol())
                if not descriptor.capabilities.supports(protocol):
                    continue
                label = identity.channel_id or "Default"
                self.channel_combo.addItem(label, identity)
        self.channel_combo.blockSignals(False)
        self._apply_selected_capabilities()
        self.endpoint_changed.emit()

    def _selected_descriptor(self) -> Optional[AdapterDescriptor]:
        identity = self.channel_combo.currentData()
        return self._descriptor_by_identity.get(identity)

    def _apply_selected_capabilities(self) -> None:
        descriptor = self._selected_descriptor()
        if descriptor is None:
            return
        protocol = TransactionProtocol(self.current_protocol())
        if protocol is TransactionProtocol.SPI and descriptor.capabilities.spi is not None:
            caps = descriptor.capabilities.spi
            self._replace_combo_values(self.spi_controls_ui["mode_combo"], sorted(caps.modes))
            self._replace_combo_values(self.spi_controls_ui["cs_combo"], range(caps.chip_select_count))
            self._replace_combo_values(
                self.spi_controls_ui["bit_order_combo"],
                [value.upper() for value in sorted(caps.bit_orders)],
            )
            self.spi_controls_ui["duplex_combo"].setEnabled(caps.full_duplex)
        elif protocol is TransactionProtocol.I2C and descriptor.capabilities.i2c is not None:
            caps = descriptor.capabilities.i2c
            widths = []
            if caps.seven_bit_address:
                widths.append(7)
            if caps.ten_bit_address:
                widths.append(10)
            self._replace_combo_values(self.i2c_controls_ui["address_bits_combo"], widths)
            self.i2c_controls_ui["stretch_chk"].setEnabled(caps.clock_stretching)
            if not caps.clock_stretching:
                self.i2c_controls_ui["stretch_chk"].setChecked(False)

    @staticmethod
    def _replace_combo_values(combo: QComboBox, values) -> None:
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems([str(value) for value in values])
        index = combo.findText(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Config / state
    # ------------------------------------------------------------------
    def get_port_name(self) -> str:
        if self.current_protocol() == ConnectionProtocol.SERIAL:
            data = self.port_combo.currentData()
            return str(data) if data else self.port_combo.currentText()
        identity = self.channel_combo.currentData()
        if isinstance(identity, AdapterIdentity):
            suffix = f"[{identity.channel_id}]" if identity.channel_id else ""
            return f"{identity.stable_id}{suffix}"
        return ""

    def get_connection_display_name(self) -> str:
        return self.get_port_name()

    def get_current_config(self) -> PortConfig | TransactionConnectionConfig:
        protocol = self.current_protocol()
        if protocol == ConnectionProtocol.SERIAL:
            config = PortConfig(port=self.get_port_name(), protocol=ConnectionProtocol.SERIAL)
            config.baudrate = int(self.serial_controls_ui["baud_combo"].currentText())
            config.bytesize = int(self.serial_controls_ui["data_combo"].currentText())
            config.parity = self.serial_controls_ui["parity_combo"].currentText()
            config.stopbits = float(self.serial_controls_ui["stop_combo"].currentText())
            config.flowctrl = self.serial_controls_ui["flow_combo"].currentText()
            return config

        identity = self.channel_combo.currentData()
        if not isinstance(identity, AdapterIdentity):
            raise ValueError("No transaction adapter/channel selected")
        session_name = self.get_connection_display_name()
        if protocol == TransactionProtocol.SPI.value:
            return TransactionConnectionConfig(
                name=session_name,
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

        address_text = self.i2c_controls_ui["address_edit"].text().strip()
        address = int(address_text, 0)
        return TransactionConnectionConfig(
            name=session_name,
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
        if self.connect_btn.isChecked():
            try:
                config = self.get_current_config()
            except Exception as exc:
                logger.warning(f"Invalid connection configuration: {exc}")
                self.connect_btn.setChecked(False)
                self.set_connection_state(PortState.ERROR)
                return
            self._current_session_name = self.get_connection_display_name()
            self.connect_requested.emit(config)
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
        else:
            self.disconnect_requested.emit()

    def set_connection_state(self, state: PortState) -> None:
        self.connect_btn.setProperty("state", state.value)
        is_connected = state is PortState.CONNECTED
        is_disconnected = state is PortState.DISCONNECTED
        self.connect_btn.setChecked(is_connected)
        if is_connected:
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
        elif state is PortState.ERROR:
            self.connect_btn.setText(language_manager.get_text("port_btn_reconnect"))
        else:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))
        self.protocol_combo.setEnabled(is_disconnected)
        self.endpoint_stack.setEnabled(is_disconnected)
        self.settings_stack.setEnabled(is_disconnected)
        self.port_connection_changed.emit(is_connected)

    def set_connected(self, connected: bool) -> None:
        self.set_connection_state(PortState.CONNECTED if connected else PortState.DISCONNECTED)

    def is_connected(self) -> bool:
        return self.connect_btn.property("state") == PortState.CONNECTED.value

    def toggle_connection(self) -> None:
        self.connect_btn.click()

    def get_state(self) -> dict:
        identity = self.channel_combo.currentData()
        transaction_identity = None
        if isinstance(identity, AdapterIdentity):
            transaction_identity = {
                "backend_id": identity.backend_id,
                "stable_id": identity.stable_id,
                "channel_id": identity.channel_id,
            }
        return {
            "protocol": self.current_protocol(),
            "port": self.get_port_name() if self.current_protocol() == ConnectionProtocol.SERIAL else "",
            "serial": {
                "baudrate": self.serial_controls_ui["baud_combo"].currentText(),
                "bytesize": self.serial_controls_ui["data_combo"].currentText(),
                "parity": self.serial_controls_ui["parity_combo"].currentText(),
                "stopbits": self.serial_controls_ui["stop_combo"].currentText(),
                "flowctrl": self.serial_controls_ui["flow_combo"].currentText(),
            },
            "spi": {
                "speed": self.spi_controls_ui["speed_combo"].currentText(),
                "mode": self.spi_controls_ui["mode_combo"].currentText(),
                "chip_select": self.spi_controls_ui["cs_combo"].currentText(),
                "bit_order": self.spi_controls_ui["bit_order_combo"].currentText().lower(),
                "full_duplex": self.spi_controls_ui["duplex_combo"].currentText() == "Full",
            },
            "i2c": {
                "speed": self.i2c_controls_ui["speed_combo"].currentText(),
                "address": self.i2c_controls_ui["address_edit"].text(),
                "address_bits": self.i2c_controls_ui["address_bits_combo"].currentText(),
                "clock_stretching": self.i2c_controls_ui["stretch_chk"].isChecked(),
            },
            "transaction_identity": transaction_identity,
        }

    def apply_state(self, state: dict) -> None:
        if not state:
            return
        protocol = state.get("protocol", DEFAULT_PORT_PROTOCOL)
        if protocol not in {ConnectionProtocol.SERIAL, TransactionProtocol.SPI.value, TransactionProtocol.I2C.value}:
            protocol = DEFAULT_PORT_PROTOCOL
        self.protocol_combo.setCurrentText(protocol)

        port = state.get("port", "")
        if port:
            index = self.port_combo.findData(port)
            if index < 0:
                self.port_combo.addItem(port, port)
                index = self.port_combo.count() - 1
            self.port_combo.setCurrentIndex(index)

        serial = state.get("serial", {})
        self.serial_controls_ui["baud_combo"].setCurrentText(str(serial.get("baudrate", DEFAULT_BAUDRATE)))
        self.serial_controls_ui["data_combo"].setCurrentText(str(serial.get("bytesize", DEFAULT_PORT_BYTESIZE)))
        self.serial_controls_ui["parity_combo"].setCurrentText(serial.get("parity", SerialParity.NONE.value))
        self.serial_controls_ui["stop_combo"].setCurrentText(str(serial.get("stopbits", SerialStopBits.ONE.value)))
        self.serial_controls_ui["flow_combo"].setCurrentText(serial.get("flowctrl", SerialFlowControl.NONE.value))

        spi = state.get("spi", {})
        self.spi_controls_ui["speed_combo"].setCurrentText(str(spi.get("speed", DEFAULT_SPI_SPEED)))
        self.spi_controls_ui["mode_combo"].setCurrentText(str(spi.get("mode", DEFAULT_SPI_MODE)))
        self.spi_controls_ui["cs_combo"].setCurrentText(str(spi.get("chip_select", 0)))
        self.spi_controls_ui["bit_order_combo"].setCurrentText(str(spi.get("bit_order", "msb")).upper())
        self.spi_controls_ui["duplex_combo"].setCurrentText("Full" if spi.get("full_duplex", True) else "Half")

        i2c = state.get("i2c", {})
        self.i2c_controls_ui["speed_combo"].setCurrentText(str(i2c.get("speed", 100_000)))
        self.i2c_controls_ui["address_edit"].setText(str(i2c.get("address", "0x50")))
        self.i2c_controls_ui["address_bits_combo"].setCurrentText(str(i2c.get("address_bits", 7)))
        self.i2c_controls_ui["stretch_chk"].setChecked(bool(i2c.get("clock_stretching", False)))

    def retranslate_ui(self) -> None:
        self.setTitle(language_manager.get_text("port_grp_settings"))
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))
