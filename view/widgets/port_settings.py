from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QGroupBox, QCheckBox, QGridLayout, QFormLayout, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, List, Dict, Any

class PortSettingsWidget(QGroupBox):
    """
    시리얼 포트 설정(Baudrate, Parity 등)을 제어하는 위젯입니다.
    """
    
    # Signals
    port_open_requested = pyqtSignal(dict)  # config dict
    port_close_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    connection_state_changed = pyqtSignal(bool)  # connected state
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortSettingsWidget 초기화.
        
        Args:
            parent: 부모 위젯
        """
        super().__init__("Port Settings", parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Row 1: Port | Scan | Baud | Open
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(5)
        
        # Port
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(80)
        self.port_combo.setToolTip("Select serial port")
        
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setFixedWidth(50)
        self.scan_btn.setToolTip("Refresh port list")
        self.scan_btn.clicked.connect(self.scan_requested.emit)
        
        # Baud
        self.baud_combo = QComboBox()
        self.baud_combo.setMinimumWidth(80)
        self.baud_combo.setToolTip("Select baud rate")
        self.baud_combo.addItems([
            "9600", "19200", "38400", "57600", "115200", 
            "230400", "460800", "921600", "1000000", "2000000", "4000000"
        ])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setEditable(True)
        
        # Connect Button
        self.connect_btn = QPushButton("Open")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setToolTip("Open/Close serial port connection")
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.connect_btn.setFixedWidth(60)
        
        row1_layout.addWidget(QLabel("Port:"))
        row1_layout.addWidget(self.port_combo)
        row1_layout.addWidget(self.scan_btn)
        row1_layout.addWidget(QLabel("Baud:"))
        row1_layout.addWidget(self.baud_combo)
        row1_layout.addWidget(self.connect_btn)
        
        main_layout.addLayout(row1_layout)
        
        # Row 2: Data | Parity | Stop | Flow | DTR | RTS
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(5)
        
        # Data
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.addItems(["5", "6", "7", "8"])
        self.bytesize_combo.setCurrentText("8")
        self.bytesize_combo.setToolTip("Data Bits")
        self.bytesize_combo.setFixedWidth(40)
        
        # Parity
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["N", "E", "O", "M", "S"])
        self.parity_combo.setToolTip("Parity")
        self.parity_combo.setFixedWidth(40)
        
        # Stop
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        self.stopbits_combo.setToolTip("Stop Bits")
        self.stopbits_combo.setFixedWidth(45)
        
        # Flow
        self.flow_combo = QComboBox()
        self.flow_combo.addItems(["None", "RTS/CTS", "XON/XOFF"])
        self.flow_combo.setToolTip("Flow Control")
        self.flow_combo.setMinimumWidth(70)
        
        # Signals
        self.dtr_check = QCheckBox("DTR")
        self.dtr_check.setChecked(True)
        self.rts_check = QCheckBox("RTS")
        self.rts_check.setChecked(True)
        
        row2_layout.addWidget(QLabel("Data:"))
        row2_layout.addWidget(self.bytesize_combo)
        row2_layout.addWidget(QLabel("Par:"))
        row2_layout.addWidget(self.parity_combo)
        row2_layout.addWidget(QLabel("Stop:"))
        row2_layout.addWidget(self.stopbits_combo)
        row2_layout.addWidget(QLabel("Flow:"))
        row2_layout.addWidget(self.flow_combo)
        row2_layout.addWidget(self.dtr_check)
        row2_layout.addWidget(self.rts_check)
        row2_layout.addStretch()
        
        main_layout.addLayout(row2_layout)
        
        self.setLayout(main_layout)
        
    def on_connect_clicked(self) -> None:
        """연결 버튼 클릭 핸들러"""
        if self.connect_btn.isChecked():
            # Request Open
            config: Dict[str, Any] = {
                "port": self.port_combo.currentText(),
                "baudrate": int(self.baud_combo.currentText()),
                "bytesize": int(self.bytesize_combo.currentText()),
                "parity": self.parity_combo.currentText(),
                "stopbits": float(self.stopbits_combo.currentText()),
                "flow_control": self.flow_combo.currentText(),
                "dtr": self.dtr_check.isChecked(),
                "rts": self.rts_check.isChecked()
            }
            self.port_open_requested.emit(config)
            self.connect_btn.setText("Close Port")
        else:
            # Request Close
            self.port_close_requested.emit()
            self.connect_btn.setText("Open Port")

    def set_port_list(self, ports: List[str]) -> None:
        """
        포트 목록을 업데이트합니다.
        
        Args:
            ports: 포트 이름 리스트
        """
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)

    def set_connected(self, connected: bool) -> None:
        """
        연결 상태에 따라 UI를 갱신합니다.
        
        Args:
            connected: 연결 여부
        """
        self.connect_btn.setChecked(connected)
        self.connect_btn.setText("Close Port" if connected else "Open Port")
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.bytesize_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stopbits_combo.setEnabled(not connected)
        self.flow_combo.setEnabled(not connected)
        
        # Emit connection state changed signal
        self.connection_state_changed.emit(connected)
