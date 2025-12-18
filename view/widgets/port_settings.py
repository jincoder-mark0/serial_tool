"""
포트 설정 위젯 모듈

시리얼 및 SPI 포트 연결을 위한 설정을 UI로 제공합니다.

## WHY
* 다양한 통신 프로토콜(Serial, SPI)에 대한 설정 인터페이스가 필요
* 연결 전 사용자가 포트 및 파라미터를 직관적으로 선택해야 함
* 포트 목록의 늦은 로딩(Lazy Loading)을 통해 불필요한 시스템 부하 방지

## WHAT
* 프로토콜 선택(Serial/SPI) 및 하위 설정 스택 위젯 제공
* 클릭 시 스캔을 요청하는 커스텀 콤보박스(ClickableComboBox) 구현
* 연결/해제 및 스캔 버튼 제공
* 현재 설정을 DTO로 변환하여 반환 (포트 이름과 설명 분리 처리)

## HOW
* QComboBox를 상속받아 showPopup 이벤트를 재정의
* QStackedWidget을 사용하여 프로토콜별 설정 UI 전환
* Signal/Slot을 통해 사용자 입력을 Presenter로 전달
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QGroupBox, QStackedWidget
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIntValidator
from view.managers.language_manager import language_manager
from typing import Optional, List, Dict, Tuple
from common.enums import PortState, SerialParity, SerialStopBits, SerialFlowControl
from common.dtos import PortConfig
from common.constants import VALID_BAUDRATES, DEFAULT_BAUDRATE
from core.logger import logger

class ClickableComboBox(QComboBox):
    """
    클릭 이벤트를 감지할 수 있는 커스텀 콤보박스

    기본 QComboBox는 팝업이 열릴 때 별도의 시그널을 보내지 않으므로,
    showPopup 메서드를 오버라이딩하여 스캔 요청 시점을 확보합니다.
    """
    popup_show_requested = pyqtSignal()

    def showPopup(self):
        """
        콤보박스 팝업이 열릴 때 호출됨

        Logic:
            - 부모 클래스의 showPopup 호출 전 시그널 발생
            - 이를 통해 팝업이 뜨기 직전 최신 포트 목록 갱신 가능
        """
        # 팝업이 뜨기 직전에 스캔 요청 시그널 발생
        self.popup_show_requested.emit()
        super().showPopup()


class PortSettingsWidget(QGroupBox):
    """
    포트 설정 및 연결 제어 위젯

    프로토콜 선택에 따라 하단 설정 UI가 동적으로 변경됩니다.
    """

    # 사용자 요청 시그널
    port_open_requested = pyqtSignal(object)  # PortConfig DTO 전달

    port_close_requested = pyqtSignal()
    port_scan_requested = pyqtSignal()
    port_connection_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortSettingsWidget 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(language_manager.get_text("port_grp_settings"), parent)

        # UI 컴포넌트 변수 선언
        self.protocol_lbl: Optional[QLabel] = None
        self.protocol_combo: Optional[QComboBox] = None
        self.port_lbl: Optional[QLabel] = None
        self.port_combo: Optional[ClickableComboBox] = None
        self.scan_btn: Optional[QPushButton] = None
        self.connect_btn: Optional[QPushButton] = None

        # 설정 UI 관리
        self.settings_stack: Optional[QStackedWidget] = None
        self.serial_controls_ui: Dict[str, QWidget] = {}
        self.spi_controls_ui: Dict[str, QWidget] = {}

        self.init_ui()

        # 언어 변경 감지
        language_manager.language_changed.connect(self.retranslate_ui)

        # 초기 연결 상태 설정
        self.set_connection_state(PortState.DISCONNECTED)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 생성 및 레이아웃 구성

        Logic:
            - 상단: 프로토콜, 포트 선택, 스캔/연결 버튼 배치
            - 하단: QStackedWidget을 이용해 Serial/SPI 설정 패널 교체
        """
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

        # ClickableComboBox 사용하여 클릭 시 스캔 트리거
        self.port_combo = ClickableComboBox()
        self.port_combo.setMinimumWidth(150) # 설명이 들어가므로 너비 확장
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))
        self.port_combo.popup_show_requested.connect(self.on_port_combo_clicked)

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
        # 2. 하단 설정부 (Bottom Settings Stack)
        # ---------------------------------------------------------
        self.settings_stack = QStackedWidget()

        # Page 0: Serial Settings
        self.settings_stack.addWidget(self._create_serial_settings_widget())

        # Page 1: SPI Settings
        self.settings_stack.addWidget(self._create_spi_settings_widget())

        # 레이아웃 조립
        top_layout = QHBoxLayout()
        top_layout.setSpacing(5)
        top_layout.addWidget(self.protocol_lbl)
        top_layout.addWidget(self.protocol_combo)
        top_layout.addWidget(self.port_lbl)
        top_layout.addWidget(self.port_combo, 1) # Stretch 적용
        top_layout.addWidget(self.scan_btn)
        top_layout.addWidget(self.connect_btn)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.settings_stack)
        self.setLayout(main_layout)

    def _create_serial_settings_widget(self) -> QWidget:
        """
        시리얼 통신 설정 위젯 생성

        Returns:
            QWidget: 시리얼 설정 패널
        """
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
        self.serial_controls_ui['parity_combo'].addItems([p.value for p in SerialParity])
        self.serial_controls_ui['parity_combo'].setFixedWidth(40)
        self.serial_controls_ui['parity_combo'].setToolTip(language_manager.get_text("port_combo_parity_tooltip"))

        # Stop Bits
        self.serial_controls_ui['stop_lbl'] = QLabel(language_manager.get_text("port_lbl_stop"))
        self.serial_controls_ui['stop_combo'] = QComboBox()
        self.serial_controls_ui['stop_combo'].addItems([str(s.value) for s in SerialStopBits])
        self.serial_controls_ui['stop_combo'].setFixedWidth(45)
        self.serial_controls_ui['stop_combo'].setToolTip(language_manager.get_text("port_combo_stopbits_tooltip"))

        # Flow Control
        self.serial_controls_ui['flow_lbl'] = QLabel(language_manager.get_text("port_lbl_flow"))
        self.serial_controls_ui['flow_combo'] = QComboBox()
        self.serial_controls_ui['flow_combo'].addItems([f.value for f in SerialFlowControl])
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
        """
        SPI 통신 설정 위젯 생성

        Returns:
            QWidget: SPI 설정 패널
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Speed
        self.spi_controls_ui['speed_lbl'] = QLabel(language_manager.get_text("port_lbl_speed"))
        self.spi_controls_ui['speed_combo'] = QComboBox()
        self.spi_controls_ui['speed_combo'].setEditable(True)
        # 일반적인 SPI 속도 예시
        self.spi_controls_ui['speed_combo'].addItems(["1000000", "500000", "100000", "50000"])
        self.spi_controls_ui['speed_combo'].setValidator(QIntValidator(1000, 20000000))
        self.spi_controls_ui['speed_combo'].setToolTip(language_manager.get_text("port_combo_speed_tooltip"))

        # Mode
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
        프로토콜 변경 핸들러

        Args:
            index (int): 콤보박스 인덱스 (0: Serial, 1: SPI)
        """
        self.port_scan_requested.emit()
        self.settings_stack.setCurrentIndex(index)

    def on_port_scan_clicked(self) -> None:
        """포트 스캔 버튼 클릭 핸들러"""
        self.port_scan_requested.emit()

    def on_port_combo_clicked(self) -> None:
        """
        포트 콤보박스 클릭 시 (연결되지 않았을 때만) 스캔 요청

        Logic:
            - 연결되어 있지 않을 때만 스캔 요청
            - 팝업이 뜨기 전에 포트 목록을 최신화하기 위함
        """
        if not self.is_connected():
            logger.debug("Port combo clicked, requesting scan...")
            self.port_scan_requested.emit()
        else:
            logger.debug("Port is connected, scan skipped.")

    def on_connect_clicked(self) -> None:
        """
        연결 버튼 클릭 핸들러

        Logic:
            - 체크 상태면 연결 요청 (DTO 생성 후 emit)
            - 체크 해제 상태면 연결 종료 요청
        """
        if self.connect_btn.isChecked():
            config = self.get_current_config()

            # 연결 요청 시그널 발행
            self.port_open_requested.emit(config)
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
        else:
            # 해제 요청 (Request Close)
            self.port_close_requested.emit()

    def get_current_config(self) -> PortConfig:
        """
        현재 UI 설정값을 바탕으로 DTO 생성

        Returns:
            PortConfig: 포트 설정 DTO

        Note:
            QComboBox의 currentData를 사용하여 실제 포트 이름을 가져옵니다.
            (화면에는 'COM1 (Description)'이 보이지만 data는 'COM1')
        """
        protocol = self.protocol_combo.currentText()

        # 화면 표시 텍스트가 아닌 실제 데이터(포트명)를 사용
        port = self.port_combo.currentData()
        if port is None:
            # 데이터가 없으면 텍스트(직접 입력 등) 사용
            port = self.port_combo.currentText()

        # DTO 생성
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

    def set_port_list(self, ports: List[Tuple[str, str]]) -> None:
        """
        포트 목록 업데이트

        Logic:
            - 입력: [(port, description), ...] 형태의 튜플 리스트
            - 현재 선택된 포트(Data)를 기억
            - 목록 갱신 (addItem(description, userData=port))
            - 이전 선택 복구 시도
            - 저장된 포트가 스캔 목록에 없어도 강제로 유지 (Phantom Port Support)
            - 갱신 후 currentTextChanged 시그널 강제 발생 (탭 제목 동기화용)

        Args:
            ports (List[Tuple[str, str]]): (포트이름, 설명) 튜플 리스트
        """
        # 1. 현재 선택된 포트(또는 저장된 포트) 기억
        current_port_data = self.port_combo.currentData()
        if current_port_data is None:
            # Data가 없으면 Text 사용 (직접 입력했거나 복원된 상태)
            current_port_data = self.port_combo.currentText()

        # 시그널 차단 (불필요한 중간 변경 이벤트 방지)
        self.port_combo.blockSignals(True)
        self.port_combo.clear()

        # 2. 스캔된 포트 추가
        for port_name, description in ports:
            display_text = f"{port_name} ({description})" if description else port_name
            self.port_combo.addItem(display_text, port_name)

        # 3. 이전 선택 복구 시도
        index = self.port_combo.findData(current_port_data)

        if index != -1:
            # 목록에 있으면 해당 인덱스 선택
            self.port_combo.setCurrentIndex(index)
        elif current_port_data:
            # 목록에 없지만 기존 값이 있으면 무시
            pass

        # 시그널 차단 해제
        self.port_combo.blockSignals(False)

        # 목록 갱신 후 현재 선택된 포트 정보를 상위(PortPanel)로 전파
        # 이렇게 해야 앱 실행 직후나 탭 생성 직후에도 탭 제목이 "Port: COMx"로 갱신됨
        if self.port_combo.count() > 0:
            self.port_combo.currentTextChanged.emit(self.port_combo.currentText())

    def set_connection_state(self, state: PortState) -> None:
        """
        연결 상태에 따른 UI 업데이트

        Logic:
            - 상태에 따른 버튼 텍스트/스타일 변경
            - 연결 중에는 설정 위젯 비활성화 (Lock)

        Args:
            state (PortState): 포트 상태
        """
        self.connect_btn.setProperty("state", state.value)
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)

        is_connected = (state == PortState.CONNECTED)
        is_disconnected = (state == PortState.DISCONNECTED)

        # 버튼 텍스트 업데이트
        if is_connected:
            self.connect_btn.setText(language_manager.get_text("port_btn_disconnect"))
            self.connect_btn.setChecked(True)
        elif is_disconnected:
            self.connect_btn.setText(language_manager.get_text("port_btn_connect"))
            self.connect_btn.setChecked(False)
        elif state == PortState.ERROR:
            self.connect_btn.setText(language_manager.get_text("port_btn_reconnect"))
            self.connect_btn.setChecked(False)

        # 연결 중에는 설정 변경 불가 (Lock UI)
        self.protocol_combo.setEnabled(is_disconnected)
        self.port_combo.setEnabled(is_disconnected)
        self.scan_btn.setEnabled(is_disconnected)
        self.settings_stack.setEnabled(is_disconnected)

        self.port_connection_changed.emit(is_connected)

    def set_connected(self, connected: bool) -> None:
        """
        연결 상태 설정 (Boolean 헬퍼)

        Args:
            connected (bool): 연결 여부
        """
        state = PortState.CONNECTED if connected else PortState.DISCONNECTED
        self.set_connection_state(state)

    def toggle_connection(self) -> None:
        """연결 버튼 클릭 시뮬레이션 (단축키 등 외부 요청 시)"""
        self.connect_btn.click()

    def is_connected(self) -> bool:
        """
        현재 연결 여부 반환

        Returns:
            bool: 연결되어 있으면 True
        """
        return self.connect_btn.property("state") == PortState.CONNECTED.value

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트 업데이트"""
        self.setTitle(language_manager.get_text("port_grp_settings"))
        self.protocol_lbl.setText(language_manager.get_text("port_lbl_protocol"))
        self.protocol_combo.setToolTip(language_manager.get_text("port_combo_protocol_tooltip"))
        self.port_lbl.setText(language_manager.get_text("port_lbl_port"))
        self.port_combo.setToolTip(language_manager.get_text("port_combo_port_tooltip"))
        self.scan_btn.setText(language_manager.get_text("port_btn_scan"))
        self.scan_btn.setToolTip(language_manager.get_text("port_btn_scan_tooltip"))
        self.connect_btn.setToolTip(language_manager.get_text("port_btn_connect_tooltip"))

        # 상태에 따른 버튼 텍스트 갱신
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

    def get_state(self) -> dict:
        """
        현재 설정을 딕셔너리로 반환

        Returns:
            dict: 설정 데이터
        """
        # 저장 시에는 실제 포트 이름(Data)을 저장
        current_data = self.port_combo.currentData()
        port_val = current_data if current_data else self.port_combo.currentText()

        state = {
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
        return state

    def apply_state(self, state: dict) -> None:
        """
        설정 데이터를 UI에 적용

        Args:
            state (dict): 설정 데이터
        """
        if not state:
            return

        self.protocol_combo.setCurrentText(state.get("protocol", "Serial"))

        # 포트는 목록에 없을 수도 있으므로 addItem으로 추가 후 설정
        port = state.get("port", "")
        if port:
            # 저장된 포트가 현재 목록(Data)에 있는지 확인
            index = self.port_combo.findData(port)
            if index != -1:
                self.port_combo.setCurrentIndex(index)
            else:
                # 목록에 없으면 텍스트로 추가 (설명 없이)
                self.port_combo.addItem(port, port)
                self.port_combo.setCurrentIndex(self.port_combo.count() - 1)

        # Serial/SPI 설정 복원 (기존 코드 유지)
        serial_state = state.get("serial", {})
        self.serial_controls_ui['baud_combo'].setCurrentText(str(serial_state.get("baudrate", DEFAULT_BAUDRATE)))
        self.serial_controls_ui['data_combo'].setCurrentText(str(serial_state.get("bytesize", "8")))
        self.serial_controls_ui['parity_combo'].setCurrentText(serial_state.get("parity", SerialParity.NONE.value))
        self.serial_controls_ui['stop_combo'].setCurrentText(str(serial_state.get("stopbits", SerialStopBits.ONE.value)))
        self.serial_controls_ui['flow_combo'].setCurrentText(serial_state.get("flowctrl", SerialFlowControl.NONE.value))

        spi_state = state.get("spi", {})
        self.spi_controls_ui['speed_combo'].setCurrentText(str(spi_state.get("speed", "1000000")))
        self.spi_controls_ui['mode_combo'].setCurrentText(str(spi_state.get("mode", "0")))
