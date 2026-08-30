"""
포트 설정 위젯 모듈

시리얼 및 SPI 포트 연결을 위한 설정을 UI로 제공합니다.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QGroupBox, QStackedWidget
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator
from typing import Optional, List, Dict

from view.managers.language_manager import language_manager
from common.enums import PortState, SerialParity, SerialStopBits, SerialFlowControl
from common.dtos import PortConfig, PortInfo
from common.constants import (
    VALID_BAUDRATES, DEFAULT_BAUDRATE,
    LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_DEFAULT, LAYOUT_SPACING_DEFAULT,
    CONTROL_WIDTH_PORT_DATA_COMBO, CONTROL_WIDTH_PORT_PARITY_COMBO, CONTROL_WIDTH_PORT_STOP_COMBO
)
from core.logger import logger

class ClickableComboBox(QComboBox):
    popup_show_requested = pyqtSignal()

    def showPopup(self):
        self.popup_show_requested.emit()
        super().showPopup()


class PortSettingsWidget(QGroupBox):
    connect_requested = pyqtSignal(object)     # PortConfig DTO
    disconnect_requested = pyqtSignal(object)  # PortConfig DTO
    port_scan_requested = pyqtSignal()
    port_connection_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(language_manager.get_text("port_grp_settings"), parent)
        self.protocol_lbl: Optional[QLabel] = None
        self.protocol_combo: Optional[QComboBox] = None
        self.port_lbl: Optional[QLabel] = None
        self.port_combo: Optional[ClickableComboBox] = None
        self.connect_btn: Optional[QPushButton] = None
        self.settings_stack: Optional[QStackedWidget] = None
        self.serial_controls_ui: Dict[str, QWidget] = {}
        self.spi_controls_ui: Dict[str, QWidget] = {}
        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)
        self.set_connection_state(PortState.DISCONNECTED)

    def init_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(LAYOUT_MARGIN_DEFAULT, LAYOUT_MARGIN_DEFAULT,
                                        LAYOUT_MARGIN_DEFAULT, LAYOUT_MARGIN_DEFAULT)
        main_layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.protocol_lbl = QLabel(language_manager.get_text("port_lbl_protocol"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["Serial", "SPI"])
        self.protocol_combo.setToolTip(language_manager.get_text("port_combo_protocol_tooltip"))
        self.protocol_combo.currentIndexChanged.connect(self.on_protocol_changed)

        self.port_lbl = QLabel(language_manager.get_text("port_lbl_port"))
        self.port_combo = ClickableComboBox()
        self.port_combo.setMinimumWidth(150)
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))
        self.port_combo.popup_show_requested.connect(self.on_port_combo_clicked)

        self.connect_btn = QPushButton(language_manager.get_text("port_btn_connect"))
        self.connect_btn.setCheckable(True)
        self.connect_btn.setMinimumWidth(70)
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))
        self.connect_btn.clicked.connect(self.on_connect_clicked)

        self.settings_stack = QStackedWidget()
        self.settings_stack.addWidget(self._create_serial_settings_widget())
        self.settings_stack.addWidget(self._create_spi_settings_widget())

        top_layout = QHBoxLayout()
        top_layout.setSpacing(LAYOUT_SPACING_DEFAULT)
        top_layout.addWidget(self.protocol_lbl)
        top_layout.addWidget(self.protocol_combo)
        top_layout.addWidget(self.port_lbl)
        top_layout.addWidget(self.port_combo, 1)
        top_layout.addWidget(self.connect_btn)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.settings_stack)
        self.setLayout(main_layout)
        self._align_first_column_labels()

    def _first_column_labels(self) -> list:
        page_first_label = (
            self.spi_controls_ui.get('speed_lbl')
            if self.settings_stack.currentIndex() == 1
            else self.serial_controls_ui.get('baud_lbl')
        )
        return [lbl for lbl in (self.protocol_lbl, page_first_label) if lbl is not None]

    def _align_first_column_labels(self) -> None:
        labels = self._first_column_labels()
        if not labels:
            return
        for lbl in labels:
            lbl.setMinimumWidth(0)
        widest = max(lbl.sizeHint().width() for lbl in labels)
        for lbl in labels:
            lbl.setMinimumWidth(widest)

    def _create_serial_settings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE,
                                   LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)
        layout.setSpacing(LAYOUT_SPACING_DEFAULT)

        self.serial_controls_ui['baud_lbl'] = QLabel(language_manager.get_text("port_lbl_baudrate"))
        self.serial_controls_ui['baud_combo'] = QComboBox()
        self.serial_controls_ui['baud_combo'].setEditable(True)
        self.serial_controls_ui['baud_combo'].addItems([str(b) for b in VALID_BAUDRATES])
        self.serial_controls_ui['baud_combo'].setCurrentText(str(DEFAULT_BAUDRATE))
        self.serial_controls_ui['baud_combo'].setValidator(QIntValidator(50, 4000000))
        self.serial_controls_ui['baud_combo'].setMinimumWidth(80)
        self.serial_controls_ui['baud_combo'].setToolTip(language_manager.get_text("port_combo_baudrate_tooltip"))

        self.serial_controls_ui['data_lbl'] = QLabel(language_manager.get_text("port_lbl_bytesize"))
        self.serial_controls_ui['data_combo'] = QComboBox()
        self.serial_controls_ui['data_combo'].addItems(["5", "6", "7", "8"])
        self.serial_controls_ui['data_combo'].setCurrentText("8")
        self.serial_controls_ui['data_combo'].setFixedWidth(CONTROL_WIDTH_PORT_DATA_COMBO)
        self.serial_controls_ui['data_combo'].setToolTip(language_manager.get_text("port_combo_bytesize_tooltip"))

        self.serial_controls_ui['parity_lbl'] = QLabel(language_manager.get_text("port_lbl_parity"))
        self.serial_controls_ui['parity_combo'] = QComboBox()
        self.serial_controls_ui['parity_combo'].addItems([p.value for p in SerialParity])
        self.serial_controls_ui['parity_combo'].setFixedWidth(CONTROL_WIDTH_PORT_PARITY_COMBO)
        self.serial_controls_ui['parity_combo'].setToolTip(language_manager.get_text("port_combo_parity_tooltip"))

        self.serial_controls_ui['stop_lbl'] = QLabel(language_manager.get_text("port_lbl_stop"))
        self.serial_controls_ui['stop_combo'] = QComboBox()
        self.serial_controls_ui['stop_combo'].addItems([str(s.value) for s in SerialStopBits])
        self.serial_controls_ui['stop_combo'].setFixedWidth(CONTROL_WIDTH_PORT_STOP_COMBO)
        self.serial_controls_ui['stop_combo'].setToolTip(language_manager.get_text("port_combo_stopbits_tooltip"))

        self.serial_controls_ui['flow_lbl'] = QLabel(language_manager.get_text("port_lbl_flow"))
        self.serial_controls_ui['flow_combo'] = QComboBox()
        self.serial_controls_ui['flow_combo'].addItems([f.value for f in SerialFlowControl])
        self.serial_controls_ui['flow_combo'].setMinimumWidth(70)
        self.serial_controls_ui['flow_combo'].setToolTip(language_manager.get_text("port_combo_flow_tooltip"))

        for key in ('baud_lbl','baud_combo','data_lbl','data_combo','parity_lbl','parity_combo','stop_lbl','stop_combo','flow_lbl','flow_combo'):
            layout.addWidget(self.serial_controls_ui[key])
        layout.addStretch()
        return widget

    def _create_spi_settings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE,
                                   LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)
        layout.setSpacing(10)
        self.spi_controls_ui['speed_lbl'] = QLabel(language_manager.get_text("port_lbl_speed"))
        self.spi_controls_ui['speed_combo'] = QComboBox()
        self.spi_controls_ui['speed_combo'].setEditable(True)
        self.spi_controls_ui['speed_combo'].addItems(["1000000", "500000", "100000", "50000"])
        self.spi_controls_ui['speed_combo'].setValidator(QIntValidator(1000, 20000000))
        self.spi_controls_ui['speed_combo'].setToolTip(language_manager.get_text("port_combo_speed_tooltip"))
        self.spi_controls_ui['mode_lbl'] = QLabel(language_manager.get_text("port_lbl_mode"))
        self.spi_controls_ui['mode_combo'] = QComboBox()
        self.spi_controls_ui['mode_combo'].addItems(["0", "1", "2", "3"])
        self.spi_controls_ui['mode_combo'].setToolTip(language_manager.get_text("port_combo_mode_tooltip"))
        layout.addWidget(self.spi_controls_ui['speed_lbl'])
        layout.addWidget(self.spi_controls_ui['speed_combo'])
        layout.addWidget(self.spi_controls_ui['mode_lbl'])
        layout.addWidget(self.spi_controls_ui['mode_combo'])
        layout.addStretch()
        return widget

    def on_protocol_changed(self, index: int) -> None:
        self.port_scan_requested.emit()
        self.settings_stack.setCurrentIndex(index)
        self._align_first_column_labels()

    def on_port_combo_clicked(self) -> None:
        if not self.is_connected():
            logger.debug("Port combo clicked, requesting scan...")
            self.port_scan_requested.emit()
        else:
            logger.debug("Port is connected, scan skipped.")

    def on_connect_clicked(self) -> None:
        if self.connect_btn.isChecked():
            config = self.get_current_config()
            self.connect_requested.emit(config)
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
        else:
            # 연결 요청과 동일하게 현재 설정 DTO를 명시적으로 전달한다.
            self.disconnect_requested.emit(self.get_current_config())

    def get_port_name(self) -> str:
        port_data = self.port_combo.currentData()
        if port_data:
            return str(port_data)
        return self.port_combo.currentText()

    def get_current_config(self) -> PortConfig:
        protocol = self.protocol_combo.currentText()
        port = self.get_port_name()
        config = PortConfig(port=port, protocol=protocol)
        if protocol == "Serial":
            config.baudrate = int(self.serial_controls_ui['baud_combo'].currentText())
            config.bytesize = int(self.serial_controls_ui['data_combo'].currentText())
            config.parity = self.serial_controls_ui['parity_combo'].currentText()
            config.stopbits = float(self.serial_controls_ui['stop_combo'].currentText())
            config.flowctrl = self.serial_controls_ui['flow_combo'].currentText()
        elif protocol == "SPI":
            config.speed = int(self.spi_controls_ui['speed_combo'].currentText())
            config.mode = int(self.spi_controls_ui['mode_combo'].currentText())
        return config

    def set_port_list(self, ports: List[PortInfo]) -> None:
        current_port_data = self.port_combo.currentData()
        if current_port_data is None:
            current_port_data = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for info in ports:
            display_text = f"{info.device} ({info.description})" if info.description else info.device
            self.port_combo.addItem(display_text, info.device)
        index = self.port_combo.findData(current_port_data)
        if index != -1:
            self.port_combo.setCurrentIndex(index)
        self.port_combo.blockSignals(False)
        if self.port_combo.count() > 0:
            self.port_combo.currentTextChanged.emit(self.port_combo.currentText())

    def set_connection_state(self, state: PortState) -> None:
        self.connect_btn.setProperty("state", state.value)
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        is_connected = (state == PortState.CONNECTED)
        is_disconnected = (state == PortState.DISCONNECTED)
        if is_connected:
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
            self.connect_btn.setChecked(True)
        elif is_disconnected:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))
            self.connect_btn.setChecked(False)
        elif state == PortState.ERROR:
            self.connect_btn.setText(language_manager.get_text("port_btn_reconnect"))
            self.connect_btn.setChecked(False)
        self.protocol_combo.setEnabled(is_disconnected)
        self.port_combo.setEnabled(is_disconnected)
        self.settings_stack.setEnabled(is_disconnected)
        self.port_connection_changed.emit(is_connected)

    def set_connected(self, connected: bool) -> None:
        state = PortState.CONNECTED if connected else PortState.DISCONNECTED
        self.set_connection_state(state)

    def toggle_connection(self) -> None:
        self.connect_btn.click()

    def is_connected(self) -> bool:
        return self.connect_btn.property("state") == PortState.CONNECTED.value

    def retranslate_ui(self) -> None:
        self.setTitle(language_manager.get_text("port_grp_settings"))
        self.protocol_lbl.setText(language_manager.get_text("port_lbl_protocol"))
        self.protocol_combo.setToolTip(language_manager.get_text("port_combo_protocol_tooltip"))
        self.port_lbl.setText(language_manager.get_text("port_lbl_port"))
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))
        current_state = PortState(self.connect_btn.property("state"))
        if current_state == PortState.DISCONNECTED:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))
        self.serial_controls_ui['baud_lbl'].setText(language_manager.get_text("port_lbl_baudrate"))
        self.serial_controls_ui['data_lbl'].setText(language_manager.get_text("port_lbl_bytesize"))
        self.serial_controls_ui['parity_lbl'].setText(language_manager.get_text("port_lbl_parity"))
        self.serial_controls_ui['stop_lbl'].setText(language_manager.get_text("port_lbl_stop"))
        self.serial_controls_ui['flow_lbl'].setText(language_manager.get_text("port_lbl_flow"))
        self.spi_controls_ui['speed_lbl'].setText(language_manager.get_text("port_lbl_speed"))
        self.spi_controls_ui['mode_lbl'].setText(language_manager.get_text("port_lbl_mode"))
        self._align_first_column_labels()

    def get_state(self) -> dict:
        port_val = self.get_port_name()
        return {
            "protocol": self.protocol_combo.currentText(),
            "port": port_val,
            "serial": {
                "baudrate": self.serial_controls_ui['baud_combo'].currentText(),
                "bytesize": self.serial_controls_ui['data_combo'].currentText(),
                "parity": self.serial_controls_ui['parity_combo'].currentText(),
                "stopbits": self.serial_controls_ui['stop_combo'].currentText(),
                "flowctrl": self.serial_controls_ui['flow_combo'].currentText(),
            },
            "spi": {
                "speed": self.spi_controls_ui['speed_combo'].currentText(),
                "mode": self.spi_controls_ui['mode_combo'].currentText(),
            }
        }

    def apply_state(self, state: dict) -> None:
        if not state:
            return
        self.protocol_combo.setCurrentText(state.get("protocol", "Serial"))
        port = state.get("port", "")
        if port:
            index = self.port_combo.findData(port)
            if index != -1:
                self.port_combo.setCurrentIndex(index)
            else:
                self.port_combo.addItem(port, port)
                self.port_combo.setCurrentIndex(self.port_combo.count() - 1)
        serial_state = state.get("serial", {})
        self.serial_controls_ui['baud_combo'].setCurrentText(str(serial_state.get("baudrate", DEFAULT_BAUDRATE)))
        self.serial_controls_ui['data_combo'].setCurrentText(str(serial_state.get("bytesize", "8")))
        self.serial_controls_ui['parity_combo'].setCurrentText(serial_state.get("parity", SerialParity.NONE.value))
        self.serial_controls_ui['stop_combo'].setCurrentText(str(serial_state.get("stopbits", SerialStopBits.ONE.value)))
        self.serial_controls_ui['flow_combo'].setCurrentText(serial_state.get("flowctrl", SerialFlowControl.NONE.value))
        spi_state = state.get("spi", {})
        self.spi_controls_ui['speed_combo'].setCurrentText(str(spi_state.get("speed", "1000000")))
        self.spi_controls_ui['mode_combo'].setCurrentText(str(spi_state.get("mode", "0")))