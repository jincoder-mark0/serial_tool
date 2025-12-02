from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QGroupBox, QCheckBox, QGridLayout, QFormLayout, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, List, Dict, Any

class PortSettingsWidget(QGroupBox):
    """
    시리얼 포트 설정(Baudrate, Parity 등)을 제어하는 위젯 클래스입니다.
    포트 스캔, 연결/해제 및 통신 파라미터 설정을 담당합니다.
    """
    
    # 시그널 정의
    port_open_requested = pyqtSignal(dict)  # config dict
    port_close_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    connection_state_changed = pyqtSignal(bool)  # connected state
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortSettingsWidget을 초기화합니다.
        
        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__("Port Settings", parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 1행: Port | Scan | Baud | Open
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(5)
        
        # 포트 선택 콤보박스
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(80)
        self.port_combo.setToolTip("시리얼 포트를 선택합니다.")
        
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setFixedWidth(50)
        self.scan_btn.setToolTip("포트 목록을 새로고침합니다.")
        self.scan_btn.clicked.connect(self.scan_requested.emit)
        
        # 보드레이트 선택 콤보박스
        self.baud_combo = QComboBox()
        self.baud_combo.setMinimumWidth(80)
        self.baud_combo.setToolTip("통신 속도(Baudrate)를 선택합니다.")
        self.baud_combo.addItems([
            "9600", "19200", "38400", "57600", "115200", 
            "230400", "460800", "921600", "1000000", "2000000", "4000000"
        ])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setEditable(True)
        
        # 연결 버튼
        self.connect_btn = QPushButton("Open")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setToolTip("시리얼 포트를 연결하거나 해제합니다.")
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.connect_btn.setFixedWidth(60)
        
        row1_layout.addWidget(QLabel("Port:"))
        row1_layout.addWidget(self.port_combo)
        row1_layout.addWidget(self.scan_btn)
        row1_layout.addWidget(QLabel("Baud:"))
        row1_layout.addWidget(self.baud_combo)
        row1_layout.addWidget(self.connect_btn)
        
        main_layout.addLayout(row1_layout)
        
        # 2행: Data | Parity | Stop | Flow | DTR | RTS
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(5)
        
        # 데이터 비트
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.addItems(["5", "6", "7", "8"])
        self.bytesize_combo.setCurrentText("8")
        self.bytesize_combo.setToolTip("데이터 비트 (Data Bits)")
        self.bytesize_combo.setFixedWidth(40)
        
        # 패리티 비트
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["N", "E", "O", "M", "S"])
        self.parity_combo.setToolTip("패리티 비트 (Parity)")
        self.parity_combo.setFixedWidth(40)
        
        # 정지 비트
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        self.stopbits_combo.setToolTip("정지 비트 (Stop Bits)")
        self.stopbits_combo.setFixedWidth(45)
        
        # 흐름 제어
        self.flow_combo = QComboBox()
        self.flow_combo.addItems(["None", "RTS/CTS", "XON/XOFF"])
        self.flow_combo.setToolTip("흐름 제어 (Flow Control)")
        self.flow_combo.setMinimumWidth(70)
        
        # 제어 신호
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
        """연결 버튼 클릭 핸들러입니다."""
        if self.connect_btn.isChecked():
            # 연결 요청 (Request Open)
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
            # 해제 요청 (Request Close)
            self.port_close_requested.emit()
            self.connect_btn.setText("Open Port")

    def set_port_list(self, ports: List[str]) -> None:
        """
        포트 목록을 업데이트합니다.
        
        Args:
            ports (List[str]): 포트 이름 리스트.
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
            connected (bool): 연결 여부.
        """
        self.connect_btn.setChecked(connected)
        self.connect_btn.setText("Close Port" if connected else "Open Port")
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.bytesize_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stopbits_combo.setEnabled(not connected)
        self.flow_combo.setEnabled(not connected)
        
        # 연결 상태 변경 시그널 발생
        self.connection_state_changed.emit(connected)
