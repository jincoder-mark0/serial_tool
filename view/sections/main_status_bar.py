"""
메인 상태바 모듈

애플리케이션 하단에 시스템 상태, 통신 속도(RX/TX), 버퍼 상태 등을 실시간으로 표시합니다.

## WHY
* 통신 포트 상태와 데이터 전송 속도를 실시간으로 모니터링 필요
* 시스템 메시지나 에러를 비간섭적(Non-intrusive)으로 표시할 공간 필요

## WHAT
* 포트 상태 라벨 (연결 여부 시각화)
* RX/TX 속도계 및 BPS 표시기
* 버퍼 점유율 바 (Progress Bar)
* 현재 시간 표시

## HOW
* QStatusBar 상속
* addPermanentWidget을 사용하여 우측에 상태 위젯 고정
* HTML 태그를 사용하여 상태 아이콘 색상 변경
"""
from PyQt5.QtWidgets import QStatusBar, QLabel, QProgressBar, QWidget
from PyQt5.QtCore import Qt

from view.managers.language_manager import language_manager
from common.dtos import PortStatistics


class MainStatusBar(QStatusBar):
    """
    메인 윈도우의 하단 상태바를 관리하는 클래스입니다.
    """

    def __init__(self, parent=None) -> None:
        """
        MainStatusBar 초기화

        Args:
            parent: 부모 위젯.
        """
        super().__init__(parent)

        # UI 컴포넌트 참조
        self.port_lbl: QLabel = None
        self.rx_count_lbl: QLabel = None
        self.tx_count_lbl: QLabel = None
        self.bps_lbl: QLabel = None
        self.buffer_bar: QProgressBar = None
        self.time_lbl: QLabel = None

        self.init_ui()

    def init_ui(self) -> None:
        """상태바 UI 및 영구 위젯 초기화"""
        # 초기 메시지
        self.showMessage(language_manager.get_text("main_status_msg_ready"))

        self._init_widgets()

    def _init_widgets(self) -> None:
        """상태바 우측에 표시될 영구 위젯들을 생성하고 배치합니다."""
        # 1. Port Label (연결 상태 표시)
        self.port_lbl = QLabel("Port: -- ○")
        self.port_lbl.setMinimumWidth(100)
        self.addPermanentWidget(self.port_lbl)

        # 2. RX Speed
        self.rx_count_lbl = QLabel("RX: 0 KB/s")
        self.rx_count_lbl.setMinimumWidth(80)
        self.addPermanentWidget(self.rx_count_lbl)

        # 3. TX Speed
        self.tx_count_lbl = QLabel("TX: 0 KB/s")
        self.tx_count_lbl.setMinimumWidth(80)
        self.addPermanentWidget(self.tx_count_lbl)

        # 4. BPS (Bits Per Second)
        self.bps_lbl = QLabel("BPS: 0")
        self.bps_lbl.setMinimumWidth(80)
        self.addPermanentWidget(self.bps_lbl)

        # 5. Buffer Bar (데이터 버퍼 점유율)
        self.buffer_bar = QProgressBar()
        self.buffer_bar.setMaximum(100)
        self.buffer_bar.setFixedWidth(100)
        self.buffer_bar.setFormat("Buffer: %p%")
        self.buffer_bar.setAlignment(Qt.AlignCenter)
        self.addPermanentWidget(self.buffer_bar)

        # 6. Time Label (시스템 시간)
        self.time_lbl = QLabel("00:00:00")
        self.addPermanentWidget(self.time_lbl)

    def update_port_status(self, port: str, connected: bool) -> None:
        """
        포트 연결 상태를 업데이트합니다.

        Args:
            port (str): 포트 이름 (예: COM3).
            connected (bool): 연결 여부.
        """
        status_symbol = "●" if connected else "○"
        color = "#4CAF50" if connected else "#9E9E9E"  # Green / Grey

        # HTML 태그로 색상 적용
        self.port_lbl.setText(f"Port: {port} <span style='color:{color}; font-weight:bold;'>{status_symbol}</span>")

    def update_rx_speed(self, bytes_per_sec: int) -> None:
        """수신 속도 업데이트"""
        speed = bytes_per_sec / 1024
        self.rx_count_lbl.setText(f"RX: {speed:.1f} KB/s")

    def update_tx_speed(self, bytes_per_sec: int) -> None:
        """송신 속도 업데이트"""
        speed = bytes_per_sec / 1024
        self.tx_count_lbl.setText(f"TX: {speed:.1f} KB/s")

    def update_buffer(self, percent: int) -> None:
        """
        버퍼 점유율 바 업데이트.
        80% 이상이면 빨간색으로 경고 표시합니다.

        Args:
            percent (int): 버퍼 점유율 (0~100).
        """
        self.buffer_bar.setValue(percent)

        if percent >= 80:
            self.buffer_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF5252; }") # Red
        else:
            self.buffer_bar.setStyleSheet("") # Default Theme Style

    def update_time(self, time_str: str) -> None:
        """시간 표시 업데이트"""
        self.time_lbl.setText(time_str)

    def show_message(self, message: str, timeout: int = 3000) -> None:
        """
        상태바 좌측에 임시 메시지를 표시합니다.

        Args:
            message (str): 표시할 메시지.
            timeout (int): 표시 시간 (ms). 기본값 3초. 0이면 계속 표시.
        """
        self.showMessage(message, timeout)

    def update_statistics(self, stats: PortStatistics) -> None:
        """
        통계 DTO를 기반으로 상태바 정보를 일괄 업데이트합니다.

        Args:
            stats (PortStatistics): 통계 데이터 객체.
        """
        # RX/TX Speed
        self.update_rx_speed(stats.rx_bytes) # Note: stats.rx_bytes가 속도인지 누적량인지 확인 필요. 여기선 속도로 가정.
        self.update_tx_speed(stats.tx_bytes)

        # BPS (Optional)
        if hasattr(stats, 'bps'):
             self.bps_lbl.setText(f"BPS: {stats.bps}")

    def retranslate_ui(self) -> None:
        """언어 변경 시 상태바 텍스트를 업데이트합니다."""
        # 현재 표시 중인 메시지가 'Ready' 메시지라면 번역해서 다시 표시
        current_msg = self.currentMessage()
        ready_key = "main_status_msg_ready"

        # 텍스트가 비어있거나 Ready 메시지와 일치하면 갱신
        if not current_msg or language_manager.text_matches_key(current_msg, ready_key):
            self.showMessage(language_manager.get_text(ready_key))