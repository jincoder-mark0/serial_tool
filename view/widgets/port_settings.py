"""
PortSettingsWidget 모듈
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QGroupBox, QStackedWidget
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator
from view.managers.language_manager import language_manager
from typing import Optional, List
from common.enums import PortState
from common.dtos import PortConfig # DTO 임포트
from common.constants import VALID_BAUDRATES, DEFAULT_BAUDRATE

class PortSettingsWidget(QGroupBox):
    """
    포트 설정 위젯.
    프로토콜(Serial/SPI)에 따라 하단 설정 UI가 동적으로 변경됩니다.
    """

    # 시그널 정의
    port_open_requested = pyqtSignal(object)

    port_close_requested = pyqtSignal()
    port_scan_requested = pyqtSignal()
    port_connection_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortSettingsWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(language_manager.get_text("port_grp_settings"), parent)
        # 공통 UI 요소
        self.protocol_lbl: Optional[QLabel] = None
        self.protocol_combo: Optional[QComboBox] = None
        self.port_lbl: Optional[QLabel] = None
        self.port_combo: Optional[QComboBox] = None
        self.scan_btn: Optional[QPushButton] = None
        self.connect_btn: Optional[QPushButton] = None

        # 하단 레이아웃 스택
        self.settings_stack: Optional[QStackedWidget] = None
        self.serial_controls_ui = {}
        self.spi_controls_ui = {}
        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

        # 초기 상태 설정
        self.set_connection_state(PortState.DISCONNECTED)

    def init_ui(self) -> None:
        """UI 초기화 및 레이아웃 구성"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ---------------------------------------------------------
        # 1. 상단 행 (Top Row): Protocol | Port | Scan | Open
        # ---------------------------------------------------------
        # 프로토콜 선택 (Serial / SPI)
        self.protocol_lbl = QLabel(language_manager.get_text("port_lbl_protocol"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["Serial", "SPI"])
        self.protocol_combo.setToolTip(language_manager.get_text("port_combo_protocol_tooltip"))
        self.protocol_combo.currentIndexChanged.connect(self.on_protocol_changed)

        # 포트 선택
        self.port_lbl = QLabel(language_manager.get_text("port_lbl_port"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))

        # 스캔 버튼
        self.scan_btn = QPushButton(language_manager.get_text("port_btn_scan"))
        self.scan_btn.setFixedWidth(50)
        self.scan_btn.setToolTip(language_manager.get_text("port_btn_scan_tooltip"))
        self.scan_btn.clicked.connect(self.on_port_scan_clicked)

        # 연결 버튼
        self.connect_btn = QPushButton(language_manager.get_text("port_btn_connect"))
        self.connect_btn.setCheckable(True)
        self.connect_btn.setFixedWidth(70)
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))
        self.connect_btn.clicked.connect(self.on_connect_clicked)

        # ---------------------------------------------------------
        # 2. 하단 설정 스택 (Bottom Stack): Serial/SPI 설정
        # ---------------------------------------------------------
        self.settings_stack = QStackedWidget()

        # Page 0: Serial Settings
        self.settings_stack.addWidget(self._create_serial_settings_widget())

        # Page 1: SPI Settings
        self.settings_stack.addWidget(self._create_spi_settings_widget())

        top_layout = QHBoxLayout()
        top_layout.setSpacing(5)
        top_layout.addWidget(self.protocol_lbl)
        top_layout.addWidget(self.protocol_combo)
        top_layout.addWidget(self.port_lbl)
        top_layout.addWidget(self.port_combo, 1)
        top_layout.addWidget(self.scan_btn)
        top_layout.addWidget(self.connect_btn)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.settings_stack)
        self.setLayout(main_layout)

    def _create_serial_settings_widget(self) -> QWidget:
        """시리얼 설정 위젯 생성"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Baudrate
        self.serial_controls_ui['baud_lbl'] = QLabel(language_manager.get_text("port_lbl_baudrate"))
        self.serial_controls_ui['baud_combo'] = QComboBox()
        self.serial_controls_ui['baud_combo'].setEditable(True)
        self.serial_controls_ui['baud_combo'].addItems([str(b) for b in VALID_BAUDRATES])
        self.serial_controls_ui['baud_combo'].setCurrentText(str(DEFAULT_BAUDRATE))
        self.serial_controls_ui['baud_combo'].setValidator(QIntValidator(50, 4000000))
        self.serial_controls_ui['baud_combo'].setMinimumWidth(80)
        self.serial_controls_ui['baud_combo'].setToolTip(language_manager.get_text("port_combo_baudrate_tooltip"))

        # Data Bits
        self.serial_controls_ui['data_lbl'] = QLabel(language_manager.get_text("port_lbl_bytesize"))
        self.serial_controls_ui['data_combo'] = QComboBox()
        self.serial_controls_ui['data_combo'].addItems(["5", "6", "7", "8"])
        self.serial_controls_ui['data_combo'].setCurrentText("8")
        self.serial_controls_ui['data_combo'].setFixedWidth(40)
        self.serial_controls_ui['data_combo'].setToolTip(language_manager.get_text("port_combo_bytesize_tooltip"))

        # Parity
        self.serial_controls_ui['parity_lbl'] = QLabel(language_manager.get_text("port_lbl_parity"))
        self.serial_controls_ui['parity_combo'] = QComboBox()
        self.serial_controls_ui['parity_combo'].addItems(["N", "E", "O", "M", "S"])
        self.serial_controls_ui['parity_combo'].setFixedWidth(40)
        self.serial_controls_ui['parity_combo'].setToolTip(language_manager.get_text("port_combo_parity_tooltip"))

        # Stop Bits
        self.serial_controls_ui['stop_lbl'] = QLabel(language_manager.get_text("port_lbl_stop"))
        self.serial_controls_ui['stop_combo'] = QComboBox()
        self.serial_controls_ui['stop_combo'].addItems(["1", "1.5", "2"])
        self.serial_controls_ui['stop_combo'].setFixedWidth(45)
        self.serial_controls_ui['stop_combo'].setToolTip(language_manager.get_text("port_combo_stopbits_tooltip"))

        # Flow Control
        self.serial_controls_ui['flow_lbl'] = QLabel(language_manager.get_text("port_lbl_flow"))
        self.serial_controls_ui['flow_combo'] = QComboBox()
        self.serial_controls_ui['flow_combo'].addItems(["None", "RTS/CTS", "XON/XOFF"])
        self.serial_controls_ui['flow_combo'].setMinimumWidth(70)
        self.serial_controls_ui['flow_combo'].setToolTip(language_manager.get_text("port_combo_flow_tooltip"))

        # 배치
        layout.addWidget(self.serial_controls_ui['baud_lbl'])
        layout.addWidget(self.serial_controls_ui['baud_combo'])
        layout.addWidget(self.serial_controls_ui['data_lbl'])
        layout.addWidget(self.serial_controls_ui['data_combo'])
        layout.addWidget(self.serial_controls_ui['parity_lbl'])
        layout.addWidget(self.serial_controls_ui['parity_combo'])
        layout.addWidget(self.serial_controls_ui['stop_lbl'])
        layout.addWidget(self.serial_controls_ui['stop_combo'])
        layout.addWidget(self.serial_controls_ui['flow_lbl'])
        layout.addWidget(self.serial_controls_ui['flow_combo'])
        layout.addStretch()

        return widget

    def _create_spi_settings_widget(self) -> QWidget:
        """SPI 설정 위젯 생성"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Speed (Frequency)
        self.spi_controls_ui['speed_lbl'] = QLabel(language_manager.get_text("port_lbl_speed"))
        self.spi_controls_ui['speed_combo'] = QComboBox()
        self.spi_controls_ui['speed_combo'].setEditable(True)
        # 일반적인 SPI 속도 예시
        self.spi_controls_ui['speed_combo'].addItems(["1000000", "500000", "100000", "50000"])
        self.spi_controls_ui['speed_combo'].setValidator(QIntValidator(1000, 20000000))
        self.spi_controls_ui['speed_combo'].setToolTip(language_manager.get_text("port_combo_speed_tooltip"))

        # Mode (0, 1, 2, 3)
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
        """
        프로토콜 변경 시 하단 레이아웃 변경
        """
        self.port_scan_requested.emit()
        self.settings_stack.setCurrentIndex(index)


    def on_port_scan_clicked(self) -> None:
        """
        포트 스캔 버튼 클릭 핸들러입
        """
        self.port_scan_requested.emit()

    def on_connect_clicked(self) -> None:
        """
        연결 버튼 클릭 처리
        """
        if self.connect_btn.isChecked():
            # 연결 요청 (프로토콜에 따라 설정값 분기)
            protocol = self.protocol_combo.currentText()
            config = {"protocol": protocol, "port": self.port_combo.currentText()}

            if protocol == "Serial":
                config.update({
                    "baudrate": int(self.serial_controls_ui['baud_combo'].currentText()),
                    "bytesize": int(self.serial_controls_ui['data_combo'].currentText()),
                    "parity": self.serial_controls_ui['parity_combo'].currentText(),
                    "stopbits": float(self.serial_controls_ui['stop_combo'].currentText()),
                    "flowctrl": self.serial_controls_ui['flow_combo'].currentText(),
                })
            elif protocol == "SPI":
                config.update({
                    "speed": int(self.spi_controls_ui['speed_combo'].currentText()),
                    "mode": int(self.spi_controls_ui['mode_combo'].currentText()),
                })

            self.port_open_requested.emit(config)
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
        else:
            # 해제 요청 (Request Close)
            self.port_close_requested.emit()

    def get_current_config(self) -> PortConfig:
        """
        현재 UI 설정값을 바탕으로 PortConfig DTO를 반환합니다.
        """
        protocol = self.protocol_combo.currentText()
        port = self.port_combo.currentText()

        config = PortConfig(port=port, protocol=protocol)

        if protocol == "Serial":
            config.baudrate = int(self.serial_controls_ui['baud_combo'].currentText())
            config.bytesize = int(self.serial_controls_ui['data_combo'].currentText())
            config.parity = self.serial_controls_ui['parity_combo'].currentText()
            config.stopbits = float(self.serial_controls_ui['stop_combo'].currentText())
            config.flowctrl = self.serial_controls_ui['flow_combo'].currentText()
        elif protocol == "SPI":
            # SPI 설정 매핑 (예시)
            pass

        return config

    def set_port_list(self, ports: List[str]) -> None:
        """
        포트 목록을 업데이트합니다.

        Args:
            ports (List[str]): 포트 이름 리스트.
        """
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)

        # 이전에 선택된 포트가 목록에 있으면 유지
        if current_port in ports:
            self.port_combo.setCurrentText(current_port)

    def set_connection_state(self, state: PortState) -> None:
        """
        연결 버튼의 상태(색상, 텍스트)를 변경합니다.

        Args:
            state (PortState): 포트 상태 Enum.
        """
        self.connect_btn.setProperty("state", state.value)
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)

        connected = (state == PortState.CONNECTED)

        # 버튼 텍스트 업데이트
        if state == PortState.CONNECTED:
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
            self.connect_btn.setChecked(True)
        elif state == PortState.DISCONNECTED:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))
            self.connect_btn.setChecked(False)
        elif state == PortState.ERROR:
            self.connect_btn.setText(language_manager.get_text("port_btn_reconnect"))
            self.connect_btn.setChecked(False)

        # 설정 위젯 활성화/비활성화
        self.protocol_combo.setEnabled(not connected)
        self.port_combo.setEnabled(not connected)
        self.scan_btn.setEnabled(not connected)
        self.settings_stack.setEnabled(not connected)

        self.port_connection_changed.emit(connected)

    def set_connected(self, connected: bool) -> None:
        """
        PortPresenter와의 호환성을 위한 헬퍼 메서드입니다.
        단순 boolean 값을 받아 내부의 PortState로 변환하여 처리합니다.

        Args:
            connected (bool): 연결 여부
        """
        state = PortState.CONNECTED if connected else PortState.DISCONNECTED
        self.set_connection_state(state)

    def toggle_connection(self) -> None:
        """연결 상태를 토글합니다 (버튼 클릭 시뮬레이션)."""
        self.connect_btn.click()

    def is_connected(self) -> bool:
        """현재 연결 상태를 반환합니다."""
        return self.connect_btn.property("state") == PortState.CONNECTED.value

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.setTitle(language_manager.get_text("port_grp_settings"))
        self.protocol_lbl.setText(language_manager.get_text("port_lbl_protocol"))
        self.protocol_combo.setToolTip(language_manager.get_text("port_combo_protocol_tooltip"))
        self.port_lbl.setText(language_manager.get_text("port_lbl_port"))
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))
        self.scan_btn.setText(language_manager.get_text("port_btn_scan"))
        self.scan_btn.setToolTip(language_manager.get_text("port_btn_scan_tooltip"))
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))

        # 상태에 따라 버튼 텍스트 갱신
        current_state = PortState(self.connect_btn.property("state"))
        if current_state == PortState.DISCONNECTED:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))

        # Serial Label 갱신
        self.serial_controls_ui['baud_lbl'].setText(language_manager.get_text("port_lbl_baudrate"))
        self.serial_controls_ui['baud_combo'].setToolTip(language_manager.get_text("port_combo_baudrate_tooltip"))
        self.serial_controls_ui['data_lbl'].setText(language_manager.get_text("port_lbl_bytesize"))
        self.serial_controls_ui['data_combo'].setToolTip(language_manager.get_text("port_combo_bytesize_tooltip"))
        self.serial_controls_ui['parity_lbl'].setText(language_manager.get_text("port_lbl_parity"))
        self.serial_controls_ui['parity_combo'].setToolTip(language_manager.get_text("port_combo_parity_tooltip"))
        self.serial_controls_ui['stop_lbl'].setText(language_manager.get_text("port_lbl_stop"))
        self.serial_controls_ui['stop_combo'].setToolTip(language_manager.get_text("port_combo_stopbits_tooltip"))
        self.serial_controls_ui['flow_lbl'].setText(language_manager.get_text("port_lbl_flow"))
        self.serial_controls_ui['flow_combo'].setToolTip(language_manager.get_text("port_combo_flow_tooltip"))

        # SPI Label 갱신
        self.spi_controls_ui['speed_lbl'].setText(language_manager.get_text("port_lbl_speed"))
        self.spi_controls_ui['speed_combo'].setToolTip(language_manager.get_text("port_combo_speed_tooltip"))
        self.spi_controls_ui['mode_lbl'].setText(language_manager.get_text("port_lbl_mode"))
        self.spi_controls_ui['mode_combo'].setToolTip(language_manager.get_text("port_combo_mode_tooltip"))

    def save_state(self) -> dict:
        """
        현재 설정을 딕셔너리로 반환합니다.

        Returns:
            dict: 설정 데이터.
        """
        state = {
            "protocol": self.protocol_combo.currentText(),
            "port": self.port_combo.currentText(),
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
        return state

    def load_state(self, state: dict) -> None:
        """
        저장된 설정을 적용합니다.

        Args:
            state (dict): 설정 데이터.
        """
        if not state:
            return

        self.protocol_combo.setCurrentText(state.get("protocol", "Serial"))

        # 포트는 목록에 없을 수도 있으므로 addItem으로 추가 후 설정
        port = state.get("port", "")
        if port:
            if self.port_combo.findText(port) == -1:
                self.port_combo.addItem(port)
            self.port_combo.setCurrentText(port)

        serial_state = state.get("serial", {})
        self.serial_controls_ui['baud_combo'].setCurrentText(str(serial_state.get("baudrate", "115200")))
        self.serial_controls_ui['data_combo'].setCurrentText(str(serial_state.get("bytesize", "8")))
        self.serial_controls_ui['parity_combo'].setCurrentText(serial_state.get("parity", "N"))
        self.serial_controls_ui['stop_combo'].setCurrentText(str(serial_state.get("stopbits", "1")))
        self.serial_controls_ui['flow_combo'].setCurrentText(serial_state.get("flowctrl", "None"))

        spi_state = state.get("spi", {})
        self.spi_controls_ui['speed_combo'].setCurrentText(str(spi_state.get("speed", "1000000")))
        self.spi_controls_ui['mode_combo'].setCurrentText(str(spi_state.get("mode", "0")))
